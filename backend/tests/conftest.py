"""Global pytest configuration for AgentFlow test suite.

Two concerns addressed here:

1. Escalation threshold patch
   The .env sets ESCALATION_CONTINUE_MAX=0.0 for the UI demo, which causes
   every graph run to block on REQUEST_APPROVAL. We patch thresholds._settings
   to permissive values so graph-completion tests can reach status="completed".

2. DB table initialisation
   FastAPI's lifespan() (which calls Base.metadata.create_all) does NOT run
   when tests use TestClient at module scope. We call create_all explicitly in
   a session-scope fixture so Event, Run, and EscalationDecision tables exist
   before any test that writes to the DB.
"""
from __future__ import annotations

import pytest


# ── 1. Permissive escalation thresholds ──────────────────────────────────────

@pytest.fixture(autouse=True, scope="session")
def _permissive_escalation():
    """Patch thresholds._settings to allow graph runs to reach 'completed'."""
    import app.core.escalation.thresholds as thresholds_mod
    from app.config import Settings

    permissive = Settings(
        escalation_continue_max=0.99,
        escalation_approve_max=0.999,
    )
    original = thresholds_mod._settings
    thresholds_mod._settings = permissive
    yield
    thresholds_mod._settings = original


# ── 2. DB table creation ──────────────────────────────────────────────────────

@pytest.fixture(autouse=True, scope="session")
def _create_db_tables():
    """Create all SQLAlchemy ORM tables before any test runs.

    FastAPI's lifespan context manager calls create_all on startup, but
    TestClient (when used at module scope, not as a context manager) does
    not trigger the lifespan. We call create_all directly here so that
    Event, Run, and EscalationDecision tables exist for any test that
    writes to the DB.
    """
    from app.db.session import engine, Base
    from app.db import models  # noqa: F401 — registers all models with Base
    from app.observability import models as obs_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    yield
    # Do NOT drop tables between tests — we want persistence across the session.
