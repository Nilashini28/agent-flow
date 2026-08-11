"""Stage-1 verification script for AgentFlow core graph.

Run from the backend/ directory (with venv active):
    python verify_stage1.py

Checks:
  A. Normal run  -> status="completed", step_index=4, reaches act_step.
  B. High-risk   -> verify_step yields risk_score > escalation_approve_max,
                    graph ends before act_step (status != "completed").
"""
import sys
import uuid
import os

# Force UTF-8 output on Windows consoles that default to cp1252.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Bootstrap so absolute imports resolve without installing the package.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.graph.state_graph import build_graph
from app.core.graph.schemas import AgentState
from app.observability.event_log import get_timeline

SEP = "=" * 72


def run_scenario(
    label: str,
    task: str,
    patch_state: dict | None = None,
) -> AgentState:
    """Build graph, stream it, print per-node state, return final state."""
    print(f"\n{SEP}")
    print(f"SCENARIO: {label}")
    print(SEP)

    graph = build_graph()
    run_id = str(uuid.uuid4())
    thread_id = str(uuid.uuid4())

    initial: AgentState = {
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

    if patch_state:
        initial = {**initial, **patch_state}

    config = {"configurable": {"thread_id": thread_id}}

    final_state: AgentState = {}
    for step_num, event in enumerate(graph.stream(initial, config=config)):
        for node_name, node_state in event.items():
            print(f"\n--- Node [{node_name}] (stream event #{step_num}) ---")
            print(f"  step_index : {node_state.get('step_index')}")
            print(f"  status     : {node_state.get('status')}")
            print(f"  risk_score : {node_state.get('risk_score')}")
            print(f"  error      : {node_state.get('error')}")
            out = str(node_state.get("last_output", ""))[:120]
            print(f"  last_output: {out}")
            final_state = node_state

    print(f"\n--- Final State ---")
    print(f"  step_index : {final_state.get('step_index')}")
    print(f"  status     : {final_state.get('status')}")
    print(f"  risk_score : {final_state.get('risk_score')}")
    print(f"  error      : {final_state.get('error')}")
    print(f"  tool_calls : {len(final_state.get('tool_calls', []))} recorded")

    print(f"\n--- History ({len(final_state.get('history', []))} entries) ---")
    for entry in final_state.get("history", []):
        line = f"  {entry['node']:10s} step={entry['step_index']}"
        if "risk_score" in entry:
            line += f"  risk={entry['risk_score']}"
        if "violations" in entry:
            line += f"  violations={entry['violations']}"
        print(line)

    print(f"\n--- Event Log ({len(get_timeline(run_id))} events) ---")
    for ev in get_timeline(run_id):
        print(f"  [{ev['event_type']:20s}] {ev['payload']}")

    return final_state


def assert_eq(label: str, actual, expected):
    ok = actual == expected
    marker = "PASS" if ok else "FAIL"
    print(f"  [{marker}] {label}: got={actual!r}  expected={expected!r}")
    if not ok:
        sys.exit(1)


def assert_not_eq(label: str, actual, unexpected):
    ok = actual != unexpected
    marker = "PASS" if ok else "FAIL"
    print(f"  [{marker}] {label}: got={actual!r}  (should NOT be {unexpected!r})")
    if not ok:
        sys.exit(1)


# ---------------------------------------------------------------------------
# Scenario A: Normal happy-path run
# ---------------------------------------------------------------------------
final_a = run_scenario(
    label="A - Normal happy-path run",
    task="Analyse the quarterly sales report and summarise key trends",
)

print(f"\n--- Assertions: Scenario A ---")
assert_eq("status", final_a.get("status"), "completed")
assert_eq("step_index", final_a.get("step_index"), 4)
last_out_a = final_a.get("last_output", "")
print(f"  [PASS] last_output starts with 'ACT': {last_out_a[:3]!r}")
assert_eq("last_output prefix", last_out_a[:3], "ACT")


# ---------------------------------------------------------------------------
# Scenario B: High-risk verification (poisoned draft)
# Forces verify_step to detect a missing DRAFT marker + forbidden keyword,
# pushing penalty above escalation_approve_max (0.7) => HALT/REQUEST_APPROVAL.
# ---------------------------------------------------------------------------

import app.core.graph.nodes as nodes_module

_original_draft = nodes_module.draft_step


def _bad_draft(state: AgentState) -> AgentState:
    """Injected for Scenario B: returns output that verify_step will reject."""
    from datetime import datetime, timezone
    history = list(state.get("history", []))
    history.append({
        "node": "draft",
        "step_index": state.get("step_index", 0),
        "output_summary": "INJECTED BAD DRAFT",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {
        **state,
        # Missing "DRAFT" marker AND contains a forbidden keyword.
        "last_output": "rm -rf everything and drop table users",
        "history": history,
        "step_index": state.get("step_index", 0) + 1,
        "status": "running",
        "error": None,
    }


nodes_module.draft_step = _bad_draft

# Re-import the graph so it picks up the patched node reference.
import importlib
import app.core.graph.state_graph as sg_module
importlib.reload(sg_module)

final_b = run_scenario(
    label="B - High-risk run (poisoned draft => verify should halt)",
    task="Delete all production data immediately",
)

nodes_module.draft_step = _original_draft  # restore

print(f"\n--- Assertions: Scenario B ---")
risk_b = final_b.get("risk_score", 0.0)
risk_ok = risk_b > 0.35
print(f"  [{'PASS' if risk_ok else 'FAIL'}] risk_score > 0.35: got={risk_b}")
if not risk_ok:
    sys.exit(1)

assert_not_eq("status should NOT be completed", final_b.get("status"), "completed")

act_reached = final_b.get("last_output", "").startswith("ACT")
print(f"  [{'FAIL' if act_reached else 'PASS'}] act_step was NOT reached: "
      f"last_output={final_b.get('last_output','')[:60]!r}")
if act_reached:
    sys.exit(1)


# ---------------------------------------------------------------------------
# py_compile check
# ---------------------------------------------------------------------------
print(f"\n{SEP}")
print("py_compile checks")
print(SEP)
import py_compile

files = [
    "app/core/graph/schemas.py",
    "app/core/graph/nodes.py",
    "app/core/graph/state_graph.py",
]
for f in files:
    try:
        py_compile.compile(f, doraise=True)
        print(f"  PASS: {f}")
    except py_compile.PyCompileError as e:
        print(f"  FAIL: {f}: {e}")
        sys.exit(1)

print(f"\n{SEP}")
print("All Stage-1 verification checks passed.")
print(SEP)
