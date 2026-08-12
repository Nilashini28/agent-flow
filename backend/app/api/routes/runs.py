"""Create and inspect agent runs.

Stage-8 extension: POST /runs accepts framework ("langgraph" | "autogen").
Stage-9 extension: GET /runs (list, paginated), GET /runs/{id}/metrics.

NAMING: All API responses use external engine labels via engine_labels.py.
Internal names ("langgraph", "autogen") never appear in any response body.
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from app.api.auth import get_api_key
from app.api.engine_labels import translate_engine, describe_engine, all_external_labels
from app.config import get_settings
from app.core.graph.state_graph import build_graph
from app.core.checkpointing.recovery import resume_run

router = APIRouter(dependencies=[Depends(get_api_key)])
_settings = get_settings()


# ── Request / Response models ─────────────────────────────────────────────────

class CreateRunRequest(BaseModel):
    task: str
    framework: Literal["langgraph", "autogen"] = "langgraph"


class RunSummary(BaseModel):
    run_id: str
    task: str
    status: str
    engine: str          # Always external label — never internal name
    engine_description: str
    created_at: str
    finished_at: Optional[str] = None


class RunListResponse(BaseModel):
    runs: list[RunSummary]
    total: int
    limit: int
    offset: int


class RunMetrics(BaseModel):
    run_id: str
    engine: str
    engine_description: str
    status: str
    total_steps: int
    total_retries: int
    total_sandbox_violations: int
    final_risk_score: float
    duration_seconds: Optional[float] = None


# ── DB helpers ────────────────────────────────────────────────────────────────

def _create_run_record(run_id: str, task: str, internal_framework: str) -> None:
    """Persist a Run row at the start of a run. Silently ignored if DB unavailable."""
    try:
        from app.db.session import SessionLocal
        from app.db.models import Run

        with SessionLocal() as session:
            run = Run(
                id=run_id,
                task=task,
                status="running",
                engine=internal_framework,  # internal name stored in DB
                created_at=datetime.now(timezone.utc),
            )
            session.add(run)
            session.commit()
    except Exception:
        pass


def _update_run_status(run_id: str, status: str) -> None:
    """Update run status and finished_at after completion/halt."""
    try:
        from app.db.session import SessionLocal
        from app.db.models import Run

        with SessionLocal() as session:
            run = session.get(Run, run_id)
            if run:
                run.status = status
                run.finished_at = datetime.now(timezone.utc)
                session.commit()
    except Exception:
        pass


def _get_run_from_db(run_id: str) -> dict | None:
    try:
        from app.db.session import SessionLocal
        from app.db.models import Run

        with SessionLocal() as session:
            run = session.get(Run, run_id)
            if not run:
                return None
            return {
                "id": run.id,
                "task": run.task,
                "status": run.status,
                "engine": run.engine,
                "created_at": run.created_at.isoformat(),
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            }
    except Exception:
        return None


def _list_runs_from_db(
    status: str | None,
    engine_external: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    """Return (runs_page, total_count) from the DB Run table."""
    try:
        from app.db.session import SessionLocal
        from app.db.models import Run
        from sqlalchemy import select, func

        # Reverse-map external label to internal name for DB query.
        from app.api.engine_labels import INTERNAL_TO_EXTERNAL
        external_to_internal = {v: k for k, v in INTERNAL_TO_EXTERNAL.items()}
        engine_internal = external_to_internal.get(engine_external or "", None)

        with SessionLocal() as session:
            query = session.query(Run)
            if status:
                query = query.filter(Run.status == status)
            if engine_internal:
                query = query.filter(Run.engine == engine_internal)
            total = query.count()
            runs = query.order_by(Run.created_at.desc()).offset(offset).limit(limit).all()
            return [
                {
                    "id": r.id,
                    "task": r.task,
                    "status": r.status,
                    "engine": r.engine,
                    "created_at": r.created_at.isoformat(),
                    "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                }
                for r in runs
            ], total
    except Exception:
        return [], 0


# ── Background thread executors ───────────────────────────────────────────────

def _execute_run(run_id: str, task: str) -> None:
    """Run the LangGraph agent graph in a background thread."""
    graph = build_graph()
    config = {"configurable": {"thread_id": run_id}}
    initial_state = {
        "run_id": run_id, "task": task, "step_index": 0,
        "history": [], "last_output": "", "tool_calls": [],
        "risk_score": 0.0, "status": "running", "error": None, "retry_count": 0,
    }
    final_status = "completed"
    try:
        graph.invoke(initial_state, config=config)
    except Exception:
        final_status = "failed"
    finally:
        _update_run_status(run_id, final_status)


def _execute_autogen_run(run_id: str, task: str) -> None:
    """Run an AutoGen multi-agent conversation through AgentFlow's reliability layer."""
    from app.core.adapters.autogen_adapter import AutoGenAdapter
    from app.core.adapters.runner import run_adapter

    initial_state = {
        "run_id": run_id, "task": task, "step_index": 0,
        "history": [], "last_output": "", "tool_calls": [],
        "risk_score": 0.0, "status": "running", "error": None, "retry_count": 0,
    }
    adapter = AutoGenAdapter(task=task, run_id=run_id, stub_mode=True)
    final_status = "completed"
    try:
        result = run_adapter(adapter, initial_state)
        final_status = result.get("status", "completed")
    except Exception:
        final_status = "failed"
    finally:
        _update_run_status(run_id, final_status)


