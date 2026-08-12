"""Consistent error response handlers for FastAPI.

All API errors are returned as:
  { "error": "<error_code>", "message": "<human readable>", "detail": <optional> }

This prevents raw stack traces from leaking to the frontend.
"""
from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Returns 422 with a clean structured body for Pydantic/body validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "message": "Request body failed validation.",
            "detail": exc.errors(),
        },
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Returns a clean JSON body for all HTTP exceptions (404, 401, etc.)."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all 500 handler — never exposes internal tracebacks."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred. Check server logs.",
        },
    )
