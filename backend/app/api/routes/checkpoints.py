"""Inspect checkpoints for a run."""
from fastapi import APIRouter

from app.core.checkpointing.recovery import get_latest_checkpoint

router = APIRouter()


@router.get("/{run_id}/checkpoints")
def latest_checkpoint(run_id: str):
    state = get_latest_checkpoint(run_id)
    return {"run_id": run_id, "checkpoint": state}
