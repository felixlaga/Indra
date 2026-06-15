#!/usr/bin/env python
"""
Run a research query through the recursive research agent.

Usage:
    python run_research.py "your research query here"
    python run_research.py "transformer attention mechanisms" --iterations 5
    python run_research.py "LLM reasoning" --profile research-accurate
"""

import argparse
import asyncio
import logging
import os
import sys

# Fix OpenMP issue on macOS
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


async def run_research(
    query: str,
    max_iterations: int = 5,
    profile: str = "research-fast",
    stop_on_hypotheses: int = 0,
):
    """Run a research query and display results."""
    from src.config import load_config
    from src.orchestration import ResearchSession

    print("=" * 60)
    print(f"Research Query: {query}")
    print(f"Profile: {profile}")
    print(f"Max Iterations: {max_iterations}")
    print("=" * 60 + "\n")

    # Load configuration
    print("Loading configuration...")
    config = load_config(profile)
    print(f"  - Groundedness threshold: {config.research_loop.inner_loop.groundedness_threshold}")
    print(f"  - Max papers per iteration: {config.research_loop.inner_loop.max_papers_per_iteration}")
    print(f"  - Auto hypothesis mode: {config.research_loop.master_agent.auto_hypothesis_mode}")
    print()

    # Run the research session
    print("Starting research session...\n")

    async with ResearchSession(config, query) as session:
        # Run iterations
        state = await session.run(
            max_iterations=max_iterations,
            stop_on_hypotheses=stop_on_hypotheses,
        )

        # Display results
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60 + "\n")

        status = session.get_status()
        print(f"Loop ID: {status.get('loop_id', 'N/A')}")
        print(f"Total Branches: {status.get('total_branches', 0)}")
        print(f"Active Branches: {status.get('active_branches', 0)}")
        print(f"Total Papers Found: {status.get('total_papers', 0)}")
        print(f"Total Validated Summaries: {status.get('total_summaries', 0)}")
        print(f"Total Hypotheses: {status.get('total_hypotheses', 0)}")
        print(f"Context Tokens Used: {status.get('total_context_used', 0):,}")

        # Show papers
        print("\n" + "-" * 40)
        print("PAPERS FOUND")
        print("-" * 40)

        for branch in state.branches.values():
            print(f"\nBranch: {branch.id} ({branch.status.value})")
            print(f"Query: {branch.query[:50]}...")
            for i, (paper_id, paper) in enumerate(branch.accumulated_papers.items(), 1):
                if i > 5:
                    print(f"  ... and {len(branch.accumulated_papers) - 5} more papers")
                    break
                print(f"  {i}. {paper.title or 'Unknown'}")
                print(f"     Year: {paper.year} | Citations: {paper.citation_count or 0}")

        # Show summaries
        print("\n" + "-" * 40)
        print("VALIDATED SUMMARIES")
        print("-" * 40)

        for branch in state.branches.values():
            for i, (paper_id, summary) in enumerate(branch.accumulated_summaries.items(), 1):
                if i > 3:
                    print(f"\n  ... and {len(branch.accumulated_summaries) - 3} more summaries")
                    break
                print(f"\n{i}. {summary.paper_title}")
                print(f"   Groundedness: {summary.groundedness:.1%}")
                print(f"   Summary: {summary.summary[:200]}...")

        # Show hypotheses
        hypotheses = session.get_hypotheses(n=5, min_confidence=0.3)
        if hypotheses:
            print("\n" + "-" * 40)
            print("RESEARCH HYPOTHESES")
            print("-" * 40)

            for i, h in enumerate(hypotheses, 1):
                print(f"\n{i}. [{h.confidence:.0%}] {h.text}")
                print(f"   Supporting papers: {len(h.supporting_paper_ids)}")

        print("\n" + "=" * 60)
        print("Research complete!")
        print("=" * 60)

        return state


def main():
    parser = argparse.ArgumentParser(
        description="Run a research query through the recursive research agent"
    )
    parser.add_argument(
        "query",
        help="Research query to explore",
    )
    parser.add_argument(
        "--iterations", "-i",
        type=int,
        default=3,
        help="Maximum iterations to run (default: 3)",
    )
    parser.add_argument(
        "--profile", "-p",
        default="research-fast",
        choices=["research-fast", "research-accurate", "research-prod", "dev-fast", "test"],
        help="Configuration profile to use (default: research-fast)",
    )
    parser.add_argument(
        "--stop-on-hypotheses", "-s",
        type=int,
        default=0,
        help="Stop when this many hypotheses are generated (0=disabled)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress verbose logging",
    )

    args = parser.parse_args()

    # Load .env file if it exists
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    # Configure logging based on --quiet flag
    if args.quiet:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("src").setLevel(logging.WARNING)

    try:
        asyncio.run(run_research(
            query=args.query,
            max_iterations=args.iterations,
            profile=args.profile,
            stop_on_hypotheses=args.stop_on_hypotheses,
        ))
    except KeyboardInterrupt:
        print("\n\nResearch interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
