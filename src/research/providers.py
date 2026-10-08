"""Use existing research search adapters behind a bounded product interface."""

import asyncio

from ..api.models import Paper
from ..api.repository import utc_now
from ..domain.papers import PaperExternalIds, canonical_paper_key
from ..semantic_scholar.models import SearchFilters
from .models import stable_id


def to_product_paper(details, provider: str) -> Paper:
    ids = details.external_ids or {}
    external = PaperExternalIds(
        doi=ids.get("DOI"),
        arxiv_id=ids.get("ArXiv")
        or (details.paper_id.split(":", 1)[1] if provider == "arxiv" else None),
        semantic_scholar_id=details.paper_id
        if provider == "semantic_scholar"
        else None,
    )
    key = canonical_paper_key(external, details.title, details.year)
    now = utc_now()
    return Paper(
        id=stable_id(key),
        canonical_key=key,
        title=details.title or "Untitled paper",
        abstract=details.abstract,
        semantic_scholar_id=external.semantic_scholar_id,
        arxiv_id=external.arxiv_id,
        doi=external.doi,
        year=details.year,
        venue=details.venue,
        citation_count=details.citation_count,
        authors=[a.model_dump() for a in details.authors],
        url=details.url,
        open_access_pdf_url=details.open_access_pdf.url
        if details.open_access_pdf
        else None,
        metadata={"provider": provider},
        created_at=now,
        updated_at=now,
    )


async def search_provider(name, query, filters, limits):
    if name == "openalex":
        from .openalex import OpenAlexClient

        async with asyncio.timeout(limits.provider_timeout_seconds):
            async with OpenAlexClient() as client:
                found = await client.search(
                    query, limit=limits.search_limit, filters=filters
                )
                return found[: limits.max_papers]
    if name == "arxiv":
        from ..arxiv.adapters import ArXivAdapter

        adapter = ArXivAdapter()
    elif name == "semantic_scholar":
        from ..semantic_scholar.adapters import SemanticScholarAdapter

        adapter = SemanticScholarAdapter()
    else:
        raise ValueError(f"Unsupported research source: {name}")
    async with asyncio.timeout(limits.provider_timeout_seconds):
        async with adapter:
            found = await adapter.search_papers(
                query,
                filters=SearchFilters.model_validate(filters),
                limit=limits.search_limit,
            )
            # Fetch metadata and full text only for candidates selected for processing.
            selected = found[: limits.max_papers]
            if not selected:
                return []
            details = await adapter.fetch_papers([p.paper_id for p in selected])
            return [to_product_paper(p, name) for p in details]


async def enrich_citations(papers):
    """Add OpenAlex IDs and reference lists so the map can draw observed citations."""

    from .openalex import OpenAlexClient

    if not papers:
        return papers
    async with OpenAlexClient() as client:
        found = await client.lookup(papers)
    enriched = []
    for paper in papers:
        match = found.get(paper.canonical_key)
        if match is None:
            enriched.append(paper)
            continue
        enriched.append(
            paper.model_copy(
                update={
                    "openalex_id": paper.openalex_id or match.openalex_id,
                    "doi": paper.doi or match.doi,
                    "citation_count": paper.citation_count
                    if paper.citation_count is not None
                    else match.citation_count,
                    "abstract": paper.abstract or match.abstract,
                    "reference_count": paper.reference_count
                    if paper.reference_count is not None
                    else match.reference_count,
                    "open_access_pdf_url": paper.open_access_pdf_url
                    or match.open_access_pdf_url,
                    "metadata": {
                        **paper.metadata,
                        "references": match.metadata.get("references", []),
                        "citations_source": "openalex",
                    },
                }
            )
        )
    return enriched
