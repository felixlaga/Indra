"""FastAPI application factory for the Indra product API."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .claim_validation_routes import router as claim_validation_router
from .event_notifications import EventNotifications
from .export_routes import router as export_router
from .health_routes import router as health_router
from .research_map_routes import router as research_map_router
from .repository import ProductRepository
from .repository_factory import create_repository
from .routes import router
from .auth import authenticate, authorize_path
from .auth import router as auth_router
from .view_routes import router as view_router

_DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"


def _cors_origins() -> list[str]:
    """Return configured browser origins for the web dashboard."""

    configured = os.getenv("INDRA_CORS_ORIGINS", _DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in configured.split(",") if origin.strip()]


def create_app(repository: ProductRepository | None = None, *, run_memory_views: bool = True) -> FastAPI:
    """Create the Indra product API app."""

    repository = repository or create_repository()
    notifications = EventNotifications(getattr(repository, "_dsn", None))

    @asynccontextmanager
    async def lifespan(app):
        await notifications.start()
        memory_task = None
        if run_memory_views and not notifications.dsn:
            from ..jobs.view_worker import ViewWorker

            async def memory_views():
                worker = ViewWorker(repository)
                while True:
                    await asyncio.to_thread(worker.run_once)
                    await asyncio.sleep(0.2)

            memory_task = asyncio.create_task(memory_views())
        try:
            yield
        finally:
            if memory_task:
                memory_task.cancel()
                with suppress(asyncio.CancelledError):
                    await memory_task
            await notifications.close()
            if hasattr(repository, "close"):
                repository.close()

    app = FastAPI(
        lifespan=lifespan,
        title="Indra Product API",
        version="0.1.0",
        description=(
            "Product API for Indra sessions, evidence, maps, advice, and exports."
        ),
    )
    app.middleware("http")(authenticate)
    # Snapshots and exports are large, repetitive JSON and text; event streams are excluded.
    app.add_middleware(GZipMiddleware, minimum_size=2048)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Accept",
            "Authorization",
            "X-Indra-API-Key",
            "Last-Event-ID",
        ],
        expose_headers=["Content-Disposition", "X-Indra-Validation-Preserved"],
    )
    app.state.repository = repository
    app.state.event_notifications = notifications
    app.include_router(health_router)
    app.include_router(auth_router)
    # Every resource route checks that a signed-in user owns what the path names.
    owned = [Depends(authorize_path)]
    app.include_router(router, dependencies=owned)
    app.include_router(claim_validation_router, dependencies=owned)
    app.include_router(research_map_router, dependencies=owned)
    app.include_router(export_router, dependencies=owned)
    app.include_router(view_router, dependencies=owned)
    return app


app = create_app()
