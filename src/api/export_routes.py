"""Phase 8 research-artifact export routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response

from ..exports import ExportCatalog, ExportGenerator
from .repository import RepositoryError
from .routes import get_repository, handle_repository_error

router = APIRouter()
_generator = ExportGenerator()


@router.get("/sessions/{session_id}/exports", response_model=ExportCatalog)
def list_session_exports(session_id: str, request: Request) -> ExportCatalog:
    """Return every downloadable Phase 8 artifact for a session."""
    try:
        get_repository(request).get_session(session_id)
        return _generator.catalog(session_id)
    except RepositoryError as exc:
        handle_repository_error(exc)
        raise


@router.get("/sessions/{session_id}/exports/{format_name}")
def download_session_export(
    session_id: str,
    format_name: str,
    request: Request,
) -> Response:
    """Generate and download one deterministic research artifact."""
    try:
        snapshot = get_repository(request).get_session_snapshot(session_id)
        artifact = _generator.generate(snapshot, format_name)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RepositoryError as exc:
        handle_repository_error(exc)
        raise
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "X-ERLA-Validation-Preserved": "true",
            "Cache-Control": "no-store",
        },
    )
