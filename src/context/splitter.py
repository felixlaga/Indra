"""Branch splitting strategies for managing context windows."""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..orchestration.models import Branch, ValidatedSummary
    from ..semantic_scholar import PaperDetails

logger = logging.getLogger(__name__)


class SplitStrategy(Enum):
    """Strategies for splitting branches."""

    BY_TOPIC = "by_topic"  # Split by research topic/field
    BY_TIME = "by_time"  # Split by publication year
    BY_FIELD = "by_field"  # Split by field of study
    BY_CITATION_COUNT = "by_citation_count"  # Split by citation count (high vs low impact)
    RANDOM = "random"  # Random split for load balancing


@dataclass
class SplitResult:
    """Result of a split operation."""

    strategy: SplitStrategy
    groups: list[list[str]]  # Lists of paper IDs per group
    group_queries: list[str]  # Suggested query refinements per group
    group_labels: list[str]  # Human-readable labels


class BranchSplitter:
    """
    Splits branches when context window is nearly full.

    Implements various strategies to divide the research space
    into coherent sub-branches.
    """

    def __init__(self, default_num_splits: int = 2):
        """
        Initialize the branch splitter.

        Args:
            default_num_splits: Default number of splits to create
        """
        self.default_num_splits = default_num_splits

    def analyze_papers(
        self,
        papers: list[PaperDetails],
    ) -> dict:
        """
        Analyze papers to suggest split strategies.

        Args:
            papers: List of papers to analyze

        Returns:
            Dict with analysis results for each strategy
        """
        analysis = {
            "total_papers": len(papers),
            "strategies": {},
        }

        # Analyze by field of study
        fields = defaultdict(list)
        for paper in papers:
            if paper.fields_of_study:
                for field in paper.fields_of_study:
                    fields[field].append(paper.paper_id)
            else:
                fields["Unknown"].append(paper.paper_id)

        analysis["strategies"]["by_field"] = {
            "num_fields": len(fields),
            "field_counts": {k: len(v) for k, v in fields.items()},
            "viable": len(fields) >= 2,
        }

        # Analyze by year
        years = defaultdict(list)
        for paper in papers:
            year = paper.year or 0
            years[year].append(paper.paper_id)

        analysis["strategies"]["by_time"] = {
            "num_years": len(years),
            "year_range": (min(years.keys()), max(years.keys())) if years else (0, 0),
            "viable": len(years) >= 2,
        }

        # Analyze by citation count
        citation_counts = [(p.paper_id, p.citation_count or 0) for p in papers]
        median_citations = 0
        if citation_counts:
            sorted_counts = sorted(cc for _, cc in citation_counts)
            median_citations = sorted_counts[len(sorted_counts) // 2]

        analysis["strategies"]["by_citation_count"] = {
            "median_citations": median_citations,
            "high_impact": sum(1 for _, cc in citation_counts if cc > median_citations),
            "low_impact": sum(1 for _, cc in citation_counts if cc <= median_citations),
            "viable": len(papers) >= 4,  # Need enough papers for meaningful split
        }

        return analysis

    def split(
        self,
        branch: Branch,
        strategy: SplitStrategy = SplitStrategy.BY_FIELD,
        num_splits: int | None = None,
    ) -> SplitResult:
        """
        Split a branch using the specified strategy.

        Args:
            branch: Branch to split
            strategy: Split strategy to use
            num_splits: Number of splits (default from constructor)

        Returns:
            SplitResult with paper groupings and query suggestions
        """
        num_splits = num_splits or self.default_num_splits
        papers = list(branch.accumulated_papers.values())

        if strategy == SplitStrategy.BY_FIELD:
            return self._split_by_field(branch, papers, num_splits)
        elif strategy == SplitStrategy.BY_TIME:
            return self._split_by_time(branch, papers, num_splits)
        elif strategy == SplitStrategy.BY_CITATION_COUNT:
            return self._split_by_citation_count(branch, papers, num_splits)
        elif strategy == SplitStrategy.RANDOM:
            return self._split_random(branch, papers, num_splits)
        else:
            # Default to by_field
            return self._split_by_field(branch, papers, num_splits)

    def _split_by_field(
        self,
        branch: Branch,
        papers: list[PaperDetails],
        num_splits: int,
    ) -> SplitResult:
        """Split papers by field of study."""
        # Group papers by their primary field
        fields = defaultdict(list)
        for paper in papers:
            primary_field = (paper.fields_of_study or ["General"])[0]
            fields[primary_field].append(paper.paper_id)

        # Sort fields by paper count and take top N
        sorted_fields = sorted(fields.items(), key=lambda x: len(x[1]), reverse=True)
        top_fields = sorted_fields[:num_splits]

        # If we have fewer fields than splits, combine remaining into "Other"
        if len(sorted_fields) > num_splits:
            other_papers = []
            for field, paper_ids in sorted_fields[num_splits:]:
                other_papers.extend(paper_ids)
            if other_papers:
                top_fields.append(("Other", other_papers))

        groups = [paper_ids for _, paper_ids in top_fields]
        labels = [field for field, _ in top_fields]
        # Use quoted query with field context for better search results
        queries = [f'"{branch.query}" in {field}' for field in labels]

        return SplitResult(
            strategy=SplitStrategy.BY_FIELD,
            groups=groups,
            group_queries=queries,
            group_labels=labels,
        )

    def _split_by_time(
        self,
        branch: Branch,
        papers: list[PaperDetails],
        num_splits: int,
    ) -> SplitResult:
        """Split papers by publication year."""
        # Group by year
        by_year: dict[int, list[str]] = defaultdict(list)
        for paper in papers:
            year = paper.year or 0
            by_year[year].append(paper.paper_id)

        years = sorted(by_year.keys())
        if len(years) < num_splits:
            # Not enough years for requested splits, fall back to available
            num_splits = max(1, len(years))

        # Divide years into ranges
        papers_per_split = len(papers) // num_splits
        groups = []
        labels = []
        current_group: list[str] = []
        current_years: list[int] = []

        for year in years:
            current_group.extend(by_year[year])
            current_years.append(year)

            if len(current_group) >= papers_per_split and len(groups) < num_splits - 1:
                groups.append(current_group)
                if len(current_years) == 1:
                    labels.append(str(current_years[0]))
                else:
                    labels.append(f"{current_years[0]}-{current_years[-1]}")
                current_group = []
                current_years = []

        # Add remaining papers to last group
        if current_group or not groups:
            groups.append(current_group)
            if current_years:
                if len(current_years) == 1:
                    labels.append(str(current_years[0]))
                else:
                    labels.append(f"{current_years[0]}-{current_years[-1]}")
            else:
                labels.append("Unknown")

        # Use year range format for time-based search
        queries = [f'"{branch.query}" published:{label}' for label in labels]

        return SplitResult(
            strategy=SplitStrategy.BY_TIME,
            groups=groups,
            group_queries=queries,
            group_labels=labels,
        )

    def _split_by_citation_count(
        self,
        branch: Branch,
        papers: list[PaperDetails],
        num_splits: int,
    ) -> SplitResult:
        """Split papers by citation count (high vs low impact)."""
        # Sort by citation count
        sorted_papers = sorted(papers, key=lambda p: p.citation_count or 0, reverse=True)

        papers_per_split = max(1, len(sorted_papers) // num_splits)
        groups = []
        labels = []

        for i in range(num_splits):
            start = i * papers_per_split
            if i == num_splits - 1:
                # Last group gets remaining papers
                group_papers = sorted_papers[start:]
            else:
                group_papers = sorted_papers[start : start + papers_per_split]

            if group_papers:
                groups.append([p.paper_id for p in group_papers])
                min_citations = min(p.citation_count or 0 for p in group_papers)
                max_citations = max(p.citation_count or 0 for p in group_papers)
                labels.append(f"citations_{min_citations}-{max_citations}")

        # Create descriptive labels
        descriptive_labels = []
        for i, label in enumerate(labels):
            if i == 0:
                descriptive_labels.append("High Impact")
            elif i == len(labels) - 1:
                descriptive_labels.append("Emerging")
            else:
                descriptive_labels.append(f"Medium Impact {i}")

        # Use impact-specific query refinements
        queries = []
        for i, label in enumerate(descriptive_labels):
            if i == 0:
                queries.append(f'"{branch.query}" highly cited')
            elif i == len(descriptive_labels) - 1:
                queries.append(f'"{branch.query}" recent')
            else:
                queries.append(f'"{branch.query}"')

        return SplitResult(
            strategy=SplitStrategy.BY_CITATION_COUNT,
            groups=groups,
            group_queries=queries,
            group_labels=descriptive_labels,
        )

    def _split_random(
        self,
        branch: Branch,
        papers: list[PaperDetails],
        num_splits: int,
    ) -> SplitResult:
        """Split papers randomly (for load balancing)."""
        import random

        shuffled = papers.copy()
        random.shuffle(shuffled)

        papers_per_split = max(1, len(shuffled) // num_splits)
        groups = []
        labels = []

        for i in range(num_splits):
            start = i * papers_per_split
            if i == num_splits - 1:
                group_papers = shuffled[start:]
            else:
                group_papers = shuffled[start : start + papers_per_split]

            if group_papers:
                groups.append([p.paper_id for p in group_papers])
                labels.append(f"Branch {i + 1}")

        queries = [f"{branch.query} (split {i + 1})" for i in range(len(groups))]

        return SplitResult(
            strategy=SplitStrategy.RANDOM,
            groups=groups,
            group_queries=queries,
            group_labels=labels,
        )

    def suggest_strategy(self, branch: Branch) -> SplitStrategy:
        """
        Suggest the best split strategy based on branch content.

        Args:
            branch: Branch to analyze

        Returns:
            Recommended split strategy
        """
        papers = list(branch.accumulated_papers.values())
        analysis = self.analyze_papers(papers)

        # Prefer field-based split if there are multiple fields
        field_analysis = analysis["strategies"]["by_field"]
        if field_analysis["viable"] and field_analysis["num_fields"] >= 3:
            return SplitStrategy.BY_FIELD

        # Fall back to time-based if there's good year distribution
        time_analysis = analysis["strategies"]["by_time"]
        if time_analysis["viable"]:
            year_range = time_analysis["year_range"]
            if year_range[1] - year_range[0] >= 5:
                return SplitStrategy.BY_TIME

        # Use citation-based for impact analysis
        citation_analysis = analysis["strategies"]["by_citation_count"]
        if citation_analysis["viable"]:
            return SplitStrategy.BY_CITATION_COUNT

        # Default to random
        return SplitStrategy.RANDOM
