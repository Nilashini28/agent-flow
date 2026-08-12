"""Per-tool permission and resource policy definitions.

Every tool the agent can call must be registered with an explicit ToolPolicy.
No policy = not allowed to run.  This is the "granular execution boundary"
the harness enforces.

Stage-4 additions
-----------------
- Registered stub-retrieval and stub-executor (the two tools act_step uses).
- Added allowed_write_dirs: set of absolute path prefixes the tool may write
  to.  An empty set means write-anywhere is permitted (only relevant when
  allow_filesystem_write=True).
- mem_limit_bytes: integer byte limit used by the subprocess runner (the
  existing mem_limit string is kept for Docker, which accepts e.g. "256m").
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class ToolPolicy:
    tool_name: str
    risk_tier: str                  # "low" | "medium" | "high"
    allow_network: bool = False
    allow_filesystem_write: bool = False
    allowed_write_dirs: frozenset[str] = field(default_factory=frozenset)
    cpu_limit: float = 0.5          # fraction of one CPU core
    mem_limit: str = "256m"         # Docker-format string (e.g. "256m", "1g")
    mem_limit_bytes: int = 256 * 1024 * 1024  # 256 MB — used by subprocess runner
    timeout_seconds: int = 30
    reversible: bool = True

    def is_write_path_allowed(self, path: str) -> bool:
        """Return True if *path* is within an allowed write directory.

        An empty allowed_write_dirs set is treated as "write-anywhere is
        allowed" (for policies that already set allow_filesystem_write=True
        and don't further restrict paths).
        """
        if not self.allow_filesystem_write:
            return False
        if not self.allowed_write_dirs:
            return True
        abs_path = os.path.abspath(path)
        return any(abs_path.startswith(d) for d in self.allowed_write_dirs)


# ---------------------------------------------------------------------------
# Registered policies
# ---------------------------------------------------------------------------

# Temporary output directory for tools that need to write files.
# Relative to backend/ CWD; will be created if absent.
_SANDBOX_OUTPUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "sandbox_output")
)

DEFAULT_POLICIES: dict[str, ToolPolicy] = {
    # ── Read-only / network tools ─────────────────────────────────────────────
    "web_search": ToolPolicy(
        tool_name="web_search",
        risk_tier="low",
        allow_network=True,
        reversible=True,
    ),
    # ── Stub tools used by act_step (Stage 1/3 scaffold) ─────────────────────
    "stub-retrieval": ToolPolicy(
        tool_name="stub-retrieval",
        risk_tier="low",
        allow_network=False,
        allow_filesystem_write=False,
        timeout_seconds=10,
        reversible=True,
    ),
    "stub-executor": ToolPolicy(
        tool_name="stub-executor",
        risk_tier="medium",
        allow_network=False,
        allow_filesystem_write=True,
        allowed_write_dirs=frozenset([_SANDBOX_OUTPUT_DIR]),
        timeout_seconds=30,
        reversible=False,   # execution side effects are not trivially undone
    ),
    # ── Filesystem write tool ─────────────────────────────────────────────────
    "file_write": ToolPolicy(
        tool_name="file_write",
        risk_tier="high",
        allow_filesystem_write=True,
        allowed_write_dirs=frozenset([_SANDBOX_OUTPUT_DIR]),
        reversible=False,
    ),
}


def get_policy(tool_name: str) -> ToolPolicy | None:
    """Return the ToolPolicy for *tool_name*, or None if not registered."""
    return DEFAULT_POLICIES.get(tool_name)


def get_policy_or_deny(tool_name: str) -> ToolPolicy:
    """Return the ToolPolicy for *tool_name*, raising PermissionError if absent."""
    policy = DEFAULT_POLICIES.get(tool_name)
    if policy is None:
        raise PermissionError(
            f"Tool {tool_name!r} has no registered policy and cannot be executed. "
            "Register it in sandbox/policy.py before use."
        )
    return policy
