"""Typed writes shared by the research worker and repository backends."""

from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import BaseModel, ConfigDict, Field

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


class PaperChunk(BaseModel):
    id: str
    paper_id: str
    document_id: str
    chunk_index: int
    text: str = Field(min_length=1)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    section_title: str | None = None


class ClaimDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1500)
    claim_type: ClaimType


class PaperSynthesis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=8000)
    claims: list[ClaimDraft] = Field(max_length=10)


class PaperResult(BaseModel):
    paper: Paper
    chunks: list[PaperChunk] = Field(default_factory=list)
    source_url: str | None = None
    parse_status: Literal["parsed", "unavailable", "failed"] = "unavailable"
    source_note: str | None = None
    synthesis: PaperSynthesis | None = None
    provenance: dict = Field(default_factory=dict)


class EvidenceJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relation: Literal["supports", "contradicts", "insufficient"]
    quote: str
    rationale: str = Field(min_length=1, max_length=1500)
