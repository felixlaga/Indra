"""Paper selection tools for agent autonomy.

This module provides tools for intelligent paper selection, including:
- Paper quality metrics (citations, velocity, venue tier, etc.)
- Diversity scoring for paper selection
- Search with configurable filters
- Citation graph traversal
- Paper clustering by topic similarity

These tools are designed to be used by an autonomous agent to make
informed decisions about which papers to include in research.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from ..semantic_scholar import (
    SemanticScholarAdapter,
    SearchFilters,
    PaperDetails,
)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Context Manager Helper
# -----------------------------------------------------------------------------


class _AdapterContext:
    """Helper to manage SemanticScholarAdapter lifecycle safely.

    Ensures proper resource cleanup even when exceptions occur.
    Use with 'async with' to safely manage adapter lifecycle.
    """

    def __init__(self, adapter: SemanticScholarAdapter | None = None):
        self._provided_adapter = adapter
        self._created_adapter: SemanticScholarAdapter | None = None

    async def __aenter__(self) -> SemanticScholarAdapter:
        if self._provided_adapter is not None:
            return self._provided_adapter
        self._created_adapter = SemanticScholarAdapter()
        await self._created_adapter.__aenter__()
        return self._created_adapter

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._created_adapter is not None:
            await self._created_adapter.__aexit__(exc_type, exc_val, exc_tb)


# -----------------------------------------------------------------------------
# Result Types (dataclasses for structured output)
# -----------------------------------------------------------------------------


@dataclass
class PaperMetrics:
    """Quality metrics for a single paper.

    Attributes:
        paper_id: Semantic Scholar paper ID
        citation_count: Total number of citations
        citation_velocity: Citations per year since publication
        publication_year: Year of publication
        venue_tier: Estimated venue tier (1=top tier, 2=good, 3=other)
        author_h_index_avg: Average h-index of authors (if available)
        is_open_access: Whether the paper has open access PDF
        fields_of_study: List of research fields
    """
    paper_id: str
    citation_count: int
    citation_velocity: float
    publication_year: int | None
    venue_tier: int
    author_h_index_avg: float | None
    is_open_access: bool
    fields_of_study: list[str] = field(default_factory=list)


@dataclass
class DiversityScore:
    """Diversity analysis for adding a paper to a collection.

    Attributes:
        paper_id: The paper being evaluated
        topic_similarity: Average similarity to existing papers (0-1, lower = more diverse)
        unique_authors: Number of authors not in existing papers
        unique_venue: Whether the venue is different from existing papers
        unique_methodology: Whether the paper uses different methods
        diversity_score: Overall diversity score (0-1, higher = more diverse)
        recommendation: Whether to include this paper ("include", "skip", "consider")
        reasoning: Explanation for the recommendation
    """
    paper_id: str
    topic_similarity: float
    unique_authors: int
    unique_venue: bool
    unique_methodology: bool
    diversity_score: float
    recommendation: Literal["include", "skip", "consider"]
    reasoning: str


@dataclass
class SearchResult:
    """Result of a paper search operation.

    Attributes:
        papers: List of paper details matching the search
        total_results: Total number of results available
        filters_applied: The filters that were applied
        query: The original search query
    """
    papers: list[PaperDetails]
    total_results: int
    filters_applied: dict[str, Any]
    query: str


@dataclass
class CitationGraph:
    """Citation graph for a paper.

    Attributes:
        paper_id: The central paper
        direction: "forward" (papers citing this) or "backward" (papers cited by this)
        depth: How many levels of citations were traversed
        papers: List of papers in the citation graph
        edges: List of (citing_paper_id, cited_paper_id) tuples
    """
    paper_id: str
    direction: Literal["forward", "backward"]
    depth: int
    papers: list[PaperDetails]
    edges: list[tuple[str, str]]


@dataclass
class PaperCluster:
    """A cluster of related papers.

    Attributes:
        cluster_id: Unique identifier for this cluster
        topic_label: Descriptive label for the cluster topic
        paper_ids: List of paper IDs in this cluster
        centroid_paper_id: The paper closest to the cluster center
    """
    cluster_id: int
    topic_label: str
    paper_ids: list[str]
    centroid_paper_id: str | None


@dataclass
class ClusterResult:
    """Result of clustering papers.

    Attributes:
        clusters: List of paper clusters
        suggested_splits: Suggested ways to split papers for parallel exploration
        silhouette_score: Quality of clustering (0-1, higher = better)
    """
    clusters: list[PaperCluster]
    suggested_splits: list[list[str]]
    silhouette_score: float


# -----------------------------------------------------------------------------
# Venue Tier Classification
# -----------------------------------------------------------------------------

# Top-tier venues (Tier 1)
TOP_TIER_VENUES = {
    # ML/AI conferences
    "neurips", "nips", "icml", "iclr", "aaai", "ijcai",
    # NLP conferences
    "acl", "emnlp", "naacl", "eacl",
    # CV conferences
    "cvpr", "iccv", "eccv",
    # General CS
    "nature", "science", "cell",
    # ML journals
    "jmlr", "journal of machine learning research",
    # Top AI venues
    "artificial intelligence", "machine learning",
}

# Good venues (Tier 2)
GOOD_VENUES = {
    "coling", "conll", "aistats", "uai", "colt",
    "wacv", "bmvc", "accv",
    "www", "kdd", "sigir",
    "acm computing surveys",
    "ieee transactions",
    "plos one", "scientific reports",
}


def _classify_venue_tier(venue: str | None) -> int:
    """Classify a venue into tiers (1=top, 2=good, 3=other)."""
    if not venue:
        return 3

    venue_lower = venue.lower()

    for top_venue in TOP_TIER_VENUES:
        if top_venue in venue_lower:
            return 1

    for good_venue in GOOD_VENUES:
        if good_venue in venue_lower:
            return 2

    return 3


# -----------------------------------------------------------------------------
# Tool Functions
# -----------------------------------------------------------------------------


async def get_paper_metrics(
    paper_id: str,
    adapter: SemanticScholarAdapter | None = None,
) -> PaperMetrics:
    """
    Get quality metrics for a paper.

    Retrieves citation count, citation velocity, publication year, venue tier,
    author h-index average, and open access status for a paper.

    Args:
        paper_id: Semantic Scholar paper ID
        adapter: Optional SemanticScholarAdapter instance. If not provided,
                creates a new one.

    Returns:
        PaperMetrics with all available quality indicators

    Example:
        >>> async with SemanticScholarAdapter() as adapter:
        ...     metrics = await get_paper_metrics("649def34f8be52c8b66281af98ae884c09aef38b", adapter)
        ...     print(f"Citations: {metrics.citation_count}")
    """
    async with _AdapterContext(adapter) as active_adapter:
        # Fetch paper details
        papers = await active_adapter.fetch_papers([paper_id])

        if not papers:
            logger.warning(f"Paper not found: {paper_id}")
            return PaperMetrics(
                paper_id=paper_id,
                citation_count=0,
                citation_velocity=0.0,
                publication_year=None,
                venue_tier=3,
                author_h_index_avg=None,
                is_open_access=False,
                fields_of_study=[],
            )

        paper = papers[0]

        # Calculate citation velocity
        current_year = datetime.now().year
        years_since_publication = max(1, current_year - (paper.year or current_year))
        citation_velocity = (paper.citation_count or 0) / years_since_publication

        # Classify venue tier
        venue_tier = _classify_venue_tier(paper.venue)

        # Check open access
        is_open_access = paper.open_access_pdf is not None

        # Author h-index would require additional API calls per author
        # Placeholder: could be enhanced to fetch author details
        author_h_index_avg = None

        return PaperMetrics(
            paper_id=paper_id,
            citation_count=paper.citation_count or 0,
            citation_velocity=round(citation_velocity, 2),
            publication_year=paper.year,
            venue_tier=venue_tier,
            author_h_index_avg=author_h_index_avg,
            is_open_access=is_open_access,
            fields_of_study=paper.fields_of_study or [],
        )


async def calculate_diversity_score(
    paper_id: str,
    selected_paper_ids: list[str],
    adapter: SemanticScholarAdapter | None = None,
) -> DiversityScore:
    """
    Calculate how diverse a paper is compared to already selected papers.

    Evaluates topic similarity, author overlap, venue uniqueness, and
    methodology differences to provide a diversity score and recommendation.

    Args:
        paper_id: The paper to evaluate for diversity
        selected_paper_ids: List of already selected paper IDs
        adapter: Optional SemanticScholarAdapter instance

    Returns:
        DiversityScore with topic_similarity, unique factors, and recommendation

    Example:
        >>> async with SemanticScholarAdapter() as adapter:
        ...     score = await calculate_diversity_score(
        ...         "paper123",
        ...         ["paper456", "paper789"],
        ...         adapter
        ...     )
        ...     if score.recommendation == "include":
        ...         print("Add this paper for diversity!")
    """
    # Handle empty selection (no adapter needed)
    if not selected_paper_ids:
        return DiversityScore(
            paper_id=paper_id,
            topic_similarity=0.0,
            unique_authors=0,
            unique_venue=True,
            unique_methodology=True,
            diversity_score=1.0,
            recommendation="include",
            reasoning="First paper - automatically included for diversity.",
        )

    async with _AdapterContext(adapter) as active_adapter:
        # Fetch all papers
        all_paper_ids = [paper_id] + selected_paper_ids
        papers = await active_adapter.fetch_papers(all_paper_ids)

        if not papers:
            return DiversityScore(
                paper_id=paper_id,
                topic_similarity=0.0,
                unique_authors=0,
                unique_venue=True,
                unique_methodology=True,
                diversity_score=0.5,
                recommendation="consider",
                reasoning="Could not fetch paper details.",
            )

        # Find the candidate paper and selected papers
        candidate = None
        selected = []
        for p in papers:
            if p.paper_id == paper_id:
                candidate = p
            elif p.paper_id in selected_paper_ids:
                selected.append(p)

        if candidate is None:
            return DiversityScore(
                paper_id=paper_id,
                topic_similarity=0.0,
                unique_authors=0,
                unique_venue=True,
                unique_methodology=True,
                diversity_score=0.5,
                recommendation="consider",
                reasoning="Candidate paper not found.",
            )

        # Calculate topic similarity using fields of study
        candidate_fields = set(candidate.fields_of_study or [])
        all_selected_fields: set[str] = set()
        for p in selected:
            all_selected_fields.update(p.fields_of_study or [])

        if candidate_fields and all_selected_fields:
            intersection = len(candidate_fields & all_selected_fields)
            union = len(candidate_fields | all_selected_fields)
            topic_similarity = intersection / union if union > 0 else 0.0
        else:
            topic_similarity = 0.0

        # Calculate unique authors
        candidate_author_ids = {
            a.author_id for a in candidate.authors if a.author_id
        }
        selected_author_ids: set[str] = set()
        for p in selected:
            selected_author_ids.update(
                a.author_id for a in p.authors if a.author_id
            )
        unique_authors = len(candidate_author_ids - selected_author_ids)

        # Check venue uniqueness
        candidate_venue = (candidate.venue or "").lower().strip()
        selected_venues = {
            (p.venue or "").lower().strip() for p in selected
        }
        unique_venue = candidate_venue not in selected_venues or not candidate_venue

        # Methodology detection (based on publication types)
        candidate_types = set(candidate.publication_types or [])
        selected_types: set[str] = set()
        for p in selected:
            selected_types.update(p.publication_types or [])
        unique_methodology = not candidate_types.issubset(selected_types)

        # Calculate overall diversity score
        # Higher is more diverse
        diversity_factors = [
            1.0 - topic_similarity,  # Low similarity = high diversity
            min(1.0, unique_authors / 3),  # 3+ unique authors = max score
            1.0 if unique_venue else 0.0,
            1.0 if unique_methodology else 0.0,
        ]
        diversity_score = sum(diversity_factors) / len(diversity_factors)

        # Generate recommendation
        if diversity_score >= 0.6:
            recommendation: Literal["include", "skip", "consider"] = "include"
            reasoning = "High diversity - adds new perspectives to the collection."
        elif diversity_score >= 0.3:
            recommendation = "consider"
            reasoning = "Moderate diversity - may add some value."
        else:
            recommendation = "skip"
            reasoning = "Low diversity - similar to existing papers."

        return DiversityScore(
            paper_id=paper_id,
            topic_similarity=round(topic_similarity, 3),
            unique_authors=unique_authors,
            unique_venue=unique_venue,
            unique_methodology=unique_methodology,
            diversity_score=round(diversity_score, 3),
            recommendation=recommendation,
            reasoning=reasoning,
        )


async def search_papers(
    query: str,
    limit: int = 20,
    filters: dict[str, Any] | None = None,
    adapter: SemanticScholarAdapter | None = None,
) -> SearchResult:
    """
    Search for papers with configurable limit and filters.

    Wraps the Semantic Scholar search API with structured output.

    Args:
        query: Search query string
        limit: Maximum number of papers to return (default: 20)
        filters: Optional dict of filters:
            - year: Year range string (e.g., "2020-2024")
            - start_date: Start date (e.g., "2023-01-01")
            - end_date: End date (e.g., "2024-12-31")
            - fields_of_study: List of fields (e.g., ["Computer Science"])
            - min_citation_count: Minimum citations
            - publication_types: List of types (e.g., ["JournalArticle"])
            - open_access_only: Boolean for open access filter
        adapter: Optional SemanticScholarAdapter instance

    Returns:
        SearchResult with papers, total count, and applied filters

    Example:
        >>> async with SemanticScholarAdapter() as adapter:
        ...     result = await search_papers(
        ...         "transformer attention mechanism",
        ...         limit=10,
        ...         filters={"min_citation_count": 100, "open_access_only": True},
        ...         adapter=adapter
        ...     )
        ...     print(f"Found {result.total_results} papers")
    """
    async with _AdapterContext(adapter) as active_adapter:
        # Build SearchFilters from dict
        filter_params = filters or {}
        search_filters = SearchFilters(
            year=filter_params.get("year"),
            start_date=filter_params.get("start_date"),
            end_date=filter_params.get("end_date"),
            fields_of_study=filter_params.get("fields_of_study"),
            min_citation_count=filter_params.get("min_citation_count"),
            publication_types=filter_params.get("publication_types"),
            open_access_only=filter_params.get("open_access_only", False),
        )

        logger.info(f"Searching papers: query='{query}', limit={limit}")

        # Search for papers
        papers = await active_adapter.search_papers(
            query=query,
            filters=search_filters,
            limit=limit,
        )

        # Convert to PaperDetails for richer information
        paper_ids = [p.paper_id for p in papers]
        detailed_papers = await active_adapter.fetch_papers(paper_ids) if paper_ids else []

        return SearchResult(
            papers=detailed_papers,
            total_results=len(papers),  # Note: Could fetch actual total from API
            filters_applied=filter_params,
            query=query,
        )


async def get_citation_graph(
    paper_id: str,
    direction: Literal["forward", "backward"] = "forward",
    depth: int = 1,
    limit_per_level: int = 20,
    adapter: SemanticScholarAdapter | None = None,
) -> CitationGraph:
    """
    Get citation graph for a paper.

    Traverses the citation network in the specified direction up to the
    given depth. Forward citations are papers that cite this paper;
    backward citations are papers that this paper cites.

    Args:
        paper_id: The central paper ID
        direction: "forward" (citing papers) or "backward" (references)
        depth: How many levels to traverse (1-3 recommended)
        limit_per_level: Maximum papers per level of traversal
        adapter: Optional SemanticScholarAdapter instance

    Returns:
        CitationGraph with papers and citation edges

    Example:
        >>> async with SemanticScholarAdapter() as adapter:
        ...     graph = await get_citation_graph(
        ...         "paper123",
        ...         direction="forward",
        ...         depth=2,
        ...         adapter=adapter
        ...     )
        ...     print(f"Found {len(graph.papers)} papers in citation graph")
    """
    async with _AdapterContext(adapter) as active_adapter:
        all_papers: dict[str, PaperDetails] = {}
        edges: list[tuple[str, str]] = []
        current_level_ids = [paper_id]

        for level in range(depth):
            next_level_ids: list[str] = []

            for current_id in current_level_ids:
                if direction == "forward":
                    # Get papers that cite this paper
                    citations = await active_adapter.get_citations(
                        current_id, limit=limit_per_level
                    )
                    for citing_paper in citations:
                        if citing_paper.paper_id not in all_papers:
                            all_papers[citing_paper.paper_id] = citing_paper
                            next_level_ids.append(citing_paper.paper_id)
                        # Edge: citing_paper -> current_id
                        edges.append((citing_paper.paper_id, current_id))
                else:
                    # Get papers that this paper cites
                    references = await active_adapter.get_references(
                        current_id, limit=limit_per_level
                    )
                    for cited_paper in references:
                        if cited_paper.paper_id not in all_papers:
                            all_papers[cited_paper.paper_id] = cited_paper
                            next_level_ids.append(cited_paper.paper_id)
                        # Edge: current_id -> cited_paper
                        edges.append((current_id, cited_paper.paper_id))

            current_level_ids = next_level_ids

            if not current_level_ids:
                break

        return CitationGraph(
            paper_id=paper_id,
            direction=direction,
            depth=depth,
            papers=list(all_papers.values()),
            edges=edges,
        )


async def cluster_papers(
    paper_ids: list[str],
    num_clusters: int | None = None,
    adapter: SemanticScholarAdapter | None = None,
) -> ClusterResult:
    """
    Group papers by topic similarity.

    Clusters papers based on their fields of study and abstract content.
    Returns clusters with suggested splits for parallel exploration.

    Args:
        paper_ids: List of paper IDs to cluster
        num_clusters: Number of clusters (auto-detected if None)
        adapter: Optional SemanticScholarAdapter instance

    Returns:
        ClusterResult with clusters and suggested splits

    Note:
        This is a placeholder implementation using fields of study.
        For production use, consider integrating with embedding models
        for semantic clustering.

    Example:
        >>> async with SemanticScholarAdapter() as adapter:
        ...     result = await cluster_papers(
        ...         ["paper1", "paper2", "paper3"],
        ...         num_clusters=2,
        ...         adapter=adapter
        ...     )
        ...     for cluster in result.clusters:
        ...         print(f"Cluster {cluster.cluster_id}: {cluster.topic_label}")
    """
    # Handle empty input (no adapter needed)
    if not paper_ids:
        return ClusterResult(
            clusters=[],
            suggested_splits=[],
            silhouette_score=0.0,
        )

    async with _AdapterContext(adapter) as active_adapter:
        # Fetch paper details
        papers = await active_adapter.fetch_papers(paper_ids)

        if not papers:
            return ClusterResult(
                clusters=[],
                suggested_splits=[],
                silhouette_score=0.0,
            )

        # Simple clustering by primary field of study
        # This is a placeholder - could be enhanced with embeddings
        field_to_papers: dict[str, list[PaperDetails]] = {}
        uncategorized: list[PaperDetails] = []

        for paper in papers:
            if paper.fields_of_study:
                primary_field = paper.fields_of_study[0]
                if primary_field not in field_to_papers:
                    field_to_papers[primary_field] = []
                field_to_papers[primary_field].append(paper)
            else:
                uncategorized.append(paper)

        # Add uncategorized papers to an "Other" cluster
        if uncategorized:
            field_to_papers["Other"] = uncategorized

        # Limit number of clusters if specified
        if num_clusters and len(field_to_papers) > num_clusters:
            # Merge smallest clusters
            sorted_fields = sorted(
                field_to_papers.items(),
                key=lambda x: len(x[1]),
                reverse=True
            )
            merged: dict[str, list[PaperDetails]] = {}
            for i, (field, field_papers) in enumerate(sorted_fields):
                if i < num_clusters - 1:
                    merged[field] = field_papers
                else:
                    if "Other" not in merged:
                        merged["Other"] = []
                    merged["Other"].extend(field_papers)
            field_to_papers = merged

        # Build clusters
        clusters: list[PaperCluster] = []
        for i, (field, field_papers) in enumerate(field_to_papers.items()):
            # Centroid: paper with most citations in cluster
            centroid = max(
                field_papers,
                key=lambda p: p.citation_count or 0,
                default=None
            )

            clusters.append(PaperCluster(
                cluster_id=i,
                topic_label=field,
                paper_ids=[p.paper_id for p in field_papers],
                centroid_paper_id=centroid.paper_id if centroid else None,
            ))

        # Suggested splits: one branch per cluster
        suggested_splits = [cluster.paper_ids for cluster in clusters]

        # Silhouette score placeholder
        # Real implementation would compute cluster quality
        silhouette_score = 0.5 if len(clusters) > 1 else 1.0

        return ClusterResult(
            clusters=clusters,
            suggested_splits=suggested_splits,
            silhouette_score=silhouette_score,
        )


# -----------------------------------------------------------------------------
# Tool Registration
# -----------------------------------------------------------------------------


@dataclass
class PaperToolDefinition:
    """Definition of a paper tool for agent use.

    Note: Named PaperToolDefinition to avoid confusion with
    ToolDefinition in orchestration/tools.py
    """
    name: str
    description: str
    parameters: dict[str, dict[str, Any]]
    required_params: list[str]
    func: Any  # Callable[..., Awaitable[Any]]


# Tool registry for agent access
TOOLS: dict[str, PaperToolDefinition] = {
    "get_paper_metrics": PaperToolDefinition(
        name="get_paper_metrics",
        description=(
            "Get quality metrics for a paper including citation count, "
            "citation velocity, publication year, venue tier, and open access status. "
            "Use this to evaluate paper quality before selection."
        ),
        parameters={
            "paper_id": {
                "type": "string",
                "description": "Semantic Scholar paper ID",
            },
        },
        required_params=["paper_id"],
        func=get_paper_metrics,
    ),
    "calculate_diversity_score": PaperToolDefinition(
        name="calculate_diversity_score",
        description=(
            "Calculate how diverse a paper is compared to already selected papers. "
            "Returns topic similarity, unique authors/venue/methodology, and a "
            "recommendation on whether to include the paper."
        ),
        parameters={
            "paper_id": {
                "type": "string",
                "description": "Paper ID to evaluate for diversity",
            },
            "selected_paper_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of already selected paper IDs",
            },
        },
        required_params=["paper_id", "selected_paper_ids"],
        func=calculate_diversity_score,
    ),
    "search_papers": PaperToolDefinition(
        name="search_papers",
        description=(
            "Search for papers with configurable limit and filters. "
            "Supports filtering by year, fields of study, citation count, "
            "publication types, and open access status."
        ),
        parameters={
            "query": {
                "type": "string",
                "description": "Search query string",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of papers to return (default: 20)",
            },
            "filters": {
                "type": "object",
                "description": "Optional filters (year, fields_of_study, min_citation_count, etc.)",
            },
        },
        required_params=["query"],
        func=search_papers,
    ),
    "get_citation_graph": PaperToolDefinition(
        name="get_citation_graph",
        description=(
            "Get citation graph for a paper. 'forward' gets papers that cite this paper; "
            "'backward' gets papers that this paper cites. Traverses up to specified depth."
        ),
        parameters={
            "paper_id": {
                "type": "string",
                "description": "Central paper ID",
            },
            "direction": {
                "type": "string",
                "enum": ["forward", "backward"],
                "description": "Direction of citation traversal",
            },
            "depth": {
                "type": "integer",
                "description": "Levels to traverse (1-3 recommended)",
            },
        },
        required_params=["paper_id"],
        func=get_citation_graph,
    ),
    "cluster_papers": PaperToolDefinition(
        name="cluster_papers",
        description=(
            "Group papers by topic similarity. Returns clusters with topic labels "
            "and suggested ways to split papers for parallel exploration."
        ),
        parameters={
            "paper_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of paper IDs to cluster",
            },
            "num_clusters": {
                "type": "integer",
                "description": "Number of clusters (auto-detected if not specified)",
            },
        },
        required_params=["paper_ids"],
        func=cluster_papers,
    ),
}


def get_tool_schema() -> list[dict[str, Any]]:
    """
    Get OpenAI-style function schema for all paper tools.

    Returns:
        List of tool schemas for LLM function calling

    Example:
        >>> schema = get_tool_schema()
        >>> # Use with OpenAI-compatible API
        >>> response = llm.create(tools=schema, ...)
    """
    schemas = []

    for tool_def in TOOLS.values():
        schema = {
            "type": "function",
            "function": {
                "name": tool_def.name,
                "description": tool_def.description,
                "parameters": {
                    "type": "object",
                    "properties": tool_def.parameters,
                    "required": tool_def.required_params,
                },
            },
        }
        schemas.append(schema)

    return schemas
