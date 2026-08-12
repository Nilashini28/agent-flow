"""Individual node functions for the AgentFlow graph.

Each node is a pure-ish function: (state) -> partial state update.
Keep side effects (tool calls, sandboxed execution) isolated so nodes stay
testable and each transition is a clean checkpoint boundary.

All nodes follow this contract:
  1. Log entry via log_event().
  2. Do real work (stubbed LLM/tool at this stage — no real API keys).
  3. Append a history entry summarising what happened.
  4. Return a *partial* AgentState dict — never mutate the incoming state.
  5. On any exception: use the retry wrapper to attempt recovery.

Retry integration (Stage 3)
-----------------------------
Each node delegates to ``_run_with_retry(node_fn, node_name, state)``.
Retry logic lives entirely INSIDE a single node invocation:

  - If the node body raises a RETRYABLE exception, the wrapper sleeps
    (exponential backoff) and re-calls the body function.
  - If it raises a NON-RETRYABLE exception, the wrapper falls through to
    the failure return immediately (no wasted sleep/attempt).
  - On exhausting max_retries, the wrapper returns status="failed".
  - On any success, the wrapper returns the successful partial state.

CHECKPOINT INTERACTION: LangGraph checkpoints on node *completion*, not on
mid-node retries.  Because retries happen entirely within the body of a
single node invocation, LangGraph sees only the final outcome — no
intermediate retry states pollute the checkpoint history.

retry_count in AgentState: reset to 0 on each successful node completion.
On a crash-and-resume, the resumed run starts with retry_count=0 for the
freshly re-attempted node (the crashed node never returned a state update,
so no stale count is carried over).

# STAGE-4: sandbox isolation for act_step tool calls goes here.
# STAGE-5: escalation-aware retry caps (retry less when risk_score is high).
# STAGE-6: real LLM calls (Anthropic/OpenAI) replace the stubs below.
"""
from __future__ import annotations

import re
import sys
import textwrap
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.core.escalation.scoring import score_step
from app.core.graph.schemas import AgentState
from app.core.retry.backoff import backoff_sleep
from app.core.retry.policy import NODE_POLICIES, RetryPolicy, is_retryable
from app.observability.event_log import log_event

# ── Stub LLM ──────────────────────────────────────────────────────────────────


def _stub_llm(prompt: str) -> dict[str, str]:
    """Return a deterministic 'model response' for a given prompt."""
    _STOP = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "can",
        "to", "of", "in", "on", "at", "by", "for", "with", "about",
        "from", "into", "through", "how", "what", "when", "where", "why",
    }
    tokens = re.findall(r"[a-zA-Z]{3,}", prompt.lower())
    keywords = list(dict.fromkeys(t for t in tokens if t not in _STOP))[:5]
    word_count = len(prompt.split())
    confidence = min(0.4 + word_count * 0.02, 0.95)
    return {
        "content": (
            f"[stub-llm] keywords={keywords} | "
            f"confidence={confidence:.2f} | "
            f"input_words={word_count}"
        ),
        "confidence": str(confidence),
        "keywords": ",".join(keywords),
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Retry wrapper ─────────────────────────────────────────────────────────────


def _run_with_retry(
    node_fn: Callable[[AgentState], dict[str, Any]],
    node_name: str,
    state: AgentState,
    *,
    policy: RetryPolicy | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> dict[str, Any]:
    """Execute *node_fn(state)* with exponential-backoff retry.

    Args:
        node_fn:    The node body function.  Must accept AgentState and
                    return a partial state dict.
        node_name:  Human-readable name used in log_event() payloads.
        state:      Current AgentState passed in by the graph.
        policy:     RetryPolicy instance.  Defaults to NODE_POLICIES[node_name]
                    if not supplied; falls back to the global DEFAULT_POLICY.
        sleep_fn:   Injectable sleep callable.  Defaults to time.sleep.
                    Tests inject ``lambda _: None`` for fast runs.

    Returns:
        The partial AgentState dict returned by node_fn on success, or a
        failure dict (status="failed", error=str(exc)) on exhausting retries
        or hitting a non-retryable error.

    Checkpoint contract:
        This function is called synchronously within the node's LangGraph
        invocation frame.  All retry attempts happen before this function
        returns, so LangGraph never sees intermediate failed states — it
        only checkpoints the outcome of the final attempt.
    """
    from app.core.retry.policy import DEFAULT_POLICY  # avoid circular at module level

    run_id: str = state.get("run_id", "unknown")
    effective_policy: RetryPolicy = policy or NODE_POLICIES.get(node_name, DEFAULT_POLICY)
    effective_sleep = sleep_fn  # None means use time.sleep (backoff_sleep default)

    last_exc: BaseException | None = None

    for attempt in range(effective_policy.max_retries + 1):
        try:
            result = node_fn(state)
            # Success — reset retry_count so downstream nodes start clean.
            result["retry_count"] = 0
            if attempt > 0:
                log_event(
                    run_id,
                    "retry_succeeded",
                    {
                        "node": node_name,
                        "succeeded_on_attempt": attempt,
                        "total_attempts": attempt + 1,
                    },
                )
            return result

        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            retryable = is_retryable(exc)

            log_event(
                run_id,
                "retry_attempt",
                {
                    "node": node_name,
                    "attempt": attempt,
                    "max_retries": effective_policy.max_retries,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:200],
                    "retryable": retryable,
                },
            )

            if not retryable:
                # Non-retryable: fail fast, no sleep.
                log_event(
                    run_id,
                    "retry_aborted",
                    {
                        "node": node_name,
                        "reason": "non_retryable_error",
                        "error_type": type(exc).__name__,
                    },
                )
                break

            if attempt < effective_policy.max_retries:
                # Sleep before the next attempt.
                delay = backoff_sleep(
                    attempt=attempt,
                    base_delay=effective_policy.base_delay,
                    max_delay=effective_policy.max_delay,
                    **({"sleep_fn": effective_sleep} if effective_sleep is not None else {}),
                )
                log_event(
                    run_id,
                    "retry_backoff",
                    {
                        "node": node_name,
                        "attempt": attempt,
                        "delay_seconds": round(delay, 3),
                        "next_attempt": attempt + 1,
                    },
                )
            else:
                # Exhausted retries.
                log_event(
                    run_id,
                    "retry_exhausted",
                    {
                        "node": node_name,
                        "total_attempts": attempt + 1,
                        "error_type": type(exc).__name__,
                    },
                )

    # All attempts exhausted (or non-retryable error).
    return {
        **state,
        "status": "failed",
        "error": str(last_exc),
        "retry_count": state.get("retry_count", 0),
    }


# ── Nodes ─────────────────────────────────────────────────────────────────────


def research_step(state: AgentState) -> AgentState:
    """Retrieve / reason about the task; produce structured research output."""
    run_id = state["run_id"]
    log_event(run_id, "node_start", {"node": "research", "step": state.get("step_index", 0)})

    def _body(s: AgentState) -> dict[str, Any]:
        task = s["task"]

        retrieval_result = {
            "source": "stub-retrieval",
            "snippet": textwrap.shorten(
                f"Background context for '{task}': relevant prior work includes "
                "planning, decomposition, and tool-use patterns.",
                width=120,
            ),
            "score": 0.82,
        }

        llm_prompt = (
            f"Task: {task}\n"
            f"Context: {retrieval_result['snippet']}\n"
            "Summarise key facts needed to complete this task."
        )
        llm_response = _stub_llm(llm_prompt)

        output = (
            f"RESEARCH | task='{task}' | "
            f"retrieval_score={retrieval_result['score']} | "
            f"{llm_response['content']}"
        )

        tool_call_record = {
            "tool": "stub-retrieval",
            "input": task,
            "output": retrieval_result["snippet"],
            "timestamp": _utc_now(),
        }
        existing_calls: list = list(s.get("tool_calls", []))
        existing_calls.append(tool_call_record)

        history_entry = {
            "node": "research",
            "step_index": s.get("step_index", 0),
            "output_summary": output[:200],
            "timestamp": _utc_now(),
        }
        history: list = list(s.get("history", []))
        history.append(history_entry)

        log_event(run_id, "node_complete", {"node": "research", "output_len": len(output)})
        return {
            **s,
            "last_output": output,
            "tool_calls": existing_calls,
            "history": history,
            "step_index": s.get("step_index", 0) + 1,
            "status": "running",
            "error": None,
        }

    return _run_with_retry(_body, "research", state)


def draft_step(state: AgentState) -> AgentState:
    """Transform research output into a structured action plan."""
    run_id = state["run_id"]
    log_event(run_id, "node_start", {"node": "draft", "step": state.get("step_index", 0)})

    def _body(s: AgentState) -> dict[str, Any]:
        research_output = s.get("last_output", "")
        if not research_output:
            raise ValueError("draft_step received empty last_output — research may have failed")

        llm_prompt = (
            f"Based on this research:\n{research_output}\n\n"
            "Produce a numbered action plan with at most 3 steps."
        )
        llm_response = _stub_llm(llm_prompt)
        keywords_str = llm_response.get("keywords", "")
        keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]

        steps = [
            f"Step {i + 1}: Process '{kw}' sub-task"
            for i, kw in enumerate(keywords[:3])
        ] or ["Step 1: Execute primary task goal"]

        draft_body = " | ".join(steps)
        output = (
            f"DRAFT | plan_steps={len(steps)} | confidence={llm_response['confidence']} | "
            f"{draft_body}"
        )

        history_entry = {
            "node": "draft",
            "step_index": s.get("step_index", 0),
            "output_summary": output[:200],
            "timestamp": _utc_now(),
        }
        history: list = list(s.get("history", []))
        history.append(history_entry)

        log_event(run_id, "node_complete", {"node": "draft", "plan_steps": len(steps)})
        return {
            **s,
            "last_output": output,
            "history": history,
            "step_index": s.get("step_index", 0) + 1,
            "status": "running",
            "error": None,
        }

    return _run_with_retry(_body, "draft", state)


