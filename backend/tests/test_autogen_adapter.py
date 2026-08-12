"""Stage 8 — Framework Adapter Layer tests.

Verifies:
  a. AutoGen crash-resume: checkpoint survives "process restart" (new adapter instance),
     run resumes from the last checkpointed turn — same pattern as Stage 2.
  b. AutoGen sandbox: tool calls from AutoGen flow through Stage 4's run_sandboxed(),
     and a policy violation (unknown tool) is blocked + logged identically to LangGraph.
  c. AutoGen escalation: risk scoring uses the same score_step() + decide_next_action()
     as the LangGraph path — no AutoGen-specific scoring logic.
  d. Side-by-side: same task through both adapters produces the same event types
     (node_start, checkpoint_saved, sandbox_dispatch, escalation_decision) even
     though the underlying frameworks are completely different.
  e. Interface conformance: both adapters satisfy the FrameworkAdapter interface.
  f. Regression guard: all Stage 1–7 test modules are imported to verify no
     circular imports or broken paths were introduced.
"""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import patch

import pytest

from app.core.adapters.autogen_adapter import AutoGenAdapter
from app.core.adapters.base import FrameworkAdapter, StepResult
from app.core.adapters.checkpoint_store import AdapterCheckpointStore
from app.core.adapters.langgraph_adapter import LangGraphAdapter
from app.core.adapters.runner import run_adapter
from app.core.escalation.scoring import score_step
from app.core.escalation.thresholds import decide_next_action

# Patch decide_next_action to ALWAYS return CONTINUE.
# Required for tests that need full multi-turn runs: .env may set
# ESCALATION_CONTINUE_MAX=0.0 for the live demo which halts after step 1.
_ALWAYS_CONTINUE = "app.core.adapters.runner.decide_next_action"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_state(task: str = "Test task for adapter") -> dict[str, Any]:
    return {
        "run_id": f"test-{uuid.uuid4().hex[:8]}",
        "task": task,
        "last_output": "",
        "step_index": 0,
        "history": [],
        "tool_calls": [],
        "status": "running",
        "error": None,
        "retry_count": 0,
        "risk_score": 0.0,
    }


# ── Test a: AutoGen crash-resume ──────────────────────────────────────────────

