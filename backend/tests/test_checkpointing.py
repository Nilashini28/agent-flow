"""Stage-2 crash-simulation tests for the AgentFlow checkpointing subsystem.

Core thesis under test
----------------------
A hard process kill mid-run must not lose already-completed work.  When the
process restarts and calls resume_run(), the graph must:
  a. Continue from the last persisted node (step_index > 0, not 0).
  b. Preserve all history entries written before the "crash".
  c. Complete to status="completed" without re-running completed nodes.

How the crash is simulated (important)
---------------------------------------
We deliberately call graph.stream() and break the iterator after N events,
then *discard the graph object entirely*.  A second, independent graph object
(built via _build_graph_with_saver() calling get_checkpointer_for_path() on
the same temp file) is used for the resume.  This exercises the same code
path as a real process restart:

  - graph1 and its SqliteSaver are garbage-collected — no shared Python state.
  - Only the SQLite file on disk carries the checkpoint forward.
  - graph2 opens a brand-new sqlite3.Connection to the same file and reads
    from it as if it were a freshly started process.

Gap-closure note (Stage-2 audit)
---------------------------------
The crash-simulation test previously used graph2.invoke(None) directly
instead of resume_run(), because resume_run() internally calls build_graph()
which uses the process-wide get_checkpointer() singleton (pointing at the
default agentflow_checkpoints.db) rather than the test's temp DB.

Fix: _resume_via_graph2() now replicates resume_run()'s pre-flight checks
(RunNotFoundError / RunAlreadyCompletedError) and then calls graph2.invoke().
This proves the *persistence mechanism* without coupling the test to the
singleton, while a separate test (test_resume_run_public_api) exercises the
public resume_run() contract end-to-end against the default DB.

Concurrency safety analysis
----------------------------
SqliteSaver.cursor() acquires self.lock (a threading.Lock) before every DB
operation.  The SQLite file is opened in WAL journal mode with a 5 000 ms
busy_timeout, so concurrent threads on the same connection are serialised by
the lock at the Python level — no "database is locked" errors are possible
under the single-connection model.  test_concurrent_runs validates this with
10 simultaneous ThreadPoolExecutor workers.

Mocks / patches: none.  All tests work purely through the public API.
"""
import os
import sqlite3
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from app.core.checkpointing.checkpointer import get_checkpointer_for_path
from app.core.checkpointing.recovery import (
    CheckpointError,
    RunAlreadyCompletedError,
    RunNotFoundError,
    get_checkpoint_history,
    get_latest_checkpoint,
    resume_run,
)
from app.core.graph.state_graph import build_graph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_initial_state(run_id: str, task: str = "Stage-2 crash simulation task") -> dict:
    return {
        "run_id": run_id,
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


def _build_graph_with_saver(db_path: str):
    """Build a compiled graph wired to a FRESH, independent SqliteSaver.

    Each call to this function creates a new sqlite3.Connection and a new
    SqliteSaver pointing at db_path.  Two calls with the same db_path share
    no Python objects — only the on-disk file — which is exactly what a
    real process restart looks like.

    Returns (compiled_graph, saver).
    """
    from langgraph.graph import END, StateGraph

    from app.core.escalation.thresholds import decide_next_action
    from app.core.graph.nodes import act_step, draft_step, research_step, verify_step
    from app.core.graph.schemas import AgentState

    # get_checkpointer_for_path() opens a brand-new sqlite3.Connection; it
    # never returns the cached singleton.  Two calls = two independent objects.
    saver = get_checkpointer_for_path(db_path)

    g = StateGraph(AgentState)
    g.add_node("research", research_step)
    g.add_node("draft", draft_step)
    g.add_node("verify", verify_step)
    g.add_node("act", act_step)
    g.set_entry_point("research")
    g.add_edge("research", "draft")
    g.add_edge("draft", "verify")

    def _route(state):
        decision = decide_next_action(state.get("risk_score", 0.0))
        return "act" if decision == "CONTINUE" else END

    g.add_conditional_edges("verify", _route, {"act": "act", END: END})
    g.add_edge("act", END)

    return g.compile(checkpointer=saver), saver


def _resume_via_graph2(graph2, config: dict) -> dict:
    """Mirror resume_run()'s pre-flight logic using graph2 (the fresh instance).

    This replicates the RunNotFoundError / RunAlreadyCompletedError guards from
    recovery.resume_run() so the crash-sim test exercises those same code paths
    without being forced to use the global singleton checkpointer.
    """
    snap = graph2.get_state(config)
    if not snap.values:
        raise RunNotFoundError(config["configurable"]["thread_id"])
    if not snap.next:
        status = snap.values.get("status", "unknown")
        raise RunAlreadyCompletedError(config["configurable"]["thread_id"], status)
    return graph2.invoke(None, config=config)


# ---------------------------------------------------------------------------
# Test 1 — crash simulation: two fully independent checkpointer instances
# ---------------------------------------------------------------------------


def test_resume_continues_from_last_checkpoint():
    """Core crash-simulation test using two fully independent saver instances.

    Independence proof:
      - graph1 is built with get_checkpointer_for_path(db_path) → connection A.
      - graph1 is explicitly deleted (garbage-collected) after 2 nodes.
      - graph2 is built with get_checkpointer_for_path(db_path) → connection B.
      - graph2 knows nothing about graph1 except what is on disk.

    If this test could pass by sharing Python state between graph1 and graph2,
    it would fail when db_path is replaced by ":memory:" — because in-memory
    SQLite databases are not shared across connections.  The test uses a real
    on-disk temp file, so only genuine persistence can make graph2 see
    graph1's data.

    Three guarantees asserted (a, b, c from the Stage-2 spec):
      a. step_index continues from the crash point, not from 0.
      b. history entries from the first 2 nodes are unchanged.
      c. final status == "completed".
    """
    run_id = f"crash-sim-{uuid.uuid4().hex[:8]}"
    thread_id = run_id

    # Temp file: must survive after NamedTemporaryFile closes (delete=False).
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name

    try:
        # ── Phase 1: partial run via graph1 (connection A) ────────────────────
        graph1, saver1 = _build_graph_with_saver(db_path)
        config = {"configurable": {"thread_id": thread_id}}
        initial = _make_initial_state(run_id)

        events_seen = 0
        step_index_after_crash: int = 0

        for event in graph1.stream(initial, config=config):
            events_seen += 1
            for _node_name, node_state in event.items():
                step_index_after_crash = node_state.get("step_index", 0)
            if events_seen >= 2:
                break  # simulate hard kill

        assert events_seen == 2, f"Expected 2 events before break, got {events_seen}"
        assert step_index_after_crash == 2, (
            f"Expected step_index=2 after 2 nodes, got {step_index_after_crash}"
        )

        # ── Discard graph1 entirely — the "crash" ────────────────────────────
        # After del, saver1.conn (connection A) is closed.  No Python object
        # from Phase 1 survives.  Only the bytes written to db_path remain.
        del graph1, saver1

        # ── Phase 2: fresh graph2 (connection B) — simulates new process ──────
        graph2, saver2 = _build_graph_with_saver(db_path)

        # Verify the checkpoint is readable from a completely new connection.
        snap = graph2.get_state(config)
        assert snap.values, (
            "Phase-2 graph (new connection) sees no checkpoint — "
            "data was NOT persisted to disk; test is invalid."
        )
        assert snap.values.get("step_index") == 2, (
            f"Checkpoint step_index should be 2, got {snap.values.get('step_index')}"
        )

        history_before_resume = snap.values.get("history", [])
        assert len(history_before_resume) == 2, (
            f"Expected 2 history entries pre-resume, got {len(history_before_resume)}"
        )
        assert history_before_resume[0]["node"] == "research"
        assert history_before_resume[1]["node"] == "draft"

        # ── Resume via graph2 with full pre-flight checks ─────────────────────
        # _resume_via_graph2() replicates resume_run()'s RunNotFoundError /
        # RunAlreadyCompletedError guards, then calls graph2.invoke(None).
        final_state = _resume_via_graph2(graph2, config)

        # a. step_index must have advanced beyond the crash-point value.
        assert final_state["step_index"] > step_index_after_crash, (
            f"step_index should exceed {step_index_after_crash}, "
            f"got {final_state['step_index']}"
        )

        # b. First 2 history entries must be byte-identical (no redo/mutation).
        final_history = final_state.get("history", [])
        assert len(final_history) >= 2
        assert final_history[0] == history_before_resume[0], (
            "research history entry changed after resume — work was redone"
        )
        assert final_history[1] == history_before_resume[1], (
            "draft history entry changed after resume — work was redone"
        )

        # c. Run must reach completed.
        assert final_state["status"] == "completed", (
            f"Expected status='completed' after resume, got {final_state['status']!r}"
        )

    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Test 2 — RunNotFoundError for an unknown run_id
# ---------------------------------------------------------------------------


def test_resume_raises_run_not_found_for_unknown_id():
    """resume_run() on an ID that was never started must raise RunNotFoundError."""
    fake_id = f"never-started-{uuid.uuid4().hex}"
    with pytest.raises(RunNotFoundError) as exc_info:
        resume_run(fake_id)
    assert fake_id in str(exc_info.value)


# ---------------------------------------------------------------------------
# Test 3 — RunAlreadyCompletedError for a finished run
# ---------------------------------------------------------------------------


def test_resume_raises_already_completed_for_finished_run():
    """resume_run() on an already-completed run must raise RunAlreadyCompletedError."""
    run_id = f"completed-run-{uuid.uuid4().hex[:8]}"
    graph = build_graph()
    config = {"configurable": {"thread_id": run_id}}
    initial = _make_initial_state(run_id)

    result = graph.invoke(initial, config=config)
    assert result["status"] == "completed", "Setup: full run should complete"

    with pytest.raises(RunAlreadyCompletedError) as exc_info:
        resume_run(run_id)
    assert run_id in str(exc_info.value)
    assert exc_info.value.status == "completed"


# ---------------------------------------------------------------------------
# Test 4 — resume_run() public API end-to-end (exercises the singleton)
# ---------------------------------------------------------------------------


def test_resume_run_public_api_on_interrupted_run():
    """resume_run() via the public API correctly resumes a partially-run thread.

    This test uses the global singleton checkpointer (agentflow_checkpoints.db)
    to exercise resume_run() end-to-end — including its RunNotFoundError /
    RunAlreadyCompletedError guards — without touching the temp-DB path.

    The "crash" is simulated by breaking graph.stream() after 2 nodes, then
    discarding the graph object.  resume_run() must pick up from step_index=2
    using only the data persisted to the default DB.
    """
    run_id = f"public-resume-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": run_id}}
    initial = _make_initial_state(run_id)

    # Phase 1: partial run via the singleton graph (same path resume_run() uses)
    graph = build_graph()
    events_seen = 0
    for event in graph.stream(initial, config=config):
        events_seen += 1
        if events_seen >= 2:
            break

    assert events_seen == 2
    del graph  # discard — resume_run() will build a fresh graph internally

    # resume_run() must raise RunNotFoundError for a truly unknown ID.
    ghost = f"ghost-{uuid.uuid4().hex}"
    with pytest.raises(RunNotFoundError):
        resume_run(ghost)

    # resume_run() on the interrupted run must complete it.
    final = resume_run(run_id)
    assert final["status"] == "completed", (
        f"resume_run() should complete the run; got status={final['status']!r}"
    )
    assert final["step_index"] == 4, (
        f"Full run has 4 nodes; expected step_index=4, got {final['step_index']}"
    )
    # After resume, calling again must raise RunAlreadyCompletedError.
    with pytest.raises(RunAlreadyCompletedError) as exc_info:
        resume_run(run_id)
    assert exc_info.value.status == "completed"


