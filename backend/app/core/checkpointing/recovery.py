"""Resume-from-last-checkpoint logic.

This is the function you call after a crash/restart: given a run_id (used
as LangGraph's thread_id), it inspects the checkpoint store and re-invokes
the graph from the last persisted node transition, rather than from scratch.

Error model
-----------
Two failure cases are intentionally distinguished:

  RunNotFoundError  — no checkpoint exists at all for this run_id.
                      This means either the run never started or the wrong
                      run_id was supplied.

  RunAlreadyCompletedError — a checkpoint exists but the run has already
                             reached a terminal state (status="completed",
                             "halted", or "failed") and graph.next is empty,
                             meaning there is nothing left to resume.

Callers (API layer, Stage-7) should catch these explicitly so they can
return the right HTTP status code (404 vs. 409) rather than a 500.
"""
from __future__ import annotations

from typing import Any

from app.core.checkpointing.checkpointer import get_checkpointer
from app.core.graph.state_graph import build_graph


# ── Typed exceptions ─────────────────────────────────────────────────────────


class CheckpointError(Exception):
    """Base class for all checkpoint-recovery errors."""


class RunNotFoundError(CheckpointError):
    """Raised when no checkpoint exists for the requested run_id.

    Possible causes:
      - The run was never started (wrong run_id supplied).
      - The checkpoint DB was wiped between invocations.
    """

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        super().__init__(
            f"No checkpoint found for run_id={run_id!r}.  "
            "The run may never have started, or the checkpoint store may have "
            "been reset."
        )


class RunAlreadyCompletedError(CheckpointError):
    """Raised when the run is already in a terminal state with nothing to resume.

    LangGraph signals this by returning an empty `next` tuple from
    StateSnapshot — there are no pending nodes left to execute.
    """

    def __init__(self, run_id: str, status: str) -> None:
        self.run_id = run_id
        self.status = status
        super().__init__(
            f"Run run_id={run_id!r} is already in terminal state "
            f"status={status!r}.  Nothing left to resume."
        )


# ── Public API ────────────────────────────────────────────────────────────────


def resume_run(run_id: str) -> dict[str, Any]:
    """Resume a previously started run from its last persisted checkpoint.

    Args:
        run_id: The run identifier used as LangGraph's thread_id when the
                original run was started.

    Returns:
        The final AgentState dict after the graph finishes executing the
        remaining nodes.

    Raises:
        RunNotFoundError: No checkpoint exists for run_id.
        RunAlreadyCompletedError: The run reached a terminal state; there is
            nothing left to resume.  The caller may want to return the final
            state from get_latest_checkpoint() instead of re-running.
    """
    graph = build_graph()
    config = {"configurable": {"thread_id": run_id}}

    # Inspect the current state *before* invoking to give precise errors.
    snap = graph.get_state(config)

    # An empty values dict means the checkpointer has no record for this thread.
    if not snap.values:
        raise RunNotFoundError(run_id)

    # An empty `next` tuple means the graph has no pending nodes — it already
    # reached END.  Check state status to decide whether to raise or just
    # return the persisted final state.
    if not snap.next:
        status = snap.values.get("status", "unknown")
        raise RunAlreadyCompletedError(run_id, status)

    # Passing None as input tells LangGraph to resume from the last checkpoint
    # for this thread_id instead of starting a new run.
    return graph.invoke(None, config=config)


def get_latest_checkpoint(run_id: str) -> dict[str, Any] | None:
    """Return the most recent persisted state for run_id, or None.

    Unlike resume_run() this is a read-only probe — it never re-executes the
    graph.  Returns None (rather than raising) when no checkpoint exists so
    callers can use it safely as a presence check.

    STAGE-7: the API layer will call this to serve GET /runs/{run_id}/state.
    """
    graph = build_graph()
    config = {"configurable": {"thread_id": run_id}}
    snap = graph.get_state(config)

    if not snap.values:
        return None

    # Return the raw values dict so callers get a plain dict, not a
    # LangGraph-internal StateSnapshot object.
    return dict(snap.values)


def get_checkpoint_history(run_id: str) -> list[dict[str, Any]]:
    """Return ALL checkpoints for run_id in chronological order (oldest first).

    Each entry is a plain dict containing:
      - step (int): the LangGraph superstep counter (−1 = input, 0 = first node)
      - checkpoint_id (str): the unique ID for this checkpoint
      - next (tuple[str, ...]): node(s) scheduled to run after this checkpoint
      - values (dict): the full AgentState snapshot at this point
      - metadata (dict): LangGraph metadata (source, step, parents, ...)

    The list is ordered oldest-first (ascending step) so callers can render a
    timeline without re-sorting.

    Returns an empty list if no checkpoints exist for run_id.

    STAGE-9: the dashboard's checkpoint timeline view will consume this
    endpoint directly via GET /runs/{run_id}/checkpoints.
    """
    # get_checkpointer() is used directly here (rather than build_graph()) so
    # we can call checkpointer.list() without compiling the full graph.
    # This is the correct pattern for read-only history queries.
    checkpointer = get_checkpointer()
    config = {"configurable": {"thread_id": run_id}}

    raw: list[dict[str, Any]] = []
    for tup in checkpointer.list(config):
        raw.append(
            {
                "step": tup.metadata.get("step", -1) if tup.metadata else -1,
                "checkpoint_id": tup.config["configurable"].get("checkpoint_id", ""),
                "next": tup.checkpoint.get("channel_values", {}).get(
                    # LangGraph doesn't expose `next` on the raw checkpoint;
                    # derive it from pending_writes or leave empty.
                    "__next__", ()
                ),
                "values": dict(tup.checkpoint.get("channel_values", {})),
                "metadata": dict(tup.metadata) if tup.metadata else {},
            }
        )

    # checkpointer.list() yields newest-first; reverse for chronological order.
    raw.reverse()
    return raw
