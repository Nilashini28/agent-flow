"""Synthetic scenarios validating the escalation model's decisions."""
from app.core.escalation.scoring import score_step
from app.core.escalation.thresholds import decide_next_action

SCENARIOS = [
    ({"last_output": "", "step_index": 1}, "web_search", "CONTINUE"),
    ({"last_output": "", "step_index": 1}, "file_write", None),  # risk-dependent; assert score bounds instead
]


def test_low_risk_tool_continues():
    state = {"run_id": "t", "task": "x", "step_index": 1, "history": [],
             "last_output": "", "risk_score": 0.0, "status": "running"}
    score = score_step(state, tool_name="web_search")
    assert decide_next_action(score) == "CONTINUE"


def test_high_risk_irreversible_tool_escalates():
    state = {"run_id": "t", "task": "x", "step_index": 1, "history": [],
             "last_output": "", "risk_score": 0.0, "status": "running"}
    score = score_step(state, tool_name="file_write")
    decision = decide_next_action(score)
    assert decision in {"REQUEST_APPROVAL", "HALT"}
