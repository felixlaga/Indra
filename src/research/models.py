"""Typed writes shared by the research worker and repository backends."""

from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..api.models import ClaimType, Paper


def stable_id(*parts: str) -> str:
    return str(uuid5(NAMESPACE_URL, "indra:" + ":".join(parts)))


class ResearchLimits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_papers: int = Field(default=5, ge=1, le=20)
    search_limit: int = Field(default=15, ge=1, le=50)
    max_claims: int = Field(default=5, ge=1, le=10)
    max_model_calls: int = Field(default=30, ge=1, le=100)
    max_source_chars: int = Field(default=24000, ge=1000, le=60000)
    provider_timeout_seconds: float = Field(default=45, ge=1, le=120)
    # Scouts: follow-up branches proposed after a branch's evidence is checked.
    max_depth: int = Field(default=1, ge=0, le=3)
    max_branches: int = Field(default=3, ge=0, le=12)
    branch_papers: int = Field(default=3, ge=1, le=20)
    synthesize: bool = True

    @property
    def scouting(self) -> bool:
        return self.max_depth > 0 and self.max_branches > 0

    def reserved_model_calls(self) -> int:
        """Calls kept back so planning and synthesis survive verification spending."""

        return min(self.max_model_calls // 3, int(self.scouting) + int(self.synthesize))

    def papers_for(self, *, root: bool) -> int:
        return self.max_papers if root else self.branch_papers

    def branch_model_calls(self, *, root: bool) -> int:
        """Share of non-reserved calls by paper count, so the root cannot starve Scouts."""

        papers = self.max_papers + (
            self.max_branches * self.branch_papers if self.scouting else 0
        )
        spendable = self.max_model_calls - self.reserved_model_calls()
        return max(1, spendable * self.papers_for(root=root) // papers)


class PaperChunk(BaseModel):
    id: str
    paper_id: str
    document_id: str
    chunk_index: int
    text: str = Field(min_length=1)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    section_title: str | None = None
    # Stored for semantic retrieval; never sent to API clients.
    embedding: list[float] | None = Field(default=None, exclude=True)


class ClaimDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1500)
    claim_type: ClaimType


class PaperSynthesis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=8000)
    claims: list[ClaimDraft] = Field(max_length=10)


def without_nul(value: str | None) -> str | None:
    """PostgreSQL text cannot hold NUL characters, which some PDFs and APIs contain."""

    return value.replace("\x00", "") if value else value


READ_REASON = "Chosen from the branch's candidate papers."


class PaperResult(BaseModel):
    paper: Paper
    # Why the branch chose to read this paper, such as the model's selection reason.
    selection_reason: str | None = None
    chunks: list[PaperChunk] = Field(default_factory=list)
    source_url: str | None = None
    parse_status: Literal["parsed", "unavailable", "failed"] = "unavailable"
    source_note: str | None = None
    synthesis: PaperSynthesis | None = None
    provenance: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def storable_text(self) -> "PaperResult":
        self.paper.title = without_nul(self.paper.title)
        self.paper.abstract = without_nul(self.paper.abstract)
        for chunk in self.chunks:
            chunk.text = without_nul(chunk.text)
        if self.synthesis:
            self.synthesis.summary = without_nul(self.synthesis.summary)
            for claim in self.synthesis.claims:
                claim.text = without_nul(claim.text)
        return self


class SearchPlan(BaseModel):
    """Keyword queries for a question too long or conversational to search verbatim."""

    model_config = ConfigDict(extra="forbid")
    topic: str = Field(min_length=1, max_length=200)
    queries: list[str] = Field(max_length=5)


class PaperChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate: int
    reason: str = Field(min_length=1, max_length=400)


class PaperSelection(BaseModel):
    """Candidates chosen by number, most useful first."""

    model_config = ConfigDict(extra="forbid")
    assessment: str = Field(min_length=1, max_length=1000)
    selected: list[PaperChoice] = Field(max_length=20)


class EvidenceJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relation: Literal["supports", "contradicts", "insufficient"]
    quote: str
    rationale: str = Field(min_length=1, max_length=1500)


class PassageJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passage: int
    relation: Literal["supports", "contradicts", "insufficient"]
    quote: str
    rationale: str = Field(min_length=1, max_length=1500)


class EvidenceJudgments(BaseModel):
    """One call judges every retrieved passage for a claim."""

    model_config = ConfigDict(extra="forbid")
    judgments: list[PassageJudgment] = Field(max_length=10)


# Model-facing Scout and synthesis schemas refer to claims by short aliases (C1, C2…)
# so IDs cannot be garbled; the worker maps them back and drops unknown aliases.
class FollowUpQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=3, max_length=300)
    label: str = Field(min_length=1, max_length=80)
    rationale: str = Field(min_length=1, max_length=800)
    motivation: Literal[
        "contradiction",
        "missing_evidence",
        "mechanism",
        "method",
        "limitation",
        "adjacent_area",
    ]
    motivating_claims: list[str] = Field(max_length=5)


class ScoutPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assessment: str = Field(min_length=1, max_length=1500)
    follow_ups: list[FollowUpQuestion] = Field(max_length=3)


class HypothesisDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=600)
    rationale: str = Field(min_length=1, max_length=1500)
    supporting_claims: list[str] = Field(max_length=8)
    contradicting_claims: list[str] = Field(max_length=8)
    missing_evidence: list[str] = Field(max_length=5)
    next_steps: list[str] = Field(max_length=5)
    testability: Literal["low", "medium", "high"]
    risk: Literal["low", "medium", "high", "unknown"]


class SessionSynthesis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overview: str = Field(min_length=1, max_length=6000)
    hypotheses: list[HypothesisDraft] = Field(max_length=5)


class ScoutBranchDraft(BaseModel):
    id: str
    query: str
    label: str
    rationale: str
    motivation: str
    motivating_claim_ids: list[str] = Field(default_factory=list)


class DecisionRecord(BaseModel):
    """An agent decision plus the branches it creates, written in one transaction."""

    id: str
    branch_id: str | None = None
    decision_type: str
    decision: str
    rationale: str | None = None
    input_summary: str | None = None
    alternatives: list[dict] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    provenance: dict = Field(default_factory=dict)
    children: list[ScoutBranchDraft] = Field(default_factory=list)


class HypothesisRecord(BaseModel):
    id: str
    text: str
    rationale: str
    testability: float = Field(ge=0, le=1)
    risk: str
    supporting_claim_ids: list[str]
    contradicting_claim_ids: list[str] = Field(default_factory=list)
    supporting_paper_ids: list[str]
    missing_evidence: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class SynthesisRecord(BaseModel):
    summary_id: str
    overview: str
    provenance: dict = Field(default_factory=dict)
    hypotheses: list[HypothesisRecord] = Field(default_factory=list)
    decision: DecisionRecord
