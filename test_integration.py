"""Integration test: Search papers, summarize with LLM, and validate with HaluGate."""

import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

# Set up logging before imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)

from src.semantic_scholar import SemanticScholarAdapter, SearchFilters
from src.config import load_config, create_from_profile


async def main():
    # Load configuration
    profile_name = os.environ.get("MODEL_PROFILE", "dev-fast")
    print(f"\n=== Using profile: {profile_name} ===\n")

    try:
        profile = load_config(profile=profile_name)
    except Exception as e:
        print(f"Error loading config: {e}")
        print("Falling back to 'test' profile...")
        profile = load_config(profile="test")

    print(f"  Summarizer: {profile.summarizer.backend}")
    print(f"  HaluGate: {profile.halugate.backend}")
    print(f"  Overseer: max_retries={profile.overseer.max_retries}")
    print()

    # Create backends from profile
    summarizer, halugate, overseer = create_from_profile(profile)

    query = input("Enter search query (or press Enter for default): ").strip()
    if not query:
        query = "large language models reasoning"

    print(f"\n=== Searching for papers on: '{query}' ===\n")

    # Phase 1: Search papers (relaxed filters for better results)
    async with SemanticScholarAdapter() as search:
        results = await search.search_papers(
            query,
            filters=SearchFilters(year="2020-2025"),
            limit=3,  # Fewer papers for faster testing
        )

    if not results:
        print("No papers found.")
        return

    print(f"Found {len(results)} papers:\n")
    for i, paper in enumerate(results, 1):
        print(f"{i}. {paper.title} ({paper.year})")
        print(f"   Citations: {paper.citation_count}")
        print()

    # Phase 2: Summarize first paper with validation
    paper = results[0]
    print("=" * 60)
    print(f"Summarizing: {paper.title}")
    print("=" * 60)

    async with summarizer:
        summary, result, groundedness = await overseer.summarize_with_validation(paper)

    print(f"\nSummary:")
    print("-" * 40)
    print(summary)
    print("-" * 40)
    print(f"\nValidation Results:")
    print(f"  Fact-check needed: {result.fact_check_needed}")
    print(f"  Hallucination detected: {result.hallucination_detected}")
    print(f"  Groundedness: {groundedness:.1%}")
    print(f"  NLI contradictions: {result.nli_contradictions}")
    print(f"  Hallucinated spans: {len(result.spans)}")

    if result.spans:
        print("\n  Problematic spans:")
        for span in result.spans[:3]:  # Show first 3
            print(f"    - \"{span.text[:50]}...\" (severity={span.severity})")


async def test_overseer_with_mock():
    """Quick test with mock backends."""
    print("\n" + "=" * 60)
    print("QUICK TEST: Overseer with mock backends")
    print("=" * 60)

    from src.config import load_config, create_from_profile
    from src.semantic_scholar.models import PaperDetails, Author

    # Load test profile (all mocks)
    profile = load_config(profile="test")
    summarizer, halugate, overseer = create_from_profile(profile)

    # Create a test paper
    paper = PaperDetails(
        paper_id="test123",
        title="Test Paper on Machine Learning",
        abstract="This paper presents a novel approach to deep learning using transformers.",
        authors=[Author(author_id="a1", name="Test Author")],
        year=2024,
        citation_count=100,
    )

    print(f"\nTest paper: {paper.title}")
    print(f"Abstract: {paper.abstract}")

    async with summarizer:
        summary, result, groundedness = await overseer.summarize_with_validation(paper)

    print(f"\nMock Summary: {summary[:100]}...")
    print(f"Groundedness: {groundedness:.1%}")
    print(f"Hallucinations detected: {result.hallucination_detected}")

    print("\n[PASS] Overseer pipeline works with mock backends")


if __name__ == "__main__":
    # Check for API keys (warn but don't fail - mock mode works without keys)
    if not os.getenv("OPENROUTER_API_KEY"):
        print("Warning: OPENROUTER_API_KEY not set in .env")
        print("Running with mock backends only...")
        print()
        asyncio.run(test_overseer_with_mock())
    else:
        asyncio.run(main())
