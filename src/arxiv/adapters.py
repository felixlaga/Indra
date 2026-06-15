"""arXiv adapter implementing paper search protocols."""

import logging
import tempfile
from pathlib import Path

import arxiv

from ..semantic_scholar.protocols import PaperSearchProvider, PDFExtractor
from ..semantic_scholar.models import (
    PaperSearchResult,
    PaperDetails,
    SearchFilters,
    Author,
    OpenAccessPdf,
)
from .client import ArXivClient

logger = logging.getLogger(__name__)


# Mapping arXiv categories to Semantic Scholar fields of study
ARXIV_CATEGORY_TO_FIELD = {
    "cs.LG": "Computer Science",
    "cs.AI": "Computer Science",
    "cs.CL": "Computer Science",
    "cs.CV": "Computer Science",
    "cs.NE": "Computer Science",
    "cs.RO": "Computer Science",
    "cs.SE": "Computer Science",
    "cs.PL": "Computer Science",
    "cs.DB": "Computer Science",
    "cs.IR": "Computer Science",
    "stat.ML": "Mathematics",
    "stat.": "Mathematics",
    "math.": "Mathematics",
    "physics.": "Physics",
    "q-bio.": "Biology",
    "q-fin.": "Economics",
    "econ.": "Economics",
    "eess.": "Engineering",
}


def _arxiv_category_to_field(category: str) -> str:
    """Map arXiv category to field of study."""
    for prefix, field in ARXIV_CATEGORY_TO_FIELD.items():
        if category.startswith(prefix):
            return field
    return "Other"


def _extract_arxiv_id(entry_id: str) -> str:
    """Extract clean arXiv ID from entry URL.

    Example: "http://arxiv.org/abs/2301.00001v1" -> "2301.00001"
    """
    # entry_id is URL like http://arxiv.org/abs/2301.00001v1
    id_part = entry_id.split("/abs/")[-1]
    # Remove version suffix
    if "v" in id_part:
        id_part = id_part.rsplit("v", 1)[0]
    return id_part


def _result_to_paper_search_result(result: arxiv.Result) -> PaperSearchResult:
    """Convert arxiv.Result to PaperSearchResult model."""
    arxiv_id = _extract_arxiv_id(result.entry_id)

    return PaperSearchResult(
        paper_id=f"arxiv:{arxiv_id}",
        title=result.title,
        abstract=result.summary,
        authors=[Author(author_id=None, name=author.name) for author in result.authors],
        year=result.published.year if result.published else None,
        citation_count=None,  # arXiv doesn't provide this
        fields_of_study=[_arxiv_category_to_field(result.primary_category)],
        publication_types=["Preprint"],
    )


def _result_to_paper_details(result: arxiv.Result) -> PaperDetails:
    """Convert arxiv.Result to PaperDetails model."""
    arxiv_id = _extract_arxiv_id(result.entry_id)

    external_ids: dict[str, str | int] = {"ArXiv": arxiv_id}
    if result.doi:
        external_ids["DOI"] = result.doi

    return PaperDetails(
        paper_id=f"arxiv:{arxiv_id}",
        title=result.title,
        abstract=result.summary,
        authors=[Author(author_id=None, name=author.name) for author in result.authors],
        year=result.published.year if result.published else None,
        citation_count=None,
        fields_of_study=[_arxiv_category_to_field(result.primary_category)],
        publication_types=["Preprint"],
        open_access_pdf=OpenAccessPdf(url=result.pdf_url, status="green"),
        venue="arXiv",
        url=result.entry_id,
        external_ids=external_ids,
        full_text=None,
    )


