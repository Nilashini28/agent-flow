"""Shared state shape passed between graph nodes.

AgentState is a TypedDict with total=False so any node can return a *partial*
dict — LangGraph merges it with the accumulated state rather than replacing it.

Field ownership by node:
  research_step  -> last_output, tool_calls, step_index, history
  draft_step     -> last_output, step_index, history
  verify_step    -> risk_score, step_index, history, error
  act_step       -> last_output, status, step_index, history
"""
from typing import Any, Literal, TypedDict


class AgentState(TypedDict, total=False):
    # ── Identity ─────────────────────────────────────────────────────────────
    run_id: str          # UUID assigned at graph invocation time
    task: str            # Natural-language goal driving the entire run

    # ── Progress ──────────────────────────────────────────────────────────────
    step_index: int      # Monotonically incremented after every node completes
    history: list[dict[str, Any]]  # Append-only record of per-node outputs

    # ── Data payload ──────────────────────────────────────────────────────────
    last_output: str     # Most recent node's primary text output
    tool_calls: list[dict[str, Any]]  # Tool invocations made this run so far

    # ── Risk / control ────────────────────────────────────────────────────────
    risk_score: float    # [0, 1] — computed by verify_step; drives routing

    # ── Status ────────────────────────────────────────────────────────────────
    status: Literal["running", "awaiting_approval", "halted", "completed", "failed"]

    # ── Error handling ────────────────────────────────────────────────────────
    error: str | None    # Set by any node's except block; None on clean runs
    retry_count: int     # Incremented on retryable failures (Stage 3 will use this)
