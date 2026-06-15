"""
Iteration Loop: Depth expansion via citation graph traversal.

Layer 2 of the recursive research agent system.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..semantic_scholar import SemanticScholarAdapter, PaperDetails
    from ..config.loader import IterationLoopConfig, InnerLoopConfig
    from .models import Branch, IterationResult, InnerLoopMode
    from .inner_loop import InnerLoop
    from ..context.estimator import ContextEstimator

logger = logging.getLogger(__name__)


class IterationLoop:
    """
    The Iteration Loop: expands research depth via citation traversal.

    Each iteration:
    1. If first iteration: run Inner Loop with initial query
    2. If subsequent: find papers citing/referenced by previous papers
    3. Run Inner Loop on new papers
    4. Track context usage

    Citation graph expansion:
    - Iter 1: query → papers P1-P5
    - Iter 2: citations(P1-P5) → papers P6-P20
    - Iter 3: citations(P6-P20) → papers P21-P80
    - ... exponential growth
    """

    def __init__(
        self,
        inner_loop: InnerLoop,
        search_provider: SemanticScholarAdapter,
        context_estimator: ContextEstimator,
        config: IterationLoopConfig | None = None,
    ):
        """
        Initialize the Iteration Loop.

        Args:
            inner_loop: Inner Loop for search-summarize-validate
            search_provider: Semantic Scholar adapter (for citations)
            context_estimator: Token/context estimator
            config: Iteration loop configuration
        """
        self.inner_loop = inner_loop
        self.search_provider = search_provider
        self.context_estimator = context_estimator

        # Load config with defaults
        if config is None:
            from ..config.loader import IterationLoopConfig
            config = IterationLoopConfig()

        self.max_iterations = config.max_iterations_per_branch
        self.citation_depth = config.citation_depth
        self.max_citations_per_paper = config.max_citations_per_paper
        self.max_references_per_paper = config.max_references_per_paper
        self.include_references = config.include_references

    async def run_iteration(
        self,
        branch: Branch,
    ) -> IterationResult:
        """
        Run a single iteration on a branch.

        If first iteration (no previous iterations), searches using the branch query.
        For subsequent iterations, finds papers that cite/reference papers from
        the previous iteration.

        Args:
            branch: The branch to run iteration on

        Returns:
            IterationResult with papers found and validated summaries
        """
        from .models import IterationResult, InnerLoopMode

        iteration_num = len(branch.iterations) + 1
        logger.info(f"Running iteration {iteration_num} on branch {branch.id}")

        generate_hypotheses = branch.mode == InnerLoopMode.HYPOTHESIS

        if iteration_num == 1:
            # First iteration: search using query
            papers, summaries, hypotheses = await self.inner_loop.run(
                query=branch.query,
                branch_id=branch.id,
                generate_hypotheses=generate_hypotheses,
                filters=branch.filters,
            )
        else:
            # Subsequent iterations: follow citation graph
            previous_iteration = branch.iterations[-1]
            previous_paper_ids = [p.paper_id for p in previous_iteration.papers_found]

            # Get citing/referenced papers
            papers = await self._get_related_papers(
                paper_ids=previous_paper_ids,
                exclude_ids=set(branch.accumulated_papers.keys()),
            )

            if not papers:
                logger.info(f"No new papers found for iteration {iteration_num}")
                return IterationResult(
                    iteration_number=iteration_num,
                    papers_found=[],
                    summaries=[],
                    hypotheses=None if not generate_hypotheses else [],
                    context_tokens_used=0,
                    timestamp=datetime.now(),
                )

            # Fetch full text for papers (if configured)
            paper_ids = [p.paper_id for p in papers]
            logger.info(f"Fetching full text for {len(paper_ids)} papers")
            try:
                if self.inner_loop.fetch_full_text:
                    papers = await self.search_provider.fetch_papers_with_text(paper_ids)
                else:
                    papers = await self.search_provider.fetch_papers(paper_ids)
                logger.info(f"Fetched details for {len(papers)} papers")
            except Exception as e:
                logger.warning(f"Failed to fetch paper details: {e}, using basic info")

            # Summarize the related papers directly (in parallel like inner_loop does)
            logger.info(f"Starting summarization of {len(papers)} papers")
            if self.inner_loop.parallel:
                summaries = await self.inner_loop._summarize_parallel(papers)
            else:
                summaries = await self.inner_loop._summarize_sequential(papers)

            # Generate hypotheses if in hypothesis mode
            hypotheses = None
            if generate_hypotheses and summaries:
                hypotheses = await self.inner_loop.generate_hypotheses(
                    summaries=summaries,
                    branch_id=branch.id,
                )

        # Estimate context tokens used
        context_tokens = self._estimate_iteration_tokens(papers, summaries)

        result = IterationResult(
            iteration_number=iteration_num,
            papers_found=papers,
            summaries=summaries,
            hypotheses=hypotheses,
            context_tokens_used=context_tokens,
            timestamp=datetime.now(),
        )

        logger.info(
            f"Iteration {iteration_num} complete: "
            f"{len(papers)} papers, {len(summaries)} summaries, "
            f"{len(hypotheses) if hypotheses else 0} hypotheses, "
            f"{context_tokens} tokens"
        )

        return result

    async def _get_related_papers(
        self,
        paper_ids: list[str],
        exclude_ids: set[str],
    ) -> list[PaperDetails]:
        """
        Get papers related to the given papers via citations/references.

        Args:
            paper_ids: IDs of papers to find relations for
            exclude_ids: Paper IDs to exclude (already processed)

        Returns:
            List of new related papers
        """
        all_papers: dict[str, PaperDetails] = {}

        # Get citing papers (papers that cite these)
        logger.info(f"Fetching citations for {len(paper_ids)} papers")
        try:
            citations = await self.search_provider.get_citations_batch(
                paper_ids=paper_ids,
                limit_per_paper=self.max_citations_per_paper,
            )
            for paper in citations:
                if paper.paper_id not in exclude_ids:
                    all_papers[paper.paper_id] = paper
        except Exception as e:
            logger.warning(f"Failed to get citations: {e}")

        # Get referenced papers (papers these cite)
        if self.include_references:
            logger.info(f"Fetching references for {len(paper_ids)} papers")
            try:
                references = await self.search_provider.get_references_batch(
                    paper_ids=paper_ids,
                    limit_per_paper=self.max_references_per_paper,
                )
                for paper in references:
                    if paper.paper_id not in exclude_ids:
                        all_papers[paper.paper_id] = paper
            except Exception as e:
                logger.warning(f"Failed to get references: {e}")

        papers = list(all_papers.values())

        # Limit to max_papers from inner_loop config to avoid processing too many
        max_papers = self.inner_loop.max_papers
        if len(papers) > max_papers:
            # Sort by citation count and take top papers
            papers.sort(key=lambda p: p.citation_count or 0, reverse=True)
            papers = papers[:max_papers]
            logger.info(f"Found {len(all_papers)} related papers, limited to top {max_papers}")
        else:
            logger.info(f"Found {len(papers)} new related papers")

        return papers

    def _estimate_iteration_tokens(
        self,
        papers: list[PaperDetails],
        summaries: list,
    ) -> int:
        """Estimate tokens used by an iteration."""
        tokens = 0

        # Estimate paper content tokens
        for paper in papers:
            tokens += self.context_estimator.estimate_paper_tokens(paper)

        # Estimate summary tokens
        for summary in summaries:
            tokens += self.context_estimator.estimate_summary_tokens(summary)

        return tokens

    async def run_until_threshold(
        self,
        branch: Branch,
        context_threshold: float = 0.8,
    ) -> list[IterationResult]:
        """
        Run iterations until context threshold is reached.

        Args:
            branch: Branch to run on
            context_threshold: Stop when context utilization exceeds this

        Returns:
            List of all iteration results
        """
        results = []

        while len(branch.iterations) < self.max_iterations:
            # Check context utilization
            if branch.context_utilization >= context_threshold:
                logger.info(
                    f"Branch {branch.id} context threshold reached "
                    f"({branch.context_utilization:.1%})"
                )
                break

            # Run iteration
            result = await self.run_iteration(branch)
            results.append(result)

            # Add iteration to branch
            branch.add_iteration(result)

            # If no new papers found, stop
            if not result.papers_found:
                logger.info(f"Branch {branch.id} exhausted (no new papers)")
                break

        return results

    async def get_citing_papers(
        self,
        paper_ids: list[str],
        limit_per_paper: int | None = None,
    ) -> list[PaperDetails]:
        """
        Get papers that cite the given papers.

        Args:
            paper_ids: IDs of papers to find citations for
            limit_per_paper: Max citations to fetch per paper

        Returns:
            List of citing papers (deduplicated)
        """
        limit = limit_per_paper or self.max_citations_per_paper
        return await self.search_provider.get_citations_batch(
            paper_ids=paper_ids,
            limit_per_paper=limit,
        )

    async def get_referenced_papers(
        self,
        paper_ids: list[str],
        limit_per_paper: int | None = None,
    ) -> list[PaperDetails]:
        """
        Get papers referenced by the given papers.

        Args:
            paper_ids: IDs of papers to find references for
            limit_per_paper: Max references to fetch per paper

        Returns:
            List of referenced papers (deduplicated)
        """
        limit = limit_per_paper or self.max_references_per_paper
        return await self.search_provider.get_references_batch(
            paper_ids=paper_ids,
            limit_per_paper=limit,
        )
