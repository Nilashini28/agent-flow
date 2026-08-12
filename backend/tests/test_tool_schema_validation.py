"""Test: schema validation fires BEFORE sandbox dispatch.

Verifies that when a tool call carries an invalid input:
  1. A tool_validation_failed event is logged.
  2. No sandbox_dispatch event fires.
  3. The run_adapter() call raises PermissionError.

This proves the schema guard sits in front of the sandbox, not inside it.
"""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

import pytest

from app.core.adapters.base import FrameworkAdapter, StepResult
from app.core.adapters.runner import run_adapter
from app.tools.schema import validate_tool_input, WebSearchInput, FileWriteInput


# ── Schema unit tests ─────────────────────────────────────────────────────────

class TestSchemaValidation:
    def test_web_search_valid(self):
        result = validate_tool_input("web_search", {"query": "AgentFlow reliability"})
        assert isinstance(result, WebSearchInput)
        assert result.query == "AgentFlow reliability"

    def test_web_search_string_input_coerced(self):
        """A plain string is wrapped as {"command": ...} for passthrough schemas."""
        # web_search uses WebSearchInput which needs "query", not "command",
        # so a raw string that can't be coerced to {"query": ...} should fail.
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            validate_tool_input("web_search", "bare string without query field")

    def test_web_search_empty_query_fails(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            validate_tool_input("web_search", {"query": ""})  # min_length=1

    def test_file_write_valid(self):
        result = validate_tool_input("file_write", {"path": "output/report.txt", "content": "hello"})
        assert isinstance(result, FileWriteInput)

    def test_file_write_path_traversal_blocked(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="must not contain"):
            validate_tool_input("file_write", {"path": "../../etc/passwd", "content": "evil"})

    def test_file_write_absolute_path_blocked(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            validate_tool_input("file_write", {"path": "/etc/passwd", "content": "evil"})

    def test_stub_executor_valid(self):
        result = validate_tool_input("stub-executor", {"command": "echo hello"})
        assert result.command == "echo hello"

    def test_stub_executor_string_coerced(self):
        result = validate_tool_input("stub-executor", "echo hello")
        assert result.command == "echo hello"

    def test_unknown_tool_uses_passthrough(self):
        """Unknown tools use PassthroughInput — validation is deferred to policy layer."""
        result = validate_tool_input("completely-unknown-tool", "any input")
        assert result is not None  # PassthroughInput accepts anything

    def test_get_schema_dict_returns_json_schema(self):
        from app.tools.schema import get_schema_dict
        schema = get_schema_dict("web_search")
        assert "properties" in schema
        assert "query" in schema["properties"]


# ── Integration: validation fires BEFORE sandbox, no sandbox_dispatch event ──

def _make_state(task: str = "schema test") -> dict[str, Any]:
    return {
        "run_id": f"test-schema-{uuid.uuid4().hex[:8]}",
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


class _InvalidToolAdapter(FrameworkAdapter):
    """Adapter that injects one tool call with an INVALID input (path traversal)."""
    def list_steps(self) -> list[str]:
        return ["step_0"]

    def run_step(self, step_id: str, input_state: dict[str, Any]) -> StepResult:
        return StepResult(
            step_id=step_id,
            output_state={**input_state, "last_output": "attempted bad write"},
            raw_output="attempted bad write",
            status="running",
            tool_calls=[
                {
                    "tool": "file_write",
                    "input": {"path": "../../etc/passwd", "content": "evil"},
                    "output": "",
                }
            ],
            risk_score=0.0,
        )


class TestValidationBeforeSandbox:
    """Prove schema validation fires before sandbox dispatch."""

    def test_invalid_tool_input_raises_before_sandbox(self, tmp_path):
        """run_adapter() raises PermissionError for invalid tool input.

        The schema guard sits in front of the sandbox path — no sandbox
        subprocess is ever launched for an invalid call.
        """
        state = _make_state("invalid path traversal test")
        adapter = _InvalidToolAdapter()

        with pytest.raises(PermissionError, match="schema validation"):
            run_adapter(adapter, state, db_path=str(tmp_path / "test.db"))

    def test_tool_validation_failed_event_logged(self, tmp_path):
        """A tool_validation_failed event is logged for an invalid tool call."""
        state = _make_state("validation event test")
        adapter = _InvalidToolAdapter()

        logged_events: list[dict] = []

        def capture_log(run_id, event_type, payload=None):
            logged_events.append({"event_type": event_type, "payload": payload or {}})

        with patch("app.core.adapters.runner.log_event", side_effect=capture_log):
            try:
                run_adapter(adapter, state, db_path=str(tmp_path / "test.db"))
            except PermissionError:
                pass

        event_types = [e["event_type"] for e in logged_events]
        assert "tool_validation_failed" in event_types, (
            f"Expected tool_validation_failed event. Got: {event_types}"
        )

    def test_no_sandbox_dispatch_for_invalid_input(self, tmp_path):
        """sandbox_dispatch must NOT fire for a call with invalid input.

        This is the core assertion: the schema guard fires first so the
        sandbox is never even started for an invalid/malicious input.
        """
        state = _make_state("no sandbox dispatch test")
        adapter = _InvalidToolAdapter()

        logged_events: list[dict] = []

        def capture_log(run_id, event_type, payload=None):
            logged_events.append({"event_type": event_type})

        with patch("app.core.adapters.runner.log_event", side_effect=capture_log):
            try:
                run_adapter(adapter, state, db_path=str(tmp_path / "test.db"))
            except PermissionError:
                pass

        event_types = [e["event_type"] for e in logged_events]
        assert "sandbox_dispatch" not in event_types, (
            f"sandbox_dispatch fired despite invalid input! Events: {event_types}"
        )

    def test_valid_tool_input_proceeds_to_sandbox(self, tmp_path):
        """Confirm a valid tool input DOES fire sandbox_dispatch (positive control)."""

        class ValidToolAdapter(FrameworkAdapter):
            def list_steps(self) -> list[str]:
                return ["step_0"]

            def run_step(self, step_id: str, input_state: dict[str, Any]) -> StepResult:
                return StepResult(
                    step_id=step_id,
                    output_state={**input_state, "last_output": "ok"},
                    raw_output="ok",
                    status="completed",
                    tool_calls=[
                        {
                            "tool": "stub-executor",
                            "input": "echo hello",
                            "output": "",
                        }
                    ],
                    risk_score=0.0,
                )

        state = _make_state("valid tool positive control")
        adapter = ValidToolAdapter()

        sandbox_dispatched: list[bool] = []

        def capture_log(run_id, event_type, payload=None):
            if event_type == "sandbox_dispatch":
                sandbox_dispatched.append(True)

        with patch("app.core.adapters.runner.log_event", side_effect=capture_log), \
             patch("app.core.adapters.runner.decide_next_action", return_value="CONTINUE"):
            try:
                run_adapter(adapter, state, db_path=str(tmp_path / "test.db"))
            except Exception:
                pass  # sandbox may fail in test env — we only care about dispatch

        assert len(sandbox_dispatched) > 0, (
            "sandbox_dispatch should have fired for a valid tool call (positive control)"
        )
