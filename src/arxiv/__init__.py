"""arXiv API integration for paper search.

This module provides an adapter for the arXiv API that implements
the same protocols as the Semantic Scholar adapter.

Usage:
    from src.arxiv import ArXivAdapter

    async with ArXivAdapter(categories=["cs.LG", "cs.AI"]) as adapter:
        results = await adapter.search_papers("transformer attention")
        details = await adapter.fetch_papers([r.paper_id for r in results])
"""

from .adapters import ArXivAdapter
from .client import ArXivClient

__all__ = ["ArXivAdapter", "ArXivClient"]
