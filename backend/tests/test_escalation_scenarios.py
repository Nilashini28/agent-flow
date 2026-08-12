"""Synthetic scenarios validating the escalation model's decisions."""
from app.core.escalation.scoring import score_step
from app.core.escalation.thresholds import decide_next_action

# Production-level escalation thresholds used for assertions in this file.
# These are the values in production config (0.35 / 0.70), NOT the test-patched
# permissive values from conftest.py. We assert against the SCORE directly so
# these tests remain independent of the conftest threshold patch.
_REAL_CONTINUE_MAX = 0.35

SCENARIOS = [
    ({"last_output": "", "step_index": 1}, "web_search", "CONTINUE"),
    ({"last_output": "", "step_index": 1}, "file_write", None),  # risk-dependent; assert score bounds instead
]


def test_low_risk_tool_continues():
    state = {"run_id": "t", "task": "x", "step_index": 1, "history": [],
             "last_output": "", "risk_score": 0.0, "status": "running"}
    score = score_step(state, tool_name="web_search")
    # web_search is low risk — score must be below the real continue threshold.
    assert score <= _REAL_CONTINUE_MAX, (
        f"web_search risk score {score} exceeds production continue_max {_REAL_CONTINUE_MAX}"
    )


def test_high_risk_irreversible_tool_escalates():
    state = {"run_id": "t", "task": "x", "step_index": 1, "history": [],
             "last_output": "", "risk_score": 0.0, "status": "running"}
    score = score_step(state, tool_name="file_write")
    # file_write is irreversible + filesystem access — score must exceed the
    # production continue threshold (i.e. would escalate in production).
    # We assert on the score rather than the decision so the test is
    # independent of the conftest.py threshold patch.
    assert score > _REAL_CONTINUE_MAX, (
        f"file_write risk score {score!r} should exceed production continue_max "
        f"{_REAL_CONTINUE_MAX} — tool is irreversible and should require escalation."
    )
