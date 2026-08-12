"""LangGraph Framework Adapter — Task 2.

Wraps the existing LangGraph node functions (research_step, draft_step,
verify_step, act_step) behind the FrameworkAdapter interface, proving that
the interface is real by showing LangGraph itself conforms to it.

REFACTORING APPROACH:
  The existing nodes.py functions are not changed — they remain the canonical
  implementation. This adapter calls each function directly (bypassing
  LangGraph's graph.invoke()), which means:

  - Checkpointing: done externally by the adapter runner (not by LangGraph's
    SqliteSaver via compile(checkpointer=...)).
  - Conditional routing (verify → act or verify → END): the LangGraph
    conditional edge is reimplemented here via the risk_score threshold
    — the adapter reads risk_score from the verify result and sets status
    accordingly, letting the runner's escalation routing take over.

WHAT STAYS THE SAME:
  - All four node body functions are identical — no changes to nodes.py.
  - Stage 3 retry logic in _run_with_retry() still wraps each node body.
  - Stage 4 sandbox wiring in act_step._body() is unchanged.
  - Stage 5 risk score computed by verify_step and read here.

WHAT CHANGED (honestly):
  - The LangGraph compiled graph (build_graph()) is no longer called.
    The adapter calls node functions directly, so LangGraph's state-merging
    and conditional edge traversal don't apply.
  - For tests that test graph.invoke() behaviour (Stage 1–7), the original
    build_graph() path is unchanged — those tests do not use this adapter.
  - For tests of the adapter itself, both paths coexist.
"""
from __future__ import annotations

from typing import Any

from app.core.adapters.base import FrameworkAdapter, StepResult
from app.core.graph.nodes import act_step, draft_step, research_step, verify_step
from app.core.graph.schemas import AgentState

# Ordered step list — mirrors the LangGraph node order.
_STEPS = ["research", "draft", "verify", "act"]

# Node function map — same functions nodes.py exports, called directly.
_NODE_FN = {
    "research": research_step,
    "draft": draft_step,
    "verify": verify_step,
    "act": act_step,
}


class LangGraphAdapter(FrameworkAdapter):
    """Adapter that runs AgentFlow's LangGraph nodes through run_step().

    Each call to run_step() executes one LangGraph node function directly
    (not via graph.invoke()). The adapter runner applies checkpointing,
    sandbox, and escalation externally after each run_step() call.

    Step boundary rule (LangGraph → FrameworkAdapter):
      One LangGraph node = one step_id. The mapping is 1:1 and explicit
      because LangGraph's graph definition already has named node boundaries.
      No approximation is needed.

    Verify step special case:
      verify_step() returns a risk_score in its output state. The adapter
      propagates this as StepResult.risk_score so the runner's escalation
      model receives the pre-computed score rather than recomputing it.
      This avoids double-scoring while using the same decide_next_action()
      routing logic.
    """

    def list_steps(self) -> list[str]:
        return list(_STEPS)

    def run_step(self, step_id: str, input_state: dict[str, Any]) -> StepResult:
        if step_id not in _NODE_FN:
            raise ValueError(f"Unknown step_id {step_id!r}. Expected one of {_STEPS}.")

        node_fn = _NODE_FN[step_id]
        # Cast to AgentState — the node functions accept TypedDict, which is
        # structurally compatible with any dict that has the required keys.
        state: AgentState = input_state  # type: ignore[assignment]

        output: AgentState = node_fn(state)

        # Determine status from the node's output.
        raw_status = output.get("status", "running")
        if raw_status == "completed":
            final_status = "completed"
        elif raw_status == "failed":
            final_status = "failed"
        else:
            # Verify is the last step before a possible escalation or act.
            # Keep status as "running" — the runner's escalation routing
            # will decide whether to proceed to act or gate/halt.
            final_status = "running"

        # Propagate the risk score from verify_step so the runner can use it
        # for escalation without re-calling score_step() unnecessarily.
        risk = float(output.get("risk_score", 0.0))

        last_output: str = output.get("last_output", "")
        tool_calls: list[dict[str, Any]] = list(output.get("tool_calls", []))
        error: str | None = output.get("error")

        return StepResult(
            step_id=step_id,
            output_state=dict(output),
            raw_output=last_output,
            status=final_status,
            tool_calls=tool_calls,
            risk_score=risk,
            error=error,
        )
