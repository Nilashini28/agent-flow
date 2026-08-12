"""Create and inspect agent runs.

Stage-5 fix: run executes in a background thread so POST /runs returns the
run_id immediately. The frontend can then start polling GET /timeline right
away and watch events arrive as the graph progresses through each node.
"""
import threading
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.graph.state_graph import build_graph
from app.core.checkpointing.recovery import resume_run

router = APIRouter()


class CreateRunRequest(BaseModel):
    task: str


def _execute_run(run_id: str, task: str) -> None:
    """Run the agent graph in a background thread.

    Invoked via threading.Thread so POST /runs can return immediately while
    the graph streams node_start / node_complete events into the timeline.
    The frontend polls GET /{run_id}/timeline at 800 ms intervals to pick
    them up live.
    """
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


@router.post("")
def create_run(body: CreateRunRequest):
    """Start a new agent run and return the run_id immediately.

    The graph runs in a daemon thread — the caller should poll
    GET /{run_id}/timeline to follow progress.
    """
    run_id = str(uuid.uuid4())
    t = threading.Thread(target=_execute_run, args=(run_id, body.task), daemon=True)
    t.start()
    return {"run_id": run_id, "status": "running"}


@router.post("/{run_id}/resume")
def resume(run_id: str):
    result = resume_run(run_id)
    return {"run_id": run_id, "result": result}
