"""Canonical session, branch, event, hypothesis, and artifact models."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from .base import DomainModel
from .enums import (
    AgentDecisionType,
    BranchMode,
    BranchStatus,
    EventSeverity,
    ExportStatus,
    ExportType,
    HypothesisStatus,
    SessionStatus,
)
from .provenance import GenerationProvenance, utc_now


class Project(DomainModel):
    id: UUID
    title: str
    description: str | None = None
    field: str | None = None
    settings: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ResearchSession(DomainModel):
    id: UUID
    initial_query: str
    project_id: UUID | None = None
    status: SessionStatus = SessionStatus.PENDING
    source_providers: list[str] = Field(default_factory=list)
    filters: dict = Field(default_factory=dict)
    parameters: dict = Field(default_factory=dict)
    failure_reason: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Branch(DomainModel):
    id: UUID
    session_id: UUID
    query: str
    mode: BranchMode = BranchMode.SEARCH_SUMMARIZE
    status: BranchStatus = BranchStatus.PENDING
    parent_branch_id: UUID | None = None
    label: str | None = None
    rationale: str | None = None
    prune_reason: str | None = None
    failure_reason: str | None = None
    depth: int = Field(default=0, ge=0)
    context_tokens_used: int = Field(default=0, ge=0)
    max_context_tokens: int | None = Field(default=None, gt=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Hypothesis(DomainModel):
    id: UUID
    session_id: UUID
    text: str
    branch_id: UUID | None = None
    rationale: str | None = None
    supporting_paper_ids: list[UUID] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    testability: float | None = Field(default=None, ge=0, le=1)
    novelty_estimate: float | None = Field(default=None, ge=0, le=1)
    risk_level: str | None = None
    status: HypothesisStatus | None = HypothesisStatus.DRAFT
    generation_provenance: GenerationProvenance | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AgentDecision(DomainModel):
    id: UUID
    session_id: UUID
    decision_type: AgentDecisionType
    decision: str
    branch_id: UUID | None = None
    input_summary: str | None = None
    rationale: str | None = None
    alternatives: list[dict] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    generation_provenance: GenerationProvenance | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Event(DomainModel):
    id: UUID
    session_id: UUID
    event_type: str
    payload: dict = Field(default_factory=dict)
    severity: EventSeverity = EventSeverity.INFO
    branch_id: UUID | None = None
    paper_id: UUID | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Export(DomainModel):
    id: UUID
    session_id: UUID
    export_type: ExportType
    status: ExportStatus = ExportStatus.PENDING
    storage_uri: str | None = None
    content: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
