"""Centralized, env-driven settings."""
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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
