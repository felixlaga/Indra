"""Search functions for paper search APIs.

This module provides convenience functions that work with any PaperSearchProvider.
By default, it uses the SemanticScholarAdapter.
"""

from .adapters import SemanticScholarAdapter
from .models import PaperSearchResult, PaperDetails, SearchFilters
from .protocols import PaperSearchProvider, PDFExtractor


async def search_papers(
    query: str,
    filters: SearchFilters | None = None,
    limit: int = 100,
    provider: PaperSearchProvider | None = None,
) -> list[PaperSearchResult]:
    """
    Search for papers matching query and filters.

    Args:
        query: Search query string
        filters: Optional search filters (year, fields of study, etc.)
        limit: Maximum number of results to return (default 100)
        provider: Optional provider implementing PaperSearchProvider protocol.
                  If not provided, uses SemanticScholarAdapter.

    Returns:
        List of PaperSearchResult objects

    Example:
        # Using default Semantic Scholar provider
        results = await search_papers("machine learning", limit=10)

        # Using custom provider
        async with MyCustomProvider() as provider:
            results = await search_papers("machine learning", provider=provider)
    """
    if provider:
        return await provider.search_papers(query, filters, limit)
    else:
        async with SemanticScholarAdapter() as adapter:
            return await adapter.search_papers(query, filters, limit)


async def fetch_papers(
    paper_ids: list[str],
    provider: PaperSearchProvider | None = None,
) -> list[PaperDetails]:
    """
    Fetch full paper details including open access PDF URLs.

    Args:
        paper_ids: List of paper IDs
        provider: Optional provider implementing PaperSearchProvider protocol.
                  If not provided, uses SemanticScholarAdapter.

    Returns:
        List of PaperDetails objects with openAccessPdf field

    Example:
        # Using default Semantic Scholar provider
        details = await fetch_papers(["paper_id_1", "paper_id_2"])

        # Using custom provider
        async with MyCustomProvider() as provider:
            details = await fetch_papers(["paper_id_1"], provider=provider)
    """
    if provider:
        return await provider.fetch_papers(paper_ids)
    else:
        async with SemanticScholarAdapter() as adapter:
            return await adapter.fetch_papers(paper_ids)


async def fetch_papers_with_text(
    paper_ids: list[str],
    provider: PaperSearchProvider | None = None,
) -> list[PaperDetails]:
    """
    Fetch full paper details including extracted full text from PDFs.

    Tries open access PDFs first, falls back to arXiv if available.
    Papers without accessible PDFs will have full_text=None.

    Args:
        paper_ids: List of paper IDs
        provider: Optional provider implementing PaperSearchProvider protocol.
                  If not provided, uses SemanticScholarAdapter.

    Returns:
        List of PaperDetails objects with full_text populated where possible

    Example:
        details = await fetch_papers_with_text(["paper_id_1", "paper_id_2"])
        for paper in details:
            if paper.full_text:
                print(f"{paper.title}: {len(paper.full_text)} chars")
    """
    if provider and hasattr(provider, "fetch_papers_with_text"):
        return await provider.fetch_papers_with_text(paper_ids)
    else:
        async with SemanticScholarAdapter() as adapter:
            return await adapter.fetch_papers_with_text(paper_ids)


async def download_and_extract_pdf(
    pdf_url: str,
    extractor: PDFExtractor | None = None,
) -> str:
    """
    Download PDF and extract text content.

    Args:
        pdf_url: URL of the PDF to download
        extractor: Optional extractor implementing PDFExtractor protocol.
                   If not provided, uses SemanticScholarAdapter.

    Returns:
        Extracted text content from the PDF

    Example:
        text = await download_and_extract_pdf("https://example.com/paper.pdf")
    """
    if extractor:
        return await extractor.extract_text(pdf_url)
    else:
        async with SemanticScholarAdapter() as adapter:
            return await adapter.extract_text(pdf_url)
