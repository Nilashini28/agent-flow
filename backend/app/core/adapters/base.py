"""Framework Adapter Interface for AgentFlow — Task 1.

This module defines the minimal contract that ANY agent framework must satisfy
to receive AgentFlow's four reliability guarantees:
  1. Checkpointing   — crash recovery (Stage 2)
  2. Sandbox         — tool execution isolation (Stage 4)
  3. Escalation      — risk-scored human approval gate (Stage 5)
  4. Event logging   — replayable audit timeline

Design principle: MINIMAL SURFACE.
The interface models exactly one concept: a STEP — something that takes state
in and produces state out, with an optional set of tool calls as a side effect.
That is the smallest shape both LangGraph nodes and AutoGen conversation turns
share. Nothing framework-specific leaks through.

What this interface does NOT require from a framework:
  - No checkpointing knowledge: AgentFlow calls run_step(), gets a StepResult,
    and persists it. The framework never touches the checkpoint store.
  - No retry knowledge: AgentFlow's Stage 3 retry wrapper wraps run_step()
    calls externally. The framework sees only a single call per attempt.
  - No sandbox knowledge: AgentFlow intercepts tool_calls from StepResult and
    routes them through the Stage 4 sandbox. The framework declares what tool
    calls were made; AgentFlow enforces the policy.
  - No escalation knowledge: AgentFlow reads risk_score from StepResult and
    applies Stage 5 routing. The framework never calls decide_next_action().
  - No structured event logging: AgentFlow emits node_start / node_complete /
    sandbox_dispatch events using StepResult fields. The framework produces
    text; AgentFlow produces the audit record.
  - No specific state format: output_state is a plain dict. AgentFlow applies
    the AgentState schema after the adapter returns.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StepResult:
    """Output of one logical step executed by an agent framework.

    This is the ONLY thing AgentFlow's reliability layer needs after a step
    completes. All four guarantees (checkpoint, sandbox, escalation, log) are
    applied externally by AgentFlow's runner using these fields alone.

    Fields
    ------
    step_id : str
        The step identifier (e.g. "research", "turn_0"). Used as the event
        name in the timeline and as the checkpoint label.
    output_state : dict
        Updated state after this step. Must contain at minimum:
          - run_id   : str
          - task     : str
          - last_output : str
          - step_index : int
        AgentFlow merges this with the incoming state to form the checkpoint.
    raw_output : str
        Primary text produced by the step. Used by Stage 5 escalation scoring
        and included verbatim in node_complete event payloads.
    status : str
        One of "running" | "completed" | "failed".
        "completed" signals the final step; AgentFlow stops iteration after it.
        "failed" triggers Stage 3 retry logic (if max_retries not exhausted).
    tool_calls : list[dict]
        Tool invocations the step made or intends to make. AgentFlow routes
        these through the Stage 4 sandbox before considering the step done.
        Format: [{"tool": str, "input": str, "output": str, "timestamp": str}]
        An empty list is valid — not every step calls a tool.
    risk_score : float
        [0.0, 1.0] risk estimate. If the adapter leaves this at 0.0, AgentFlow
        calls score_step(output_state, tool_name) from Stage 5 to compute it.
        If the adapter provides a non-zero value, that value is used directly
        (useful when the framework has its own confidence/risk signal).
    error : str | None
        Error message when status == "failed". None on clean steps.
    """

    step_id: str
    output_state: dict[str, Any]
    raw_output: str
    status: str = "running"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    risk_score: float = 0.0
    error: str | None = None


class FrameworkAdapter(ABC):
    """Abstract base for AgentFlow framework adapters.

    Each concrete subclass wraps one agent framework (LangGraph, AutoGen, ...)
    and translates its execution model into AgentFlow's step-based interface.

    The adapter is responsible ONLY for the translation layer. It must never:
      - Call get_checkpointer() or save/load checkpoint state.
      - Call run_sandboxed() directly.
      - Call score_step() or decide_next_action().
      - Call log_event() for node_start / node_complete events.
    All of those are applied by AgentFlow's adapter runner AFTER run_step()
    returns, identically for every adapter implementation.

    Lifecycle (applied by the runner, not the adapter):
      For step_id in adapter.list_steps():
        1. log_event(run_id, "node_start", {step_id})
        2. result = adapter.run_step(step_id, state)          ← adapter work
        3. For each tc in result.tool_calls:
             run_sandboxed(tc)  [Stage 4]
        4. risk = score_step(result.output_state)             [Stage 5]
        5. decision = decide_next_action(risk)                [Stage 5]
        6. checkpoint(run_id, step_id, result.output_state)   [Stage 2]
        7. log_event(run_id, "node_complete", {step_id, risk}) [Stage 2]
        8. If status in (completed, halted, failed): stop.
    """

    @abstractmethod
    def run_step(self, step_id: str, input_state: dict[str, Any]) -> StepResult:
        """Execute one logical step and return its result.

        The adapter MUST NOT apply checkpointing, sandbox, or escalation here.
        Those are applied externally after this returns.

        Parameters
        ----------
        step_id : str
            The step to execute (must be in list_steps()).
        input_state : dict
            Current state dict. Contains at minimum run_id, task,
            last_output, step_index. Additional keys are framework-specific.

        Returns
        -------
        StepResult
            Updated state, tool calls made, risk estimate, and status.
        """

    @abstractmethod
    def list_steps(self) -> list[str]:
        """Return the ordered list of step IDs this adapter executes.

        Each ID becomes a node name in AgentFlow's event timeline. The runner
        calls run_step() for each ID in order, stopping early on
        "completed", "failed", or if escalation routes to HALT.

        Returns
        -------
        list[str]
            Step IDs in execution order.
            LangGraph example : ["research", "draft", "verify", "act"]
            AutoGen example   : ["turn_0", "turn_1", "turn_2"]
        """
