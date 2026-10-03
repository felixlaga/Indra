"""Session research-map and research-advice routes."""

from fastapi import APIRouter, Request

from ..maps import ResearchMap
from .view_routes import research_view
from .repository import RepositoryError
from .research_advice_routes import router as research_advice_router
from .routes import get_repository, handle_repository_error

router = APIRouter()
router.include_router(research_advice_router)


@router.get("/sessions/{session_id}/map", response_model=ResearchMap)
def get_research_map(session_id: str, request: Request) -> ResearchMap:
    """Build a research landscape from durable session state."""
    try:
        return research_view(get_repository(request), session_id, "map")
    except RepositoryError as exc:
        handle_repository_error(exc)
        raise
