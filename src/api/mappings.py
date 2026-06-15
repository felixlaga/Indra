"""Explicit canonical-domain to API schema mappings."""

from __future__ import annotations

from ..domain.claims import Claim as DomainClaim
from ..domain.evidence import ClaimEvidence as DomainClaimEvidence
from ..domain.papers import (
    Paper as DomainPaper,
    SessionPaper as DomainSessionPaper,
    SessionPaperView as DomainSessionPaperView,
)
from ..domain.sessions import Branch as DomainBranch
from ..domain.sessions import Event as DomainEvent
from ..domain.summaries import Summary as DomainSummary
from .models import (
    Branch,
    Claim,
    ClaimEvidence,
    Event,
    Paper,
    SessionPaper,
    SessionPaperView,
    Summary,
)


def paper_to_api(paper: DomainPaper) -> Paper:
    """Project a global domain Paper to its API representation."""

    return Paper(
        id=str(paper.id),
        canonical_key=paper.canonical_key,
        semantic_scholar_id=paper.external_ids.semantic_scholar_id,
        arxiv_id=paper.external_ids.arxiv_id,
        doi=paper.external_ids.doi,
        openalex_id=paper.external_ids.openalex_id,
        title=paper.title,
        abstract=paper.abstract,
        authors=[
            author.model_dump(mode="json")
            for author in paper.authors
        ],
        year=paper.year,
        venue=paper.venue,
        citation_count=paper.citation_count,
        reference_count=paper.reference_count,
        influential_citation_count=paper.influential_citation_count,
        url=paper.url,
        pdf_url=paper.pdf_url,
        open_access_pdf_url=paper.open_access_pdf_url,
        metadata=paper.metadata,
        created_at=paper.created_at,
        updated_at=paper.updated_at,
    )


def session_paper_to_api(session_paper: DomainSessionPaper) -> SessionPaper:
    """Project contextual paper discovery to API."""

    return SessionPaper(
        id=str(session_paper.id),
        session_id=str(session_paper.session_id),
        paper_id=str(session_paper.paper_id),
        branch_id=str(session_paper.branch_id) if session_paper.branch_id else None,
        discovery_method=session_paper.discovery_method,
        selection_reason=session_paper.selection_reason,
        selected=session_paper.selected,
        iteration_number=session_paper.iteration_number,
        created_at=session_paper.created_at,
    )


def session_paper_view_to_api(view: DomainSessionPaperView) -> SessionPaperView:
    """Project combined domain paper/session-paper view to API."""

    paper = paper_to_api(view.paper)
    session_paper = view.session_paper
    return SessionPaperView(
        id=str(session_paper.id),
        session_id=str(session_paper.session_id),
        branch_id=str(session_paper.branch_id) if session_paper.branch_id else None,
        paper_id=str(view.paper.id),
        discovery_method=session_paper.discovery_method,
        selection_reason=session_paper.selection_reason,
        selected=session_paper.selected,
        iteration_number=session_paper.iteration_number,
        paper=paper,
        created_at=session_paper.created_at,
    )


def branch_to_api(branch: DomainBranch) -> Branch:
    """Project canonical Branch to API Branch."""

    return Branch(
        id=str(branch.id),
        session_id=str(branch.session_id),
        parent_branch_id=str(branch.parent_branch_id) if branch.parent_branch_id else None,
        query=branch.query,
        label=branch.label,
        rationale=branch.rationale,
        mode=branch.mode,
        status=branch.status,
        prune_reason=branch.prune_reason,
        failure_reason=branch.failure_reason,
        depth=branch.depth,
        context_tokens_used=branch.context_tokens_used,
        max_context_tokens=branch.max_context_tokens,
        created_at=branch.created_at,
        updated_at=branch.updated_at,
    )


def summary_to_api(summary: DomainSummary) -> Summary:
    """Project canonical Summary to API Summary."""

    return Summary(
        id=str(summary.id),
        session_id=str(summary.session_id),
        branch_id=str(summary.branch_id) if summary.branch_id else None,
        paper_id=str(summary.paper_id) if summary.paper_id else None,
        summary_type=summary.summary_type,
        text=summary.text,
        groundedness_score=summary.groundedness_score,
        validation_status=summary.validation_status,
        validation_details=summary.validation_details,
        generation_provenance=(
            summary.generation_provenance.model_dump(mode="json")
            if summary.generation_provenance
            else None
        ),
        created_at=summary.created_at,
        updated_at=summary.updated_at,
    )


def claim_to_api(claim: DomainClaim) -> Claim:
    """Project canonical Claim to API Claim."""

    return Claim(
        id=str(claim.id),
        session_id=str(claim.session_id),
        branch_id=str(claim.branch_id) if claim.branch_id else None,
        paper_id=str(claim.paper_id) if claim.paper_id else None,
        summary_id=str(claim.summary_id) if claim.summary_id else None,
        claim_text=claim.claim_text,
        claim_type=claim.claim_type,
        status=claim.status,
        confidence=claim.confidence,
        created_by=claim.created_by,
        created_at=claim.created_at,
        updated_at=claim.updated_at,
    )


def claim_evidence_to_api(evidence: DomainClaimEvidence) -> ClaimEvidence:
    """Project canonical ClaimEvidence to API ClaimEvidence."""

    locator = evidence.locator
    return ClaimEvidence(
        id=str(evidence.id),
        claim_id=str(evidence.claim_id),
        session_id=str(evidence.session_id),
        source_type=locator.source_type,
        paper_id=str(locator.paper_id) if locator.paper_id else None,
        chunk_id=str(locator.chunk_id) if locator.chunk_id else None,
        metadata_field=locator.metadata_field,
        upload_id=locator.upload_id,
        document_id=locator.document_id,
        external_uri=locator.external_uri,
        source_id=locator.source_id,
        reviewer_id=locator.reviewer_id,
        evidence_text=evidence.evidence_text,
        relation=evidence.relation,
        score=evidence.score,
        page_start=locator.page_start,
        page_end=locator.page_end,
        section_title=locator.section_title,
        created_at=evidence.created_at,
    )


def event_to_api(event: DomainEvent) -> Event:
    """Project canonical Event to API Event."""

    return Event(
        id=str(event.id),
        session_id=str(event.session_id),
        branch_id=str(event.branch_id) if event.branch_id else None,
        paper_id=str(event.paper_id) if event.paper_id else None,
        event_type=event.event_type,
        payload=event.payload,
        severity=event.severity,
        created_at=event.created_at,
    )
