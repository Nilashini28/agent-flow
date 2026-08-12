"""ORM models for structured events and traces.

NOTE: The canonical Event model is now in app.db.models (persistent, with
full observability columns). This module re-exports it for backward compatibility
so any existing import from app.observability.models still works.
"""
from app.db.models import Event  # noqa: F401 — re-export

__all__ = ["Event"]
