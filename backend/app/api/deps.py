"""Shared FastAPI dependencies."""
from app.db.session import get_db  # re-exported for convenience

__all__ = ["get_db"]
