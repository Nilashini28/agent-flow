"""Agents listing & details API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.auth import get_api_key
from app.tools.registry import list_tools
from app.db.session import SessionLocal
from app.db.models import Run

router = APIRouter(dependencies=[Depends(get_api_key)])


class AgentItem(BaseModel):
    id: str
    name: str
    status: str
    model: str
    assignedRiskPolicy: str
    toolCount: int
    workflowCount: int
    activeNowCount: int
    successRate: float
    tools: list[str]


@router.get("", response_model=list[AgentItem])
def get_agents():
    tools = [t["name"] for t in list_tools()]

    # Query run counts per engine
    graph_count = 0
    autogen_count = 0
    graph_active = 0
    autogen_active = 0

    try:
        with SessionLocal() as session:
            runs = session.query(Run).all()
            for r in runs:
                if r.engine == "langgraph":
                    graph_count += 1
                    if r.status == "running":
                        graph_active += 1
                elif r.engine == "autogen":
                    autogen_count += 1
                    if r.status == "running":
                        autogen_active += 1
    except Exception:
        pass

    return [
        AgentItem(
            id="engine-a-agent",
            name="Graph Execution Agent A",
            status="active",
            model="Claude-3.5-Sonnet / Graph Engine",
            assignedRiskPolicy="Standard Governance Policy v1",
            toolCount=len(tools),
            workflowCount=graph_count,
            activeNowCount=graph_active,
            successRate=0.98,
            tools=tools,
        ),
        AgentItem(
            id="engine-b-agent",
            name="Multi-Agent Conversation Engine B",
            status="active",
            model="AutoGen Multi-Agent Group",
            assignedRiskPolicy="Strict Sandbox & Verification Policy",
            toolCount=len(tools),
            workflowCount=autogen_count,
            activeNowCount=autogen_active,
            successRate=0.95,
            tools=tools,
        ),
    ]