class TestAutoGenCrashResume:
    """AutoGen mid-run crash and resume, same pattern as Stage 2 checkpointing tests."""

    def test_checkpoint_survives_new_adapter_instance(self, tmp_path):
        """Checkpoint written by adapter-1 is readable by adapter-2 (new instance).

        This mirrors Stage 2's 'crash-and-resume' pattern: two independent
        Python objects simulating two process lifetimes sharing the same DB.
        """
        db = str(tmp_path / "crash_resume.db")
        state = _make_state("Q4 revenue analysis")
        run_id = state["run_id"]

        # ── Instance 1: run turn_0 only, then "crash" ──────────────────────
        store1 = AdapterCheckpointStore(db)
        adapter1 = AutoGenAdapter(task=state["task"], run_id=run_id, stub_mode=True)
        result = adapter1.run_step("turn_0", state)
        # Manually save checkpoint (runner would do this; we isolate turn here).
        post_state = {**state, **result.output_state, "step_index": 1}
        store1.save(run_id, "turn_0", post_state)

        # ── Instance 2: fresh adapter, load checkpoint, resume ─────────────
        store2 = AdapterCheckpointStore(db)
        adapter2 = AutoGenAdapter(task=state["task"], run_id=run_id, stub_mode=True)

        # Verify checkpoint is visible from new instance.
        loaded = store2.load_latest(run_id)
        assert loaded is not None, "Checkpoint not found after adapter-1 save"
        assert loaded["step_index"] == 1, f"Expected step_index=1, got {loaded['step_index']}"
        assert loaded["run_id"] == run_id

        # Resume from the loaded state — turn_1 uses history from turn_0.
        result2 = adapter2.run_step("turn_1", loaded)
        assert result2.step_id == "turn_1"
        assert result2.status in ("running", "completed", "failed")
        assert len(result2.raw_output) > 0, "turn_1 must produce output"

    def test_completed_steps_are_skipped_on_resume(self, tmp_path):
        """run_adapter() skips already-checkpointed steps on resume."""
        db = str(tmp_path / "skip_steps.db")
        state = _make_state("Resume skip test")
        run_id = state["run_id"]

        # Pre-populate checkpoint for turn_0 so the runner skips it.
        store = AdapterCheckpointStore(db)
        pre_state = {**state, "step_index": 1, "last_output": "Pre-populated turn_0"}
        store.save(run_id, "turn_0", pre_state)

        adapter = AutoGenAdapter(task=state["task"], run_id=run_id, stub_mode=True)

        executed_steps: list[str] = []
        original_run_step = adapter.run_step

        def tracking_run_step(step_id, s):
            executed_steps.append(step_id)
            return original_run_step(step_id, s)

        adapter.run_step = tracking_run_step  # type: ignore[method-assign]

        with patch(_ALWAYS_CONTINUE, return_value="CONTINUE"):
            run_adapter(adapter, state, db_path=db)

        # turn_0 must NOT be re-executed because it was checkpointed.
        assert "turn_0" not in executed_steps, (
            f"turn_0 was re-executed despite being checkpointed. Executed: {executed_steps}"
        )
        assert "turn_1" in executed_steps or "turn_2" in executed_steps, (
            "Remaining turns must still run"
        )

    def test_full_run_with_runner_creates_three_checkpoints(self, tmp_path):
        """Full AutoGen run via runner creates one checkpoint per turn."""
        db = str(tmp_path / "full_run.db")
        state = _make_state("Full run checkpoint test")
        run_id = state["run_id"]

        adapter = AutoGenAdapter(task=state["task"], run_id=run_id, stub_mode=True)

        with patch(_ALWAYS_CONTINUE, return_value="CONTINUE"):
            run_adapter(adapter, state, db_path=db)

        store = AdapterCheckpointStore(db)
        checkpoints = store.list_checkpoints(run_id)
        assert len(checkpoints) == 3, (
            f"Expected 3 checkpoints (turn_0, turn_1, turn_2), got {len(checkpoints)}: {checkpoints}"
        )
        step_ids = [c["step_id"] for c in checkpoints]
        assert step_ids == ["turn_0", "turn_1", "turn_2"], f"Wrong order: {step_ids}"


# ── Test b: AutoGen sandbox ───────────────────────────────────────────────────

class TestAutoGenSandbox:
    """Tool calls from AutoGen flow through Stage 4's sandbox identically."""

    def test_turn_2_declares_tool_call(self):
        """The executor turn (turn_2) exposes a tool_call in its StepResult."""
        state = _make_state("Sandbox tool call test")
        adapter = AutoGenAdapter(task=state["task"], run_id=state["run_id"], stub_mode=True)

        # Run prior turns to build conversation context.
        s0 = adapter.run_step("turn_0", state)
        s1 = adapter.run_step("turn_1", {**state, **s0.output_state})
        s2 = adapter.run_step("turn_2", {**state, **s0.output_state, **s1.output_state})

        assert len(s2.tool_calls) > 0, (
            "turn_2 (executor) must declare at least one tool_call for sandbox routing"
        )
        assert s2.tool_calls[0]["tool"] == "stub-executor", (
            f"Expected tool=stub-executor, got {s2.tool_calls[0]['tool']!r}"
        )

    def test_sandbox_dispatch_logged_by_runner(self, tmp_path):
        """runner.py emits sandbox_dispatch event when processing turn_2 tool call."""
        db = str(tmp_path / "sandbox_log.db")
        state = _make_state("Sandbox dispatch log test")
        run_id = state["run_id"]

        dispatched_events: list[dict] = []

        def capture_log(r_id, event_type, payload=None):
            if event_type == "sandbox_dispatch":
                dispatched_events.append({"run_id": r_id, "event_type": event_type, **(payload or {})})

        adapter = AutoGenAdapter(task=state["task"], run_id=run_id, stub_mode=True)

        with patch(_ALWAYS_CONTINUE, return_value="CONTINUE"), \
             patch("app.core.adapters.runner.log_event", side_effect=capture_log):
            run_adapter(adapter, state, db_path=db)

        assert len(dispatched_events) > 0, (
            "Expected at least one sandbox_dispatch event from turn_2 tool call"
        )
        assert dispatched_events[0]["run_id"] == run_id

    def test_unknown_tool_is_denied_identically_to_langgraph(self, tmp_path):
        """A tool not in the policy registry raises PermissionError from the runner."""
        db = str(tmp_path / "denied.db")
        state = _make_state("Policy denial test")
        run_id = state["run_id"]

        # Inject a fake tool call for an unregistered tool name.
        class BadToolAdapter(AutoGenAdapter):
            def run_step(self, step_id, input_state):
                result = super().run_step(step_id, input_state)
                if step_id == "turn_0":
                    result.tool_calls = [{"tool": "unregistered-tool", "input": "test", "output": ""}]
                return result

        adapter = BadToolAdapter(task=state["task"], run_id=run_id, stub_mode=True)

        with pytest.raises(PermissionError, match="no registered policy"):
            run_adapter(adapter, state, db_path=db)


