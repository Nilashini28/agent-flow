"""Weighted-sum risk scoring for a given step.

score = sum(weight_i * signal_i), clipped to [0, 1].
Transparent by design: every factor and weight is inspectable, which
matters when judges/interviewers ask "why did it escalate here?"
"""
from app.core.graph.schemas import AgentState
from app.core.escalation.signals import (
    reversibility_signal,
    tool_risk_signal,
    confidence_signal,
    failure_history_signal,
)

WEIGHTS = {
    "reversibility": 0.3,
    "tool_risk": 0.3,
    "confidence": 0.25,  # inverted: low confidence -> high risk
    "failure_history": 0.15,
}


def score_step(state: AgentState, tool_name: str | None = None) -> float:
    signals = {
        "reversibility": reversibility_signal(tool_name),
        "tool_risk": tool_risk_signal(tool_name),
        "confidence": 1.0 - confidence_signal(state),
        "failure_history": failure_history_signal(state.get("last_output", "")),
    }
    score = sum(WEIGHTS[k] * v for k, v in signals.items())
    return round(min(max(score, 0.0), 1.0), 4)
