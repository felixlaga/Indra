"""Protocol definitions for paper search APIs."""

from typing import Protocol, runtime_checkable

from .models import PaperSearchResult, PaperDetails, SearchFilters


@runtime_checkable
class PaperSearchProvider(Protocol):
    """Protocol for paper search providers.

    Implement this protocol to add support for new paper search APIs.
    """

    async def search_papers(
        self,
        query: str,
        filters: SearchFilters | None = None,
        limit: int = 100,
    ) -> list[PaperSearchResult]:
        """
        Search for papers matching query and filters.

        Args:
            query: Search query string
            filters: Optional search filters (year, fields of study, etc.)
            limit: Maximum number of results to return

        Returns:
            List of PaperSearchResult objects
        """
        ...

    async def fetch_papers(
        self,
        paper_ids: list[str],
    ) -> list[PaperDetails]:
        """
        Fetch full paper details including open access PDF URLs.

        Args:
            paper_ids: List of paper IDs (format depends on provider)

        Returns:
            List of PaperDetails objects with openAccessPdf field
        """
        ...


@runtime_checkable
class PDFExtractor(Protocol):
    """Protocol for PDF text extraction."""

    async def extract_text(self, pdf_url: str) -> str:
        """
        Download PDF and extract text content.

        Args:
            pdf_url: URL of the PDF to download

        Returns:
            Extracted text content from the PDF
        """
        ...


@runtime_checkable
class CitationProvider(Protocol):
    """Protocol for citation graph traversal."""

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
        ...

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
        ...

    async def get_citations_batch(
        self,
        paper_ids: list[str],
        limit_per_paper: int = 20,
    ) -> list[PaperDetails]:
        """
        Get papers that cite any of the given papers.

        Args:
            paper_ids: List of paper IDs
            limit_per_paper: Max citations per paper

        Returns:
            Deduplicated list of citing papers
        """
        ...

    async def get_references_batch(
        self,
        paper_ids: list[str],
        limit_per_paper: int = 20,
    ) -> list[PaperDetails]:
        """
        Get papers referenced by any of the given papers.

        Args:
            paper_ids: List of paper IDs
            limit_per_paper: Max references per paper

        Returns:
            Deduplicated list of referenced papers
        """
        ...
