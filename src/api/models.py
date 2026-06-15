"""Pydantic models for the ERLA product API skeleton."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    """Allowed research session statuses."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class BranchStatus(str, Enum):
    """Allowed branch statuses."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    PRUNED = "pruned"
    FAILED = "failed"


class BranchMode(str, Enum):
    """Allowed branch modes."""

    SEARCH_SUMMARIZE = "search_summarize"
    HYPOTHESIS = "hypothesis"
    SYNTHESIS = "synthesis"
    GAP_ANALYSIS = "gap_analysis"


class ClaimType(str, Enum):
    """Allowed claim types."""

    FACTUAL = "factual"
    METHODOLOGICAL = "methodological"
    EMPIRICAL_RESULT = "empirical_result"
    THEORETICAL_RESULT = "theoretical_result"
    DEFINITION = "definition"
    LIMITATION = "limitation"
    ASSUMPTION = "assumption"
    COMPARISON = "comparison"
    HYPOTHESIS = "hypothesis"
    RECOMMENDATION = "recommendation"


class ClaimStatus(str, Enum):
    """Allowed claim statuses."""

    SUPPORTED = "supported"
    WEAKLY_SUPPORTED = "weakly_supported"
    CONTRADICTED = "contradicted"
    NOT_FOUND = "not_found"
    SPECULATIVE = "speculative"
    NEEDS_REVIEW = "needs_review"


class EvidenceRelation(str, Enum):
    """Allowed claim evidence relations."""

    SUPPORTS = "supports"
    WEAKLY_SUPPORTS = "weakly_supports"
    CONTRADICTS = "contradicts"
    MENTIONS = "mentions"
    INSUFFICIENT = "insufficient"


class ProjectCreate(BaseModel):
    """Payload for creating a project."""

    title: str
    description: str | None = None
    field: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


class Project(ProjectCreate):
    """A long-lived research workspace."""

    id: str
    created_at: datetime
    updated_at: datetime


class SessionCreate(BaseModel):
    """Payload for creating a research session."""

    project_id: str | None = None
    initial_query: str
    source_providers: list[str] = Field(default_factory=lambda: ["semantic_scholar"])
    filters: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)


class ResearchSession(SessionCreate):
    """A product-level research session."""

    id: str
    status: SessionStatus = SessionStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class BranchCreate(BaseModel):
    """Payload for creating a branch in the API skeleton."""

    query: str
    label: str | None = None
    rationale: str | None = None
    mode: BranchMode = BranchMode.SEARCH_SUMMARIZE


class BranchPatch(BaseModel):
    """Payload for updating branch metadata or status."""

    query: str | None = None
    label: str | None = None
    rationale: str | None = None
    status: BranchStatus | None = None


class Branch(BranchCreate):
    """A Scout branch exploring part of a research session."""

    id: str
    session_id: str
    parent_branch_id: str | None = None
    status: BranchStatus = BranchStatus.PENDING
    depth: int = 0
    context_tokens_used: int = 0
    max_context_tokens: int | None = None
    created_at: datetime
    updated_at: datetime


class BranchSplitRequest(BaseModel):
    """Payload for splitting a branch into child branches."""

    branches: list[BranchCreate]


class Paper(BaseModel):
    """Normalized paper metadata exposed by the product API."""

    id: str
    session_id: str
    branch_id: str | None = None
    paper_id: str
    title: str
    abstract: str | None = None
    year: int | None = None
    venue: str | None = None
    citation_count: int | None = None
    created_at: datetime


class ClaimExtractionRequest(BaseModel):
    """Payload for extracting claims from summary or synthesis text."""

    source_text: str = Field(min_length=1)
    branch_id: str | None = None
    paper_id: str | None = None
    summary_id: str | None = None
    created_by: str = "deterministic_claim_extractor"
    max_claims: int = Field(default=20, ge=1, le=100)


class Claim(BaseModel):
    """Atomic claim extracted from generated research text."""

    id: str
    session_id: str
    branch_id: str | None = None
    paper_id: str | None = None
    summary_id: str | None = None
    claim_text: str
    claim_type: ClaimType
    status: ClaimStatus = ClaimStatus.NEEDS_REVIEW
    confidence: float | None = Field(default=None, ge=0, le=1)
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class ClaimEvidenceCreate(BaseModel):
    """Evidence supplied for claim validation."""

    evidence_text: str = Field(min_length=1)
    relation: EvidenceRelation
    paper_id: str | None = None
    chunk_id: str | None = None
    score: float | None = Field(default=None, ge=0, le=1)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    section_title: str | None = None


class ClaimValidationRequest(BaseModel):
    """Payload for validating a claim against supplied evidence."""

    evidence: list[ClaimEvidenceCreate] = Field(default_factory=list)
    validator_type: str = "deterministic_claim_verifier"
    notes: str | None = None


class ClaimEvidence(BaseModel):
    """Evidence passage attached to a claim."""

    id: str
    claim_id: str
    session_id: str
    paper_id: str | None = None
    chunk_id: str | None = None
    evidence_text: str
    relation: EvidenceRelation
    score: float | None = Field(default=None, ge=0, le=1)
    page_start: int | None = None
    page_end: int | None = None
    section_title: str | None = None
    created_at: datetime


class ClaimValidationResult(BaseModel):
    """Result of validating a claim and storing its evidence."""

    claim: Claim
    evidence: list[ClaimEvidence] = Field(default_factory=list)


class Event(BaseModel):
    """Realtime and historical event log entry."""

    id: str
    session_id: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    branch_id: str | None = None
    paper_id: str | None = None
    severity: str = "info"
    created_at: datetime


class RuntimeLoopBinding(BaseModel):
    """Binding between a product session and runtime research-loop state."""

    session_id: str
    loop_id: str
    loop_number: int
    root_branch_id: str
    created_at: datetime
    updated_at: datetime


class SessionSnapshot(BaseModel):
    """A reconstructable session view for dashboard clients."""

    session: ResearchSession
    runtime_loop: RuntimeLoopBinding | None = None
    branches: list[Branch] = Field(default_factory=list)
    papers: list[Paper] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    claim_evidence: list[ClaimEvidence] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
