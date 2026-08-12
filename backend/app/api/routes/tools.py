"""GET /tools — list all registered tools with their schema and policy."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from app.api.auth import get_api_key
from app.tools.registry import list_tools

router = APIRouter(dependencies=[Depends(get_api_key)])


@router.get("")
def get_tools():
    """Return all registered tools with their risk tier, schema, and sandbox policy.

    Allows the dashboard (and auditors) to inspect exactly what this agent
    is allowed to do — as a real, queryable list rather than buried config.
    """
    return {"tools": list_tools(), "total": len(list_tools())}