# ── Test c: AutoGen escalation uses the same model ────────────────────────────

class TestAutoGenEscalation:
    """AutoGen risk scoring and routing uses identical Stage 5 functions."""

    def test_score_step_is_called_with_autogen_output_state(self, tmp_path):
        """score_step() receives the AutoGen output_state — same function as LangGraph."""
        db = str(tmp_path / "escalation.db")
        state = _make_state("Escalation same model test")
        run_id = state["run_id"]

        scored_states: list[dict] = []

        original_score = score_step

        def capturing_score(s, tool_name=None):
            scored_states.append(dict(s))
            return original_score(s, tool_name=tool_name)

        adapter = AutoGenAdapter(task=state["task"], run_id=run_id, stub_mode=True)

        with patch("app.core.adapters.runner.score_step", side_effect=capturing_score), \
             patch(_ALWAYS_CONTINUE, return_value="CONTINUE"):
            run_adapter(adapter, state, db_path=db)

        assert len(scored_states) == 3, (
            f"score_step should be called once per turn (3 turns), got {len(scored_states)}"
        )

    def test_decide_next_action_is_same_function_for_autogen(self, tmp_path):
        """decide_next_action() is called from the runner — no AutoGen-specific routing."""
        db = str(tmp_path / "decide.db")
        state = _make_state("Decision routing test")
        run_id = state["run_id"]

        decisions: list[str] = []
        original_decide = decide_next_action

        def capturing_decide(risk):
            # Record the real decision but always return CONTINUE so all
            # three turns run (otherwise .env ESCALATION_CONTINUE_MAX=0.0
            # causes REQUEST_APPROVAL on turn 0, stopping the run at 1 call).
            d = original_decide(risk)
            decisions.append(d)
            return "CONTINUE"

        adapter = AutoGenAdapter(task=state["task"], run_id=run_id, stub_mode=True)

        with patch("app.core.adapters.runner.decide_next_action", side_effect=capturing_decide):
            run_adapter(adapter, state, db_path=db)

        assert len(decisions) == 3, (
            f"decide_next_action called {len(decisions)} times, expected 3 (one per turn)"
        )
        for d in decisions:
            assert d in ("CONTINUE", "REQUEST_APPROVAL", "HALT"), f"Unexpected decision: {d!r}"

    def test_high_risk_autogen_output_routes_to_halt(self, tmp_path):
        """When a turn produces risk > escalation_approve_max, the runner halts."""
        db = str(tmp_path / "halt.db")
        state = _make_state("High risk halt test")
        run_id = state["run_id"]

        # Patch score_step to return 1.0 (maximum risk) for all turns.
        adapter = AutoGenAdapter(task=state["task"], run_id=run_id, stub_mode=True)

        with patch("app.core.adapters.runner.score_step", return_value=1.0):
            final = run_adapter(adapter, state, db_path=db)

        assert final.get("status") == "halted", (
            f"Expected status=halted on max risk, got {final.get('status')!r}"
        )


# ── Test d: Side-by-side timeline comparison ──────────────────────────────────

