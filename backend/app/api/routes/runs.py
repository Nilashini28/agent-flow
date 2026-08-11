"""Create and inspect agent runs."""
import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.graph.state_graph import build_graph
from app.core.checkpointing.recovery import resume_run

router = APIRouter()


class CreateRunRequest(BaseModel):
    task: str


@router.post("")
def create_run(body: CreateRunRequest):
    run_id = str(uuid.uuid4())
    graph = build_graph()
    config = {"configurable": {"thread_id": run_id}}
    initial_state = {
        "run_id": run_id,
        "task": body.task,
        "step_index": 0,
        "history": [],
        "last_output": "",
        "risk_score": 0.0,
        "status": "running",
    }
    result = graph.invoke(initial_state, config=config)
    return {"run_id": run_id, "result": result}


@router.post("/{run_id}/resume")
def resume(run_id: str):
    result = resume_run(run_id)
    return {"run_id": run_id, "result": result}
