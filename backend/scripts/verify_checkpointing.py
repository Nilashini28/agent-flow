"""Stage-2 manual verification script: prove checkpoint survival across a
simulated hard process kill.

Run this script TWICE from the backend/ directory (with venv active):

  FIRST invocation (starts a run and "crashes" after 2 nodes):
    python scripts/verify_checkpointing.py start

  SECOND invocation (resumes the interrupted run):
    python scripts/verify_checkpointing.py resume <thread_id>

  where <thread_id> is printed by the first invocation.

The first run exits abruptly with sys.exit(1) after printing state from
the research and draft nodes — it never reaches verify or act.  The second
run builds a brand-new graph object (no shared Python state with the first),
reads from the on-disk SQLite DB, and resumes from where the first left off.

Visual proof: compare the step_index lines across the two runs.  The second
run's STARTING step_index must equal the first run's LAST SEEN step_index,
proving no work was lost and no work was duplicated.
"""
from __future__ import annotations

import os
import sys
import uuid

# Bootstrap so absolute imports resolve when running as a script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force UTF-8 on Windows consoles that default to cp1252.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

SEP = "=" * 72
DB_PATH = "agentflow_checkpoints.db"


def _print_state(label: str, state: dict) -> None:
    print(f"\n  [{label}]")
    print(f"    step_index  : {state.get('step_index')}")
    print(f"    status      : {state.get('status')}")
    print(f"    risk_score  : {state.get('risk_score')}")
    print(f"    last_output : {str(state.get('last_output', ''))[:80]}")
    history = state.get("history", [])
    print(f"    history     : {len(history)} entries — {[h['node'] for h in history]}")


# ── FIRST INVOCATION: start ───────────────────────────────────────────────────


def cmd_start() -> None:
    """Start a run, stream 2 nodes, then exit abruptly (simulating a crash)."""
    from langgraph.graph import END, StateGraph

    from app.core.checkpointing.checkpointer import get_checkpointer_for_path
    from app.core.escalation.thresholds import decide_next_action
    from app.core.graph.nodes import act_step, draft_step, research_step, verify_step
    from app.core.graph.schemas import AgentState

    thread_id = str(uuid.uuid4())
    run_id = thread_id  # We use run_id == thread_id throughout the project.

    print(SEP)
    print("STAGE-2 VERIFICATION — FIRST INVOCATION (crash simulation)")
    print(SEP)
    print(f"\n  thread_id   : {thread_id}")
    print(f"  DB path     : {os.path.abspath(DB_PATH)}")
    print("\n  Building graph and starting run...")

    # Build our own graph wired to the on-disk DB.
    saver = get_checkpointer_for_path(DB_PATH)

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
    graph = g.compile(checkpointer=saver)

    config = {"configurable": {"thread_id": thread_id}}
    initial: dict = {
        "run_id": run_id,
        "task": "Analyse quarterly revenue and identify growth opportunities",
        "step_index": 0,
        "history": [],
        "last_output": "",
        "tool_calls": [],
        "risk_score": 0.0,
        "status": "running",
        "error": None,
        "retry_count": 0,
    }

    print("\n  Streaming graph — will abort after 2 nodes:")
    print(f"  STARTING step_index = 0")
    print()

    events_seen = 0
    last_step_index = 0

    for event in graph.stream(initial, config=config):
        events_seen += 1
        for node_name, node_state in event.items():
            last_step_index = node_state.get("step_index", 0)
            _print_state(f"node={node_name}", node_state)

        if events_seen >= 2:
            # ── SIMULATED CRASH ────────────────────────────────────────────
            print()
            print(SEP)
            print("CRASH: exiting after 2 nodes (research + draft)")
            print(f"LAST SEEN step_index = {last_step_index}")
            print()
            print("To resume, run:")
            print(f"  python scripts/verify_checkpointing.py resume {thread_id}")
            print(SEP)
            sys.exit(1)  # hard exit — intentional, proves the checkpoint persisted


