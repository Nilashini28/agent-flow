"""Feature extraction for the escalation scoring model.

Each function returns a 0-1 normalized signal. Keep these simple and
explainable — a transparent scoring function is easier to defend in a demo
or interview than a black-box classifier.
"""
from app.core.graph.schemas import AgentState
from app.core.sandbox.policy import get_policy


def reversibility_signal(tool_name: str | None) -> float:
    if not tool_name:
        return 0.0
    policy = get_policy(tool_name)
    if policy is None:
        return 1.0  # unknown tool = treat as maximally risky
    return 0.0 if policy.reversible else 1.0


def tool_risk_signal(tool_name: str | None) -> float:
    if not tool_name:
        return 0.0
    policy = get_policy(tool_name)
    if policy is None:
        return 1.0
    return {"low": 0.1, "medium": 0.5, "high": 0.9}.get(policy.risk_tier, 0.5)


def confidence_signal(state: AgentState) -> float:
    # TODO: wire in real model confidence / retrieval similarity score.
    # Placeholder: assume mid-confidence until instrumented.
    return 0.5


def failure_history_signal(node_name: str) -> float:
    # TODO: query historical failure rate for this node from the event log.
    return 0.1
