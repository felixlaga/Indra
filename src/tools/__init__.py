"""Tools for agent autonomy in paper selection."""

from .paper_tools import (
    # Result types
    PaperMetrics,
    DiversityScore,
    SearchResult,
    CitationGraph,
    PaperCluster,
    ClusterResult,
    PaperToolDefinition,
    # Tool functions
    get_paper_metrics,
    calculate_diversity_score,
    search_papers,
    get_citation_graph,
    cluster_papers,
    # Tool registration
    TOOLS,
    get_tool_schema,
)

__all__ = [
    # Result types
    "PaperMetrics",
    "DiversityScore",
    "SearchResult",
    "CitationGraph",
    "PaperCluster",
    "ClusterResult",
    "PaperToolDefinition",
    # Tool functions
    "get_paper_metrics",
    "calculate_diversity_score",
    "search_papers",
    "get_citation_graph",
    "cluster_papers",
    # Tool registration
    "TOOLS",
    "get_tool_schema",
]
