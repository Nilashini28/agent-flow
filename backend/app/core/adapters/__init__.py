"""Framework adapter layer for AgentFlow.

Exports the public adapter interface and both built-in implementations.
"""
from app.core.adapters.base import FrameworkAdapter, StepResult

__all__ = ["FrameworkAdapter", "StepResult"]
