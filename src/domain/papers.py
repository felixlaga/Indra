"""Canonical paper identity and session discovery models."""

from __future__ import annotations

import re
from datetime import date, datetime
from uuid import UUID

from pydantic import Field, model_validator

from .base import DomainModel
from .enums import PaperDiscoveryMethod
from .provenance import utc_now


DOI_URL_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.I)
ARXIV_URL_PREFIX = re.compile(r"^(?:https?://arxiv\.org/(?:abs|pdf)/|arxiv:)", re.I)
ARXIV_VERSION_SUFFIX = re.compile(r"v\d+$", re.I)


def normalize_doi(value: str | None) -> str | None:
    """Normalize a DOI for durable identity matching."""

    if not value:
        return None
    doi = DOI_URL_PREFIX.sub("", value.strip()).strip()
    return doi.lower() or None


def normalize_arxiv_id(value: str | None) -> str | None:
    """Normalize an arXiv identifier without version or PDF suffix."""

    if not value:
        return None
    arxiv_id = ARXIV_URL_PREFIX.sub("", value.strip()).strip()
    arxiv_id = arxiv_id.removesuffix(".pdf")
    arxiv_id = ARXIV_VERSION_SUFFIX.sub("", arxiv_id)
    return arxiv_id.lower() or None


def normalize_title(value: str | None) -> str | None:
    """Normalize a title for deterministic fallback keys."""

    if not value:
        return None
    title = re.sub(r"\s+", " ", value.strip().lower())
    title = re.sub(r"[^a-z0-9 ]+", "", title)
    return title or None


class PaperExternalIds(DomainModel):
    """Provider-specific paper identifiers."""

    semantic_scholar_id: str | None = None
    arxiv_id: str | None = None
    doi: str | None = None
    openalex_id: str | None = None
    other: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_known_ids(self) -> "PaperExternalIds":
        self.doi = normalize_doi(self.doi)
        self.arxiv_id = normalize_arxiv_id(self.arxiv_id)
        return self


def canonical_paper_key(
    external_ids: PaperExternalIds,
    title: str | None = None,
    year: int | None = None,
) -> str:
    """Build the canonical paper key using the Phase 1 precedence order."""

    if external_ids.doi:
        return f"doi:{external_ids.doi}"
    if external_ids.arxiv_id:
        return f"arxiv:{external_ids.arxiv_id}"
    if external_ids.semantic_scholar_id:
        return f"semantic_scholar:{external_ids.semantic_scholar_id}"
    if external_ids.openalex_id:
        return f"openalex:{external_ids.openalex_id}"
    normalized_title = normalize_title(title)
    if normalized_title and year is not None:
        return f"title_year:{normalized_title}:{year}"
    raise ValueError("Cannot derive canonical paper key without provider ID or title+year")


class PaperAuthor(DomainModel):
    """Author metadata for a global paper."""

    name: str
    author_id: str | None = None
    position: int | None = Field(default=None, ge=0)
    metadata: dict = Field(default_factory=dict)


class Paper(DomainModel):
    """Global paper identity and metadata.

    A paper is not session-scoped. Session and branch discovery context belongs
    in SessionPaper.
    """

    id: UUID
    canonical_key: str
    external_ids: PaperExternalIds = Field(default_factory=PaperExternalIds)
    title: str
    abstract: str | None = None
    authors: list[PaperAuthor] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    publication_date: date | None = None
    citation_count: int | None = Field(default=None, ge=0)
    reference_count: int | None = Field(default=None, ge=0)
    influential_citation_count: int | None = Field(default=None, ge=0)
    url: str | None = None
    pdf_url: str | None = None
    open_access_pdf_url: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def forbid_session_context(self) -> "Paper":
        if "session_id" in self.metadata or "branch_id" in self.metadata:
            raise ValueError("Paper metadata must not carry session or branch identity")
        return self


class SessionPaper(DomainModel):
    """Session-specific discovery context for a global paper."""

    id: UUID
    session_id: UUID
    paper_id: UUID
    branch_id: UUID | None = None
    discovery_method: PaperDiscoveryMethod | None = None
    selection_reason: str | None = None
    selected: bool = False
    iteration_number: int | None = Field(default=None, ge=0)
    created_at: datetime = Field(default_factory=utc_now)


class SessionPaperView(DomainModel):
    """Read view combining global metadata with session discovery context."""

    paper: Paper
    session_paper: SessionPaper
