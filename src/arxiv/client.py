"""Low-level arXiv API client with rate limiting."""

import asyncio
import logging
import time

import arxiv

from ..settings import ARXIV_RATE_LIMIT_SECONDS

logger = logging.getLogger(__name__)


class ArXivRateLimiter:
    """Rate limiter enforcing minimum delay between arXiv requests."""

    def __init__(self, min_interval: float = 3.0):
        """
        Initialize rate limiter.

        Args:
            min_interval: Minimum seconds between requests (default: 3.0 per arXiv guidelines)
        """
        self._min_interval = min_interval
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire rate limit slot, waiting if necessary."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request_time = time.monotonic()


class ArXivClient:
    """Async wrapper around the arxiv Python library."""

    def __init__(
        self,
        rate_limit_seconds: float = ARXIV_RATE_LIMIT_SECONDS,
        max_retries: int = 0,
    ):
        """
        Initialize arXiv client.

        Args:
            rate_limit_seconds: Minimum seconds between requests
            max_retries: Maximum retries on failure
        """
        self._rate_limiter = ArXivRateLimiter(rate_limit_seconds)
        self._max_retries = max_retries
        self._client = arxiv.Client(
            page_size=100,
            delay_seconds=rate_limit_seconds,
            num_retries=max_retries,
        )

    async def search(
        self,
        query: str,
        max_results: int = 100,
        sort_by: arxiv.SortCriterion = arxiv.SortCriterion.Relevance,
        sort_order: arxiv.SortOrder = arxiv.SortOrder.Descending,
        categories: list[str] | None = None,
    ) -> list[arxiv.Result]:
        """
        Search arXiv for papers matching query.

        Args:
            query: Search query (supports arXiv query syntax)
            max_results: Maximum results to return
            sort_by: Sort criterion (Relevance, LastUpdatedDate, SubmittedDate)
            sort_order: Sort order (Ascending, Descending)
            categories: Optional list of arXiv categories to filter (e.g., ["cs.LG", "cs.AI"])

        Returns:
            List of arxiv.Result objects
        """
        # Build query with optional category filter
        if categories:
            cat_query = " OR ".join(f"cat:{cat}" for cat in categories)
            full_query = f"({query}) AND ({cat_query})"
        else:
            full_query = query

        search = arxiv.Search(
            query=full_query,
            max_results=max_results,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        # Run in thread pool since arxiv.py is synchronous
        await self._rate_limiter.acquire()
        results = await asyncio.to_thread(lambda: list(self._client.results(search)))

        logger.debug(f"arXiv search '{query}' returned {len(results)} results")
        return results

    async def get_paper(self, arxiv_id: str) -> arxiv.Result | None:
        """
        Fetch a single paper by arXiv ID.

        Args:
            arxiv_id: arXiv paper ID (e.g., "2301.00001" or "arxiv:2301.00001")

        Returns:
            arxiv.Result or None if not found
        """
        # Strip any prefix
        clean_id = arxiv_id.removeprefix("arxiv:").removeprefix("arXiv:")

        search = arxiv.Search(id_list=[clean_id])
        await self._rate_limiter.acquire()
        results = await asyncio.to_thread(lambda: list(self._client.results(search)))

        return results[0] if results else None

    async def get_papers(self, arxiv_ids: list[str]) -> list[arxiv.Result]:
        """
        Fetch multiple papers by arXiv ID.

        Args:
            arxiv_ids: List of arXiv paper IDs

        Returns:
            List of arxiv.Result objects
        """
        clean_ids = [
            id.removeprefix("arxiv:").removeprefix("arXiv:") for id in arxiv_ids
        ]

        search = arxiv.Search(id_list=clean_ids)
        await self._rate_limiter.acquire()
        results = await asyncio.to_thread(lambda: list(self._client.results(search)))

        return results

    async def download_pdf(self, result: arxiv.Result) -> bytes:
        """
        Download PDF for a paper.

        Args:
            result: arxiv.Result object

        Returns:
            PDF content as bytes
        """
        await self._rate_limiter.acquire()

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            path = await asyncio.to_thread(result.download_pdf, dirpath=tmpdir)
            return Path(path).read_bytes()
