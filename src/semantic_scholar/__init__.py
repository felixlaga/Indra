"""Semantic Scholar API integration with protocol-based adapter pattern."""

from .models import (
    Author,
    OpenAccessPdf,
    PaperSearchResult,
    PaperDetails,
    SearchFilters,
    SearchResponse,
)
from .protocols import PaperSearchProvider, PDFExtractor, CitationProvider
from .adapters import SemanticScholarAdapter
from .client import SemanticScholarClient
from .search import search_papers, fetch_papers, fetch_papers_with_text, download_and_extract_pdf

__all__ = [
    # Models
    "Author",
    "OpenAccessPdf",
    "PaperSearchResult",
    "PaperDetails",
    "SearchFilters",
    "SearchResponse",
    # Protocols (for implementing custom providers)
    "PaperSearchProvider",
    "PDFExtractor",
    "CitationProvider",
    # Adapters
    "SemanticScholarAdapter",
    # Low-level client
    "SemanticScholarClient",
    # Convenience functions
    "search_papers",
    "fetch_papers",
    "fetch_papers_with_text",
    "download_and_extract_pdf",
]
