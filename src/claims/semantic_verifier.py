"""Evidence judgment separate from retrieval, with explicit abstention."""

from ..api.models import ClaimEvidenceCreate
from ..research.models import EvidenceJudgment


async def judge_passage(claim_text, retrieved, model):
    candidate = retrieved.candidate
    relation, quote = "mentions", candidate.evidence_text
    trace = {
        "retrieval_score": retrieved.retrieval_score,
        "strategy": "retrieval_only",
        "rationale": "No verification model configured; this passage requires review.",
    }
    if model is not None:
        decision, provenance = await model.generate(
            EvidenceJudgment,
            "Judge whether the passage supports, contradicts, or provides insufficient evidence for the claim. "
            "Check exact numeric values, negations and which entity outperforms which. Include a verbatim quote "
            "from the passage for supports or contradicts. A related topic alone is insufficient.",
            {"claim": claim_text, "passage": candidate.evidence_text},
        )
        if decision.relation != "insufficient" and (
            not decision.quote.strip() or decision.quote not in candidate.evidence_text
        ):
            raise ValueError(
                "Verification quote is not present verbatim in the source passage"
            )
        relation = decision.relation
        quote = (
            decision.quote
            if decision.quote and decision.quote in candidate.evidence_text
            else candidate.evidence_text
        )
        trace = {
            **trace,
            "strategy": "structured_evidence_judge_v1",
            "rationale": decision.rationale,
            "provenance": provenance,
        }
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
    ), trace
