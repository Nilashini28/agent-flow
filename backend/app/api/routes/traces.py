"""Replay a run's full structured event timeline (DB-backed)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from app.api.auth import get_api_key
from app.observability.event_log import get_timeline

router = APIRouter(dependencies=[Depends(get_api_key)])


@router.get("/{run_id}/timeline")
def timeline(run_id: str):
    """Return the full ordered event log for a run.

    Events are read from the DB — durable across process restarts.
    Falls back to in-memory if DB is unavailable (e.g. test context).
    """
    return {"run_id": run_id, "events": get_timeline(run_id)}
