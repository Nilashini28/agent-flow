"""Tool input/output schemas with Pydantic validation.

Each tool registered in the registry declares its expected input shape here.
validate_tool_input() is called BEFORE the sandbox executes a tool call,
so malformed calls fail fast with a clear ValidationError rather than
failing silently inside the sandbox.

Design:
  - Input schemas are strict Pydantic models (extra="forbid").
  - Output schemas are lenient (extra="allow") to accommodate future fields.
  - Unknown tools get a PassthroughSchema that accepts any string input —
    validated at the policy layer instead.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


# ── Input Schemas ─────────────────────────────────────────────────────────────

class WebSearchInput(BaseModel):
    """Input for the web_search tool."""
    model_config = {"extra": "forbid"}
    query: str = Field(..., min_length=1, max_length=512, description="Search query string")


class FileWriteInput(BaseModel):
    """Input for the file_write tool."""
    model_config = {"extra": "forbid"}
    path: str = Field(..., min_length=1, description="Destination file path")
    content: str = Field(default="", description="Content to write")

    @field_validator("path")
    @classmethod
    def path_must_not_escape(cls, v: str) -> str:
        if ".." in v or v.startswith("/"):
            raise ValueError("Path must be relative and must not contain '..'")
        return v


class StubRetrievalInput(BaseModel):
    """Input for the stub-retrieval memory tool."""
    model_config = {"extra": "allow"}
    query: str = Field(default="", max_length=512, description="Memory retrieval query")
    command: str = Field(default="", max_length=512, description="Memory retrieval command")


class StubExecutorInput(BaseModel):
    """Input for the stub-executor sandbox tool."""
    model_config = {"extra": "forbid"}
    command: str = Field(default="", max_length=1024, description="Command to execute")


class PassthroughInput(BaseModel):
    """Fallback schema for tools without a strict schema.

    Accepts any string or dict — validation is deferred to the policy layer.
    """
    model_config = {"extra": "allow"}
    command: str = Field(default="")


# ── Output Schemas ────────────────────────────────────────────────────────────

class ToolOutputSchema(BaseModel):
    """Generic output schema — all tool outputs must have at least a result field."""
    model_config = {"extra": "allow"}
    result: str = Field(default="")
    success: bool = Field(default=True)


# ── Validation registry ───────────────────────────────────────────────────────

_INPUT_SCHEMAS: dict[str, type[BaseModel]] = {
    "web_search":     WebSearchInput,
    "file_write":     FileWriteInput,
    "stub-retrieval": StubRetrievalInput,
    "stub-executor":  StubExecutorInput,
}


def validate_tool_input(tool_name: str, raw_input: object) -> BaseModel:
    """Validate raw_input against the registered schema for tool_name.

    Called BEFORE sandbox dispatch. Raises pydantic.ValidationError on failure.

    Args:
        tool_name: Registered tool name (e.g. "web_search").
        raw_input: The raw input — may be a str, dict, or any caller-provided value.

    Returns:
        The validated model instance.
    """
    schema_cls = _INPUT_SCHEMAS.get(tool_name, PassthroughInput)

    # Normalise: if input is a plain string, wrap it as {"command": ...}
    # so PassthroughInput / StubExecutorInput can receive it.
    if isinstance(raw_input, str):
        coerced: object = {"command": raw_input}
    elif raw_input is None:
        coerced = {}
    else:
        coerced = raw_input

    # Pydantic v2 model_validate raises ValidationError on failure.
    return schema_cls.model_validate(coerced)


def get_schema_dict(tool_name: str) -> dict:
    """Return a JSON-serialisable description of the input schema for a tool."""
    schema_cls = _INPUT_SCHEMAS.get(tool_name, PassthroughInput)
    return schema_cls.model_json_schema()
