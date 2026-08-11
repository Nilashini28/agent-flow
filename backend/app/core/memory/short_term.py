"""Short-term / working memory: per-run scratchpad.

In-process dict for local dev; swap for Redis in production by changing
the backend, not the call sites.
"""
from app.config import get_settings

_settings = get_settings()
_store: dict[str, dict] = {}


def get_scratchpad(run_id: str) -> dict:
    return _store.setdefault(run_id, {})


def set_value(run_id: str, key: str, value) -> None:
    get_scratchpad(run_id)[key] = value


def clear(run_id: str) -> None:
    _store.pop(run_id, None)
