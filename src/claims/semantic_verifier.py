"""Evidence judgment separate from retrieval, with explicit abstention."""

from ..api.models import ClaimEvidenceCreate
from ..research.models import EvidenceJudgment, EvidenceJudgments

JUDGE_INSTRUCTION = (
    "Judge whether the passage supports, contradicts, or provides insufficient evidence for the claim. "
    "Check exact numeric values, negations and which entity outperforms which. Include a verbatim quote "
    "from the passage for supports or contradicts. A related topic alone is insufficient."
)
BATCH_INSTRUCTION = (
    "For each numbered passage, judge whether it supports, contradicts, or provides insufficient evidence "
    "for the claim. Judge each passage on its own text only. Check exact numeric values, negations and "
    "which entity outperforms which. For supports or contradicts, quote that passage verbatim. A related "
    "topic alone is insufficient. Return one judgment per passage, using its number."
)


def _unjudged_trace(retrieved) -> dict:
    return {
        "retrieval_score": retrieved.retrieval_score,
        "strategy": "retrieval_only",
        "rationale": "No verification model configured; this passage requires review.",
    }


def _evidence(candidate, relation: str, quote: str) -> ClaimEvidenceCreate:
    # Retrieval rank and model self-confidence are never stored as factual confidence.
    return ClaimEvidenceCreate(
        source_type=candidate.source_type,
        paper_id=candidate.paper_id,
        chunk_id=candidate.chunk_id,
        metadata_field=candidate.metadata_field,
        reviewer_id=None,
        evidence_text=quote,
        relation=relation,
        score=None,
        page_start=candidate.page_start,
        page_end=candidate.page_end,
        section_title=candidate.section_title,
    )


def _checked(judgment, candidate) -> tuple[str, str]:
    """A supporting or contradicting judgment must quote its passage verbatim."""

    if judgment.relation != "insufficient" and (
        not judgment.quote.strip() or judgment.quote not in candidate.evidence_text
    ):
        raise ValueError(
            "Verification quote is not present verbatim in the source passage"
        )
    quote = (
        judgment.quote
        if judgment.quote and judgment.quote in candidate.evidence_text
        else candidate.evidence_text
    )
    return judgment.relation, quote


async def judge_passage(claim_text, retrieved, model):
    candidate = retrieved.candidate
    relation, quote = "mentions", candidate.evidence_text
    trace = _unjudged_trace(retrieved)
    if model is not None:
        decision, provenance = await model.generate(
            EvidenceJudgment,
            JUDGE_INSTRUCTION,
            {"claim": claim_text, "passage": candidate.evidence_text},
        )
        relation, quote = _checked(decision, candidate)
        trace = {
            **trace,
            "strategy": "structured_evidence_judge_v1",
            "rationale": decision.rationale,
            "provenance": provenance,
        }
    return _evidence(candidate, relation, quote), trace


async def judge_passages(claim_text, retrieved: list, model):
    """Judge all retrieved passages for one claim in a single model call."""

    if model is None or not retrieved:
        return [
            (_evidence(item.candidate, "mentions", item.candidate.evidence_text), _unjudged_trace(item))
            for item in retrieved
        ]
    decisions, provenance = await model.generate(
        EvidenceJudgments,
        BATCH_INSTRUCTION,
        {
            "claim": claim_text,
            "passages": [
                {"passage": number, "text": item.candidate.evidence_text}
                for number, item in enumerate(retrieved, 1)
            ],
        },
    )
    by_passage = {}
    for judgment in decisions.judgments:
        if not 1 <= judgment.passage <= len(retrieved) or judgment.passage in by_passage:
            raise ValueError("Verification answer referenced an unknown or repeated passage")
        by_passage[judgment.passage] = judgment
    results = []
    for number, item in enumerate(retrieved, 1):
        judgment = by_passage.get(number)
        if judgment is None:
            # An omitted passage stays unjudged rather than counting as insufficient.
            results.append(
                (
                    _evidence(item.candidate, "mentions", item.candidate.evidence_text),
                    {**_unjudged_trace(item), "rationale": "The model did not judge this passage; it requires review."},
                )
            )
            continue
        relation, quote = _checked(judgment, item.candidate)
        results.append(
            (
                _evidence(item.candidate, relation, quote),
                {
                    "retrieval_score": item.retrieval_score,
                    "strategy": "structured_evidence_judge_batch_v1",
                    "rationale": judgment.rationale,
                    "provenance": provenance,
                },
            )
        )
    return results
