"""Structured logging for blocked or out-of-policy actions."""
from datetime import datetime, timezone

from app.observability.event_log import log_event

_VIOLATIONS: list[dict] = []  # replace with a DB table in production


def log_violation(tool_name: str, reason: str, run_id: str | None = None) -> None:
    record = {
        "tool_name": tool_name,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _VIOLATIONS.append(record)
    if run_id:
        log_event(run_id, "sandbox_violation", record)


def get_violations() -> list[dict]:
    return list(_VIOLATIONS)
