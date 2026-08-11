"""View and act on escalation decisions (approve/reject)."""
from fastapi import APIRouter

router = APIRouter()

# In-memory placeholder; back with app.db.models.EscalationDecision in production
_PENDING_APPROVALS: dict[str, dict] = {}


@router.get("/{run_id}/escalations")
def list_escalations(run_id: str):
    return {"run_id": run_id, "pending": _PENDING_APPROVALS.get(run_id)}


@router.post("/{run_id}/escalations/approve")
def approve(run_id: str):
    _PENDING_APPROVALS.pop(run_id, None)
    return {"run_id": run_id, "status": "approved"}


@router.post("/{run_id}/escalations/reject")
def reject(run_id: str):
    _PENDING_APPROVALS.pop(run_id, None)
    return {"run_id": run_id, "status": "rejected"}
