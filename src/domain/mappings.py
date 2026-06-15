"""Explicit mappings into canonical domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
from uuid import UUID

from .enums import BranchMode, BranchStatus, SummaryType
from .ids import parse_uuid
from .papers import (
    Paper,
    PaperAuthor,
    PaperExternalIds,
    canonical_paper_key,
    normalize_arxiv_id,
    normalize_doi,
)
from .provenance import GenerationProvenance
from .provenance import utc_now
from .sessions import Branch, Hypothesis
from .summaries import Summary, SummaryGenerationResult


class MappingError(ValueError):
    """Raised when a mapping cannot be performed without inventing data."""


IdFactory = Callable[[], UUID]


def _require_uuid(value: str | UUID | None, field_name: str) -> UUID:
    if value is None:
        raise MappingError(f"{field_name} is required")
    try:
        return parse_uuid(value)
    except ValueError as exc:
        raise MappingError(str(exc)) from exc


def paper_from_provider(
    provider_paper: Any,
    *,
    paper_id: str | UUID | None = None,
    id_factory: IdFactory | None = None,
) -> Paper:
    """Map provider paper metadata to canonical Paper.

    Creation mappings may receive an explicit ID factory. Read mappings must
    pass an existing paper_id and should not call this with neither argument.
    """

    if paper_id is None:
        if id_factory is None:
            raise MappingError("paper_id or id_factory is required")
        parsed_id = id_factory()
    else:
        parsed_id = _require_uuid(paper_id, "paper_id")

    title = getattr(provider_paper, "title", None)
    if not title:
        raise MappingError("Provider paper title is required")

    raw_external_ids = getattr(provider_paper, "external_ids", None) or {}
    semantic_scholar_id = getattr(provider_paper, "paper_id", None)
    arxiv_id = None
    if isinstance(semantic_scholar_id, str) and semantic_scholar_id.lower().startswith("arxiv:"):
        arxiv_id = semantic_scholar_id.split(":", 1)[1]
        semantic_scholar_id = None

    external_ids = PaperExternalIds(
        semantic_scholar_id=semantic_scholar_id,
        arxiv_id=raw_external_ids.get("ArXiv") or raw_external_ids.get("arXiv") or arxiv_id,
        doi=raw_external_ids.get("DOI") or raw_external_ids.get("doi"),
        openalex_id=raw_external_ids.get("OpenAlex") or raw_external_ids.get("openalex"),
        other={
            str(key): str(value)
            for key, value in raw_external_ids.items()
            if key not in {"ArXiv", "arXiv", "DOI", "doi", "OpenAlex", "openalex"}
        },
    )
    canonical_key = canonical_paper_key(
        external_ids,
        title=title,
        year=getattr(provider_paper, "year", None),
    )

    authors = [
        PaperAuthor(
            author_id=getattr(author, "author_id", None),
            name=getattr(author, "name", None) or "Unknown",
            position=index,
        )
        for index, author in enumerate(getattr(provider_paper, "authors", []) or [])
    ]
    open_access_pdf = getattr(provider_paper, "open_access_pdf", None)

    return Paper(
        id=parsed_id,
        canonical_key=canonical_key,
        external_ids=external_ids,
        title=title,
        abstract=getattr(provider_paper, "abstract", None),
        authors=authors,
        year=getattr(provider_paper, "year", None),
        venue=getattr(provider_paper, "venue", None),
        citation_count=getattr(provider_paper, "citation_count", None),
        url=getattr(provider_paper, "url", None),
        pdf_url=getattr(open_access_pdf, "url", None) if open_access_pdf else None,
        open_access_pdf_url=getattr(open_access_pdf, "url", None) if open_access_pdf else None,
        metadata={"provider_paper_id": getattr(provider_paper, "paper_id", None)},
    )


def runtime_branch_to_domain(
    runtime_branch: Any,
    *,
    session_id: str | UUID,
) -> Branch:
    """Map an orchestration branch into the canonical branch contract."""

    created_at = getattr(runtime_branch, "created_at", None) or utc_now()
    updated_at = getattr(runtime_branch, "updated_at", None) or created_at
    return Branch(
        id=_require_uuid(getattr(runtime_branch, "id", None), "branch.id"),
        session_id=_require_uuid(session_id, "session_id"),
        parent_branch_id=(
            _require_uuid(getattr(runtime_branch, "parent_branch_id", None), "parent_branch_id")
            if getattr(runtime_branch, "parent_branch_id", None)
            else None
        ),
        query=getattr(runtime_branch, "query", None) or "",
        mode=BranchMode(getattr(runtime_branch, "mode").value),
        status=BranchStatus(getattr(runtime_branch, "status").value),
        failure_reason=getattr(runtime_branch, "failure_reason", None),
        prune_reason=getattr(runtime_branch, "prune_reason", None),
        context_tokens_used=getattr(runtime_branch, "context_window_used", 0),
        max_context_tokens=getattr(runtime_branch, "max_context_window", None),
        created_at=created_at,
        updated_at=updated_at,
    )


def summary_from_runtime_result(
    result: SummaryGenerationResult,
    *,
    summary_id: str | UUID,
    session_id: str | UUID,
    summary_type: SummaryType,
    branch_id: str | UUID | None = None,
    paper_id: str | UUID | None = None,
) -> Summary:
    """Map a runtime summary-generation result to canonical Summary."""

    if result.summary_text is None:
        raise MappingError("summary_text is required to persist a summary")
    return Summary(
        id=_require_uuid(summary_id, "summary_id"),
        session_id=_require_uuid(session_id, "session_id"),
        branch_id=_require_uuid(branch_id, "branch_id") if branch_id else None,
        paper_id=_require_uuid(paper_id, "paper_id") if paper_id else None,
        summary_type=summary_type,
        text=result.summary_text,
        groundedness_score=result.groundedness_score,
        validation_status=result.validation_status,
        validation_details=result.validation_details,
        generation_provenance=result.generation_provenance,
    )


def runtime_hypothesis_to_domain(
    hypothesis: Any,
    *,
    session_id: str | UUID,
    branch_id: str | UUID | None = None,
    paper_id_lookup: Callable[[str], str | UUID] | None = None,
) -> Hypothesis:
    """Map a runtime ResearchHypothesis to the canonical hypothesis model."""

    supporting: list[UUID] = []
    for provider_or_internal_id in getattr(hypothesis, "supporting_paper_ids", []):
        mapped = paper_id_lookup(provider_or_internal_id) if paper_id_lookup else provider_or_internal_id
        supporting.append(_require_uuid(mapped, "supporting_paper_id"))

    return Hypothesis(
        id=_require_uuid(getattr(hypothesis, "id", None), "hypothesis.id"),
        session_id=_require_uuid(session_id, "session_id"),
        branch_id=_require_uuid(branch_id, "branch_id") if branch_id else None,
        text=getattr(hypothesis, "text", ""),
        supporting_paper_ids=supporting,
        confidence=getattr(hypothesis, "confidence", None),
        generation_provenance=getattr(hypothesis, "generation_provenance", None),
        created_at=getattr(hypothesis, "timestamp", None) or datetime.now(),
    )


def normalize_provider_ids(external_ids: dict[str, str | int] | None) -> PaperExternalIds:
    """Normalize provider IDs without creating a Paper."""

    external_ids = external_ids or {}
    return PaperExternalIds(
        semantic_scholar_id=external_ids.get("SemanticScholar") or external_ids.get("CorpusId"),
        arxiv_id=normalize_arxiv_id(str(external_ids["ArXiv"])) if "ArXiv" in external_ids else None,
        doi=normalize_doi(str(external_ids["DOI"])) if "DOI" in external_ids else None,
        openalex_id=str(external_ids["OpenAlex"]) if "OpenAlex" in external_ids else None,
    )
