"""
Overseer: Orchestrates summarization with hallucination detection and retry.

The Overseer coordinates the summarization pipeline:
1. Generate a summary using the LLM
2. Validate it with HaluGate (3-stage hallucination detection)
3. If hallucinations detected, retry with stricter guidance
4. Return the best summary with validation results
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..halugate import LocalHaluGate, HallucinationResult
    from ..llm.protocols import LLMProvider
    from ..semantic_scholar import PaperDetails

logger = logging.getLogger(__name__)

# Strict guidance for retry attempts
STRICT_GUIDANCE = """
Only include claims directly supported by the provided paper content.
Prefer omission over speculation. If something is not stated, say it is not stated.
Do not infer or extrapolate beyond what is explicitly written.
Focus on verifiable facts from the text.
"""


class Overseer:
    """
    Orchestrates summarization with automatic hallucination detection and retry.

    The Overseer implements a generate-then-validate loop:
    1. Summarize the paper using the configured LLM
    2. Validate the summary using HaluGate's 3-stage pipeline
    3. If groundedness is below threshold or contradictions found, retry with stricter guidance
    4. Return the summary, validation result, and groundedness score
    """

    def __init__(
        self,
        halugate,
        summarizer,
        max_retries: int = 2,
        groundedness_threshold: float = 0.8,
    ):
        """
        Initialize the Overseer.

        Args:
            halugate: HaluGate instance for hallucination detection
            summarizer: LLM provider for summarization
            max_retries: Maximum number of retry attempts (default: 2)
            groundedness_threshold: Minimum acceptable groundedness score (default: 0.8)
        """
        self.halugate = halugate
        self.summarizer = summarizer
        self.max_retries = max_retries
        self.groundedness_threshold = groundedness_threshold

    async def summarize_with_validation(
        self,
        paper: PaperDetails,
        guidance: str | None = None,
    ) -> tuple[str, HallucinationResult, float]:
        """
        Summarize a paper with hallucination detection and automatic retry.

        This method implements the full validation loop:
        1. Generate summary (with optional guidance)
        2. Validate against paper content using HaluGate
        3. Check groundedness and contradiction count
        4. If below threshold, retry with stricter guidance
        5. Return best result

        Args:
            paper: Paper to summarize (with full_text or abstract)
            guidance: Optional guidance string to steer summarization

        Returns:
            Tuple of (summary, hallucination_result, groundedness_score)
        """
        from ..summarize import summarize_paper

        # Use full text if available, otherwise fall back to abstract
        context = paper.full_text or paper.abstract or ""
        question = f"Summarize the paper: {paper.title}"

        current_guidance = guidance
        best_summary = ""
        best_result = None
        best_groundedness = 0.0

        for attempt in range(self.max_retries + 1):
            # Generate summary
            logger.info(f"Summarization attempt {attempt + 1}/{self.max_retries + 1}")

            summary = await summarize_paper(
                paper=paper,
                provider=self.summarizer,
                guidance=current_guidance,
            )

            # Validate with HaluGate
            result = await self.halugate.validate(
                context=context,
                question=question,
                answer=summary,
            )

            groundedness = self.halugate.compute_groundedness(result, summary)

            logger.info(
                f"Attempt {attempt + 1}: groundedness={groundedness:.2%}, "
                f"contradictions={result.nli_contradictions}, "
                f"hallucinated_spans={len(result.spans)}"
            )

            # Track best result
            if groundedness > best_groundedness:
                best_summary = summary
                best_result = result
                best_groundedness = groundedness

            # Check if good enough
            if groundedness >= self.groundedness_threshold and result.nli_contradictions == 0:
                logger.info(f"Validation passed on attempt {attempt + 1}")
                return summary, result, groundedness

            # Prepare for retry with stricter guidance
            if attempt < self.max_retries:
                logger.warning(
                    f"Validation failed (groundedness={groundedness:.2%}, "
                    f"contradictions={result.nli_contradictions}), retrying with strict guidance"
                )
                current_guidance = STRICT_GUIDANCE

        # Return best attempt if we exhausted retries
        logger.warning(
            f"Exhausted {self.max_retries + 1} attempts, returning best result "
            f"(groundedness={best_groundedness:.2%})"
        )
        return best_summary, best_result, best_groundedness

    async def validate_summary(
        self,
        summary: str,
        context: str,
        question: str = "Summarize the content",
    ) -> tuple[HallucinationResult, float]:
        """
        Validate an existing summary against context.

        Use this when you already have a summary and just want to check it.

        Args:
            summary: The summary to validate
            context: Source text to validate against
            question: The query that generated the summary

        Returns:
            Tuple of (hallucination_result, groundedness_score)
        """
        result = await self.halugate.validate(
            context=context,
            question=question,
            answer=summary,
        )
        groundedness = self.halugate.compute_groundedness(result, summary)
        return result, groundedness
