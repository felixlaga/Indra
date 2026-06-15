from src.halugate import HallucinationResult
from src.halugate.models import HallucinationSpan
from src.halugate.protocols import HallucinationDetectorProtocol
from src.semantic_scholar.models import PaperDetails


async def validate_summary(
    client: HallucinationDetectorProtocol,
    summary: str,
    papers: list[PaperDetails],
    query: str,
) -> tuple[str, float, HallucinationResult]:
    """
    Validate LLM summary against source papers.

    Returns:
        - Validated summary (with hallucinations removed)
        - Groundedness score (0-1)
        - Full hallucination result
    """
    # Build context from paper abstracts
    context = "\n\n".join(
        [f"Title: {p.title}\nAbstract: {p.abstract}" for p in papers if p.abstract]
    )

    # Run HaluGate validation
    result = await client.validate(
        context=context,
        question=query,
        answer=summary,
    )

    # Calculate groundedness
    groundedness = client.compute_groundedness(result, summary)

    # Remove hallucinated spans from summary
    validated = remove_hallucinated_spans(summary, result.spans)

    return validated, groundedness, result


def remove_hallucinated_spans(text: str, spans: list[HallucinationSpan]) -> str:
    """Remove hallucinated spans from text, replacing with [UNVERIFIED]."""
    if not spans:
        return text

    # Sort spans by start position (descending) to avoid offset issues
    sorted_spans = sorted(spans, key=lambda s: s.start, reverse=True)

    result = text
    for span in sorted_spans:
        if span.start >= 0:
            result = result[: span.start] + "[UNVERIFIED]" + result[span.end :]

    return result
