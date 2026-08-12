"""Risk engine scoring & dynamic factor evaluation API."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.auth import get_api_key
from app.config import get_settings
from app.core.escalation.scoring import score_step
from app.core.escalation.thresholds import decide_next_action

router = APIRouter(dependencies=[Depends(get_api_key)])
_settings = get_settings()


class RiskFactorItem(BaseModel):
    name: str
    value: float
    weight: float
    contribution: float


class RiskEvaluationResponse(BaseModel):
    actionLabel: str
    amount: float | None
    compositeScore: float
    decisionOutcome: str  # "CONTINUE" | "REQUEST_APPROVAL" | "HALT"
    factors: list[RiskFactorItem]


class TestActionRequest(BaseModel):
    tool_name: str = "file_write"
    step_index: int = 1
    has_error: bool = False
    retry_count: int = 0


class ThresholdsUpdateRequest(BaseModel):
    escalation_continue_max: float
    escalation_approve_max: float


@router.get("/config")
def get_risk_config():
    return {
        "escalation_continue_max": _settings.escalation_continue_max,
        "escalation_approve_max": _settings.escalation_approve_max,
        "test_fields": [
            {"name": "step_index", "min": 0, "max": 10, "current": 1, "label": "Step Index"},
            {"name": "retry_count", "min": 0, "max": 5, "current": 0, "label": "Retry Count"},
        ]
    }


@router.post("/evaluate", response_model=RiskEvaluationResponse)
def evaluate_risk(req: TestActionRequest):
    state = {
        "step_index": req.step_index,
        "retry_count": req.retry_count,
        "history": [],
        "last_output": "Simulated error output" if req.has_error else "Simulated output",
        "error": "Error details" if req.has_error else None,
    }
    score = score_step(state, tool_name=req.tool_name)
    decision = decide_next_action(score)

    factors = [
        RiskFactorItem(name="Tool Risk Tier", value=0.6 if req.tool_name == "file_write" else 0.1, weight=0.4, contribution=0.24 if req.tool_name == "file_write" else 0.04),
        RiskFactorItem(name="Execution State / Errors", value=0.8 if req.has_error else 0.0, weight=0.3, contribution=0.24 if req.has_error else 0.0),
        RiskFactorItem(name="Retry Escalation Depth", value=min(1.0, req.retry_count * 0.2), weight=0.3, contribution=min(0.3, req.retry_count * 0.06)),
    ]

    return RiskEvaluationResponse(
        actionLabel=f"Execute {req.tool_name}",
        amount=None,
        compositeScore=round(score, 3),
        decisionOutcome=decision,
        factors=factors,
    )


@router.post("/thresholds")
def update_thresholds(req: ThresholdsUpdateRequest):
    import app.core.escalation.thresholds as thresholds_mod
    _settings.escalation_continue_max = req.escalation_continue_max
    _settings.escalation_approve_max = req.escalation_approve_max
    thresholds_mod._settings = _settings
    return {"status": "ok", "escalation_continue_max": req.escalation_continue_max, "escalation_approve_max": req.escalation_approve_max}
