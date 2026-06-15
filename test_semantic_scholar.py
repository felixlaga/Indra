"""Test script for Semantic Scholar search module."""

import asyncio
import os
from src.semantic_scholar import (
    SemanticScholarAdapter,
    SearchFilters,
    PaperSearchProvider,
)


async def test_with_adapter(adapter: PaperSearchProvider):
    """Test using the adapter pattern."""
    print("=== Testing Semantic Scholar Search Module ===\n")

    # Phase 1: Search for papers
    query = "large language models reasoning"
    filters = SearchFilters(
        year="2023-2024",
        min_citation_count=10,
    )

    print(f"Searching for: '{query}'")
    print(f"Filters: year={filters.year}, min_citations={filters.min_citation_count}\n")

    try:
        results = await adapter.search_papers(query, filters=filters, limit=5)
    except Exception as e:
        print(f"Error during search: {e}")
        print("\nNote: Semantic Scholar API requires an API key for reliable access.")
        print("Set SEMANTIC_SCHOLAR_API_KEY in your .env file.")
        print("Get a key at: https://www.semanticscholar.org/product/api#api-key-form")
        return

    print(f"Found {len(results)} papers:\n")

    for i, paper in enumerate(results, 1):
        print(f"{i}. {paper.title}")
        print(f"   Year: {paper.year} | Citations: {paper.citation_count}")
        print(f"   Authors: {', '.join(a.name or 'Unknown' for a in paper.authors[:3])}")
        if paper.abstract:
            abstract_preview = (
                paper.abstract[:200] + "..."
                if len(paper.abstract) > 200
                else paper.abstract
            )
            print(f"   Abstract: {abstract_preview}")
        print()

    # Phase 2: Fetch full details for top 3
    if results:
        print("=== Fetching Full Paper Details ===\n")

        paper_ids = [p.paper_id for p in results[:3]]
        details = await adapter.fetch_papers(paper_ids)

        for paper in details:
            print(f"Title: {paper.title}")
            print(f"Venue: {paper.venue or 'N/A'}")
            if paper.open_access_pdf:
                print(f"Open Access PDF: {paper.open_access_pdf.url}")
            else:
                print("Open Access PDF: Not available")
            print()


async def main():
    # Check for API key
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if not api_key:
        print("Warning: No SEMANTIC_SCHOLAR_API_KEY set.")
        print("The API may rate-limit requests without a key.\n")

    # Use the adapter pattern
    async with SemanticScholarAdapter(api_key=api_key) as adapter:
        await test_with_adapter(adapter)


if __name__ == "__main__":
    asyncio.run(main())
