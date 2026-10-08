"""Gap, contradiction, and research-advisor API routes."""

from fastapi import APIRouter, Request

from ..analysis import ResearchAdvice
from .view_routes import research_view
from .repository import RepositoryError
from .routes import get_repository, handle_repository_error

router = APIRouter()


@router.get("/sessions/{session_id}/analysis", response_model=ResearchAdvice)
def get_research_advice(session_id: str, request: Request) -> ResearchAdvice:
    """Return inspectable uncertainty signals and research-navigation advice."""
    try:
        return research_view(get_repository(request), session_id, "analysis")
    except RepositoryError as exc:
        handle_repository_error(exc)
        raise