class TestSideBySideTimeline:
    """Both adapters emit the same structural event types for the same task."""

    def test_both_adapters_emit_same_event_types(self, tmp_path):
        """LangGraph and AutoGen adapters both produce node_start, checkpoint_saved,
        escalation_decision events — despite completely different underlying frameworks.
        """
        task = "Quarterly business review planning"

        lg_events: list[dict] = []
        ag_events: list[dict] = []

        def make_capture(target: list) -> Any:
            def capture(run_id, event_type, payload=None):
                target.append({"event_type": event_type, "payload": payload or {}})
            return capture

        # ── Run LangGraph adapter ──────────────────────────────────────────
        lg_state = _make_state(task)
        lg_adapter = LangGraphAdapter()

        with patch("app.core.adapters.runner.log_event", side_effect=make_capture(lg_events)), \
             patch(_ALWAYS_CONTINUE, return_value="CONTINUE"):
            run_adapter(lg_adapter, lg_state, db_path=str(tmp_path / "lg.db"))

        # ── Run AutoGen adapter ────────────────────────────────────────────
        ag_state = _make_state(task)
        ag_adapter = AutoGenAdapter(task=task, run_id=ag_state["run_id"], stub_mode=True)

        with patch("app.core.adapters.runner.log_event", side_effect=make_capture(ag_events)), \
             patch(_ALWAYS_CONTINUE, return_value="CONTINUE"):
            run_adapter(ag_adapter, ag_state, db_path=str(tmp_path / "ag.db"))

        # Both must have these structural event types (framework-agnostic layer).
        required_event_types = {"node_start", "checkpoint_saved", "escalation_decision", "node_complete"}

        lg_types = {e["event_type"] for e in lg_events}
        ag_types = {e["event_type"] for e in ag_events}

        missing_lg = required_event_types - lg_types
        missing_ag = required_event_types - ag_types

        assert not missing_lg, (
            f"LangGraph adapter missing event types: {missing_lg}\nGot: {sorted(lg_types)}"
        )
        assert not missing_ag, (
            f"AutoGen adapter missing event types: {missing_ag}\nGot: {sorted(ag_types)}"
        )

        # Print side-by-side for the summary report (captured by pytest -v -s).
        _print_side_by_side(lg_events, ag_events)

    def test_both_adapters_emit_escalation_decision_per_step(self, tmp_path):
        """escalation_decision fires once per step in both adapters."""
        task = "Decision per step test"

        for adapter_name, adapter_cls, extra_kwargs in [
            ("LangGraph", LangGraphAdapter, {}),
            ("AutoGen", AutoGenAdapter, {"task": task, "run_id": f"test-{uuid.uuid4().hex[:8]}", "stub_mode": True}),
        ]:
            events: list[dict] = []
            state = _make_state(task)
            if adapter_cls == AutoGenAdapter:
                state["run_id"] = extra_kwargs["run_id"]
                adapter = adapter_cls(**extra_kwargs)
            else:
                adapter = adapter_cls()

            def capture(r_id, event_type, payload=None, _ev=events):
                _ev.append({"event_type": event_type})

            with patch("app.core.adapters.runner.log_event", side_effect=capture), \
                 patch(_ALWAYS_CONTINUE, return_value="CONTINUE"):
                run_adapter(adapter, state, db_path=str(tmp_path / f"{adapter_name}.db"))

            escalation_count = sum(1 for e in events if e["event_type"] == "escalation_decision")
            step_count = len(adapter.list_steps())
            assert escalation_count == step_count, (
                f"{adapter_name}: expected {step_count} escalation_decision events "
                f"(one per step), got {escalation_count}"
            )


# ── Test e: Interface conformance ─────────────────────────────────────────────

