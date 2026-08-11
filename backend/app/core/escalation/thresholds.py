"""Map a risk score to a control decision."""
from app.config import get_settings

_settings = get_settings()


def decide_next_action(risk_score: float) -> str:
    if risk_score <= _settings.escalation_continue_max:
        return "CONTINUE"
    if risk_score <= _settings.escalation_approve_max:
        return "REQUEST_APPROVAL"
    return "HALT"