# ── API endpoints ─────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_run(body: CreateRunRequest):
    """Start a new agent run. Returns run_id and external engine label immediately.

    The agent runs in a daemon thread. Poll GET /{run_id}/timeline for progress.
    """
    run_id = str(uuid.uuid4())
    external_engine = translate_engine(body.framework)

    _create_run_record(run_id, body.task, body.framework)

    target = _execute_autogen_run if body.framework == "autogen" else _execute_run
    t = threading.Thread(target=target, args=(run_id, body.task), daemon=True)
    t.start()

    return {
        "run_id": run_id,
        "status": "running",
        "engine": external_engine,
        "engine_description": describe_engine(external_engine),
    }


@router.get("", response_model=RunListResponse)
def list_runs(
    status: Optional[str] = Query(None, description="Filter by status: running|completed|halted|failed"),
    engine: Optional[str] = Query(None, description="Filter by external engine label"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List all runs, paginated and filterable by status and engine.

    Engine filter uses EXTERNAL labels (execution-engine-a, execution-engine-b).
    """
    if engine and engine not in all_external_labels():
        raise HTTPException(400, f"Unknown engine label. Valid values: {all_external_labels()}")

    raw_runs, total = _list_runs_from_db(status, engine, limit, offset)
    summaries = [
        RunSummary(
            run_id=r["id"],
            task=r["task"],
            status=r["status"],
            engine=translate_engine(r["engine"]),
            engine_description=describe_engine(translate_engine(r["engine"])),
            created_at=r["created_at"],
            finished_at=r.get("finished_at"),
        )
        for r in raw_runs
    ]
    return RunListResponse(runs=summaries, total=total, limit=limit, offset=offset)


@router.get("/{run_id}/metrics", response_model=RunMetrics)
def run_metrics(run_id: str):
    """Return aggregate stats for a single run — pre-computed for the dashboard."""
    from app.observability.event_log import get_timeline

    run = _get_run_from_db(run_id)
    events = get_timeline(run_id)

    if not events and not run:
        raise HTTPException(404, f"Run {run_id!r} not found.")

    node_complete = [e for e in events if e["event_type"] == "node_complete"]
    retry_events  = [e for e in events if e["event_type"] == "retry_attempt"]
    violations    = [e for e in events if e["event_type"] in ("sandbox_violation", "policy_violation")]
    escalations   = [e for e in events if e["event_type"] == "escalation_decision"]

    # Duration: wall-clock between first and last event.
    duration: float | None = None
    if len(events) >= 2:
        try:
            t0 = datetime.fromisoformat(events[0]["timestamp"])
            t1 = datetime.fromisoformat(events[-1]["timestamp"])
            duration = (t1 - t0).total_seconds()
        except Exception:
            pass

    final_risk = 0.0
    if escalations:
        try:
            final_risk = float(escalations[-1]["payload"].get("risk_score", 0.0))
        except Exception:
            pass

    internal_engine = run["engine"] if run else "langgraph"
    external_engine = translate_engine(internal_engine)
    current_status  = run["status"] if run else (
        "completed" if any(e["event_type"] == "run_completed" for e in events) else "unknown"
    )

    return RunMetrics(
        run_id=run_id,
        engine=external_engine,
        engine_description=describe_engine(external_engine),
        status=current_status,
        total_steps=len(node_complete),
        total_retries=len(retry_events),
        total_sandbox_violations=len(violations),
        final_risk_score=round(final_risk, 4),
        duration_seconds=round(duration, 3) if duration is not None else None,
    )


@router.post("/{run_id}/resume")
def resume(run_id: str):
    result = resume_run(run_id)
    return {"run_id": run_id, "result": result}
