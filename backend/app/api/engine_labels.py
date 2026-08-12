"""Engine label translation layer — API boundary only.

CRITICAL: This is the ONLY place where internal adapter identifiers are
translated to external-facing labels. Every route that returns run metadata
MUST call translate_engine() before serialising.

Internal → External:
  "langgraph" → "execution-engine-a"
  "autogen"   → "execution-engine-b"
"""
from __future__ import annotations

INTERNAL_TO_EXTERNAL: dict[str, str] = {
    "langgraph": "execution-engine-a",
    "autogen":   "execution-engine-b",
}

EXTERNAL_DESCRIPTION: dict[str, str] = {
    "execution-engine-a": "Graph Execution Engine",
    "execution-engine-b": "Multi-Agent Conversation Engine",
    "unknown":            "Unknown Engine",
}

_FALLBACK = "execution-engine-a"


def translate_engine(internal_name: str | None) -> str:
    """Convert internal adapter name → external API label. Never leaks internals."""
    if not internal_name:
        return _FALLBACK
    return INTERNAL_TO_EXTERNAL.get(internal_name.lower(), _FALLBACK)


def describe_engine(external_label: str | None) -> str:
    """Human-readable description for an external label."""
    return EXTERNAL_DESCRIPTION.get(external_label or "", "Unknown Engine")


def all_external_labels() -> list[str]:
    return list(INTERNAL_TO_EXTERNAL.values())
