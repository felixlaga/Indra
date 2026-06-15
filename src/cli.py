"""Command-line interface for the research agent."""

import asyncio
import json
import sys
from typing import Annotated

import typer

from .config.loader import load_config, PaperSourcesConfig
from .config.factory import create_paper_provider

app = typer.Typer(
    name="erla",
    help="Research agent for searching academic papers.",
    add_completion=False,
)


def get_paper_sources_config(
    sources: list[str],
    strategy: str,
    arxiv_categories: list[str] | None,
) -> PaperSourcesConfig:
    """Build PaperSourcesConfig from CLI args."""
    return PaperSourcesConfig(
        providers=sources,
        strategy=strategy,
        deduplication=strategy == "parallel",
        prefer_provider="semantic_scholar",
        arxiv_categories=arxiv_categories,
        arxiv_rate_limit=3.0,
    )


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Search query for papers")],
    sources: Annotated[
        list[str],
        typer.Option(
            "--source", "-s",
            help="Paper sources to use (can specify multiple)",
        ),
    ] = ["semantic_scholar"],
    strategy: Annotated[
        str,
        typer.Option(
            "--strategy",
            help="Search strategy: single, parallel, or fallback",
        ),
    ] = "single",
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Maximum number of results"),
    ] = 10,
    arxiv_categories: Annotated[
        list[str],
        typer.Option(
            "--arxiv-cat", "-c",
            help="arXiv categories to filter (e.g., cs.LG, cs.AI)",
        ),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: text or json"),
    ] = "text",
    year_start: Annotated[
        str,
        typer.Option("--year-start", help="Filter papers from this year (e.g., 2023)"),
    ] = None,
    year_end: Annotated[
        str,
        typer.Option("--year-end", help="Filter papers until this year"),
    ] = None,
):
    """
    Search for academic papers.

    Examples:

        # Search Semantic Scholar (default)
        erla search "transformer attention"

        # Search arXiv only
        erla search "neural networks" -s arxiv

        # Search both in parallel
        erla search "deep learning" -s semantic_scholar -s arxiv --strategy parallel

        # Search arXiv with category filter
        erla search "LLM reasoning" -s arxiv -c cs.LG -c cs.AI

        # Output as JSON
        erla search "machine learning" --format json
    """
    # Validate sources
    valid_sources = {"semantic_scholar", "arxiv"}
    for s in sources:
        if s not in valid_sources:
            typer.echo(f"Error: Invalid source '{s}'. Must be one of: {valid_sources}", err=True)
            raise typer.Exit(1)

    # Validate strategy
    if strategy not in ("single", "parallel", "fallback"):
        typer.echo("Error: Strategy must be one of: single, parallel, fallback", err=True)
        raise typer.Exit(1)

    # Auto-select strategy if multiple sources
    if len(sources) > 1 and strategy == "single":
        strategy = "parallel"
        typer.echo(f"Note: Using '{strategy}' strategy for multiple sources\n", err=True)

    asyncio.run(_search_async(
        query=query,
        sources=sources,
        strategy=strategy,
        limit=limit,
        arxiv_categories=arxiv_categories,
        output_format=output_format,
        year_start=year_start,
        year_end=year_end,
    ))


async def _search_async(
    query: str,
    sources: list[str],
    strategy: str,
    limit: int,
    arxiv_categories: list[str] | None,
    output_format: str,
    year_start: str | None,
    year_end: str | None,
):
    """Async implementation of search."""
    from .semantic_scholar.models import SearchFilters

    # Build config
    config = get_paper_sources_config(sources, strategy, arxiv_categories)

    # Create provider
    search_provider, _ = create_paper_provider(config)

    # Build filters
    filters = None
    if year_start or year_end:
        filters = SearchFilters(start_date=year_start, end_date=year_end)

    # Search
    async with search_provider:
        results = await search_provider.search_papers(query, filters=filters, limit=limit)

    # Output
    if output_format == "json":
        output = [
            {
                "paper_id": r.paper_id,
                "title": r.title,
                "year": r.year,
                "authors": [a.name for a in r.authors],
                "citation_count": r.citation_count,
                "abstract": r.abstract[:300] + "..." if r.abstract and len(r.abstract) > 300 else r.abstract,
                "fields": r.fields_of_study,
            }
            for r in results
        ]
        typer.echo(json.dumps(output, indent=2))
    else:
        if not results:
            typer.echo("No papers found.")
            return

        typer.echo(f"Found {len(results)} papers:\n")
        for i, r in enumerate(results, 1):
            source_tag = "[arXiv]" if r.paper_id.startswith("arxiv:") else "[SS]"
            typer.echo(f"{i}. {source_tag} {r.title}")
            typer.echo(f"   Year: {r.year or 'N/A'} | Citations: {r.citation_count or 'N/A'}")
            if r.authors:
                authors = ", ".join(a.name or "Unknown" for a in r.authors[:3])
                if len(r.authors) > 3:
                    authors += f" (+{len(r.authors) - 3} more)"
                typer.echo(f"   Authors: {authors}")
            typer.echo(f"   ID: {r.paper_id}")
            typer.echo()


