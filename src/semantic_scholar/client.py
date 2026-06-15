"""Async HTTP client for Semantic Scholar API with rate limiting."""

import asyncio
import logging
import time
from typing import Any

import httpx

from ..settings import (
    SEMANTIC_SCHOLAR_API_KEY,
    SEMANTIC_SCHOLAR_BASE_URL,
    RATE_LIMIT_REQUESTS_PER_SECOND,
    RATE_LIMIT_REQUESTS_PER_SECOND_NO_KEY,
    MAX_RETRIES,
    RETRY_BACKOFF_FACTOR,
)

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, requests_per_second: float):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until we can make another request."""
        async with self._lock:
            now = time.monotonic()
            time_since_last = now - self.last_request_time
            if time_since_last < self.min_interval:
                await asyncio.sleep(self.min_interval - time_since_last)
            self.last_request_time = time.monotonic()


class SemanticScholarClient:
    """Async client for Semantic Scholar API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or SEMANTIC_SCHOLAR_API_KEY
        self.base_url = SEMANTIC_SCHOLAR_BASE_URL
        if not self.base_url:
            raise ValueError(
                "Semantic Scholar base URL required. Set SEMANTIC_SCHOLAR_BASE_URL in .env"
            )

        # Set rate limit based on whether we have an API key
        rate_limit = (
            RATE_LIMIT_REQUESTS_PER_SECOND
            if self.api_key
            else RATE_LIMIT_REQUESTS_PER_SECOND_NO_KEY
        )
        self.rate_limiter = RateLimiter(rate_limit)

        # Build headers
        self.headers: dict[str, str] = {}
        if self.api_key:
            self.headers["x-api-key"] = self.api_key
            logger.info("Semantic Scholar client initialized with API key")
        else:
            logger.warning("No API key provided - rate limiting will be strict")

        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "SemanticScholarClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self.headers,
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                "Client not initialized. Use 'async with' context manager."
            )
        return self._client

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make a request with rate limiting and exponential backoff retry."""
        last_exception: Exception | None = None
        last_response: httpx.Response | None = None

        for attempt in range(MAX_RETRIES):
            await self.rate_limiter.acquire()
            logger.debug(f"Request attempt {attempt + 1}/{MAX_RETRIES}: {method} {url}")

            try:
                response = await self.client.request(method, url, **kwargs)
                last_response = response
                logger.debug(f"Response status: {response.status_code}")

                # Handle rate limiting (429) with exponential backoff
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 0))
                    # Exponential backoff: 10s, 20s, 40s, 80s, 160s
                    backoff = max(retry_after, 10 * (2 ** attempt))
                    logger.warning(f"Rate limited (429), waiting {backoff}s (attempt {attempt + 1})")
                    await asyncio.sleep(backoff)
                    continue

                # Handle server errors with retry
                if response.status_code in (500, 502, 503, 504):
                    backoff = RETRY_BACKOFF_FACTOR ** attempt
                    logger.warning(f"Server error ({response.status_code}), backoff {backoff}s")
                    await asyncio.sleep(backoff)
                    continue

                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as e:
                last_exception = e
                logger.error(f"HTTP error: {e.response.status_code} - {e.response.text[:200]}")
                if e.response.status_code in (429, 500, 502, 503, 504):
                    backoff = RETRY_BACKOFF_FACTOR ** attempt
                    await asyncio.sleep(backoff)
                    continue
                raise

            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                last_exception = e
                backoff = RETRY_BACKOFF_FACTOR ** attempt
                logger.warning(f"Connection error: {e}, backoff {backoff}s")
                await asyncio.sleep(backoff)
                continue

        # Provide better error message
        logger.error(f"Request failed after {MAX_RETRIES} retries")
        if last_exception:
            raise last_exception
        if last_response is not None:
            raise httpx.HTTPStatusError(
                f"Request failed with status {last_response.status_code}: {last_response.text}",
                request=last_response.request,
                response=last_response,
            )
        raise RuntimeError("Request failed after all retries")

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a GET request."""
        return await self._request_with_retry("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a POST request."""
        return await self._request_with_retry("POST", url, **kwargs)

    async def search_papers(
        self,
        query: str,
        fields: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        **filter_params: str,
    ) -> dict[str, Any]:
        """Search for papers using the /paper/search endpoint."""
        default_fields = [
            "paperId",
            "title",
            "abstract",
            "authors",
            "year",
            "citationCount",
            "fieldsOfStudy",
            "publicationTypes",
        ]

        params: dict[str, Any] = {
            "query": query,
            "fields": ",".join(fields or default_fields),
            "limit": min(limit, 100),  # API max is 100 per request
            "offset": offset,
        }
        params.update(filter_params)

        logger.info(f"Searching papers: query='{query}', limit={limit}, offset={offset}")
        logger.debug(f"Filter params: {filter_params}")

        response = await self.get("/paper/search", params=params)
        data = response.json()

        total = data.get("total", 0)
        found = len(data.get("data", []))
        logger.info(f"Search returned {found} papers (total available: {total})")

        return data

    async def get_paper_batch(
        self,
        paper_ids: list[str],
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch multiple papers by ID using the /paper/batch endpoint."""
        default_fields = [
            "paperId",
            "title",
            "abstract",
            "authors",
            "year",
            "citationCount",
            "fieldsOfStudy",
            "publicationTypes",
            "openAccessPdf",
            "venue",
            "url",
            "externalIds",
        ]

        params = {"fields": ",".join(fields or default_fields)}

        response = await self.post(
            "/paper/batch",
            params=params,
            json={"ids": paper_ids},
        )
        return response.json()

    async def download_pdf(self, url: str) -> bytes:
        """Download a PDF from a URL."""
        # Create a separate client for PDF downloads (different base URL)
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    async def get_paper_citations(
        self,
        paper_id: str,
        fields: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Get papers that cite the given paper.

        Uses the /paper/{paper_id}/citations endpoint.

        Args:
            paper_id: Semantic Scholar paper ID
            fields: Fields to return for each citing paper
            limit: Maximum number of citations to return (max 1000)
            offset: Offset for pagination

        Returns:
            Dict with 'data' list of citing papers and pagination info
        """
        default_fields = [
            "paperId",
            "title",
            "abstract",
            "authors",
            "year",
            "citationCount",
            "fieldsOfStudy",
            "publicationTypes",
            "openAccessPdf",
            "externalIds",
        ]

        params: dict[str, Any] = {
            "fields": ",".join(fields or default_fields),
            "limit": min(limit, 1000),
            "offset": offset,
        }

        logger.info(f"Fetching citations for paper {paper_id}, limit={limit}")
        response = await self.get(f"/paper/{paper_id}/citations", params=params)
        data = response.json()

        found = len(data.get("data", []))
        logger.info(f"Found {found} citations for paper {paper_id}")

        return data

    async def get_paper_references(
        self,
        paper_id: str,
        fields: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Get papers referenced by the given paper.

        Uses the /paper/{paper_id}/references endpoint.

        Args:
            paper_id: Semantic Scholar paper ID
            fields: Fields to return for each referenced paper
            limit: Maximum number of references to return (max 1000)
            offset: Offset for pagination

        Returns:
            Dict with 'data' list of referenced papers and pagination info
        """
        default_fields = [
            "paperId",
            "title",
            "abstract",
            "authors",
            "year",
            "citationCount",
            "fieldsOfStudy",
            "publicationTypes",
            "openAccessPdf",
            "externalIds",
        ]

        params: dict[str, Any] = {
            "fields": ",".join(fields or default_fields),
            "limit": min(limit, 1000),
            "offset": offset,
        }

        logger.info(f"Fetching references for paper {paper_id}, limit={limit}")
        response = await self.get(f"/paper/{paper_id}/references", params=params)
        data = response.json()

        found = len(data.get("data", []))
        logger.info(f"Found {found} references for paper {paper_id}")

        return data

    async def get_all_citations(
        self,
        paper_id: str,
        fields: list[str] | None = None,
        max_citations: int = 500,
    ) -> list[dict[str, Any]]:
        """
        Get all citations for a paper, handling pagination.

        Args:
            paper_id: Semantic Scholar paper ID
            fields: Fields to return for each citing paper
            max_citations: Maximum total citations to fetch

        Returns:
            List of citing paper data dicts
        """
        all_citations: list[dict[str, Any]] = []
        offset = 0
        batch_size = 100

        while len(all_citations) < max_citations:
            remaining = max_citations - len(all_citations)
            limit = min(remaining, batch_size)

            data = await self.get_paper_citations(
                paper_id, fields=fields, limit=limit, offset=offset
            )

            citations = data.get("data", [])
            if not citations:
                break

            # Extract the citing paper from each citation entry
            for entry in citations:
                citing_paper = entry.get("citingPaper")
                if citing_paper and citing_paper.get("paperId"):
                    all_citations.append(citing_paper)

            if data.get("next") is None:
                break

            offset = data["next"]

        return all_citations[:max_citations]

    async def get_all_references(
        self,
        paper_id: str,
        fields: list[str] | None = None,
        max_references: int = 500,
    ) -> list[dict[str, Any]]:
        """
        Get all references for a paper, handling pagination.

        Args:
            paper_id: Semantic Scholar paper ID
            fields: Fields to return for each referenced paper
            max_references: Maximum total references to fetch

        Returns:
            List of referenced paper data dicts
        """
        all_references: list[dict[str, Any]] = []
        offset = 0
        batch_size = 100

        while len(all_references) < max_references:
            remaining = max_references - len(all_references)
            limit = min(remaining, batch_size)

            data = await self.get_paper_references(
                paper_id, fields=fields, limit=limit, offset=offset
            )

            references = data.get("data", [])
            if not references:
                break

            # Extract the cited paper from each reference entry
            for entry in references:
                cited_paper = entry.get("citedPaper")
                if cited_paper and cited_paper.get("paperId"):
                    all_references.append(cited_paper)

            if data.get("next") is None:
                break

            offset = data["next"]

        return all_references[:max_references]
