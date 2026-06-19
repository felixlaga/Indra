"""Read models for Phase 7 research advice and uncertainty analysis."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ContradictionCandidate(BaseModel):
    id: str
    kind: Literal["evidence_contradiction", "opposing_claim_candidate"]
    status: Literal["observed", "candidate"]
    claim_ids: list[str] = Field(default_factory=list)
    paper_ids: list[str] = Field(default_factory=list)
    branch_ids: list[str] = Field(default_factory=list)
    description: str
    rationale: str
    score: float = Field(ge=0, le=1)


class WeakEvidenceItem(BaseModel):
    claim_id: str
    claim_text: str
    claim_status: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    paper_id: str | None = None
    branch_id: str | None = None
    evidence_count: int = Field(default=0, ge=0)
    reason: str
    priority: Literal["high", "medium", "low"]


class ResearchGap(BaseModel):
    id: str
    gap_type: Literal[
        "claim_evidence",
        "branch_grounding",
        "paper_claim_coverage",
        "citation_metadata",
    ]
    title: str
    description: str
    score: float = Field(ge=0, le=1)
    claim_ids: list[str] = Field(default_factory=list)
    paper_ids: list[str] = Field(default_factory=list)
    branch_ids: list[str] = Field(default_factory=list)
    caveat: str


class OpenProblem(BaseModel):
    id: str
    text: str
    source: Literal["limitation_claim", "recommendation_claim", "gap_signal"]
    status: Literal["speculative"] = "speculative"
    score: float = Field(ge=0, le=1)
    claim_ids: list[str] = Field(default_factory=list)
    paper_ids: list[str] = Field(default_factory=list)
    branch_ids: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class AdvisorRecommendation(BaseModel):
    id: str
    priority: Literal["high", "medium", "low"]
    title: str
    action: str
    rationale: str
    claim_ids: list[str] = Field(default_factory=list)
    paper_ids: list[str] = Field(default_factory=list)
    branch_ids: list[str] = Field(default_factory=list)


class HypothesisProposal(BaseModel):
    id: str
    text: str
    status: Literal["speculative"] = "speculative"
    rationale: str
    confidence: float = Field(ge=0, le=1)
    testability: float = Field(ge=0, le=1)
    risk: Literal["low", "medium", "high", "unknown"] = "unknown"
    source_open_problem_id: str
    supporting_claim_ids: list[str] = Field(default_factory=list)
    supporting_paper_ids: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class ResearchAdviceOverview(BaseModel):
    text: str
    contradiction_count: int = Field(ge=0)
    gap_count: int = Field(ge=0)
    weak_evidence_count: int = Field(ge=0)
    open_problem_count: int = Field(ge=0)
    hypothesis_count: int = Field(ge=0)
    caveats: list[str] = Field(default_factory=list)


class ResearchAdvice(BaseModel):
    session_id: str
    contradictions: list[ContradictionCandidate] = Field(default_factory=list)
    weak_evidence: list[WeakEvidenceItem] = Field(default_factory=list)
    gaps: list[ResearchGap] = Field(default_factory=list)
    open_problems: list[OpenProblem] = Field(default_factory=list)
    recommendations: list[AdvisorRecommendation] = Field(default_factory=list)
    hypotheses: list[HypothesisProposal] = Field(default_factory=list)
    overview: ResearchAdviceOverview
