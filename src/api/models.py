"""Pydantic models for the ERLA product API skeleton."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from ..domain.enums import (
    BranchMode,
    BranchStatus,
    ClaimStatus,
    ClaimType,
    EventSeverity,
    EvidenceRelation,
    EvidenceSourceType,
    JobStatus,
    JobType,
    PaperDiscoveryMethod,
    SessionStatus,
    SummaryType,
    SummaryValidationStatus,
)


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
    failure_reason: str | None = None
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
    prune_reason: str | None = None
    failure_reason: str | None = None


class Branch(BranchCreate):
    """A Scout branch exploring part of a research session."""

    id: str
    session_id: str
    parent_branch_id: str | None = None
    status: BranchStatus = BranchStatus.PENDING
    prune_reason: str | None = None
    failure_reason: str | None = None
    depth: int = 0
    context_tokens_used: int = 0
    max_context_tokens: int | None = None
    created_at: datetime
    updated_at: datetime


class BranchSplitRequest(BaseModel):
    """Payload for splitting a branch into child branches."""

    branches: list[BranchCreate]


class Paper(BaseModel):
    """Global paper metadata exposed by the product API."""

    id: str
    canonical_key: str
    semantic_scholar_id: str | None = None
    arxiv_id: str | None = None
    doi: str | None = None
    openalex_id: str | None = None
    title: str
    abstract: str | None = None
    authors: list[dict[str, Any]] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    citation_count: int | None = None
    reference_count: int | None = None
    influential_citation_count: int | None = None
    url: str | None = None
    pdf_url: str | None = None
    open_access_pdf_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class SessionPaper(BaseModel):
    """Contextual discovery record connecting a paper to a session/branch."""

    id: str
    session_id: str
    paper_id: str
    branch_id: str | None = None
    discovery_method: PaperDiscoveryMethod | None = None
    selection_reason: str | None = None
    selected: bool = False
    iteration_number: int | None = None
    created_at: datetime


class SessionPaperView(BaseModel):
    """Session paper read model with global metadata plus discovery context."""

    id: str
    session_id: str
    branch_id: str | None = None
    paper_id: str
    discovery_method: PaperDiscoveryMethod | None = None
    selection_reason: str | None = None
    selected: bool = False
    iteration_number: int | None = None
    paper: Paper
    created_at: datetime


class Summary(BaseModel):
    """Generated summary with explicit validation status."""

    id: str
    session_id: str
    summary_type: SummaryType
    text: str
    branch_id: str | None = None
    paper_id: str | None = None
    groundedness_score: float | None = Field(default=None, ge=0, le=1)
    validation_status: SummaryValidationStatus = (
        SummaryValidationStatus.NOT_VALIDATED
    )
    validation_details: dict[str, Any] = Field(default_factory=dict)
    generation_provenance: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


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
    source_type: EvidenceSourceType = EvidenceSourceType.MANUAL
    paper_id: str | None = None
    chunk_id: str | None = None
    metadata_field: str | None = None
    upload_id: str | None = None
    document_id: str | None = None
    external_uri: str | None = None
    source_id: str | None = None
    reviewer_id: str | None = "api_user"
    score: float | None = Field(default=None, ge=0, le=1)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    section_title: str | None = None

    @model_validator(mode="after")
    def validate_source_locator(self) -> "ClaimEvidenceCreate":
        """Validate source-specific evidence locator requirements."""

        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_end < self.page_start
        ):
            raise ValueError("page_end cannot precede page_start")

        if self.source_type == EvidenceSourceType.PAPER_CHUNK:
            if not self.paper_id or not self.chunk_id:
                raise ValueError("paper_chunk evidence requires paper_id and chunk_id")
        elif self.source_type == EvidenceSourceType.PAPER_ABSTRACT:
            if not self.paper_id:
                raise ValueError("paper_abstract evidence requires paper_id")
        elif self.source_type == EvidenceSourceType.PAPER_METADATA:
            if not self.paper_id or not self.metadata_field:
                raise ValueError("paper_metadata evidence requires paper_id and metadata_field")
        elif self.source_type == EvidenceSourceType.USER_UPLOAD:
            if not (self.upload_id or self.document_id):
                raise ValueError("user_upload evidence requires upload_id or document_id")
        elif self.source_type == EvidenceSourceType.EXTERNAL_SOURCE:
            if not (self.external_uri or self.source_id):
                raise ValueError("external_source evidence requires external_uri or source_id")
        elif self.source_type == EvidenceSourceType.MANUAL:
            if not self.reviewer_id:
                raise ValueError("manual evidence requires reviewer_id")
        return self


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
    source_type: EvidenceSourceType
    paper_id: str | None = None
    chunk_id: str | None = None
    metadata_field: str | None = None
    upload_id: str | None = None
    document_id: str | None = None
    external_uri: str | None = None
    source_id: str | None = None
    reviewer_id: str | None = None
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
    severity: EventSeverity = EventSeverity.INFO
    created_at: datetime


class RuntimeLoopBinding(BaseModel):
    """Binding between a product session and runtime research-loop state."""

    session_id: str
    loop_id: str
    loop_number: int
    root_branch_id: str
    created_at: datetime
    updated_at: datetime


class JobCreate(BaseModel):
    """Durable background job enqueue contract."""

    session_id: str
    branch_id: str | None = None
    job_type: JobType
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    max_attempts: int = Field(default=3, ge=1, le=20)
    timeout_seconds: int = Field(default=1800, ge=1, le=86_400)
    run_at: datetime | None = None


class Job(JobCreate):
    """Durable background job state exposed to API and workers."""

    id: str
    status: JobStatus = JobStatus.QUEUED
    run_at: datetime
    result: dict[str, Any] = Field(default_factory=dict)
    attempts: int = 0
    locked_by: str | None = None
    locked_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class JobLeaseRequest(BaseModel):
    """Worker request to lease the next runnable job."""

    worker_id: str = Field(min_length=1)
    job_types: list[JobType] = Field(default_factory=list)


class JobCompletionRequest(BaseModel):
    """Worker payload for completing a leased job."""

    result: dict[str, Any] = Field(default_factory=dict)


class JobFailureRequest(BaseModel):
    """Worker payload for failing or retrying a leased job."""

    error: str = Field(min_length=1)
    retryable: bool = True
    retry_delay_seconds: int = Field(default=60, ge=0, le=86_400)


class SessionSnapshot(BaseModel):
    """A reconstructable session view for dashboard clients."""

    session: ResearchSession
    runtime_loop: RuntimeLoopBinding | None = None
    branches: list[Branch] = Field(default_factory=list)
    jobs: list[Job] = Field(default_factory=list)
    papers: list[SessionPaperView] = Field(default_factory=list)
    summaries: list[Summary] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    claim_evidence: list[ClaimEvidence] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