# ---------------------------------------------------------------------------
# Test 5 — get_latest_checkpoint returns None for unknown run_id
# ---------------------------------------------------------------------------


def test_get_latest_checkpoint_returns_none_for_unknown():
    """get_latest_checkpoint() must return None, not raise, for an unknown run."""
    result = get_latest_checkpoint(f"nonexistent-{uuid.uuid4().hex}")
    assert result is None


# ---------------------------------------------------------------------------
# Test 6 — get_latest_checkpoint returns state dict for a known run
# ---------------------------------------------------------------------------


def test_get_latest_checkpoint_returns_state_dict():
    run_id = f"ckpt-test-{uuid.uuid4().hex[:8]}"
    graph = build_graph()
    config = {"configurable": {"thread_id": run_id}}
    initial = _make_initial_state(run_id)
    graph.invoke(initial, config=config)

    result = get_latest_checkpoint(run_id)
    assert result is not None
    assert isinstance(result, dict)
    assert result.get("status") == "completed"
    assert result.get("step_index") == 4


# ---------------------------------------------------------------------------
# Test 7 — get_checkpoint_history returns ordered list with multiple entries
# ---------------------------------------------------------------------------


def test_get_checkpoint_history_returns_ordered_entries():
    run_id = f"hist-test-{uuid.uuid4().hex[:8]}"
    graph = build_graph()
    config = {"configurable": {"thread_id": run_id}}
    initial = _make_initial_state(run_id)
    graph.invoke(initial, config=config)

    history = get_checkpoint_history(run_id)
    assert isinstance(history, list)
    assert len(history) >= 5, f"Expected >= 5 checkpoint entries, got {len(history)}"

    steps = [h["step"] for h in history]
    assert steps == sorted(steps), f"History not in ascending step order: {steps}"

    for entry in history:
        assert "step" in entry
        assert "checkpoint_id" in entry
        assert "values" in entry
        assert "metadata" in entry


