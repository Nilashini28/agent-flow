"""Inspect checkpoints for a run."""
from fastapi import APIRouter, Depends

from app.api.auth import get_api_key
from app.core.checkpointing.recovery import get_latest_checkpoint

router = APIRouter(dependencies=[Depends(get_api_key)])


@router.get("/{run_id}/checkpoints")
def latest_checkpoint(run_id: str):
    state = get_latest_checkpoint(run_id)
    return {"run_id": run_id, "checkpoint": state}
