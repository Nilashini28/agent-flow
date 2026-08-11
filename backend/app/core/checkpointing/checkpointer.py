"""Checkpoint saver setup.

Start with SQLite for zero-infra local dev; swap to the Postgres saver by
changing DATABASE_URL — no code changes needed elsewhere.

THREAD-SAFETY ANALYSIS (Stage-2 finding)
-----------------------------------------
SQLite's default `check_same_thread=True` raises a ProgrammingError if a
connection object is used from a thread other than the one that created it.
FastAPI runs each request in a different thread (ThreadPoolExecutor), so a
single module-level `sqlite3.connect()` call *without* `check_same_thread=False`
will work fine for the first request but will silently fail or raise on any
subsequent request handled by a different OS thread.

Fix applied: `check_same_thread=False` is passed when opening the connection.
This is safe here because:
  1. SQLite's WAL-mode serialises writes internally.
  2. SqliteSaver wraps every write in its own cursor/transaction, so there is
     no application-level state that is shared across the connection other than
     the connection handle itself.
  3. For production, swap get_checkpointer() to return an
     AsyncPostgresSaver (see STAGE-2 comment below); thread-safety then becomes
     the Postgres driver's concern.

NOTE (API compatibility): langgraph-checkpoint-sqlite ≥ 3.x changed
SqliteSaver.from_conn_string() to a @contextmanager, which requires a `with`
block and closes the connection on exit — unsuitable for a long-lived FastAPI
process.  We open the raw sqlite3.Connection here and keep it alive for the
process lifetime; SqliteSaver accepts a plain Connection in its constructor.
"""
import os
import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

from app.config import get_settings

_settings = get_settings()
_checkpointer: SqliteSaver | None = None

# Default DB path (relative to the backend/ working directory).
# The settings object doesn't expose a dedicated checkpoint DB key yet, so we
# derive a sensible default here.  STAGE-8 (observability) may want to share
# the same DB; revisit when that stage lands.
_DEFAULT_DB_PATH = "agentflow_checkpoints.db"


def get_checkpointer(db_path: str | None = None) -> SqliteSaver:
    """Return the process-wide SqliteSaver instance (lazily initialised).

    Args:
        db_path: Override the default DB file path.  Primarily used by tests
                 that want an isolated in-memory or temp-file database.

    Thread safety: the underlying sqlite3 connection is opened with
    ``check_same_thread=False`` so FastAPI's threaded request handlers can all
    share a single connection without raising ProgrammingError.  See module
    docstring for the full analysis.
    """
    global _checkpointer
    if _checkpointer is None:
        path = db_path or _DEFAULT_DB_PATH

        # check_same_thread=False — required for multi-threaded FastAPI use.
        # See module docstring for the full thread-safety rationale.
        conn = sqlite3.connect(path, check_same_thread=False)

        _checkpointer = SqliteSaver(conn)
        _checkpointer.setup()  # idempotent: creates checkpoint tables if absent
    return _checkpointer


def get_checkpointer_for_path(db_path: str) -> SqliteSaver:
    """Return a *fresh*, independent SqliteSaver for the given file path.

    Unlike get_checkpointer() this never caches — it is intended for tests and
    scripts that need an isolated saver that shares the same on-disk DB as a
    prior run without sharing the same Python object (i.e. simulating a process
    restart).

    STAGE-2 usage: verify_checkpointing.py and test_checkpointing.py use this
    to prove that checkpoint data survives discarding the original graph object.
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver
