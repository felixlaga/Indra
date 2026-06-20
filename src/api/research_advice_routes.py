"""Gap, contradiction, and research-advisor API routes."""

from fastapi import APIRouter, Request

from ..analysis import ResearchAdvice, ResearchAdviceBuilder
from ..maps import ResearchMapBuilder
from .repository import RepositoryError
from .routes import get_repository, handle_repository_error

router = APIRouter()
_map_builder = ResearchMapBuilder()
_advice_builder = ResearchAdviceBuilder()


@router.get("/sessions/{session_id}/analysis", response_model=ResearchAdvice)
def get_research_advice(session_id: str, request: Request) -> ResearchAdvice:
    """Return inspectable uncertainty signals and research-navigation advice."""
    try:
        snapshot = get_repository(request).get_session_snapshot(session_id)
        research_map = _map_builder.build(snapshot)
        return _advice_builder.build(snapshot, research_map)
    except RepositoryError as exc:
        handle_repository_error(exc)
        raise
