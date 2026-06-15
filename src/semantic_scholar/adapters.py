"""Adapter implementations for the paper search protocols."""

import logging
import tempfile
from pathlib import Path

from .client import SemanticScholarClient

logger = logging.getLogger(__name__)
from .models import (
    PaperSearchResult,
    PaperDetails,
    SearchFilters,
    SearchResponse,
)
from .protocols import PaperSearchProvider, PDFExtractor, CitationProvider


class SemanticScholarAdapter(PaperSearchProvider, PDFExtractor, CitationProvider):
    """
    Adapter for Semantic Scholar API.

    Implements both PaperSearchProvider and PDFExtractor protocols.

    Usage:
        async with SemanticScholarAdapter() as adapter:
            results = await adapter.search_papers("machine learning")
            details = await adapter.fetch_papers([r.paper_id for r in results])
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize the Semantic Scholar adapter.

        Args:
            api_key: Optional API key. If not provided, uses SEMANTIC_SCHOLAR_API_KEY
                    environment variable.
        """
        self._client = SemanticScholarClient(api_key=api_key)
        self._entered = False

    async def __aenter__(self) -> "SemanticScholarAdapter":
        await self._client.__aenter__()
        self._entered = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._client.__aexit__(exc_type, exc_val, exc_tb)
        self._entered = False

    def _ensure_entered(self) -> None:
        if not self._entered:
            raise RuntimeError(
                "Adapter not initialized. Use 'async with' context manager."
            )

    async def search_papers(
        self,
        query: str,
        filters: SearchFilters | None = None,
        limit: int = 100,
    ) -> list[PaperSearchResult]:
        """
        Search for papers matching query and filters.

        Uses Semantic Scholar /paper/search endpoint.
        """
        self._ensure_entered()
        filters = filters or SearchFilters()
        filter_params = filters.to_query_params()

        all_results: list[PaperSearchResult] = []
        offset = 0

        while len(all_results) < limit:
            remaining = limit - len(all_results)
            batch_size = min(remaining, 100)  # API max is 100

            response_data = await self._client.search_papers(
                query=query,
                limit=batch_size,
                offset=offset,
                **filter_params,
            )

            response = SearchResponse.model_validate(response_data)

            for paper_data in response.data:
                all_results.append(paper_data)

            # Check if there are more results
            if response.next is None or len(response.data) == 0:
                break

            offset = response.next

        return all_results[:limit]

    async def fetch_papers(
        self,
        paper_ids: list[str],
    ) -> list[PaperDetails]:
        """
        Fetch full paper details including open access PDF URLs.

        Uses Semantic Scholar /paper/batch endpoint.
        """
        self._ensure_entered()

        if not paper_ids:
            return []

        all_results: list[PaperDetails] = []

        # Process in batches of 500 (API limit)
        batch_size = 500
        for i in range(0, len(paper_ids), batch_size):
            batch_ids = paper_ids[i : i + batch_size]
            response_data = await self._client.get_paper_batch(batch_ids)

            for paper_data in response_data:
                if paper_data:  # API returns null for not found papers
                    all_results.append(PaperDetails.model_validate(paper_data))

        return all_results

    def _get_pdf_url(self, paper: PaperDetails) -> str | None:
        """Get PDF URL, trying open access first, then arXiv fallback."""
        if paper.open_access_pdf and paper.open_access_pdf.url:
            return paper.open_access_pdf.url

        # arXiv fallback: https://arxiv.org/pdf/{arxiv_id}.pdf
        if paper.external_ids and paper.external_ids.get("ArXiv"):
            return f"https://arxiv.org/pdf/{paper.external_ids['ArXiv']}.pdf"

        return None

    async def fetch_papers_with_text(
        self,
        paper_ids: list[str],
    ) -> list[PaperDetails]:
        """
        Fetch full paper details including extracted full text from PDFs.

        Tries open access PDFs first, falls back to arXiv if available.
        Papers without accessible PDFs will have full_text=None.
        """
        self._ensure_entered()

        # First fetch paper details (includes openAccessPdf and externalIds)
        papers = await self.fetch_papers(paper_ids)

        # Extract text for each paper
        for paper in papers:
            pdf_url = self._get_pdf_url(paper)
            if pdf_url:
                try:
                    logger.info(f"Extracting text from: {pdf_url}")
                    paper.full_text = await self.extract_text(pdf_url)
                except Exception as e:
                    logger.warning(f"Failed to extract text for {paper.paper_id}: {e}")
                    paper.full_text = None
            else:
                logger.info(f"No PDF available for {paper.paper_id}")

        return papers

    async def extract_text(self, pdf_url: str) -> str:
        """
        Download PDF and extract text content.

        Uses httpx for download + PyMuPDF for extraction.
        """
        self._ensure_entered()
        import fitz  # PyMuPDF

        # Download PDF
        pdf_bytes = await self._client.download_pdf(pdf_url)

        # Save to temp file and extract text
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            temp_path = Path(f.name)

        try:
            # Open PDF and extract text
            doc = fitz.open(temp_path)
            text_parts: list[str] = []

            for page in doc:
                text_parts.append(page.get_text())

            doc.close()
            return "\n".join(text_parts)

        finally:
            # Clean up temp file
            temp_path.unlink(missing_ok=True)

    async def get_citations(
        self,
        paper_id: str,
        limit: int = 100,
    ) -> list[PaperDetails]:
        """
        Get papers that cite the given paper.

        Args:
            paper_id: Paper ID to find citations for
            limit: Maximum citations to return

        Returns:
            List of PaperDetails for citing papers
        """
        self._ensure_entered()

        citation_data = await self._client.get_all_citations(paper_id, max_citations=limit)

        papers = []
        for paper_dict in citation_data:
            try:
                papers.append(PaperDetails.model_validate(paper_dict))
            except Exception as e:
                logger.warning(f"Failed to parse citation paper: {e}")

        return papers

    async def get_references(
        self,
        paper_id: str,
        limit: int = 100,
    ) -> list[PaperDetails]:
        """
        Get papers referenced by the given paper.

        Args:
            paper_id: Paper ID to find references for
            limit: Maximum references to return

        Returns:
            List of PaperDetails for referenced papers
        """
        self._ensure_entered()

        reference_data = await self._client.get_all_references(paper_id, max_references=limit)

        papers = []
        for paper_dict in reference_data:
            try:
                papers.append(PaperDetails.model_validate(paper_dict))
            except Exception as e:
                logger.warning(f"Failed to parse reference paper: {e}")

        return papers

    async def get_citations_batch(
        self,
        paper_ids: list[str],
        limit_per_paper: int = 20,
    ) -> list[PaperDetails]:
        """
        Get papers that cite any of the given papers (deduplicated).

        Args:
            paper_ids: List of paper IDs
            limit_per_paper: Max citations per paper

        Returns:
            Deduplicated list of citing papers
        """
        self._ensure_entered()

        seen_ids: set[str] = set()
        all_papers: list[PaperDetails] = []

        for paper_id in paper_ids:
            try:
                citations = await self.get_citations(paper_id, limit=limit_per_paper)
                for paper in citations:
                    if paper.paper_id not in seen_ids:
                        seen_ids.add(paper.paper_id)
                        all_papers.append(paper)
            except Exception as e:
                logger.warning(f"Failed to get citations for {paper_id}: {e}")

        return all_papers

    async def get_references_batch(
        self,
        paper_ids: list[str],
        limit_per_paper: int = 20,
    ) -> list[PaperDetails]:
        """
        Get papers referenced by any of the given papers (deduplicated).

        Args:
            paper_ids: List of paper IDs
            limit_per_paper: Max references per paper

        Returns:
            Deduplicated list of referenced papers
        """
        self._ensure_entered()

        seen_ids: set[str] = set()
        all_papers: list[PaperDetails] = []

        for paper_id in paper_ids:
            try:
                references = await self.get_references(paper_id, limit=limit_per_paper)
                for paper in references:
                    if paper.paper_id not in seen_ids:
                        seen_ids.add(paper.paper_id)
                        all_papers.append(paper)
            except Exception as e:
                logger.warning(f"Failed to get references for {paper_id}: {e}")

        return all_papers
