"""Routes for the Indra product API skeleton."""

from __future__ import annotations

import asyncio
from queue import Empty

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from .event_stream import (
    EVENT_STREAM_MEDIA_TYPE,
    format_sse_comment,
    format_sse_event,
)
from .models import (
    Branch,
    BranchPatch,
    BranchSplitRequest,
    Claim,
    ClaimEvidence,
    ClaimExtractionRequest,
    ClaimValidationRequest,
    ClaimValidationResult,
    Event,
    Job,
    JobCompletionRequest,
    JobFailureRequest,
    JobLeaseRequest,
    Paper,
    Project,
    ProjectCreate,
    ResearchSession,
    RuntimeLoopBinding,
    SessionCreate,
    SessionPaperView,
    SessionSnapshot,
    SessionStatus,
)
from .repository import ConflictError, NotFoundError, ProductRepository, RepositoryError

router = APIRouter()


def get_repository(request: Request) -> ProductRepository:
    """Get the repository attached to the FastAPI app."""

    return request.app.state.repository