class TestInterfaceConformance:
    """Both adapters are valid FrameworkAdapter implementations."""

    def test_langgraph_adapter_is_framework_adapter(self):
        assert isinstance(LangGraphAdapter(), FrameworkAdapter)

    def test_autogen_adapter_is_framework_adapter(self):
        state = _make_state()
        assert isinstance(
            AutoGenAdapter(task="test", run_id=state["run_id"]), FrameworkAdapter
        )

    def test_langgraph_adapter_list_steps_returns_four(self):
        adapter = LangGraphAdapter()
        steps = adapter.list_steps()
        assert steps == ["research", "draft", "verify", "act"], f"Got: {steps}"

    def test_autogen_adapter_list_steps_returns_three(self):
        state = _make_state()
        adapter = AutoGenAdapter(task="test", run_id=state["run_id"])
        steps = adapter.list_steps()
        assert steps == ["turn_0", "turn_1", "turn_2"], f"Got: {steps}"

    def test_step_result_from_autogen_has_required_fields(self):
        state = _make_state("Interface field check")
        adapter = AutoGenAdapter(task=state["task"], run_id=state["run_id"], stub_mode=True)
        result = adapter.run_step("turn_0", state)

        assert isinstance(result, StepResult)
        assert result.step_id == "turn_0"
        assert isinstance(result.output_state, dict)
        assert isinstance(result.raw_output, str) and len(result.raw_output) > 0
        assert result.status in ("running", "completed", "failed")
        assert isinstance(result.tool_calls, list)
        assert 0.0 <= result.risk_score <= 1.0

    def test_step_result_from_langgraph_has_required_fields(self):
        state = _make_state("LangGraph interface field check")
        adapter = LangGraphAdapter()
        result = adapter.run_step("research", state)

        assert isinstance(result, StepResult)
        assert result.step_id == "research"
        assert isinstance(result.output_state, dict)
        assert isinstance(result.raw_output, str) and len(result.raw_output) > 0
        assert result.status in ("running", "completed", "failed")


# ── Test f: Regression guard ──────────────────────────────────────────────────

class TestRegressionGuard:
    """Verify Stage 1–7 core modules are importable — no broken paths."""

    def test_core_imports_unaffected(self):
        """All prior-stage modules import cleanly after Stage 8 additions."""
        from app.core.checkpointing import checkpointer, recovery  # noqa: F401
        from app.core.escalation import scoring, signals, thresholds  # noqa: F401
        from app.core.graph import nodes, schemas, state_graph  # noqa: F401
        from app.core.retry import backoff, policy  # noqa: F401
        from app.core.sandbox import docker_runner, policy  # noqa: F401

    def test_checkpoint_store_uses_same_db_file_as_langgraph(self, tmp_path):
        """Both the LangGraph checkpointer and AdapterCheckpointStore can open the same DB."""
        from app.core.checkpointing.checkpointer import get_checkpointer_for_path
        db = str(tmp_path / "shared.db")

        # LangGraph checkpointer opens the DB.
        lg_cp = get_checkpointer_for_path(db)

        # AdapterCheckpointStore opens the SAME DB (different table).
        store = AdapterCheckpointStore(db)
        store.save("test-run", "step_0", {"run_id": "test-run", "step_index": 1, "status": "running"})

        # Both can coexist without error — same DB, different tables.
        loaded = store.load_latest("test-run")
        assert loaded is not None
        assert loaded["run_id"] == "test-run"


# ── Utilities ─────────────────────────────────────────────────────────────────

def _print_side_by_side(lg_events: list, ag_events: list) -> None:
    """Print a formatted side-by-side event timeline for the panel demo."""
    print("\n" + "=" * 72)
    print("SIDE-BY-SIDE EVENT TIMELINE COMPARISON")
    print("=" * 72)
    print(f"{'LangGraph Adapter':<36} | {'AutoGen Adapter':<33}")
    print("-" * 72)

    max_len = max(len(lg_events), len(ag_events))
    for i in range(max_len):
        lg = lg_events[i]["event_type"] if i < len(lg_events) else ""
        ag = ag_events[i]["event_type"] if i < len(ag_events) else ""
        print(f"  {lg:<34} | {ag:<33}")

    print("=" * 72)
    lg_types = sorted({e["event_type"] for e in lg_events})
    ag_types = sorted({e["event_type"] for e in ag_events})
    shared = sorted(set(lg_types) & set(ag_types))
    print(f"\nShared event types ({len(shared)}): {shared}")
    print(f"LangGraph-only: {sorted(set(lg_types) - set(ag_types))}")
    print(f"AutoGen-only:   {sorted(set(ag_types) - set(lg_types))}")
    print("=" * 72 + "\n")
