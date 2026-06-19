"""Session research-map routes."""

from fastapi import APIRouter, Request

from ..maps import ResearchMap, ResearchMapBuilder
from .repository import RepositoryError
from .routes import get_repository, handle_repository_error

router = APIRouter()
_builder = ResearchMapBuilder()


@router.get("/sessions/{session_id}/map", response_model=ResearchMap)
def get_research_map(session_id: str, request: Request) -> ResearchMap:
    """Build a research landscape from durable session state."""
    try:
        snapshot = get_repository(request).get_session_snapshot(session_id)
        return _builder.build(snapshot)
    except RepositoryError as exc:
        handle_repository_error(exc)
        raise
