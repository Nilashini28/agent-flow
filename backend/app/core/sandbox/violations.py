"""Structured logging for blocked or out-of-policy sandbox actions.

Every policy violation — whether a blocked network call, an out-of-bounds
write attempt, a timeout, or a resource-limit kill — goes through
log_violation() so it appears in the Stage-2 timeline and is independently
queryable via get_violations().

Stage-4 additions
-----------------
- check_network_policy(): validates network access before the subprocess
  or container is started.
- check_write_path_policy(): validates that a requested write path is within
  the tool's allowed_write_dirs; raises PermissionError with a clear message
  that includes the denied path so it's obvious in logs.
- Both functions call log_violation() and log_event() so violations surface
  in the Stage-2 timeline immediately.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.observability.event_log import log_event

_VIOLATIONS: list[dict] = []  # replace with a DB table in production


def log_violation(
    tool_name: str,
    reason: str,
    run_id: str | None = None,
    extra: dict | None = None,
) -> None:
    """Record a sandbox policy violation and optionally attach it to a run timeline."""
    record = {
        "tool_name": tool_name,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **(extra or {}),
    }
    _VIOLATIONS.append(record)
    if run_id:
        log_event(run_id, "sandbox_violation", record)


def check_network_policy(
    tool_name: str,
    allow_network: bool,
    run_id: str | None = None,
) -> None:
    """Raise PermissionError if a network call is attempted on a no-network policy.

    This is called by run_sandboxed() BEFORE starting the subprocess or
    container, so the violation is logged even if the process never starts.
    """
    if not allow_network:
        log_violation(
            tool_name,
            "attempted_network_access_without_permission",
            run_id=run_id,
            extra={"policy_allow_network": False},
        )
        raise PermissionError(
            f"Tool {tool_name!r} is not permitted to access the network. "
            "Set allow_network=True in its ToolPolicy to grant access."
        )


def check_write_path_policy(
    tool_name: str,
    requested_path: str,
    policy,  # ToolPolicy — avoid circular import by not type-hinting here
    run_id: str | None = None,
) -> None:
    """Raise PermissionError if *requested_path* violates the tool's write policy.

    Two failure cases:
    1. allow_filesystem_write=False: the tool has no write permission at all.
    2. allow_filesystem_write=True but path is outside allowed_write_dirs.

    Both are realistic demo violations:
    - Case 1: a read-only tool (stub-retrieval) trying to write a file.
    - Case 2: a write-permitted tool trying to write outside its sandbox dir
              (e.g. writing to /etc/passwd or C:\\Windows\\System32).
    """
    import os

    abs_path = os.path.abspath(requested_path)

    if not policy.allow_filesystem_write:
        log_violation(
            tool_name,
            "filesystem_write_not_permitted",
            run_id=run_id,
            extra={
                "requested_path": abs_path,
                "policy_allow_filesystem_write": False,
            },
        )
        raise PermissionError(
            f"Tool {tool_name!r} does not have filesystem write permission. "
            f"Attempted path: {abs_path!r}. "
            "Set allow_filesystem_write=True in its ToolPolicy to grant access."
        )

    if not policy.is_write_path_allowed(requested_path):
        log_violation(
            tool_name,
            "write_path_outside_allowed_dirs",
            run_id=run_id,
            extra={
                "requested_path": abs_path,
                "allowed_dirs": list(policy.allowed_write_dirs),
            },
        )
        raise PermissionError(
            f"Tool {tool_name!r} attempted to write to {abs_path!r}, "
            f"which is outside its allowed directories: "
            f"{sorted(policy.allowed_write_dirs)}. "
            "Update allowed_write_dirs in its ToolPolicy if this path is intentional."
        )


def get_violations() -> list[dict]:
    """Return a copy of all recorded violations."""
    return list(_VIOLATIONS)
