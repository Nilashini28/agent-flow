"""Create and inspect agent runs.

Stage-5 fix: run executes in a background thread so POST /runs returns the
run_id immediately. The frontend can then start polling GET /timeline right
away and watch events arrive as the graph progresses through each node.

Stage-8 extension: POST /runs now accepts an optional `framework` field
("langgraph" | "autogen"). Both paths use the same background-thread pattern
and write to the same event log, so the frontend polling works unchanged.
"""
import threading
import uuid

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal

from app.core.graph.state_graph import build_graph
from app.core.checkpointing.recovery import resume_run

router = APIRouter()


class CreateRunRequest(BaseModel):
    task: str
    framework: Literal["langgraph", "autogen"] = "langgraph"


# ── LangGraph runner (unchanged) ──────────────────────────────────────────────

def _execute_run(run_id: str, task: str) -> None:
    """Run the LangGraph agent graph in a background thread."""
    graph = build_graph()
    config = {"configurable": {"thread_id": run_id}}
    initial_state = {
        "run_id": run_id,
        "task": task,
        "step_index": 0,
        "history": [],
        "last_output": "",
        "tool_calls": [],
        "risk_score": 0.0,
        "status": "running",
        "error": None,
        "retry_count": 0,
    }
    try:
        graph.invoke(initial_state, config=config)
    except Exception:
        pass  # errors are captured inside node wrappers and written to state


# ── AutoGen runner ────────────────────────────────────────────────────────────

def _execute_autogen_run(run_id: str, task: str) -> None:
    """Run an AutoGen multi-agent conversation through AgentFlow's reliability layer.

    Uses the exact same run_adapter() runner as the test suite — same sandbox,
    same escalation model, same event log. The background thread pattern is
    identical to the LangGraph path.
    """
    from app.core.adapters.autogen_adapter import AutoGenAdapter
    from app.core.adapters.runner import run_adapter

    initial_state = {
        "run_id": run_id,
        "task": task,
        "step_index": 0,
        "history": [],
        "last_output": "",
        "tool_calls": [],
        "risk_score": 0.0,
        "status": "running",
        "error": None,
        "retry_count": 0,
    }
    adapter = AutoGenAdapter(task=task, run_id=run_id, stub_mode=True)
    try:
        run_adapter(adapter, initial_state)
    except Exception:
        pass


# ── API endpoints ─────────────────────────────────────────────────────────────

@router.post("")
def create_run(body: CreateRunRequest):
    """Start a new agent run and return the run_id immediately.

    The agent (LangGraph or AutoGen) runs in a daemon thread. Poll
    GET /{run_id}/timeline to follow progress — works the same for both.
    """
    run_id = str(uuid.uuid4())

    if body.framework == "autogen":
        target = _execute_autogen_run
    else:
        target = _execute_run

    t = threading.Thread(target=target, args=(run_id, body.task), daemon=True)
    t.start()
    return {"run_id": run_id, "status": "running", "framework": body.framework}


@router.post("/{run_id}/resume")
def resume(run_id: str):
    result = resume_run(run_id)
    return {"run_id": run_id, "result": result}