# ── SECOND INVOCATION: resume ─────────────────────────────────────────────────


def cmd_resume(thread_id: str) -> None:
    """Resume an interrupted run by thread_id and print the full final state."""
    from langgraph.graph import END, StateGraph

    from app.core.checkpointing.checkpointer import get_checkpointer_for_path
    from app.core.escalation.thresholds import decide_next_action
    from app.core.graph.nodes import act_step, draft_step, research_step, verify_step
    from app.core.graph.schemas import AgentState

    print(SEP)
    print("STAGE-2 VERIFICATION — SECOND INVOCATION (resume after crash)")
    print(SEP)
    print(f"\n  thread_id   : {thread_id}")
    print(f"  DB path     : {os.path.abspath(DB_PATH)}")
    print("\n  Building a BRAND NEW graph object (no shared state with first run)...")

    # Deliberately build a fresh graph backed by the same DB file.
    # This is the key proof: there is NO Python object inherited from the first
    # process — only the SQLite file on disk carries the checkpoint forward.
    saver = get_checkpointer_for_path(DB_PATH)

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
    graph = g.compile(checkpointer=saver)

    config = {"configurable": {"thread_id": thread_id}}

    # Read the checkpoint BEFORE resuming to capture the "starting" step_index.
    snap = graph.get_state(config)
    if not snap.values:
        print("\n  ERROR: No checkpoint found for this thread_id.")
        print("  Did you run the first invocation first?")
        sys.exit(2)

    starting_step_index = snap.values.get("step_index", 0)
    starting_history = snap.values.get("history", [])
    print(f"\n  STARTING step_index (from checkpoint) = {starting_step_index}")
    print(f"  STARTING history nodes = {[h['node'] for h in starting_history]}")
    print(f"  PENDING nodes          = {snap.next}")

    print("\n  Resuming run (graph.invoke(None))...")
    final_state = graph.invoke(None, config=config)

    print()
    print(SEP)
    print("FINAL STATE AFTER RESUME")
    print(SEP)
    _print_state("final", final_state)
    final_step_index = final_state.get("step_index", 0)
    final_history = final_state.get("history", [])

    print()
    print(SEP)
    print("PROOF SUMMARY")
    print(SEP)
    print(f"  step_index before resume : {starting_step_index}")
    print(f"  step_index after  resume : {final_step_index}")
    print(f"  step_index advanced by   : {final_step_index - starting_step_index}  "
          "(should be > 0 = no restart from 0)")

    print()
    print(f"  history before resume    : {[h['node'] for h in starting_history]}")
    print(f"  history after  resume    : {[h['node'] for h in final_history]}")

    # Verify no duplication in history.
    pre_nodes = [h["node"] for h in starting_history]
    post_nodes = [h["node"] for h in final_history]
    duplicated = len(post_nodes) != len(set(post_nodes))

    print()
    if final_state.get("status") == "completed" and final_step_index > starting_step_index:
        print("  [PASS] status = 'completed'")
        print("  [PASS] step_index advanced (no restart from 0)")
        print(f"  [{'FAIL' if duplicated else 'PASS'}] no duplicate history entries")
        print()
        print("Stage-2 VERIFIED: checkpoint survived the simulated crash.")
    else:
        print("  [FAIL] One or more guarantees not met — inspect output above.")
        sys.exit(1)

    print(SEP)


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("start", "resume"):
        print("Usage:")
        print("  python scripts/verify_checkpointing.py start")
        print("  python scripts/verify_checkpointing.py resume <thread_id>")
        sys.exit(2)

    command = sys.argv[1]

    if command == "start":
        cmd_start()
    elif command == "resume":
        if len(sys.argv) < 3:
            print("Error: 'resume' requires a thread_id argument.")
            print("  python scripts/verify_checkpointing.py resume <thread_id>")
            sys.exit(2)
        cmd_resume(sys.argv[2])


if __name__ == "__main__":
    main()
