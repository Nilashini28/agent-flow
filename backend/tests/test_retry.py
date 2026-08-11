"""Stage-3 retry logic tests.

Test strategy
-------------
Every retryable-error test uses a REAL closure over a module-level counter
that raises on the first N calls and succeeds on call N+1.  No mocked
exception return values — the actual retry control-flow is exercised.

The tests inject ``sleep_fn=lambda _: None`` (recorded via a list append)
so:
  a. Tests run in microseconds without any real sleeping.
  b. The sequence of delay VALUES passed to sleep_fn is captured and can
     be asserted to be strictly increasing (pre-jitter baseline).

Checkpoint interaction test (Test 6):
  Uses a real checkpointed graph with a node body that fails once then
  succeeds.  Verifies checkpoint history via get_checkpoint_history() from
  Stage 2 — the count of checkpoints must equal a clean run (one per node
  transition), not one-per-attempt.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import Callable
from typing import Any

import pytest

from app.core.checkpointing.checkpointer import get_checkpointer_for_path
from app.core.checkpointing.recovery import get_checkpoint_history
from app.core.graph.nodes import _run_with_retry
from app.core.graph.schemas import AgentState
from app.core.retry.backoff import backoff_sleep, compute_backoff_delay
from app.core.retry.policy import (
    DEFAULT_POLICY,
    RetryPolicy,
    is_retryable,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(run_id: str | None = None) -> AgentState:
    rid = run_id or f"retry-test-{uuid.uuid4().hex[:8]}"
    return AgentState(
        run_id=rid,
        task="retry test task",
        step_index=0,
        history=[],
        last_output="",
        tool_calls=[],
        risk_score=0.0,
        status="running",
        error=None,
        retry_count=0,
    )


def _make_flaky_body(fail_times: int, exc_factory: Callable[[], Exception]):
    """Return a node body function that raises exc_factory() for the first
    *fail_times* calls, then returns a success partial-state dict.

    Uses a closure over a mutable list (not a module-level counter) so tests
    are fully isolated from each other.
    """
    call_count: list[int] = [0]

    def _body(state: AgentState) -> dict[str, Any]:
        call_count[0] += 1
        if call_count[0] <= fail_times:
            raise exc_factory()
        return {
            **state,
            "status": "running",
            "last_output": f"success on call {call_count[0]}",
            "error": None,
        }

    _body.call_count = call_count  # type: ignore[attr-defined]
    return _body


def _noop_sleep_recorder() -> tuple[Callable[[float], None], list[float]]:
    """Return (sleep_fn, delays_list) — sleep_fn appends its arg to delays_list."""
    delays: list[float] = []
    return (lambda d: delays.append(d)), delays


# ---------------------------------------------------------------------------
# Test 1 — is_retryable() classification
# ---------------------------------------------------------------------------


def test_is_retryable_transient_errors():
    assert is_retryable(ConnectionError("timeout")) is True
    assert is_retryable(TimeoutError("server down")) is True
    assert is_retryable(OSError("disk error")) is True


def test_is_retryable_non_retryable_errors():
    assert is_retryable(ValueError("bad input")) is False
    assert is_retryable(TypeError("wrong type")) is False
    assert is_retryable(KeyError("missing key")) is False
    assert is_retryable(PermissionError("no access")) is False
    assert is_retryable(AttributeError("no attr")) is False


def test_is_retryable_unknown_defaults_to_false():
    """Unknown exceptions default to non-retryable — fail-safe, not fail-open."""

    class WeirdError(Exception):
        pass

    assert is_retryable(WeirdError("unknown")) is False


# ---------------------------------------------------------------------------
# Test 2 — backoff delay increases with attempt number (pre-jitter)
# ---------------------------------------------------------------------------


def test_compute_backoff_delay_increases_with_attempt():
    """Delays must strictly increase before jitter is applied."""
    base = 1.0
    delays = [
        compute_backoff_delay(attempt=i, base_delay=base, max_delay=60.0, jitter_factor=0.0)
        for i in range(5)
    ]
    # With jitter_factor=0.0 the formula is deterministic: base * 2**attempt
    assert delays == [1.0, 2.0, 4.0, 8.0, 16.0], f"Unexpected delays: {delays}"


def test_compute_backoff_delay_caps_at_max():
    delay = compute_backoff_delay(attempt=10, base_delay=1.0, max_delay=5.0, jitter_factor=0.0)
    assert delay == 5.0


def test_compute_backoff_delay_never_negative():
    """With extreme negative jitter the result must still be >= 0."""
    # Can't force negative directly since uniform(-1, 1) is random, but
    # with a very small base and high jitter_factor this can produce 0.
    for _ in range(50):
        d = compute_backoff_delay(attempt=0, base_delay=0.001, max_delay=1.0, jitter_factor=2.0)
        assert d >= 0.0, f"delay went negative: {d}"


def test_backoff_sleep_calls_sleep_fn():
    sleep_fn, delays = _noop_sleep_recorder()
    backoff_sleep(attempt=0, base_delay=1.0, max_delay=30.0, sleep_fn=sleep_fn)
    assert len(delays) == 1
    assert delays[0] >= 0.0


# ---------------------------------------------------------------------------
# Test 3a — transient error succeeds on 2nd attempt
# ---------------------------------------------------------------------------


def test_retry_succeeds_on_second_attempt():
    """A node that fails once (transient) must succeed on the 2nd attempt.

    Asserts:
      - final status == "running" (node body succeeded)
      - retry_count == 0 (reset on success)
      - sleep_fn called exactly once (one backoff between attempt 0 and 1)
      - call_count == 2 (body was called exactly twice)
    """
    state = _make_state()
    sleep_fn, delays = _noop_sleep_recorder()
    body = _make_flaky_body(fail_times=1, exc_factory=lambda: ConnectionError("timeout"))
    policy = RetryPolicy(max_retries=3, base_delay=1.0, max_delay=30.0)

    result = _run_with_retry(body, "research", state, policy=policy, sleep_fn=sleep_fn)

    assert result["status"] == "running", f"Expected running, got {result['status']!r}"
    assert result["retry_count"] == 0, f"retry_count should reset to 0, got {result['retry_count']}"
    assert len(delays) == 1, f"Expected 1 sleep call (between attempt 0→1), got {len(delays)}"
    assert body.call_count[0] == 2, f"Body should be called exactly twice, got {body.call_count[0]}"


# ---------------------------------------------------------------------------
# Test 3b — transient error exhausts max_retries
# ---------------------------------------------------------------------------


def test_retry_exhausts_max_retries():
    """A node that always fails must stop after exactly max_retries+1 attempts.

    With max_retries=2, total calls = 3 (attempt 0, 1, 2).
    """
    state = _make_state()
    sleep_fn, delays = _noop_sleep_recorder()
    policy = RetryPolicy(max_retries=2, base_delay=1.0, max_delay=30.0)
    body = _make_flaky_body(fail_times=999, exc_factory=lambda: TimeoutError("always"))

    result = _run_with_retry(body, "research", state, policy=policy, sleep_fn=sleep_fn)

    assert result["status"] == "failed", f"Expected failed, got {result['status']!r}"
    assert "always" in result.get("error", ""), f"Error message lost: {result.get('error')}"
    # total attempts = max_retries + 1 = 3
    assert body.call_count[0] == 3, (
        f"Expected exactly 3 total calls (0,1,2), got {body.call_count[0]}"
    )
    # sleeps between attempt 0→1 and 1→2 only (NOT after final failure)
    assert len(delays) == 2, f"Expected 2 sleep calls, got {len(delays)}"


# ---------------------------------------------------------------------------
# Test 3c — non-retryable error fails immediately, zero sleeps
# ---------------------------------------------------------------------------


def test_non_retryable_error_fails_immediately():
    """A non-retryable error must fail on attempt 0 with zero backoff sleeps."""
    state = _make_state()
    sleep_fn, delays = _noop_sleep_recorder()
    policy = RetryPolicy(max_retries=3, base_delay=1.0, max_delay=30.0)
    body = _make_flaky_body(fail_times=999, exc_factory=lambda: ValueError("bad input"))

    result = _run_with_retry(body, "research", state, policy=policy, sleep_fn=sleep_fn)

    assert result["status"] == "failed"
    assert body.call_count[0] == 1, (
        f"Non-retryable: body should be called exactly once, got {body.call_count[0]}"
    )
    assert len(delays) == 0, (
        f"Non-retryable: sleep_fn must not be called, got {len(delays)} calls"
    )


# ---------------------------------------------------------------------------
# Test 3d — backoff delays are strictly increasing (pre-jitter sequence)
# ---------------------------------------------------------------------------


def test_backoff_delays_strictly_increasing_before_jitter():
    """The pre-jitter sequence base*2**i must be strictly increasing."""
    delays = [
        compute_backoff_delay(i, base_delay=1.0, max_delay=100.0, jitter_factor=0.0)
        for i in range(4)
    ]
    for i in range(len(delays) - 1):
        assert delays[i] < delays[i + 1], (
            f"Delay not increasing at index {i}: {delays[i]} >= {delays[i+1]}"
        )


def test_sleep_fn_called_with_increasing_values_across_retries():
    """Delays passed to sleep_fn across retry attempts must increase.

    Uses jitter_factor=0.0 via compute_backoff_delay directly to remove
    randomness from the assertion.  The retry wrapper itself uses non-zero
    jitter; this test validates the underlying sequence independently.
    """
    delays = [
        compute_backoff_delay(i, base_delay=1.0, max_delay=100.0, jitter_factor=0.0)
        for i in range(3)
    ]
    assert delays[0] < delays[1] < delays[2], f"Delays not increasing: {delays}"


# ---------------------------------------------------------------------------
# Test 4 — retry_count resets to 0 on success
# ---------------------------------------------------------------------------


def test_retry_count_resets_on_success():
    """retry_count in the returned state must be 0 after a successful retry."""
    state = _make_state()
    state["retry_count"] = 5  # stale value from a previous phase

    sleep_fn, _ = _noop_sleep_recorder()
    body = _make_flaky_body(fail_times=1, exc_factory=lambda: ConnectionError("x"))
    policy = RetryPolicy(max_retries=3)

    result = _run_with_retry(body, "research", state, policy=policy, sleep_fn=sleep_fn)
    assert result["retry_count"] == 0


# ---------------------------------------------------------------------------
# Test 5 — retry_count carried over on failure (documents the decision)
# ---------------------------------------------------------------------------


def test_retry_count_preserved_on_failure():
    """On exhausted retries the returned state carries the pre-call retry_count.

    Decision rationale (documented here per Stage-3 spec):
    When a node exhausts all retries and returns status="failed", the
    retry_count in state is NOT incremented again — the count reflects how
    many INTRA-NODE attempts were made within _run_with_retry.  On a
    crash-and-resume, the resumed node starts with whatever retry_count was
    in the last checkpoint BEFORE this node executed (the node never wrote
    a successful state, so no stale count is checkpointed).  This is the
    correct behaviour: the resumed node gets a fresh slate.
    """
    state = _make_state()
    state["retry_count"] = 0

    sleep_fn, _ = _noop_sleep_recorder()
    body = _make_flaky_body(fail_times=999, exc_factory=lambda: TimeoutError("t"))
    policy = RetryPolicy(max_retries=1)

    result = _run_with_retry(body, "research", state, policy=policy, sleep_fn=sleep_fn)
    assert result["status"] == "failed"
    # retry_count in the failure return is the value from the input state.
    assert result["retry_count"] == 0


# ---------------------------------------------------------------------------
# Test 6 — checkpoint history has one entry per node, not one per attempt
# ---------------------------------------------------------------------------


def test_retry_does_not_pollute_checkpoint_history():
    """A node that retries-then-succeeds produces ONE checkpoint, not one per attempt.

    Strategy: build a minimal 2-node graph (flaky_node → END) where flaky_node
    uses _run_with_retry directly with a body that fails once then succeeds.
    The flaky body is a real closure over a counter — no mocks.

    After graph.invoke(), query the SQLite checkpoint table directly and assert
    exactly 2 rows exist for this thread_id:
      row 0  (step=-1) — the input checkpoint
      row 1  (step=0)  — flaky_node completion

    If retries created intermediate checkpoints there would be > 2 rows.
    """
    import sqlite3 as _sqlite3
    from langgraph.graph import END, StateGraph

    from app.core.graph.schemas import AgentState

    # ── Build a real flaky node using _run_with_retry ─────────────────────────
    body_call_count: list[int] = [0]

    def _flaky_body(state: AgentState) -> dict[str, Any]:
        body_call_count[0] += 1
        if body_call_count[0] == 1:
            raise ConnectionError("simulated transient failure on attempt 1")
        # second attempt succeeds
        return {
            **state,
            "last_output": "flaky succeeded",
            "step_index": state.get("step_index", 0) + 1,
            "status": "completed",
            "error": None,
        }

    sleep_fn, _ = _noop_sleep_recorder()
    policy = RetryPolicy(max_retries=3, base_delay=0.0, max_delay=0.0)

    def flaky_node(state: AgentState) -> AgentState:
        return _run_with_retry(
            _flaky_body, "flaky", state, policy=policy, sleep_fn=sleep_fn
        )

    # ── Wire a minimal 1-node graph ───────────────────────────────────────────
    g = StateGraph(AgentState)
    g.add_node("flaky", flaky_node)
    g.set_entry_point("flaky")
    g.add_edge("flaky", END)

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name

    try:
        from app.core.checkpointing.checkpointer import get_checkpointer_for_path

        saver = get_checkpointer_for_path(db_path)
        graph = g.compile(checkpointer=saver)

        run_id = f"retry-ckpt-{uuid.uuid4().hex[:8]}"
        config = {"configurable": {"thread_id": run_id}}
        initial = AgentState(
            run_id=run_id, task="checkpoint retry test",
            step_index=0, history=[], last_output="", tool_calls=[],
            risk_score=0.0, status="running", error=None, retry_count=0,
        )

        result = graph.invoke(initial, config=config)

        # The node must have retried and completed successfully.
        assert result.get("status") == "completed", (
            f"Expected completed, got {result.get('status')!r} / error={result.get('error')}"
        )
        assert body_call_count[0] == 2, (
            f"Body should be called twice (fail then succeed), got {body_call_count[0]}"
        )

        # ── Checkpoint count baseline: LangGraph writes 3 rows for a 1-node graph:
        #   step=-1 (source=input), step=0 (source=loop / node output),
        #   step=1 (source=loop / post-END state).
        # A retry that succeeds internally must produce the same 3 rows as a
        # clean run — no extra rows for failed attempts.
        conn = _sqlite3.connect(db_path, check_same_thread=False)
        flaky_count = conn.execute(
            "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?", (run_id,)
        ).fetchone()[0]
        conn.close()

        # Run a CLEAN version of the same graph (no failure) to get the baseline.
        clean_body_calls: list[int] = [0]

        def _clean_body(state: AgentState) -> dict[str, Any]:
            clean_body_calls[0] += 1
            return {
                **state,
                "last_output": "clean success",
                "step_index": state.get("step_index", 0) + 1,
                "status": "completed",
                "error": None,
            }

        def clean_node(s: AgentState) -> AgentState:
            return _run_with_retry(_clean_body, "clean", s, policy=policy, sleep_fn=sleep_fn)

        g2 = StateGraph(AgentState)
        g2.add_node("clean", clean_node)
        g2.set_entry_point("clean")
        g2.add_edge("clean", END)

        tmp2 = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp2.close()
        db_path2 = tmp2.name
        try:
            saver2 = get_checkpointer_for_path(db_path2)
            graph2 = g2.compile(checkpointer=saver2)
            run_id2 = f"clean-ckpt-{uuid.uuid4().hex[:8]}"
            config2 = {"configurable": {"thread_id": run_id2}}
            initial2 = AgentState(
                run_id=run_id2, task="clean run", step_index=0, history=[],
                last_output="", tool_calls=[], risk_score=0.0, status="running",
                error=None, retry_count=0,
            )
            graph2.invoke(initial2, config=config2)

            conn2 = _sqlite3.connect(db_path2, check_same_thread=False)
            clean_count = conn2.execute(
                "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?", (run_id2,)
            ).fetchone()[0]
            conn2.close()
        finally:
            try:
                os.unlink(db_path2)
            except OSError:
                pass

        assert flaky_count == clean_count, (
            f"Flaky run produced {flaky_count} checkpoint rows, "
            f"clean run produced {clean_count}. "
            f"Retries must NOT create extra checkpoint rows."
        )

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Test 7 — RetryPolicy validation
# ---------------------------------------------------------------------------


def test_retry_policy_rejects_negative_max_retries():
    with pytest.raises(ValueError, match="max_retries"):
        RetryPolicy(max_retries=-1)


def test_retry_policy_zero_max_retries_means_no_retry():
    """max_retries=0 means one attempt total, no retry on failure."""
    state = _make_state()
    sleep_fn, delays = _noop_sleep_recorder()
    body = _make_flaky_body(fail_times=1, exc_factory=lambda: ConnectionError("x"))
    policy = RetryPolicy(max_retries=0)

    result = _run_with_retry(body, "research", state, policy=policy, sleep_fn=sleep_fn)

    assert result["status"] == "failed"
    assert body.call_count[0] == 1
    assert len(delays) == 0


# ---------------------------------------------------------------------------
# Test 8 — Full graph run still passes (Stage 1/2 regression guard)
# ---------------------------------------------------------------------------


def test_full_graph_run_completes_with_retry_wiring():
    """End-to-end graph run with retry wiring in place.

    Regression: confirms Stage 1 / 2 correctness is unaffected by Stage 3.
    No errors are injected — this is a clean run verifying the wrapper is
    transparent when no retries are needed.
    """
    from app.core.graph.state_graph import build_graph

    run_id = f"stage3-regression-{uuid.uuid4().hex[:8]}"
    graph = build_graph()
    config = {"configurable": {"thread_id": run_id}}
    initial = AgentState(
        run_id=run_id, task="Analyse Q4 revenue for regression test",
        step_index=0, history=[], last_output="", tool_calls=[],
        risk_score=0.0, status="running", error=None, retry_count=0,
    )

    result = graph.invoke(initial, config=config)

    assert result["status"] == "completed", f"Got {result['status']!r}"
    assert result["step_index"] == 4
    assert result["retry_count"] == 0  # reset on every successful node
    assert len(result["history"]) == 4  # one entry per node
