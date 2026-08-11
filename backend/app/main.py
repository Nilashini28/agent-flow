"""AgentFlow FastAPI entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.api.routes import runs, checkpoints, escalations, traces

settings = get_settings()

app = FastAPI(
    title="AgentFlow",
    description="Reliability control plane for autonomous agents",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before real production use
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router, prefix="/runs", tags=["runs"])
app.include_router(checkpoints.router, prefix="/runs", tags=["checkpoints"])
app.include_router(escalations.router, prefix="/runs", tags=["escalations"])
app.include_router(traces.router, prefix="/runs", tags=["traces"])


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.env}
