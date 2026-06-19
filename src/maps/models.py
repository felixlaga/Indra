"""Read models for an inspectable ERLA research landscape."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


PaperRole = Literal[
    "foundational_candidate",
    "recent",
    "established",
    "undated",
]
EdgeType = Literal[
    "cites",
    "referenced_by",
    "related",
    "same_author",
    "methodologically_related",
]


class ResearchMapNode(BaseModel):
    """One session paper positioned in the research landscape."""

    paper_id: str
    title: str
    year: int | None = None
    venue: str | None = None
    branch_id: str | None = None
    cluster_id: str
    role: PaperRole
    citation_count: int = Field(default=0, ge=0)
    influential_citation_count: int = Field(default=0, ge=0)
    selected: bool = False
    foundational_score: float = Field(default=0, ge=0, le=1)


class ResearchMapEdge(BaseModel):
    """A citation/reference path or explicitly labelled inferred relation."""

    id: str
    source_paper_id: str
    target_paper_id: str
    edge_type: EdgeType
    observed: bool
    score: float | None = Field(default=None, ge=0, le=1)
    provenance: str


class ResearchMapCluster(BaseModel):
    """An explainable group of papers, normally aligned to a session branch."""

    id: str
    label: str
    paper_ids: list[str] = Field(default_factory=list)
    branch_id: str | None = None
    keywords: list[str] = Field(default_factory=list)


class ResearchTimelineBucket(BaseModel):
    """Papers published in one year."""

    year: int
    paper_ids: list[str] = Field(default_factory=list)


class RelatedPaperRecommendation(BaseModel):
    """A session-local related-paper recommendation with an inspectable reason."""

    source_paper_id: str
    target_paper_id: str
    score: float = Field(ge=0, le=1)
    reason: str
    shared_terms: list[str] = Field(default_factory=list)


class BranchMapSynthesis(BaseModel):
    """Branch overview grounded in persisted summaries or claim state."""

    branch_id: str
    label: str
    text: str
    source: Literal["persisted_summary", "validated_claims", "structural_fallback"]
    validation_status: str | None = None
    paper_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)


class FieldOverview(BaseModel):
    """Deterministic overview of the retrieved session landscape."""

    text: str
    paper_count: int = Field(ge=0)
    cluster_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    observed_citation_edge_count: int = Field(ge=0)
    foundational_candidate_count: int = Field(ge=0)
    recent_paper_count: int = Field(ge=0)
    earliest_year: int | None = None
    latest_year: int | None = None
    claim_status_counts: dict[str, int] = Field(default_factory=dict)
    caveats: list[str] = Field(default_factory=list)


class ResearchMap(BaseModel):
    """Complete Phase 6 read model for one research session."""

    session_id: str
    nodes: list[ResearchMapNode] = Field(default_factory=list)
    edges: list[ResearchMapEdge] = Field(default_factory=list)
    clusters: list[ResearchMapCluster] = Field(default_factory=list)
    timeline: list[ResearchTimelineBucket] = Field(default_factory=list)
    recommendations: list[RelatedPaperRecommendation] = Field(default_factory=list)
    branch_syntheses: list[BranchMapSynthesis] = Field(default_factory=list)
    overview: FieldOverview
