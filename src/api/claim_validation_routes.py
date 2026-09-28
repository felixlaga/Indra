"""Claim-level evidence retrieval and inspection routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request

from ..claims import EvidenceCandidate, EvidenceRetriever, split_passages
from ..claims.semantic_verifier import judge_passage
from ..research.model import ResearchModel
from .claim_validation_models import (
    ClaimAutoValidationRequest,
    ClaimAutoValidationResult,
    ClaimInspection,
    ClaimValidationTrace,
)
from .models import ClaimStatus, ClaimValidationRequest
from .repository import RepositoryError
from .routes import get_repository, handle_repository_error

router = APIRouter()
_retriever = EvidenceRetriever()


def _paper_candidates(paper, chunks=()) -> list[EvidenceCandidate]:
    candidates: list[EvidenceCandidate] = [
        EvidenceCandidate(
            source_type="paper_chunk",
            paper_id=paper.id,
            chunk_id=chunk.id,
            evidence_text=chunk.text,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            section_title=chunk.section_title,
        )
        for chunk in chunks
    ]
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
                validator_type=str(
                    event.payload.get("validator_type", "claim_evidence")
                ),
                notes=event.payload.get("notes"),
                evidence_ids=[
                    str(item) for item in event.payload.get("evidence_ids", [])
                ],
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


async def validate_automatically(
    repository, claim_id, payload, model=None, leased=None
):
    claim = repository.get_claim(claim_id)
    if (
        claim.status == ClaimStatus.SPECULATIVE
        or claim.claim_type.value == "hypothesis"
    ):
        raise HTTPException(
            status_code=409,
            detail="Speculative or hypothesis claims are not automatically promoted. They require explicit evidence or manual review.",
        )
    entries = repository.list_papers(claim.session_id)
    if not payload.include_session_papers:
        own_id = repository.get_paper(claim.paper_id).id if claim.paper_id else None
        entries = [entry for entry in entries if entry.paper_id == own_id]
    candidates = [
        candidate
        for entry in entries
        for candidate in _paper_candidates(
            entry.paper, repository.list_paper_chunks(entry.paper.id)
        )
    ]
    retrieved = _retriever.retrieve(
        claim.claim_text, candidates, top_k=payload.top_k, min_score=payload.min_score
    )
    evidence, judgments = [], []
    for item in retrieved:
        decision, trace = await judge_passage(claim.claim_text, item, model)
        evidence.append(decision)
        judgments.append(trace)
    request = ClaimValidationRequest(
        evidence=evidence,
        validator_type="claim_evidence",
        notes=json.dumps(
            {
                "strategy": "structured_evidence_judge_v1"
                if model
                else "retrieval_only",
                "candidates_considered": len(candidates),
                "judgments": judgments,
            },
            sort_keys=True,
        ),
    )
    if leased:
        repository.validate_research_claim(leased, claim_id, request)
    else:
        repository.validate_claim(claim_id, request)
    return ClaimAutoValidationResult(
        inspection=_inspection(repository, claim_id),
        candidates_considered=len(candidates),
        evidence_retrieved=len(retrieved),
    )


@router.post(
    "/claims/{claim_id}/validate/auto", response_model=ClaimAutoValidationResult
)
async def auto_validate_claim(
    claim_id: str, payload: ClaimAutoValidationRequest, request: Request
):
    """Retrieve persisted passages, then judge or explicitly leave them for review."""
    try:
        model = ResearchModel.from_environment()
        return await validate_automatically(
            get_repository(request), claim_id, payload, model
        )
    except RepositoryError as exc:
        handle_repository_error(exc)
        raise
    except HTTPException:
        raise
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
