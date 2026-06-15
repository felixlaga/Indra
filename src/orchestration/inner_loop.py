"""
Inner Loop: The atomic search-summarize-validate unit.

Layer 1 of the recursive research agent system.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..semantic_scholar import SemanticScholarAdapter, PaperDetails, SearchFilters
    from ..llm.protocols import LLMProvider
    from ..halugate import LocalHaluGate
    from ..config.loader import InnerLoopConfig
    from .models import ValidatedSummary, ResearchHypothesis
    from ..hypothesis import HypothesisGenerator

logger = logging.getLogger(__name__)


# Agent decision prompt for intelligent paper selection
PAPER_SELECTION_PROMPT = """You are a research assistant helping to select the most relevant papers for a literature review.

## Research Query
{query}

## Candidate Papers
You have retrieved {n_papers} candidate papers. Review each paper and select between 3-20 papers to summarize in depth.

{papers_list}

## Selection Criteria
Consider the following when selecting papers:
1. **Relevance**: How directly does the paper address the research question?
2. **Diversity**: Select papers with different perspectives, methodologies, and approaches
3. **Quality signals**: Citation count, publication venue, recency
4. **Coverage**: Ensure all important aspects of the query are covered
{context_section}

## Your Task
Think step by step:
1. What key aspects of the research query need to be covered?
2. Which papers provide unique and valuable perspectives?
3. How many papers is appropriate given the query's breadth and complexity?

Then output your selection in the following JSON format:
```json
{{
    "reasoning": "Brief explanation of your selection strategy",
    "selected_papers": [
        {{"index": 1, "reason": "Why this paper was selected"}},
        {{"index": 5, "reason": "Why this paper was selected"}},
        ...
    ],
    "coverage_notes": "What aspects of the query are covered by your selection"
}}
```

