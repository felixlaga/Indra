"""FastAPI application factory for the ERLA product API skeleton."""

from __future__ import annotations

from fastapi import FastAPI

from .repository import ProductRepository
from .repository_factory import create_repository
from .routes import router


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
    app.state.repository = repository or create_repository()
    app.include_router(router)
    return app


app = create_app()
