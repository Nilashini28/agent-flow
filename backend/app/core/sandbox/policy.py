"""Per-tool permission and resource policy definitions.

Every tool the agent can call should be registered with an explicit policy.
No policy = not allowed to run. This is the "granular execution boundary"
the harness enforces.
"""
from dataclasses import dataclass, field


@dataclass
class ToolPolicy:
    tool_name: str
    risk_tier: str  # "low" | "medium" | "high"
    allow_network: bool = False
    allow_filesystem_write: bool = False
    cpu_limit: float = 0.5
    mem_limit: str = "256m"
    timeout_seconds: int = 30
    reversible: bool = True


DEFAULT_POLICIES: dict[str, ToolPolicy] = {
    "web_search": ToolPolicy(
        tool_name="web_search", risk_tier="low", allow_network=True, reversible=True
    ),
    "file_write": ToolPolicy(
        tool_name="file_write", risk_tier="high", allow_filesystem_write=True,
        reversible=False,
    ),
}


def get_policy(tool_name: str) -> ToolPolicy | None:
    return DEFAULT_POLICIES.get(tool_name)
