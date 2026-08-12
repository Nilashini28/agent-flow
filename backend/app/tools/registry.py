"""Central tool registry with schema validation.

Each tool registration includes:
  - callable: the actual tool function
  - input_schema_name: key into tools/schema.py for Pydantic validation
  - risk_tier: "low" | "medium" | "high"
  - reversible: whether the tool's effects can be undone
  - allow_network: whether the tool makes external network calls
  - description: human-readable description for GET /tools

validate_and_get_tool() validates the input against the declared schema
BEFORE the sandbox dispatches the tool — malformed inputs fail fast with
a clear ValidationError instead of failing silently inside the sandbox.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.tools.web_search_tool import web_search
from app.tools.file_write_tool import write_file
from app.tools.schema import validate_tool_input, get_schema_dict


@dataclass
class ToolRegistration:
    name: str
    callable: Callable
    description: str
    risk_tier: str            # "low" | "medium" | "high"
    reversible: bool
    allow_network: bool
    input_schema_name: str    # key in schema._INPUT_SCHEMAS
    tags: list[str] = field(default_factory=list)


_REGISTRY: dict[str, ToolRegistration] = {
    "web_search": ToolRegistration(
        name="web_search",
        callable=web_search,
        description="Perform a web search and return summarised results.",
        risk_tier="medium",
        reversible=True,
        allow_network=True,
        input_schema_name="web_search",
        tags=["read", "network"],
    ),
    "file_write": ToolRegistration(
        name="file_write",
        callable=write_file,
        description="Write content to a file at a relative path in the sandbox.",
        risk_tier="high",
        reversible=False,
        allow_network=False,
        input_schema_name="file_write",
        tags=["write", "filesystem"],
    ),
    "stub-retrieval": ToolRegistration(
        name="stub-retrieval",
        callable=lambda q: f"STUB retrieval for: {q}",
        description="Stub memory retrieval — returns deterministic placeholder results.",
        risk_tier="low",
        reversible=True,
        allow_network=False,
        input_schema_name="stub-retrieval",
        tags=["read", "memory"],
    ),
    "stub-executor": ToolRegistration(
        name="stub-executor",
        callable=lambda cmd: f"STUB executor: {cmd}",
        description="Stub command executor — runs within the sandbox subprocess.",
        risk_tier="medium",
        reversible=False,
        allow_network=False,
        input_schema_name="stub-executor",
        tags=["execute", "sandbox"],
    ),
}


def get_tool(name: str) -> ToolRegistration:
    """Return the ToolRegistration for name, or raise KeyError."""
    if name not in _REGISTRY:
        raise KeyError(f"Unknown or unregistered tool: {name!r}")
    return _REGISTRY[name]


def validate_and_get_tool(name: str, raw_input: Any) -> tuple[ToolRegistration, object]:
    """Validate raw_input against the tool's declared schema, then return registration.

    Raises:
        KeyError: Tool not registered.
        pydantic.ValidationError: Input does not match the declared schema.
            This is raised BEFORE the sandbox is invoked — the caller must catch
            it and log a tool_validation_failed event (no sandbox_dispatch fires).
    """
    registration = get_tool(name)
    validated_input = validate_tool_input(registration.input_schema_name, raw_input)
    return registration, validated_input


def list_tools() -> list[dict[str, Any]]:
    """Return all registered tools as serialisable dicts — for GET /tools."""
    result = []
    for reg in _REGISTRY.values():
        result.append({
            "name": reg.name,
            "description": reg.description,
            "risk_tier": reg.risk_tier,
            "reversible": reg.reversible,
            "allow_network": reg.allow_network,
            "tags": reg.tags,
            "input_schema": get_schema_dict(reg.input_schema_name),
        })
    return result