def verify_step(state: AgentState) -> AgentState:
    """Validate the draft and compute a risk score that drives routing."""
    run_id = state["run_id"]
    log_event(run_id, "node_start", {"node": "verify", "step": state.get("step_index", 0)})

    def _body(s: AgentState) -> dict[str, Any]:
        draft_output = s.get("last_output", "")

        penalty = 0.0
        violations: list[str] = []

        if not draft_output.strip():
            penalty += 0.5
            violations.append("empty_output")

        if "DRAFT" not in draft_output:
            penalty += 0.3
            violations.append("missing_draft_marker")

        _FORBIDDEN = {"delete all", "rm -rf", "drop table", "shutdown"}
        lower = draft_output.lower()
        for kw in _FORBIDDEN:
            if kw in lower:
                penalty += 0.4
                violations.append(f"forbidden_keyword:{kw}")

        if len(draft_output.strip()) < 20:
            penalty += 0.2
            violations.append("too_short")

        penalty = min(penalty, 1.0)
        scorer_risk = score_step(s, tool_name=None)

        if violations:
            risk = round(min(penalty * 0.7 + scorer_risk * 0.3, 1.0), 4)
        else:
            risk = scorer_risk

        history_entry = {
            "node": "verify",
            "step_index": s.get("step_index", 0),
            "risk_score": risk,
            "violations": violations,
            "timestamp": _utc_now(),
        }
        history: list = list(s.get("history", []))
        history.append(history_entry)

        log_event(
            run_id,
            "node_complete",
            {"node": "verify", "risk_score": risk, "violations": violations},
        )
        return {
            **s,
            "risk_score": risk,
            "history": history,
            "step_index": s.get("step_index", 0) + 1,
            "status": "running",
            "error": None,
        }

    result = _run_with_retry(_body, "verify", state)
    # A failed verify is treated as high-risk: set score=1.0 so routing
    # always halts rather than proceeding blindly.
    if result.get("status") == "failed":
        result["risk_score"] = 1.0
    return result


