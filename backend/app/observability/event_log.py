"""DB-backed structured event logging.

Replaces the original in-memory _EVENTS list with real SQLite/Postgres writes.
Every event persists immediately so a run's timeline is replayable after a
process restart — same durability guarantee as Stage 2's checkpoints.

Architecture:
  - log_event() writes to DB synchronously (fast — SQLite write <1ms).
  - An in-memory mirror (_EVENTS) is also maintained for same-process reads
    (avoids a DB round-trip during active polling).
  - get_timeline() prefers the DB; falls back to in-memory if DB unavailable.
  - log_event() never raises — DB failures are swallowed so agent runs
    are not blocked by observability failures.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

# In-memory mirror (same-process, same lifetime).
_EVENTS: list[dict] = []


def log_event(run_id: str, event_type: str, payload: dict | None = None) -> None:
    """Persist a structured event to the DB and the in-memory mirror."""
    record: dict[str, Any] = {
        "run_id": run_id,
        "event_type": event_type,
        "payload": payload or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _EVENTS.append(record)
    _write_to_db(record)


def get_timeline(run_id: str) -> list[dict]:
    """Return all events for run_id, preferring DB over in-memory."""
    db_events = _read_from_db(run_id)
    if db_events is not None:
        return db_events
    # Fallback: in-memory (e.g. DB not yet initialised in test context).
    return [e for e in _EVENTS if e["run_id"] == run_id]


def get_all_run_ids() -> list[str]:
    """Return all distinct run IDs that have events (for run-list endpoint)."""
    try:
        from app.db.session import SessionLocal
        from app.db.models import Event
        from sqlalchemy import select, distinct

        with SessionLocal() as session:
            rows = session.execute(select(distinct(Event.run_id))).scalars().all()
            return list(rows)
    except Exception:
        # Fallback: in-memory.
        seen: dict[str, bool] = {}
        return [seen.setdefault(e["run_id"], e["run_id"]) for e in _EVENTS
                if e["run_id"] not in seen]


# ── Private DB helpers ────────────────────────────────────────────────────────

def _write_to_db(record: dict) -> None:
    """Write one event row to the DB. Never raises."""
    try:
        from app.db.session import SessionLocal
        from app.db.models import Event

        with SessionLocal() as session:
            evt = Event(
                run_id=record["run_id"],
                event_type=record["event_type"],
                payload_json=json.dumps(record["payload"]),
                timestamp=datetime.fromisoformat(record["timestamp"]),
            )
            session.add(evt)
            session.commit()
    except Exception:
        pass  # Observability failures must never crash a run.


def _read_from_db(run_id: str) -> list[dict] | None:
    """Read events for run_id from DB. Returns None if DB unavailable."""
    try:
        from app.db.session import SessionLocal
        from app.db.models import Event

        with SessionLocal() as session:
            rows = (
                session.query(Event)
                .filter(Event.run_id == run_id)
                .order_by(Event.timestamp.asc())
                .all()
            )
            return [
                {
                    "run_id": row.run_id,
                    "event_type": row.event_type,
                    "payload": json.loads(row.payload_json),
                    "timestamp": row.timestamp.isoformat(),
                }
                for row in rows
            ]
    except Exception:
        return None
