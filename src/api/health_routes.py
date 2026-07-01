"""Operational health routes for Indra deployments."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

router = APIRouter()


@router.get("/livez")
def livez() -> dict[str, str]:
    """Return liveness for container and process supervisors."""

    return {"status": "ok", "service": "indra-api"}


@router.get("/readyz")
def readyz(request: Request) -> dict[str, str]:
    """Return readiness after the configured repository can be reached."""

    repository = request.app.state.repository
    try:
        # A cheap repository read proves that the selected backend is usable.
        repository.list_projects()
    except Exception as exc:  # pragma: no cover - defensive deployment boundary
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Indra repository is not ready: {exc}",
        ) from exc
    return {"status": "ready", "service": "indra-api"}
