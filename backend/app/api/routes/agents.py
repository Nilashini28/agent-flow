"""Agents listing & details API + Registered Engines list."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.auth import get_api_key
from app.tools.registry import list_tools
from app.db.session import SessionLocal
from app.db.models import Run

router = APIRouter(dependencies=[Depends(get_api_key)])
engines_router = APIRouter(dependencies=[Depends(get_api_key)])


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


class EngineItem(BaseModel):
    id: str
    label: str
    description: str
    executionPattern: str
    inheritsGovernance: bool


@router.get("", response_model=list[AgentItem])
def get_agents():
    tools = [t["name"] for t in list_tools()]

    graph_count = 0
    autogen_count = 0
    graph_active = 0
    autogen_active = 0

    try:
        with SessionLocal() as session:
            runs = session.query(Run).all()
            for r in runs:
                if r.engine in ("langgraph", "execution-engine-a"):
                    graph_count += 1
                    if r.status == "running":
                        graph_active += 1
                elif r.engine in ("autogen", "execution-engine-b"):
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
            model="Multi-Agent Group Engine",
            assignedRiskPolicy="Strict Sandbox & Verification Policy",
            toolCount=len(tools),
            workflowCount=autogen_count,
            activeNowCount=autogen_active,
            successRate=0.95,
            tools=tools,
        ),
    ]


@engines_router.get("", response_model=list[EngineItem])
def get_engines():
    """Return registered execution engine adapters — framework-neutral external labels only."""
    return [
        EngineItem(
            id="langgraph",
            label="Execution Engine A",
            description="Graph-based deterministic execution engine with step-by-step state checkpointing.",
            executionPattern="Deterministic Step Sequence (Research -> Draft -> Verify -> Act)",
            inheritsGovernance=True,
        ),
        EngineItem(
            id="autogen",
            label="Execution Engine B",
            description="Multi-agent group conversation engine with sandboxed tool dispatch & risk scoring.",
            executionPattern="Conversational Turn Sequence (Planner -> Critic -> Executor)",
            inheritsGovernance=True,
        ),
    ]
