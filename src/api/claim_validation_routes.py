"""Claim-level evidence retrieval and inspection routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request, status

from ..claims import EvidenceCandidate, EvidenceRetriever, split_passages
from .claim_validation_models import (
    ClaimAutoValidationRequest,
    ClaimAutoValidationResult,
    ClaimInspection,
    ClaimValidationTrace,
)
from .models import ClaimEvidenceCreate, ClaimStatus, ClaimValidationRequest
from .repository import RepositoryError
from .routes import get_repository, handle_repository_error

router = APIRouter()
_retriever = EvidenceRetriever()


def _paper_candidates(paper) -> list[EvidenceCandidate]:
    candidates: list[EvidenceCandidate] = []
    if paper.abstract:
        for passage in split_passages(paper.abstract):
            candidates.append(
                EvidenceCandidate(
                    source_type="paper_abstract",
                    paper_id=paper.id,
                    evidence_text=passage,
                    section_title="Abstract",
                )
            )

    metadata_values = {
        "title": paper.title,
        "venue": paper.venue,
        "year": str(paper.year) if paper.year is not None else None,
    }
    for field, value in metadata_values.items():
        if value:
            candidates.append(
                EvidenceCandidate(
                    source_type="paper_metadata",
                    paper_id=paper.id,
                    evidence_text=f"{field.title()}: {value}",
                    metadata_field=field,
                    section_title="Metadata",
                )
            )
    return candidates


def _inspection(repository, claim_id: str) -> ClaimInspection:
    claim = repository.get_claim(claim_id)
    evidence = repository.list_claim_evidence(claim_id)
    events = repository.list_events(claim.session_id)
    validations = []
    for event in events:
        if event.event_type != "claim_validated":
            continue
        if event.payload.get("claim_id") != claim.id:
            continue
        confidence = event.payload.get("confidence")
        validations.append(
            ClaimValidationTrace(
                id=event.id,
                status=str(event.payload.get("status", claim.status.value)),
                confidence=float(confidence) if confidence is not None else None,
                validator_type=str(event.payload.get("validator_type", "claim_evidence")),
                notes=event.payload.get("notes"),
                evidence_ids=[str(item) for item in event.payload.get("evidence_ids", [])],
                created_at=event.created_at,
            )
        )
    paper = repository.get_paper(claim.paper_id) if claim.paper_id else None
    return ClaimInspection(
        claim=claim,
        evidence=evidence,
        validations=validations,
        paper=paper,
    )


@router.get("/claims/{claim_id}/inspection", response_model=ClaimInspection)
def inspect_claim(claim_id: str, request: Request) -> ClaimInspection:
    """Return claim status, source passages, and validation history."""

    try:
        return _inspection(get_repository(request), claim_id)
    except RepositoryError as exc:
        handle_repository_error(exc)
        raise


@router.post(
    "/claims/{claim_id}/validate/auto",
    response_model=ClaimAutoValidationResult,
)
def auto_validate_claim(
    claim_id: str,
    payload: ClaimAutoValidationRequest,
    request: Request,
) -> ClaimAutoValidationResult:
    """Retrieve evidence from persisted paper records and validate one claim.

    This endpoint uses conservative lexical retrieval. It never treats model inference
    as evidence and does not auto-promote speculative or hypothesis claims.
    """

    repository = get_repository(request)
    try:
        claim = repository.get_claim(claim_id)
        if claim.status == ClaimStatus.SPECULATIVE or claim.claim_type.value == "hypothesis":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Speculative or hypothesis claims are not automatically promoted. "
                    "They require explicit evidence or manual review."
                ),
            )

        session_papers = repository.list_papers(claim.session_id)
        if claim.paper_id:
            session_papers = [
                entry for entry in session_papers if entry.paper_id == claim.paper_id
            ]
        elif not payload.include_session_papers:
            session_papers = []

        candidates = [
            candidate
            for entry in session_papers
            for candidate in _paper_candidates(entry.paper)
        ]
        retrieved = _retriever.retrieve(
            claim.claim_text,
            candidates,
            top_k=payload.top_k,
            min_score=payload.min_score,
        )
        evidence_payloads = [
            ClaimEvidenceCreate(
                evidence_text=item.candidate.evidence_text,
                relation=item.relation,
                source_type=item.candidate.source_type,
                paper_id=item.candidate.paper_id,
                chunk_id=item.candidate.chunk_id,
                metadata_field=item.candidate.metadata_field,
                reviewer_id=None,
                score=item.score,
                page_start=item.candidate.page_start,
                page_end=item.candidate.page_end,
                section_title=item.candidate.section_title,
            )
            for item in retrieved
        ]
        trace = {
            "strategy": "lexical_evidence_retriever_v1",
            "top_k": payload.top_k,
            "min_score": payload.min_score,
            "candidates_considered": len(candidates),
            "retrieved": [
                {
                    "paper_id": item.candidate.paper_id,
                    "source_type": item.candidate.source_type,
                    "relation": item.relation,
                    "score": item.score,
                    "retrieval_score": item.retrieval_score,
                    "overlap_terms": list(item.overlap_terms),
                }
                for item in retrieved
            ],
        }
        repository.validate_claim(
            claim_id,
            ClaimValidationRequest(
                evidence=evidence_payloads,
                validator_type="claim_evidence",
                notes=json.dumps(trace, sort_keys=True),
            ),
        )
        return ClaimAutoValidationResult(
            inspection=_inspection(repository, claim_id),
            candidates_considered=len(candidates),
            evidence_retrieved=len(retrieved),
        )
    except HTTPException:
        raise
    except RepositoryError as exc:
        handle_repository_error(exc)
        raise
