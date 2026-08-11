"""Replay a run's full structured event timeline."""
from fastapi import APIRouter

from app.observability.event_log import get_timeline

router = APIRouter()


@router.get("/{run_id}/timeline")
def timeline(run_id: str):
    return {"run_id": run_id, "events": get_timeline(run_id)}
