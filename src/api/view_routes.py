"""Serve only current cached results; explicitly report queued/failed work."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .repository import ProductRepository, RepositoryError
from .routes import get_repository, handle_repository_error

router = APIRouter()


def research_view(
    repository: ProductRepository, session_id: str, kind: str
) -> JSONResponse:
    row = repository.request_views(session_id)
    if row["status"] == "ready" and row["source_revision"] == row["requested_revision"]:
        return JSONResponse(
            row["result"][kind],
            headers={
                "X-Indra-View-Revision": str(row["source_revision"]),
                "Cache-Control": "no-store",
            },
        )
    failed = row["status"] == "failed"
    return JSONResponse(
        {
            "status": row["status"],
            "detail": row["error"]
            if failed
            else "Preparing this research view in the background. If it stays queued, start the view worker.",
            "revision": row["requested_revision"],
        },
        status_code=503 if failed else 202,
        headers={"Retry-After": "1", "Cache-Control": "no-store"},
    )


@router.post("/sessions/{session_id}/views/retry")
def retry_views(session_id: str, request: Request):
    try:
        row = get_repository(request).request_views(session_id, retry=True)
        return {"status": row["status"]}
    except RepositoryError as exc:
        handle_repository_error(exc)
