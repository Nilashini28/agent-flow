"""API key / bearer-token authentication dependency.

Behaviour:
  - If API_KEY is not set in env → auth is DISABLED (local dev mode).
  - If API_KEY is set → every request must carry header:
      X-Api-Key: <key>
    A missing or wrong key returns HTTP 401.

Usage:
    router = APIRouter(dependencies=[Depends(get_api_key)])
    # or per-route:
    @router.get("/...", dependencies=[Depends(get_api_key)])
"""
from __future__ import annotations

from fastapi import Header, HTTPException, status
from typing import Optional

from app.config import get_settings

_settings = get_settings()


async def get_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """FastAPI dependency that enforces API-key auth when configured."""
    required_key = _settings.api_key
    if not required_key:
        # Auth disabled — local dev mode.
        return
    if x_api_key != required_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "invalid_api_key", "message": "Missing or invalid X-Api-Key header."},
        )
