"""Composite search provider aggregating multiple sources."""

import asyncio
import logging
from typing import Literal

from ..semantic_scholar.protocols import (
    PaperSearchProvider,
    PDFExtractor,
    CitationProvider,
)
from ..semantic_scholar.models import PaperSearchResult, PaperDetails, SearchFilters
from .deduplication import deduplicate_papers

logger = logging.getLogger(__name__)


class CompositeSearchProvider(PaperSearchProvider, PDFExtractor, CitationProvider):
    """
    Aggregates multiple paper search providers.

    Supports three strategies:
    - "parallel": Search all providers concurrently, merge and deduplicate
    - "fallback": Try providers in order until one succeeds
    - "single": Use only the first provider (for single-provider configs)

    Usage:
        from src.semantic_scholar.adapters import SemanticScholarAdapter
        from src.arxiv.adapters import ArXivAdapter

        providers = [SemanticScholarAdapter(), ArXivAdapter()]

        async with CompositeSearchProvider(
            providers=providers,
            citation_provider=providers[0],  # SS has citations
            strategy="parallel",
        ) as composite:
            results = await composite.search_papers("transformer attention")
    """

    def __init__(
        self,
        providers: list[PaperSearchProvider],
        citation_provider: CitationProvider | None = None,
        strategy: Literal["parallel", "fallback", "single"] = "parallel",
        deduplicate: bool = True,
        prefer_provider: str = "semantic_scholar",
    ):
        """
        Initialize composite provider.

        Args:
            providers: List of search providers to use
            citation_provider: Separate provider for citations (if different from search)
            strategy: How to combine providers
            deduplicate: Whether to deduplicate results from multiple providers
            prefer_provider: Which provider's metadata to prefer for duplicates
        """
        self._providers = providers
        self._citation_provider = citation_provider
        self._strategy = strategy
        self._deduplicate = deduplicate
        self._prefer_provider = prefer_provider
        self._entered = False

    async def __aenter__(self) -> "CompositeSearchProvider":
        """Enter async context for all providers."""
        for provider in self._providers:
            if hasattr(provider, "__aenter__"):
                await provider.__aenter__()

        if self._citation_provider and hasattr(self._citation_provider, "__aenter__"):
            # Only enter if not already in providers list
            if self._citation_provider not in self._providers:
                await self._citation_provider.__aenter__()

        self._entered = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context for all providers."""
        for provider in self._providers:
            if hasattr(provider, "__aexit__"):
                await provider.__aexit__(exc_type, exc_val, exc_tb)

        if self._citation_provider and hasattr(self._citation_provider, "__aexit__"):
            # Only exit if not already in providers list
            if self._citation_provider not in self._providers:
                await self._citation_provider.__aexit__(exc_type, exc_val, exc_tb)

        self._entered = False

    async def search_papers(
        self,
        query: str,
        filters: SearchFilters | None = None,
        limit: int = 100,
    ) -> list[PaperSearchResult]:
        """Search papers across all providers."""
        if self._strategy == "single" or len(self._providers) == 1:
            return await self._providers[0].search_papers(query, filters, limit)

        elif self._strategy == "parallel":
            return await self._search_parallel(query, filters, limit)

        elif self._strategy == "fallback":
            return await self._search_fallback(query, filters, limit)

        raise ValueError(f"Unknown strategy: {self._strategy}")

    async def _search_parallel(
        self,
        query: str,
        filters: SearchFilters | None,
        limit: int,
    ) -> list[PaperSearchResult]:
        """Search all providers in parallel and merge results."""
        tasks = [
            provider.search_papers(query, filters, limit)
            for provider in self._providers
        ]

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        all_papers: list[PaperSearchResult] = []
        for i, results in enumerate(results_lists):
            if isinstance(results, Exception):
                logger.warning(f"Provider {i} failed: {results}")
                continue
            all_papers.extend(results)

        if self._deduplicate:
            all_papers = deduplicate_papers(
                all_papers,
                prefer_provider=self._prefer_provider,
            )

        return all_papers[:limit]

    async def _search_fallback(
        self,
        query: str,
        filters: SearchFilters | None,
        limit: int,
    ) -> list[PaperSearchResult]:
        """Try providers in order until one succeeds."""
        for i, provider in enumerate(self._providers):
            try:
                results = await provider.search_papers(query, filters, limit)
                if results:
                    return results
            except Exception as e:
                logger.warning(f"Provider {i} failed, trying next: {e}")
                continue

        return []

    async def fetch_papers(
        self,
        paper_ids: list[str],
    ) -> list[PaperDetails]:
        """Fetch papers, routing to correct provider by ID prefix."""
        # Group IDs by provider
        arxiv_ids = [pid for pid in paper_ids if pid.startswith("arxiv:")]
        ss_ids = [pid for pid in paper_ids if not pid.startswith("arxiv:")]

        all_papers: list[PaperDetails] = []

        # Fetch from each provider
        for provider in self._providers:
            # Check if this is an ArXivAdapter by looking for _default_categories
            if hasattr(provider, "_default_categories"):  # ArXivAdapter
                if arxiv_ids:
                    papers = await provider.fetch_papers(arxiv_ids)
                    all_papers.extend(papers)
            else:  # SemanticScholarAdapter
                if ss_ids:
                    papers = await provider.fetch_papers(ss_ids)
                    all_papers.extend(papers)

        return all_papers

    async def extract_text(self, pdf_url: str) -> str:
        """Extract text using the first available extractor."""
        for provider in self._providers:
            if hasattr(provider, "extract_text"):
                return await provider.extract_text(pdf_url)
        raise RuntimeError("No PDF extractor available")

    async def fetch_papers_with_text(
        self,
        paper_ids: list[str],
    ) -> list[PaperDetails]:
        """Fetch papers with full text extracted from PDFs."""
        # Group IDs by provider
        arxiv_ids = [pid for pid in paper_ids if pid.startswith("arxiv:")]
        ss_ids = [pid for pid in paper_ids if not pid.startswith("arxiv:")]

        all_papers: list[PaperDetails] = []

        # Fetch from each provider
        for provider in self._providers:
            if hasattr(provider, "fetch_papers_with_text"):
                # Check if this is an ArXivAdapter
                if hasattr(provider, "_default_categories"):  # ArXivAdapter
                    if arxiv_ids:
                        papers = await provider.fetch_papers_with_text(arxiv_ids)
                        all_papers.extend(papers)
                else:  # SemanticScholarAdapter
                    if ss_ids:
                        papers = await provider.fetch_papers_with_text(ss_ids)
                        all_papers.extend(papers)

        return all_papers

    # Citation methods delegate to citation_provider
    async def get_citations(
        self,
        paper_id: str,
        limit: int = 100,
    ) -> list[PaperDetails]:
        """Get citations using the citation provider."""
        if not self._citation_provider:
            raise RuntimeError("No citation provider configured")
        return await self._citation_provider.get_citations(paper_id, limit)

    async def get_references(
        self,
        paper_id: str,
        limit: int = 100,
    ) -> list[PaperDetails]:
        """Get references using the citation provider."""
        if not self._citation_provider:
            raise RuntimeError("No citation provider configured")
        return await self._citation_provider.get_references(paper_id, limit)

    async def get_citations_batch(
        self,
        paper_ids: list[str],
        limit_per_paper: int = 20,
    ) -> list[PaperDetails]:
        """Get citations for multiple papers."""
        if not self._citation_provider:
            raise RuntimeError("No citation provider configured")
        return await self._citation_provider.get_citations_batch(paper_ids, limit_per_paper)

    async def get_references_batch(
        self,
        paper_ids: list[str],
        limit_per_paper: int = 20,
    ) -> list[PaperDetails]:
        """Get references for multiple papers."""
        if not self._citation_provider:
            raise RuntimeError("No citation provider configured")
        return await self._citation_provider.get_references_batch(paper_ids, limit_per_paper)
