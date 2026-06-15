"""Hypothesis validation against supporting evidence."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..orchestration.models import ResearchHypothesis, ValidatedSummary
    from ..halugate import LocalHaluGate, HallucinationResult

logger = logging.getLogger(__name__)


class HypothesisValidator:
    """
    Validates research hypotheses against supporting evidence.

    Uses HaluGate to check if hypotheses are grounded in their
    supporting paper summaries (not hallucinated).
    """

    def __init__(
        self,
        halugate: LocalHaluGate,
        groundedness_threshold: float = 0.8,
    ):
        """
        Initialize the hypothesis validator.

        Args:
            halugate: HaluGate instance for validation
            groundedness_threshold: Minimum groundedness for valid hypothesis
        """
        self.halugate = halugate
        self.groundedness_threshold = groundedness_threshold

    async def validate(
        self,
        hypothesis: ResearchHypothesis,
        supporting_summaries: list[ValidatedSummary],
    ) -> tuple[bool, float, str]:
        """
        Validate a hypothesis against its supporting summaries.

        Checks if the hypothesis is grounded in the evidence
        and not a hallucination.

        Args:
            hypothesis: Hypothesis to validate
            supporting_summaries: Summaries that should support the hypothesis

        Returns:
            Tuple of (is_valid, groundedness_score, explanation)
        """
        if not supporting_summaries:
            return False, 0.0, "No supporting summaries provided"

        # Build context from supporting summaries
        context_parts = []
        for summary in supporting_summaries:
            context_parts.append(
                f"Paper: {summary.paper_title}\n"
                f"Summary: {summary.summary}\n"
            )

        context = "\n---\n".join(context_parts)
        question = "Is this hypothesis supported by the research evidence?"

        try:
            result = await self.halugate.validate(
                context=context,
                question=question,
                answer=hypothesis.text,
            )

            groundedness = self.halugate.compute_groundedness(result, hypothesis.text)
            is_valid = groundedness >= self.groundedness_threshold and result.nli_contradictions == 0

            if is_valid:
                explanation = f"Hypothesis is well-grounded ({groundedness:.2%}) with no contradictions"
            else:
                issues = []
                if groundedness < self.groundedness_threshold:
                    issues.append(f"Low groundedness ({groundedness:.2%})")
                if result.nli_contradictions > 0:
                    issues.append(f"{result.nli_contradictions} contradictions detected")
                if result.spans:
                    issues.append(f"{len(result.spans)} potentially hallucinated spans")
                explanation = "; ".join(issues)

            logger.info(
                f"Hypothesis validation: valid={is_valid}, "
                f"groundedness={groundedness:.2%}, "
                f"contradictions={result.nli_contradictions}"
            )

            return is_valid, groundedness, explanation

        except Exception as e:
            logger.error(f"Failed to validate hypothesis: {e}")
            return False, 0.0, f"Validation error: {e}"

    async def validate_batch(
        self,
        hypotheses: list[ResearchHypothesis],
        all_summaries: dict[str, ValidatedSummary],
    ) -> list[tuple[ResearchHypothesis, bool, float, str]]:
        """
        Validate multiple hypotheses.

        Args:
            hypotheses: List of hypotheses to validate
            all_summaries: Dict mapping paper_id to ValidatedSummary

        Returns:
            List of tuples (hypothesis, is_valid, groundedness, explanation)
        """
        results = []

        for hypothesis in hypotheses:
            # Gather supporting summaries for this hypothesis
            supporting = [
                all_summaries[pid]
                for pid in hypothesis.supporting_paper_ids
                if pid in all_summaries
            ]

            is_valid, groundedness, explanation = await self.validate(
                hypothesis, supporting
            )

            results.append((hypothesis, is_valid, groundedness, explanation))

        return results

    async def filter_valid(
        self,
        hypotheses: list[ResearchHypothesis],
        all_summaries: dict[str, ValidatedSummary],
    ) -> list[ResearchHypothesis]:
        """
        Filter hypotheses to only return valid ones.

        Args:
            hypotheses: Hypotheses to filter
            all_summaries: Dict mapping paper_id to ValidatedSummary

        Returns:
            List of valid hypotheses
        """
        validation_results = await self.validate_batch(hypotheses, all_summaries)
        return [h for h, is_valid, _, _ in validation_results if is_valid]

    async def rank_hypotheses(
        self,
        hypotheses: list[ResearchHypothesis],
        all_summaries: dict[str, ValidatedSummary],
    ) -> list[tuple[ResearchHypothesis, float]]:
        """
        Rank hypotheses by their groundedness score.

        Args:
            hypotheses: Hypotheses to rank
            all_summaries: Dict mapping paper_id to ValidatedSummary

        Returns:
            List of (hypothesis, score) tuples, sorted by score descending
        """
        validation_results = await self.validate_batch(hypotheses, all_summaries)

        # Combine groundedness with hypothesis confidence
        scored = []
        for hypothesis, is_valid, groundedness, _ in validation_results:
            # Combined score: groundedness * 0.7 + confidence * 0.3
            # Only include valid hypotheses
            if is_valid:
                combined_score = groundedness * 0.7 + hypothesis.confidence * 0.3
                scored.append((hypothesis, combined_score))

        # Sort by combined score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def quick_check(
        self,
        hypothesis: ResearchHypothesis,
        supporting_summaries: list[ValidatedSummary],
    ) -> tuple[bool, str]:
        """
        Quick heuristic check without LLM/HaluGate.

        Useful for filtering obviously bad hypotheses before expensive validation.

        Args:
            hypothesis: Hypothesis to check
            supporting_summaries: Supporting summaries

        Returns:
            Tuple of (passes_check, reason)
        """
        # Check if hypothesis has enough supporting evidence
        if len(supporting_summaries) < 1:
            return False, "No supporting summaries"

        # Check if hypothesis text is reasonable length
        if len(hypothesis.text) < 20:
            return False, "Hypothesis too short"

        if len(hypothesis.text) > 1000:
            return False, "Hypothesis too long"

        # Check confidence
        if hypothesis.confidence < 0.3:
            return False, "Very low confidence"

        # Check if hypothesis contains question or claim indicators
        question_indicators = ["?", "whether", "how", "what", "why", "could", "would", "might"]
        claim_indicators = ["suggests", "indicates", "shows", "demonstrates", "reveals"]

        has_question = any(ind in hypothesis.text.lower() for ind in question_indicators)
        has_claim = any(ind in hypothesis.text.lower() for ind in claim_indicators)

        if not has_question and not has_claim:
            return False, "Hypothesis doesn't appear to be a question or claim"

        return True, "Passes basic checks"
