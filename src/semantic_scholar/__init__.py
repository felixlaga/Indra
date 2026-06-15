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


def __getattr__(name: str):
    if name == "SemanticScholarAdapter":
        from .adapters import SemanticScholarAdapter

        return SemanticScholarAdapter
    if name == "SemanticScholarClient":
        from .client import SemanticScholarClient

        return SemanticScholarClient
    if name in {
        "search_papers",
        "fetch_papers",
        "fetch_papers_with_text",
        "download_and_extract_pdf",
    }:
        from . import search

        return getattr(search, name)
    raise AttributeError(f"module 'src.semantic_scholar' has no attribute {name!r}")