@app.command()
def fetch(
    paper_ids: Annotated[
        list[str],
        typer.Argument(help="Paper IDs to fetch (e.g., arxiv:2301.00001)"),
    ],
    with_text: Annotated[
        bool,
        typer.Option("--with-text", "-t", help="Extract full text from PDFs"),
    ] = False,
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: text or json"),
    ] = "text",
):
    """
    Fetch full details for specific papers.

    Examples:

        # Fetch paper details
        erla fetch arxiv:2301.00001

        # Fetch with full text extraction
        erla fetch arxiv:2301.00001 --with-text

        # Fetch multiple papers
        erla fetch arxiv:2301.00001 arxiv:2302.00002 --format json
    """
    asyncio.run(_fetch_async(paper_ids, with_text, output_format))


async def _fetch_async(paper_ids: list[str], with_text: bool, output_format: str):
    """Async implementation of fetch."""
    # Determine which sources we need
    has_arxiv = any(pid.startswith("arxiv:") for pid in paper_ids)
    has_ss = any(not pid.startswith("arxiv:") for pid in paper_ids)

    sources = []
    if has_ss:
        sources.append("semantic_scholar")
    if has_arxiv:
        sources.append("arxiv")

    config = get_paper_sources_config(sources, "single" if len(sources) == 1 else "parallel", None)
    search_provider, _ = create_paper_provider(config)

    async with search_provider:
        if with_text and hasattr(search_provider, "fetch_papers_with_text"):
            papers = await search_provider.fetch_papers_with_text(paper_ids)
        else:
            papers = await search_provider.fetch_papers(paper_ids)

    if output_format == "json":
        output = [
            {
                "paper_id": p.paper_id,
                "title": p.title,
                "year": p.year,
                "authors": [a.name for a in p.authors],
                "abstract": p.abstract,
                "venue": p.venue,
                "url": p.url,
                "pdf_url": p.open_access_pdf.url if p.open_access_pdf else None,
                "full_text_length": len(p.full_text) if p.full_text else None,
            }
            for p in papers
        ]
        typer.echo(json.dumps(output, indent=2))
    else:
        for p in papers:
            typer.echo(f"Title: {p.title}")
            typer.echo(f"ID: {p.paper_id}")
            typer.echo(f"Year: {p.year or 'N/A'}")
            typer.echo(f"Venue: {p.venue or 'N/A'}")
            if p.authors:
                typer.echo(f"Authors: {', '.join(a.name or 'Unknown' for a in p.authors)}")
            if p.open_access_pdf:
                typer.echo(f"PDF: {p.open_access_pdf.url}")
            if p.full_text:
                typer.echo(f"Full text: {len(p.full_text)} characters extracted")
            typer.echo()


@app.command()
def profiles():
    """List available configuration profiles."""
    from pathlib import Path
    import yaml

    config_path = Path(__file__).parent / "config" / "models.yaml"

    with open(config_path) as f:
        data = yaml.safe_load(f)

    typer.echo("Available profiles:\n")
    for name, profile in data.get("profiles", {}).items():
        paper_sources = profile.get("paper_sources", {})
        providers = paper_sources.get("providers", ["semantic_scholar"])
        strategy = paper_sources.get("strategy", "single")

        typer.echo(f"  {name}")
        typer.echo(f"    Sources: {', '.join(providers)}")
        typer.echo(f"    Strategy: {strategy}")
        typer.echo()


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
