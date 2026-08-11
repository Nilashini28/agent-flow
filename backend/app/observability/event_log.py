"""Structured event logging: every state transition, decision, and
memory read/write should go through here so a run's full timeline is
replayable later.
"""
from datetime import datetime, timezone

_EVENTS: list[dict] = []  # replace with DB writes via app.db.session in production


def log_event(run_id: str, event_type: str, payload: dict | None = None) -> None:
    record = {
        "run_id": run_id,
        "event_type": event_type,
        "payload": payload or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _EVENTS.append(record)


def get_timeline(run_id: str) -> list[dict]:
    return [e for e in _EVENTS if e["run_id"] == run_id]
