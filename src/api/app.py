"""FastAPI application factory for the ERLA product API skeleton."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .claim_validation_routes import router as claim_validation_router
from .repository import ProductRepository
from .repository_factory import create_repository
from .routes import router

_DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def _cors_origins() -> list[str]:
    """Return configured browser origins for the web dashboard."""

    configured = os.getenv("ERLA_CORS_ORIGINS", _DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


def create_app(repository: ProductRepository | None = None) -> FastAPI:
    """Create the ERLA product API app."""

    app = FastAPI(
        title="ERLA Product API",
        version="0.1.0",
        description=(
            "Skeleton API boundary for ERLA projects, sessions, branches, "
            "papers, claims, claim evidence, events, and run controls."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Accept"],
    )
    app.state.repository = repository or create_repository()
    app.include_router(router)
    app.include_router(claim_validation_router)
    return app


app = create_app()