Select papers by their index number (1-indexed as shown above). Choose between 3 and 20 papers."""


class InnerLoop:
    """
    The Inner Loop: atomic unit of the research agent.

    Performs:
    1. Search for papers (via Semantic Scholar)
    2. Summarize each paper (via LLM)
    3. Validate summaries (via HaluGate at ≥95% groundedness)
    4. Optionally generate hypotheses

    Two modes:
    - SEARCH_SUMMARIZE: Steps 1-3 only
    - HYPOTHESIS: Steps 1-4
    """

    def __init__(
        self,
        search_provider: SemanticScholarAdapter,
        summarizer: LLMProvider,
        halugate: LocalHaluGate,
        config: InnerLoopConfig | None = None,
        hypothesis_generator: HypothesisGenerator | None = None,
        selection_agent: LLMProvider | None = None,
    ):
        """
        Initialize the Inner Loop.

        Args:
            search_provider: Semantic Scholar adapter for paper search
            summarizer: LLM provider for summarization
            halugate: HaluGate for validation
            config: Inner loop configuration
            hypothesis_generator: Optional hypothesis generator for HYPOTHESIS mode
            selection_agent: Optional LLM provider for intelligent paper selection.
                           If not provided, uses the summarizer for selection.
        """
        self.search_provider = search_provider
        self.summarizer = summarizer
        self.halugate = halugate
        self.hypothesis_generator = hypothesis_generator
        # Use dedicated selection agent or fall back to summarizer
        self.selection_agent = selection_agent or summarizer

        # Load config with defaults
        if config is None:
            from ..config.loader import InnerLoopConfig
            config = InnerLoopConfig()

        self.groundedness_threshold = config.groundedness_threshold
        self.max_papers = config.max_papers_per_iteration
        self.parallel = config.parallel_summarization
        self.max_concurrency = config.max_summarization_concurrency
        self.fetch_full_text = config.fetch_full_text

        # Agent-based selection settings
        self.candidate_fetch_limit = 50  # Fetch more papers for agent to choose from
        self.enable_agent_selection = True  # Can be disabled for testing

    def _format_papers_for_selection(
        self,
        papers: list[PaperDetails],
    ) -> str:
        """
        Format papers as a numbered list for the selection agent.

        Args:
            papers: List of papers to format

        Returns:
            Formatted string with paper information
        """
        lines = []
        for i, paper in enumerate(papers, 1):
            # Basic info
            title = paper.title or "Unknown Title"
            year = paper.year or "N/A"
            citations = paper.citation_count or 0
            venue = paper.venue or "Unknown Venue"

            # Authors (first 3)
            if paper.authors:
                author_names = [a.name for a in paper.authors[:3] if a.name]
                authors_str = ", ".join(author_names)
                if len(paper.authors) > 3:
                    authors_str += " et al."
            else:
                authors_str = "Unknown Authors"

            # Abstract (truncated)
            abstract = paper.abstract or "No abstract available"
            if len(abstract) > 400:
                abstract = abstract[:400] + "..."

            lines.append(
                f"### Paper {i}\n"
                f"**Title**: {title}\n"
                f"**Authors**: {authors_str}\n"
                f"**Year**: {year} | **Citations**: {citations} | **Venue**: {venue}\n"
                f"**Abstract**: {abstract}\n"
            )

        return "\n".join(lines)

    def _parse_selection_response(
        self,
        response: str,
        max_papers: int,
    ) -> list[int]:
        """
        Parse the agent's selection response to extract paper indices.

        Args:
            response: The agent's response text
            max_papers: Maximum number of papers (for validation)

        Returns:
            List of 0-indexed paper indices
        """
        # Try to extract JSON from the response
        json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if "selected_papers" in data:
                    indices = []
                    for item in data["selected_papers"]:
                        if isinstance(item, dict) and "index" in item:
                            idx = item["index"] - 1  # Convert to 0-indexed
                            if 0 <= idx < max_papers:
                                indices.append(idx)
                        elif isinstance(item, int):
                            idx = item - 1
                            if 0 <= idx < max_papers:
                                indices.append(idx)
                    if indices:
                        logger.info(
                            f"Agent selected {len(indices)} papers. "
                            f"Reasoning: {data.get('reasoning', 'N/A')}"
                        )
                        return indices
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON from agent response")

        # Fallback: look for numbers in the response
        # Match patterns like "Paper 1", "papers 1, 2, 3", "#1", etc.
        numbers = re.findall(r"(?:paper\s*#?\s*|#)(\d+)", response.lower())
        if numbers:
            indices = [int(n) - 1 for n in numbers if 0 < int(n) <= max_papers]
            if indices:
                logger.info(f"Fallback parsing: found {len(indices)} paper indices")
                return list(set(indices))  # Deduplicate

        # Last resort: just take all papers up to the limit
        logger.warning("Could not parse agent selection, using all papers")
        return list(range(min(max_papers, self.max_papers)))

    async def _agent_select_papers(
        self,
        query: str,
        papers: list[PaperDetails],
        existing_context: str | None = None,
    ) -> list[PaperDetails]:
        """
        Use an LLM agent to intelligently select papers from candidates.

        Args:
            query: The research query
            papers: List of candidate papers
            existing_context: Optional context from existing summaries

        Returns:
            List of selected papers
        """
        if len(papers) <= self.max_papers:
            # Not enough papers to warrant selection
            logger.info(
                f"Only {len(papers)} papers found, skipping agent selection"
            )
            return papers

        # Format papers for the agent
        papers_list = self._format_papers_for_selection(papers)

        # Build context section
        context_section = ""
        if existing_context:
            context_section = f"\n## Existing Research Context\n{existing_context}\n"

        # Build the prompt
        prompt = PAPER_SELECTION_PROMPT.format(
            query=query,
            n_papers=len(papers),
            papers_list=papers_list,
            context_section=context_section,
        )

        # Get agent's selection
        try:
            response = await self.selection_agent.complete(
                prompt=prompt,
                system_prompt=(
                    "You are an expert research assistant skilled at evaluating "
                    "academic papers and selecting the most relevant ones for "
                    "literature reviews. Be thorough but selective."
                ),
                temperature=0.3,  # Lower temperature for more consistent selection
                max_tokens=2000,
            )

            # Parse the selection
            selected_indices = self._parse_selection_response(response, len(papers))

            # Ensure we have at least 3 papers
            if len(selected_indices) < 3:
                logger.warning(
                    f"Agent selected only {len(selected_indices)} papers, "
                    f"taking top {min(self.max_papers, len(papers))} instead"
                )
                selected_indices = list(range(min(self.max_papers, len(papers))))

            # Cap at max_papers
            if len(selected_indices) > self.max_papers:
                logger.info(
                    f"Agent selected {len(selected_indices)} papers, "
                    f"capping at {self.max_papers}"
                )
                selected_indices = selected_indices[: self.max_papers]

            selected_papers = [papers[i] for i in selected_indices]
            logger.info(
                f"Agent selected {len(selected_papers)} papers from "
                f"{len(papers)} candidates"
            )
            return selected_papers

        except Exception as e:
            logger.warning(f"Agent selection failed: {e}, using top-K fallback")
            return papers[: self.max_papers]

    async def search_and_summarize(
        self,
        query: str,
        filters: SearchFilters | None = None,
        limit: int | None = None,
        existing_context: str | None = None,
    ) -> tuple[list[PaperDetails], list[ValidatedSummary]]:
        """
        Search for papers and generate validated summaries.

        Uses intelligent agent-based paper selection when enabled.
        Only returns summaries that pass HaluGate at the configured
        groundedness threshold (default 95%).

        Args:
            query: Search query string
            filters: Optional search filters
            limit: Maximum papers to process (overrides config)
            existing_context: Optional context from previous summaries
                            (used by agent for better selection)

        Returns:
            Tuple of (papers_found, validated_summaries)
        """
        final_limit = limit or self.max_papers

        # Step 1: Search for papers with generous limit for agent selection
        if self.enable_agent_selection:
            search_limit = self.candidate_fetch_limit
        else:
            search_limit = final_limit

        logger.info(f"Searching for papers: query='{query}', limit={search_limit}")
        papers = await self.search_provider.search_papers(
            query=query,
            filters=filters,
            limit=search_limit,
        )
        logger.info(f"Found {len(papers)} candidate papers")

        if not papers:
            return [], []

        # Fetch full paper details (including PDFs if configured)
        paper_ids = [p.paper_id for p in papers]
        try:
            if self.fetch_full_text:
                detailed_papers = await self.search_provider.fetch_papers_with_text(paper_ids)
            else:
                detailed_papers = await self.search_provider.fetch_papers(paper_ids)
        except Exception as e:
            logger.warning(f"Failed to fetch paper details: {e}, using search results")
            from ..semantic_scholar import PaperDetails
            detailed_papers = [PaperDetails.model_validate(p.model_dump()) for p in papers]

        # Step 2: Agent-based paper selection
        if self.enable_agent_selection and len(detailed_papers) > final_limit:
            logger.info("Starting agent-based paper selection...")
            selected_papers = await self._agent_select_papers(
                query=query,
                papers=detailed_papers,
                existing_context=existing_context,
            )
        else:
            selected_papers = detailed_papers[:final_limit]

        logger.info(f"Selected {len(selected_papers)} papers for summarization")

        # Step 3 & 4: Summarize and validate each paper
        if self.parallel:
            summaries = await self._summarize_parallel(selected_papers)
        else:
            summaries = await self._summarize_sequential(selected_papers)

        logger.info(
            f"Validated {len(summaries)}/{len(selected_papers)} summaries "
            f"at ≥{self.groundedness_threshold:.0%} groundedness"
        )

        return selected_papers, summaries

    async def _summarize_parallel(
        self,
        papers: list[PaperDetails],
    ) -> list[ValidatedSummary]:
        """Summarize papers in parallel with concurrency limit."""
        from .models import ValidatedSummary

        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def process_paper(paper: PaperDetails) -> ValidatedSummary | None:
            async with semaphore:
                return await self._summarize_and_validate(paper)

        tasks = [process_paper(p) for p in papers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        summaries = []
        for result in results:
            if isinstance(result, ValidatedSummary):
                summaries.append(result)
            elif isinstance(result, Exception):
                logger.warning(f"Summarization failed: {result}")

        return summaries

    async def _summarize_sequential(
        self,
        papers: list[PaperDetails],
    ) -> list[ValidatedSummary]:
        """Summarize papers sequentially."""
        summaries = []

        for paper in papers:
            try:
                summary = await self._summarize_and_validate(paper)
                if summary:
                    summaries.append(summary)
            except Exception as e:
                logger.warning(f"Failed to summarize paper {paper.paper_id}: {e}")

        return summaries

    async def _summarize_and_validate(
        self,
        paper: PaperDetails,
    ) -> ValidatedSummary | None:
        """
        Summarize a single paper and validate with HaluGate.

        Returns None if validation fails.
        """
        from .models import ValidatedSummary
        from ..summarize import summarize_paper

        # Use the Overseer pattern: generate-validate-retry
        context = paper.full_text or paper.abstract or ""
        if not context:
            logger.warning(f"No content for paper {paper.paper_id}")
            return None

        question = f"Summarize the paper: {paper.title}"
        best_summary = None
        best_groundedness = 0.0

        # Try up to 2 times with stricter guidance on retry
        for attempt in range(2):
            guidance = None
            if attempt > 0:
                guidance = (
                    "Only include claims directly supported by the provided paper content. "
                    "Prefer omission over speculation. Be precise and factual."
                )

            # Generate summary
            try:
                summary_text = await summarize_paper(
                    paper=paper,
                    provider=self.summarizer,
                    guidance=guidance,
                )
            except Exception as e:
                logger.warning(f"Summarization error for {paper.paper_id}: {e}")
                continue

            # Validate with HaluGate
            try:
                result = await self.halugate.validate(
                    context=context,
                    question=question,
                    answer=summary_text,
                )
                groundedness = self.halugate.compute_groundedness(result, summary_text)
            except Exception as e:
                logger.warning(f"Validation error for {paper.paper_id}: {e}")
                continue

            logger.debug(
                f"Paper {paper.paper_id} attempt {attempt + 1}: "
                f"groundedness={groundedness:.2%}"
            )

            # Track best attempt
            if groundedness > best_groundedness:
                best_groundedness = groundedness
                best_summary = summary_text

            # Check if good enough
            if groundedness >= self.groundedness_threshold and result.nli_contradictions == 0:
                return ValidatedSummary(
                    paper_id=paper.paper_id,
                    paper_title=paper.title or "Unknown",
                    summary=summary_text,
                    groundedness=groundedness,
                    timestamp=datetime.now(),
                )

        # Return best attempt if it meets a lower threshold (for partial results)
        if best_summary and best_groundedness >= 0.7:
            logger.warning(
                f"Paper {paper.paper_id} only achieved {best_groundedness:.2%} groundedness "
                f"(below {self.groundedness_threshold:.0%} threshold)"
            )
            return ValidatedSummary(
                paper_id=paper.paper_id,
                paper_title=paper.title or "Unknown",
                summary=best_summary,
                groundedness=best_groundedness,
                timestamp=datetime.now(),
            )

        logger.warning(
            f"Paper {paper.paper_id} failed validation after 2 attempts "
            f"(best groundedness: {best_groundedness:.2%})"
        )
        return None

    async def generate_hypotheses(
        self,
        summaries: list[ValidatedSummary],
        branch_id: str,
        context: str | None = None,
    ) -> list[ResearchHypothesis]:
        """
        Generate research hypotheses from validated summaries.

        Requires hypothesis_generator to be configured.

        Args:
            summaries: List of validated summaries
            branch_id: ID of the branch these hypotheses belong to
            context: Optional additional context

        Returns:
            List of generated research hypotheses
        """
        if not self.hypothesis_generator:
            logger.warning("No hypothesis generator configured")
            return []

        if not summaries:
            logger.warning("No summaries to generate hypotheses from")
            return []

        return await self.hypothesis_generator.generate(
            summaries=summaries,
            branch_id=branch_id,
            context=context,
        )

    async def run(
        self,
        query: str,
        branch_id: str,
        filters: SearchFilters | None = None,
        generate_hypotheses: bool = False,
        limit: int | None = None,
        existing_summaries: list[ValidatedSummary] | None = None,
    ) -> tuple[list[PaperDetails], list[ValidatedSummary], list[ResearchHypothesis] | None]:
        """
        Run the complete inner loop.

        Args:
            query: Search query
            branch_id: Branch ID for hypothesis generation
            filters: Optional search filters
            generate_hypotheses: Whether to generate hypotheses (HYPOTHESIS mode)
            limit: Maximum papers to process
            existing_summaries: Optional list of existing summaries for agent context

        Returns:
            Tuple of (papers, summaries, hypotheses or None)
        """
        # Build existing context string from summaries for agent selection
        existing_context = None
        if existing_summaries:
            context_parts = [
                f"- {s.paper_title}: {s.summary[:200]}..."
                for s in existing_summaries[:10]  # Limit to avoid token overflow
            ]
            existing_context = (
                "Previously summarized papers:\n" + "\n".join(context_parts)
            )

        papers, summaries = await self.search_and_summarize(
            query=query,
            filters=filters,
            limit=limit,
            existing_context=existing_context,
        )

        hypotheses = None
        if generate_hypotheses and summaries:
            hypotheses = await self.generate_hypotheses(
                summaries=summaries,
                branch_id=branch_id,
            )

        return papers, summaries, hypotheses
