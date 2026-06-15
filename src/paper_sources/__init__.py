"""Paper sources module for multi-provider paper search.

This module provides a composite search provider that can aggregate
results from multiple paper search APIs (Semantic Scholar, arXiv, etc.).

Usage:
    from src.paper_sources import CompositeSearchProvider, create_provider

    # Using factory function
    provider, citation_provider = create_provider(config)

    # Or manually
    from src.semantic_scholar.adapters import SemanticScholarAdapter
    from src.arxiv.adapters import ArXivAdapter

    providers = [SemanticScholarAdapter(), ArXivAdapter()]
    composite = CompositeSearchProvider(
        providers=providers,
        strategy="parallel",
    )
"""

from .composite import CompositeSearchProvider
from .deduplication import deduplicate_papers
from .bridge import ArXivCitationBridge

__all__ = [
    "CompositeSearchProvider",
    "deduplicate_papers",
    "ArXivCitationBridge",
]
