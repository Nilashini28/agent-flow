"""AgentFlow FastAPI entrypoint — production-hardened."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.api.routes import (
    runs, checkpoints, escalations, traces, tools,
    system, agents, sandbox, risk, evaluation
)
from app.api.error_handlers import (
    validation_exception_handler,
    http_exception_handler,
    generic_exception_handler,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create all DB tables on startup (idempotent — safe to call on each restart)."""
    from app.db.session import engine
    from app.db import models  # noqa: F401 — ensures models are registered with Base
    from app.db.session import Base

    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="AgentFlow",
    description="Reliability control plane for autonomous agents",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# In dev: allowed_origins = "*" (default)
# In prod: set ALLOWED_ORIGINS=https://your-app.vercel.app in .env
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Error handlers ────────────────────────────────────────────────────────────
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(runs.router,         prefix="/runs",        tags=["runs"])
app.include_router(checkpoints.router,  prefix="/runs",        tags=["checkpoints"])
app.include_router(escalations.router,  prefix="/runs",        tags=["escalations"])
app.include_router(traces.router,       prefix="/runs",        tags=["traces"])
app.include_router(tools.router,        prefix="/tools",       tags=["tools"])
app.include_router(system.router,       prefix="/system",      tags=["system"])
app.include_router(agents.router,       prefix="/agents",      tags=["agents"])
app.include_router(sandbox.router,      prefix="/sandbox",     tags=["sandbox"])
app.include_router(risk.router,         prefix="/risk",        tags=["risk"])
app.include_router(evaluation.router,   prefix="/evaluation",  tags=["evaluation"])


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.env}