class ArXivAdapter(PaperSearchProvider, PDFExtractor):
    """
    Adapter for arXiv API implementing paper search protocols.

    Implements:
    - PaperSearchProvider: search_papers(), fetch_papers()
    - PDFExtractor: extract_text()

    Does NOT implement CitationProvider (arXiv has no citation API).
    Use ArXivCitationBridge for citations via Semantic Scholar.

    Usage:
        async with ArXivAdapter(categories=["cs.LG", "cs.AI"]) as adapter:
            results = await adapter.search_papers("transformer attention")
            details = await adapter.fetch_papers([r.paper_id for r in results])
    """

    def __init__(
        self,
        categories: list[str] | None = None,
        rate_limit_seconds: float = 3.0,
    ):
        """
        Initialize arXiv adapter.

        Args:
            categories: Optional default category filter (e.g., ["cs.LG", "cs.AI"])
            rate_limit_seconds: Minimum seconds between requests (default: 3.0)
        """
        self._client = ArXivClient(rate_limit_seconds=rate_limit_seconds)
        self._default_categories = categories
        self._entered = False

    async def __aenter__(self) -> "ArXivAdapter":
        """Enter async context."""
        self._entered = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context."""
        self._entered = False

    def _ensure_entered(self) -> None:
        """Ensure adapter is properly initialized."""
        if not self._entered:
            raise RuntimeError(
                "ArXivAdapter not initialized. Use 'async with' context manager."
            )

    async def search_papers(
        self,
        query: str,
        filters: SearchFilters | None = None,
        limit: int = 100,
    ) -> list[PaperSearchResult]:
        """
        Search arXiv for papers matching query.

        Args:
            query: Search query string
            filters: Optional search filters
            limit: Maximum results to return

        Returns:
            List of PaperSearchResult objects
        """
        self._ensure_entered()

        # Build arXiv-specific query from filters
        arxiv_query = self._build_arxiv_query(query, filters)

        # Determine categories
        categories = self._default_categories
        if filters and filters.fields_of_study:
            # Try to map fields of study back to arXiv categories
            categories = self._fields_to_categories(filters.fields_of_study)

        # Determine sort order
        sort_by = arxiv.SortCriterion.Relevance
        if filters and filters.start_date:
            # If filtering by date, sort by submission date
            sort_by = arxiv.SortCriterion.SubmittedDate

        results = await self._client.search(
            query=arxiv_query,
            max_results=limit,
            sort_by=sort_by,
            categories=categories,
        )

        return [_result_to_paper_search_result(r) for r in results]

    def _build_arxiv_query(
        self,
        query: str,
        filters: SearchFilters | None,
    ) -> str:
        """Build arXiv query string from query and filters."""
        parts = [query]

        if filters:
            # Date range filter
            if filters.start_date:
                # arXiv uses submittedDate field
                # Format: submittedDate:[YYYYMMDD TO YYYYMMDD]
                start = filters.start_date.replace("-", "")
                end = filters.end_date.replace("-", "") if filters.end_date else "*"
                parts.append(f"submittedDate:[{start} TO {end}]")

        return " AND ".join(parts) if len(parts) > 1 else parts[0]

    def _fields_to_categories(self, fields: list[str]) -> list[str] | None:
        """Map fields of study to arXiv categories."""
        categories = []
        for field in fields:
            field_lower = field.lower()
            if "computer" in field_lower:
                categories.extend(["cs.LG", "cs.AI", "cs.CL", "cs.CV"])
            elif "math" in field_lower:
                categories.extend(["math.ST", "stat.ML"])
            elif "physics" in field_lower:
                categories.append("physics")
            elif "biology" in field_lower:
                categories.append("q-bio")
            elif "econ" in field_lower:
                categories.append("econ")
        return categories if categories else None

    async def fetch_papers(
        self,
        paper_ids: list[str],
    ) -> list[PaperDetails]:
        """
        Fetch full paper details by arXiv IDs.

        Args:
            paper_ids: List of paper IDs (format: "arxiv:2301.00001")

        Returns:
            List of PaperDetails objects
        """
        self._ensure_entered()

        # Filter to only arXiv IDs
        arxiv_ids = [
            pid
            for pid in paper_ids
            if pid.startswith("arxiv:") or pid.startswith("arXiv:")
        ]

        if not arxiv_ids:
            return []

        results = await self._client.get_papers(arxiv_ids)
        return [_result_to_paper_details(r) for r in results]

    async def extract_text(self, pdf_url: str) -> str:
        """
        Download and extract text from arXiv PDF.

        Args:
            pdf_url: URL of the PDF (e.g., https://arxiv.org/pdf/2301.00001.pdf)

        Returns:
            Extracted text content
        """
        self._ensure_entered()

        import fitz  # PyMuPDF
        import httpx

        # Download PDF
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(pdf_url, follow_redirects=True)
            response.raise_for_status()
            pdf_bytes = response.content

        # Extract text using PyMuPDF
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf_bytes)
            temp_path = Path(f.name)

        try:
            doc = fitz.open(temp_path)
            text_parts: list[str] = []

            for page in doc:
                text_parts.append(page.get_text())

            doc.close()
            return "\n".join(text_parts)
        finally:
            temp_path.unlink(missing_ok=True)

    async def fetch_papers_with_text(
        self,
        paper_ids: list[str],
    ) -> list[PaperDetails]:
        """
        Fetch papers and extract full text from PDFs.

        Args:
            paper_ids: List of arXiv paper IDs

        Returns:
            List of PaperDetails with full_text populated
        """
        self._ensure_entered()

        papers = await self.fetch_papers(paper_ids)

        for paper in papers:
            if paper.open_access_pdf and paper.open_access_pdf.url:
                try:
                    paper.full_text = await self.extract_text(paper.open_access_pdf.url)
                except Exception as e:
                    logger.warning(f"Failed to extract text for {paper.paper_id}: {e}")
                    paper.full_text = None

        return papers
