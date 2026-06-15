"""Token estimation for context window management."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..semantic_scholar import PaperDetails
    from ..orchestration.models import ValidatedSummary

logger = logging.getLogger(__name__)

# Average characters per token (rough estimate for English text)
# This is a conservative estimate; actual ratio varies by model
CHARS_PER_TOKEN = 4.0

# Maximum characters to consider for full text (matches summarization truncation)
MAX_FULL_TEXT_CHARS = 30000


class ContextEstimator:
    """
    Estimates token counts for context window management.

    Uses a simple character-based estimation by default.
    Can optionally use tiktoken for more accurate estimation.
    """

    def __init__(
        self,
        chars_per_token: float = CHARS_PER_TOKEN,
        use_tiktoken: bool = False,
        tiktoken_encoding: str = "cl100k_base",
    ):
        """
        Initialize the context estimator.

        Args:
            chars_per_token: Average characters per token for estimation
            use_tiktoken: Whether to use tiktoken for accurate counting
            tiktoken_encoding: Tiktoken encoding to use (default: cl100k_base for GPT-4)
        """
        self.chars_per_token = chars_per_token
        self.use_tiktoken = use_tiktoken
        self._encoder = None

        if use_tiktoken:
            try:
                import tiktoken

                self._encoder = tiktoken.get_encoding(tiktoken_encoding)
                logger.info(f"Using tiktoken with encoding: {tiktoken_encoding}")
            except ImportError:
                logger.warning("tiktoken not installed, falling back to char-based estimation")
                self.use_tiktoken = False

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        if self.use_tiktoken and self._encoder is not None:
            return len(self._encoder.encode(text))

        # Character-based estimation
        return int(len(text) / self.chars_per_token)

    def estimate_paper_tokens(self, paper: PaperDetails) -> int:
        """
        Estimate tokens for a paper's content.

        Includes title, abstract, authors, and full text if available.
        Full text is truncated to MAX_FULL_TEXT_CHARS to match the
        summarization truncation behavior.

        Args:
            paper: Paper to estimate

        Returns:
            Estimated token count
        """
        parts = []

        if paper.title:
            parts.append(paper.title)

        if paper.abstract:
            parts.append(paper.abstract)

        if paper.authors:
            author_names = ", ".join(a.name or "Unknown" for a in paper.authors)
            parts.append(f"Authors: {author_names}")

        if paper.full_text:
            # Truncate to match summarization behavior
            text = paper.full_text[:MAX_FULL_TEXT_CHARS]
            parts.append(text)

        combined = "\n\n".join(parts)
        return self.estimate_tokens(combined)

    def estimate_summary_tokens(self, summary: ValidatedSummary) -> int:
        """
        Estimate tokens for a validated summary.

        Includes paper title and summary text.

        Args:
            summary: Summary to estimate

        Returns:
            Estimated token count
        """
        parts = [summary.paper_title, summary.summary]
        combined = "\n\n".join(parts)
        return self.estimate_tokens(combined)

    def estimate_papers_tokens(self, papers: list[PaperDetails]) -> int:
        """
        Estimate total tokens for a list of papers.

        Args:
            papers: List of papers

        Returns:
            Total estimated token count
        """
        return sum(self.estimate_paper_tokens(p) for p in papers)

    def estimate_summaries_tokens(self, summaries: list[ValidatedSummary]) -> int:
        """
        Estimate total tokens for a list of summaries.

        Args:
            summaries: List of summaries

        Returns:
            Total estimated token count
        """
        return sum(self.estimate_summary_tokens(s) for s in summaries)

    def will_exceed_context(
        self,
        current_tokens: int,
        additional_tokens: int,
        max_context: int,
        threshold: float = 0.8,
    ) -> bool:
        """
        Check if adding tokens would exceed context threshold.

        Args:
            current_tokens: Current token count
            additional_tokens: Tokens to add
            max_context: Maximum context window
            threshold: Threshold fraction (default 0.8 = 80%)

        Returns:
            True if adding tokens would exceed threshold
        """
        total = current_tokens + additional_tokens
        limit = int(max_context * threshold)
        return total > limit

    def remaining_capacity(
        self,
        current_tokens: int,
        max_context: int,
        threshold: float = 0.8,
    ) -> int:
        """
        Calculate remaining token capacity before hitting threshold.

        Args:
            current_tokens: Current token count
            max_context: Maximum context window
            threshold: Threshold fraction

        Returns:
            Number of tokens available before hitting threshold
        """
        limit = int(max_context * threshold)
        remaining = limit - current_tokens
        return max(0, remaining)

    def context_utilization(self, current_tokens: int, max_context: int) -> float:
        """
        Calculate context utilization as a fraction.

        Args:
            current_tokens: Current token count
            max_context: Maximum context window

        Returns:
            Utilization fraction (0-1+, can exceed 1 if over limit)
        """
        if max_context <= 0:
            return 0.0
        return current_tokens / max_context