# ---------------------------------------------------------------------------
# Test 8 — get_checkpoint_history returns empty list for unknown run_id
# ---------------------------------------------------------------------------


def test_get_checkpoint_history_empty_for_unknown():
    result = get_checkpoint_history(f"ghost-run-{uuid.uuid4().hex}")
    assert result == []


# ---------------------------------------------------------------------------
# Test 9 — SQLite rows actually exist in the DB after a run
# ---------------------------------------------------------------------------


def test_sqlite_rows_exist_after_run():
    """Direct DB inspection: prove rows were written, don't just trust the API."""
    run_id = f"db-row-check-{uuid.uuid4().hex[:8]}"
    graph = build_graph()
    config = {"configurable": {"thread_id": run_id}}
    initial = _make_initial_state(run_id)
    graph.invoke(initial, config=config)

    conn = sqlite3.connect("agentflow_checkpoints.db", check_same_thread=False)
    cur = conn.execute(
        "SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?", (run_id,)
    )
    row_count = cur.fetchone()[0]
    conn.close()

    assert row_count >= 5, (
        f"Expected >= 5 checkpoint rows in DB for thread_id={run_id!r}, "
        f"got {row_count}"
    )


# ---------------------------------------------------------------------------
# Test 10 — Concurrency: 10 simultaneous runs must not produce SQLite errors
# ---------------------------------------------------------------------------


