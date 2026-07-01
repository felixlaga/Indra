"""Optional API-key protection for the Indra product API.

Indra is usually run as a personal research service.  When INDRA_API_KEY is set,
all non-public API routes require either:

- X-Indra-API-Key: <key>
- Authorization: Bearer <key>
- api_key=<key> query parameter, used only for browser EventSource/download URLs.

When INDRA_API_KEY is unset, authentication is disabled for local development.
"""

from __future__ import annotations

import hmac
import os

from fastapi import Request, status
from fastapi.responses import JSONResponse, Response

API_KEY_ENV = "INDRA_API_KEY"
_PUBLIC_PREFIXES = (
    "/health",
    "/livez",
    "/readyz",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def _expected_api_key() -> str | None:
    configured = os.getenv(API_KEY_ENV, "").strip()
    return configured or None


def _provided_api_key(request: Request) -> str | None:
    header_key = request.headers.get("x-indra-api-key")
    if header_key:
        return header_key.strip()

    auth = request.headers.get("authorization", "").strip()
    scheme, _, token = auth.partition(" ")
    if scheme.lower() == "bearer" and token:
        return token.strip()

    query_key = request.query_params.get("api_key")
    if query_key:
        return query_key.strip()

    return None


def _is_public_request(request: Request) -> bool:
    if request.method.upper() == "OPTIONS":
        return True
    return any(request.url.path.startswith(prefix) for prefix in _PUBLIC_PREFIXES)


async def require_api_key(request: Request, call_next) -> Response:
    """FastAPI middleware that enforces INDRA_API_KEY when configured."""

    expected = _expected_api_key()
    if expected is None or _is_public_request(request):
        return await call_next(request)

    provided = _provided_api_key(request)
    if provided and hmac.compare_digest(provided, expected):
        return await call_next(request)

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "A valid Indra API key is required."},
        headers={"WWW-Authenticate": "Bearer"},
    )
