"""Centralized, env-driven settings."""
from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    env: str = "development"
    log_level: str = "INFO"

    database_url: str = "sqlite:///./agentflow.db"
    redis_url: str = "redis://localhost:6379/0"
    chroma_persist_dir: str = "./chroma_data"

    anthropic_api_key: str = ""

    sandbox_mode: str = "subprocess"  # "docker" | "subprocess"
    sandbox_cpu_limit: float = 0.5
    sandbox_mem_limit: str = "256m"
    sandbox_timeout_seconds: int = 30

    escalation_continue_max: float = 0.35
    escalation_approve_max: float = 0.7

    # ── Production hardening ──────────────────────────────────────────────────
    # API key auth: set API_KEY in env to enable; leave blank for local dev.
    api_key: str = ""

    # CORS: comma-separated list of allowed origins.
    # Default "*" is fine for local dev; set your Vercel domain in production.
    allowed_origins: str = "*"

    # OpenTelemetry: set OTLP_ENDPOINT to export spans to a real backend.
    # e.g. "http://localhost:4317" for a local Jaeger/Tempo instance.
    otlp_endpoint: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def get_allowed_origins(self) -> list[str]:
        """Parse comma-separated allowed_origins into a list."""
        raw = self.allowed_origins.strip()
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