def test_concurrent_runs_no_locking_errors():
    """Fire 10 simultaneous graph runs via ThreadPoolExecutor.

    This validates that the single shared SqliteSaver is safe under FastAPI's
    request-per-thread model.

    Why it is safe without an additional threading.Lock
    ----------------------------------------------------
    SqliteSaver.cursor() already acquires self.lock (a threading.Lock) before
    every DB read/write.  This serialises all SQLite operations at the Python
    level.  Additionally, the DB is in WAL journal mode with a 5 000 ms
    busy_timeout, so even if two connections somehow raced, SQLite would retry
    rather than immediately raising "database is locked".

    The test asserts:
      - All 10 workers complete without any exception.
      - Every worker reaches status="completed" and step_index=4.
      - No "database is locked" or ProgrammingError appears in any result.
    """
    WORKERS = 10

    def run_one(worker_index: int) -> dict:
        run_id = f"concurrent-{worker_index}-{uuid.uuid4().hex[:6]}"
        graph = build_graph()  # all workers share the global singleton saver
        config = {"configurable": {"thread_id": run_id}}
        state = _make_initial_state(run_id, task=f"concurrent task {worker_index}")
        return graph.invoke(state, config=config)

    failures: list[str] = []
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(run_one, i): i for i in range(WORKERS)}
        for future in as_completed(futures):
            worker_idx = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                failures.append(f"worker={worker_idx}: {type(exc).__name__}: {exc}")

    # All workers must succeed.
    assert not failures, (
        f"{len(failures)} worker(s) failed with exceptions:\n"
        + "\n".join(failures)
        + "\n\nThis indicates a SQLite thread-safety problem.  "
        "Fix: verify SqliteSaver.cursor() still acquires self.lock, or add "
        "an explicit threading.Lock in get_checkpointer()."
    )

    assert len(results) == WORKERS, (
        f"Expected {WORKERS} results, got {len(results)}"
    )

    for r in results:
        assert r.get("status") == "completed", (
            f"Worker result has status={r.get('status')!r}, expected 'completed'"
        )
        assert r.get("step_index") == 4, (
            f"Worker result has step_index={r.get('step_index')}, expected 4"
        )