def act_step(state: AgentState) -> AgentState:
    """Execute the verified plan via the sandbox and mark the run as completed.

    Stage-4 wiring: each plan step is dispatched through run_sandboxed()
    using the stub-executor ToolPolicy.  The sandbox enforces:
      - Wall-clock timeout (always).
      - Memory and CPU limits (POSIX only; timeout-only on Windows).
      - Filesystem write path validation (stub-executor → sandbox_output/ only).

    TimeoutError from the sandbox is RETRYABLE per Stage 3's policy
    (TimeoutError is in RETRYABLE_EXCEPTIONS).  _run_with_retry handles this
    automatically — act_step's _body just lets the exception propagate.

    Uses ACT_POLICY (max_retries=1) to limit duplicate side-effect risk.
    STAGE-6: real LLM/tool commands replace the stub-executor command below.
    """
    run_id = state["run_id"]
    log_event(run_id, "node_start", {"node": "act", "step": state.get("step_index", 0)})

    def _body(s: AgentState) -> dict[str, Any]:
        from app.core.sandbox.docker_runner import run_sandboxed
        from app.core.sandbox.policy import get_policy_or_deny
        from app.core.sandbox.violations import check_write_path_policy

        draft_output = s.get("last_output", "")

        # Parse plan steps from draft output.
        executed_steps: list[str] = []
        if "Step" in draft_output:
            raw_steps = [st.strip() for st in draft_output.split("|") if "Step" in st]
        else:
            raw_steps = [f"primary goal from '{draft_output[:60]}'"]

        # Fetch the sandbox policy for stub-executor.
        executor_policy = get_policy_or_deny("stub-executor")

        for raw in raw_steps:
            # Build a sandboxed command: echo the step name as the tool's action.
            # STAGE-6: replace with real tool dispatcher commands.
            command = [sys.executable, "-c", f"print('EXECUTED: {raw}')"]

            log_event(
                run_id,
                "sandbox_dispatch",
                {
                    "tool": "stub-executor",
                    "step": raw[:80],
                    "sandbox_mode": _get_effective_mode(),
                },
            )

            sandbox_output = run_sandboxed(executor_policy, command, run_id=run_id)
            executed_steps.append(sandbox_output.strip() or f"EXECUTED: {raw}")

        action_log = " | ".join(executed_steps)
        output = f"ACT | steps_executed={len(executed_steps)} | {action_log}"

        tool_call_record = {
            "tool": "stub-executor",
            "input": draft_output[:120],
            "output": action_log[:120],
            "timestamp": _utc_now(),
        }
        existing_calls: list = list(s.get("tool_calls", []))
        existing_calls.append(tool_call_record)

        history_entry = {
            "node": "act",
            "step_index": s.get("step_index", 0),
            "steps_executed": len(executed_steps),
            "output_summary": output[:200],
            "timestamp": _utc_now(),
        }
        history: list = list(s.get("history", []))
        history.append(history_entry)

        log_event(
            run_id,
            "node_complete",
            {"node": "act", "steps_executed": len(executed_steps)},
        )
        return {
            **s,
            "last_output": output,
            "tool_calls": existing_calls,
            "history": history,
            "status": "completed",
            "step_index": s.get("step_index", 0) + 1,
            "error": None,
        }

    return _run_with_retry(_body, "act", state)


def _get_effective_mode() -> str:
    """Return the actual sandbox mode being used (accounts for Docker fallback)."""
    from app.core.sandbox.docker_runner import _DOCKER_UNAVAILABLE
    from app.config import get_settings
    settings = get_settings()
    if settings.sandbox_mode == "docker" and _DOCKER_UNAVAILABLE:
        return "subprocess (docker-fallback)"
    return settings.sandbox_mode

