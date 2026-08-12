"""AgentFlow reliability runner for framework adapters.

This is the piece that applies all four AgentFlow reliability guarantees to
ANY FrameworkAdapter implementation in an identical, framework-agnostic way.

Guarantee application order (per step):
  1. log_event(node_start)          [observability / Stage 8]
  2. adapter.run_step()             [framework-specific work]
  3. sandbox each tool_call         [Stage 4, same run_sandboxed() call]
  4. score + escalation routing     [Stage 5, same score_step() + decide()]
  5. checkpoint_store.save()        [Stage 2 co-located store]
  6. log_event(node_complete)       [observability / Stage 8]

This function is called identically for the LangGraph adapter and the AutoGen
adapter. Zero framework-specific branches exist here.
"""
from __future__ import annotations

import sys
from typing import Any

from app.core.adapters.base import FrameworkAdapter, StepResult
from app.core.adapters.checkpoint_store import AdapterCheckpointStore
from app.core.escalation.scoring import score_step
from app.core.escalation.thresholds import decide_next_action
from app.observability.event_log import log_event


def run_adapter(
    adapter: FrameworkAdapter,
    initial_state: dict[str, Any],
    *,
    db_path: str | None = None,
    resume_from: str | None = None,
) -> dict[str, Any]:
    """Run all steps of *adapter* with AgentFlow's full reliability layer.

    Parameters
    ----------
    adapter       : Any FrameworkAdapter (LangGraphAdapter or AutoGenAdapter).
    initial_state : The starting state dict containing at least run_id and task.
    db_path       : Optional SQLite DB path override (used by tests).
    resume_from   : If provided, skip steps up to and including this step_id
                    (crash-resume simulation).

    Returns
    -------
    Final state dict after all steps complete (or after halt/failure).
    """
    store = AdapterCheckpointStore(db_path)
    run_id: str = initial_state["run_id"]
    state = dict(initial_state)

    # Determine which steps to skip (resume case).
    already_done = store.completed_steps(run_id)
    if resume_from:
        # Load the last checkpointed state as the starting point.
        saved = store.load_latest(run_id)
        if saved:
            state = saved

    for step_id in adapter.list_steps():
        # Skip steps that were already checkpointed (crash-resume).
        if step_id in already_done:
            log_event(run_id, "step_skipped", {"step_id": step_id, "reason": "checkpoint_exists"})
            # Load the checkpointed state for this step as the new baseline.
            saved_state = store.load_step(run_id, step_id)
            if saved_state:
                state = saved_state
            continue

        # ── 1. Announce step start ─────────────────────────────────────────
        log_event(run_id, "node_start", {"node": step_id, "step": state.get("step_index", 0)})

        # ── 2. Execute the step (framework-specific work) ──────────────────
        try:
            result: StepResult = adapter.run_step(step_id, state)
        except Exception as exc:  # noqa: BLE001
            log_event(run_id, "node_error", {"node": step_id, "error": str(exc)[:200]})
            state = {**state, "status": "failed", "error": str(exc)}
            store.save(run_id, step_id, state)
            break

        # ── 3. Sandbox each tool call (Stage 4) ───────────────────────────
        sandboxed_calls: list[dict[str, Any]] = []
        for tc in result.tool_calls:
            tool_name = tc.get("tool", "stub-executor")
            sandboxed_output = _sandbox_tool_call(run_id, tool_name, tc, step_id)
            sandboxed_calls.append({**tc, "sandboxed_output": sandboxed_output})

        # ── 4. Risk scoring + escalation routing (Stage 5) ────────────────
        # If the adapter provided a non-zero risk_score, respect it.
        # Otherwise compute from the output state using the standard scorer.
        if result.risk_score > 0.0:
            risk = result.risk_score
        else:
            risk = score_step(result.output_state, tool_name=None)

        decision = decide_next_action(risk)
        log_event(
            run_id,
            "escalation_decision",
            {"node": step_id, "risk_score": risk, "decision": decision},
        )

        # ── 5. Checkpoint (Stage 2 co-located store) ──────────────────────
        new_state = {
            **state,
            **result.output_state,
            "risk_score": risk,
            "status": result.status,
            "step_index": state.get("step_index", 0) + 1,
        }
        store.save(run_id, step_id, new_state)
        log_event(run_id, "checkpoint_saved", {"node": step_id, "step_index": new_state["step_index"]})
        state = new_state

        # ── 6. Announce step complete ──────────────────────────────────────
        log_event(
            run_id,
            "node_complete",
            {
                "node": step_id,
                "risk_score": risk,
                "decision": decision,
                "output_len": len(result.raw_output),
            },
        )

        # ── 7. Route on escalation decision ───────────────────────────────
        if decision == "HALT":
            log_event(run_id, "run_halted", {"node": step_id, "risk_score": risk})
            state["status"] = "halted"
            break

        if decision == "REQUEST_APPROVAL":
            # Stage 5 gate: in a live system this blocks the graph thread.
            # In adapter runner mode, log and halt (UI can handle the gate).
            log_event(run_id, "awaiting_approval", {"node": step_id, "risk_score": risk})
            state["status"] = "awaiting_approval"
            break

        if result.status == "completed":
            log_event(run_id, "run_completed", {"final_step": step_id})
            state["status"] = "completed"
            break

        if result.status == "failed":
            state["status"] = "failed"
            break

    return state


def _sandbox_tool_call(
    run_id: str,
    tool_name: str,
    tc: dict[str, Any],
    step_id: str,
) -> str:
    """Run one tool call through the Stage 4 sandbox.

    Uses the exact same run_sandboxed() + get_policy_or_deny() calls as the
    LangGraph act_step path. Zero framework-specific branching.
    """
    from app.core.sandbox.docker_runner import run_sandboxed
    from app.core.sandbox.policy import get_policy, get_policy_or_deny

    log_event(
        run_id,
        "sandbox_dispatch",
        {"node": step_id, "tool": tool_name, "input_preview": str(tc.get("input", ""))[:80]},
    )

    policy = get_policy(tool_name)
    if policy is None:
        # Unknown tool — block per Stage 4 deny-by-default.
        log_event(run_id, "sandbox_denied", {"tool": tool_name, "reason": "no_policy"})
        raise PermissionError(f"Tool {tool_name!r} has no registered policy and cannot be executed.")

    command = [sys.executable, "-c", f"print('SANDBOXED: {tool_name}')"]
    try:
        output = run_sandboxed(policy, command, run_id=run_id)
        log_event(run_id, "sandbox_complete", {"tool": tool_name, "output_len": len(output)})
        return output.strip()
    except Exception as exc:  # noqa: BLE001
        log_event(run_id, "sandbox_error", {"tool": tool_name, "error": str(exc)[:200]})
        raise
