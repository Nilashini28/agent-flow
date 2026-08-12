"""View and act on escalation decisions (approve/reject).

Stage-5 implementation: approval gates block the graph thread via
threading.Event. When verify_step routes to REQUEST_APPROVAL the graph
thread calls wait_for_approval(run_id) which blocks until the frontend
calls POST /approve or /reject.
"""
import threading

from fastapi import APIRouter, Depends, HTTPException
from app.api.auth import get_api_key
from app.db.session import SessionLocal
from app.db.models import Run

router = APIRouter(dependencies=[Depends(get_api_key)])

# run_id → {"event": threading.Event, "decision": "approved"|"rejected"|None}
_GATES: dict[str, dict] = {}


def register_approval_gate(run_id: str) -> threading.Event:
    """Create and return a gate Event for *run_id*."""
    event = threading.Event()
    _GATES[run_id] = {"event": event, "decision": None}
    return event


def get_decision(run_id: str) -> str | None:
    """Return the decision ('approved'|'rejected') for *run_id*, or None."""
    gate = _GATES.get(run_id)
    return gate["decision"] if gate else None


def clear_gate(run_id: str) -> None:
    """Remove the gate once the graph thread has consumed the decision."""
    _GATES.pop(run_id, None)


# ── HTTP endpoints ────────────────────────────────────────────────────────────

@router.get("/{run_id}/escalations")
def list_escalations(run_id: str):
    """Return whether this run is currently awaiting approval."""
    gate = _GATES.get(run_id)
    if gate and not gate["event"].is_set():
        return {"run_id": run_id, "pending": True, "decided": False}
    with SessionLocal() as session:
        r = session.query(Run).filter(Run.run_id == run_id).first()
        if r and r.status == "awaiting_approval":
            return {"run_id": run_id, "pending": True, "decided": False}
    return {"run_id": run_id, "pending": False, "decided": bool(gate)}


@router.post("/{run_id}/escalations/approve")
def approve(run_id: str):
    """Unblock the waiting graph thread with an 'approved' decision."""
    gate = _GATES.get(run_id)
    if gate:
        gate["decision"] = "approved"
        gate["event"].set()

    # Always update database Run status
    with SessionLocal() as session:
        r = session.query(Run).filter(Run.run_id == run_id).first()
        if r:
            r.status = "completed"
            session.commit()
            return {"run_id": run_id, "status": "approved"}

    if not gate:
        raise HTTPException(status_code=404, detail=f"No pending escalation for run {run_id!r}")

    return {"run_id": run_id, "status": "approved"}


@router.post("/{run_id}/escalations/reject")
def reject(run_id: str):
    """Unblock the waiting graph thread with a 'rejected' decision."""
    gate = _GATES.get(run_id)
    if gate:
        gate["decision"] = "rejected"
        gate["event"].set()

    # Always update database Run status
    with SessionLocal() as session:
        r = session.query(Run).filter(Run.run_id == run_id).first()
        if r:
            r.status = "halted"
            session.commit()
            return {"run_id": run_id, "status": "rejected"}

    if not gate:
        raise HTTPException(status_code=404, detail=f"No pending escalation for run {run_id!r}")

    return {"run_id": run_id, "status": "rejected"}
