"""Data models for the recursive research agent system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..semantic_scholar import PaperDetails, SearchFilters


class BranchStatus(Enum):
    """Status of a research branch."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    PRUNED = "pruned"


class InnerLoopMode(Enum):
    """Mode of the inner loop."""

    SEARCH_SUMMARIZE = "search_summarize"  # Variant A: search → summarize → validate
    HYPOTHESIS = "hypothesis"  # Variant B: same + generate hypotheses


@dataclass
class ValidatedSummary:
    """A summary that has passed HaluGate validation."""

    paper_id: str
    paper_title: str
    summary: str
    groundedness: float  # Must be ≥0.95 for research loop
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if self.groundedness < 0:
            raise ValueError("Groundedness must be non-negative")


@dataclass
class ResearchHypothesis:
    """A research hypothesis generated from validated summaries."""

    id: str
    text: str  # The research question/hypothesis
    supporting_paper_ids: list[str]
    confidence: float  # 0-1 confidence score
    generated_from_branch: str
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not 0 <= self.confidence <= 1:
            raise ValueError("Confidence must be between 0 and 1")


@dataclass
class IterationResult:
    """Result of a single iteration in the research loop."""

    iteration_number: int
    papers_found: list[PaperDetails]
    summaries: list[ValidatedSummary]
    hypotheses: list[ResearchHypothesis] | None  # Only if in hypothesis mode
    context_tokens_used: int
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def paper_count(self) -> int:
        """Number of papers found in this iteration."""
        return len(self.papers_found)

    @property
    def validated_summary_count(self) -> int:
        """Number of summaries that passed validation."""
        return len(self.summaries)


@dataclass
class Branch:
    """A research branch exploring a specific query or topic."""

    id: str
    query: str
    mode: InnerLoopMode
    status: BranchStatus
    parent_branch_id: str | None = None
    filters: SearchFilters | None = None
    iterations: list[IterationResult] = field(default_factory=list)
    accumulated_papers: dict[str, PaperDetails] = field(default_factory=dict)
    accumulated_summaries: dict[str, ValidatedSummary] = field(default_factory=dict)
    context_window_used: int = 0
    max_context_window: int = 128000
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def context_utilization(self) -> float:
        """Fraction of context window used (0-1)."""
        return self.context_window_used / self.max_context_window

    @property
    def is_context_nearly_full(self) -> bool:
        """Check if context window is ≥80% full (soft warning threshold).

        Note: This is now a soft warning, not a forced split trigger.
        The managing agent makes autonomous decisions about when to split.
        """
        return self.context_utilization >= 0.8

    @property
    def context_status(self) -> str:
        """Get human-readable context status.

        Returns status string indicating context utilization level.
        """
        utilization = self.context_utilization
        if utilization >= 0.90:
            return f"critical ({utilization:.0%})"
        elif utilization >= 0.80:
            return f"high ({utilization:.0%})"
        elif utilization >= 0.70:
            return f"moderate ({utilization:.0%})"
        else:
            return f"low ({utilization:.0%})"

    @property
    def total_papers(self) -> int:
        """Total number of unique papers accumulated."""
        return len(self.accumulated_papers)

    @property
    def total_summaries(self) -> int:
        """Total number of validated summaries."""
        return len(self.accumulated_summaries)

    @property
    def iteration_count(self) -> int:
        """Number of iterations completed."""
        return len(self.iterations)

    def add_iteration(self, result: IterationResult) -> None:
        """Add an iteration result and update accumulated state."""
        self.iterations.append(result)
        self.context_window_used += result.context_tokens_used
        self.updated_at = datetime.now()

        # Update accumulated papers
        for paper in result.papers_found:
            self.accumulated_papers[paper.paper_id] = paper

        # Update accumulated summaries
        for summary in result.summaries:
            self.accumulated_summaries[summary.paper_id] = summary

    def get_all_hypotheses(self) -> list[ResearchHypothesis]:
        """Get all hypotheses generated across all iterations."""
        hypotheses = []
        for iteration in self.iterations:
            if iteration.hypotheses:
                hypotheses.extend(iteration.hypotheses)
        return hypotheses


@dataclass
class LoopState:
    """State of the entire research loop (can span multiple big loops)."""

    loop_id: str
    loop_number: int  # 1 = initial loop, 2+ = hypothesis-seeded loops
    session_filters: SearchFilters | None = None
    branches: dict[str, Branch] = field(default_factory=dict)
    hypotheses: list[ResearchHypothesis] = field(default_factory=list)
    seeding_hypotheses: list[ResearchHypothesis] | None = None  # For Big Loop 2+
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def active_branches(self) -> list[Branch]:
        """Get branches that are running or pending."""
        return [
            b for b in self.branches.values()
            if b.status in (BranchStatus.RUNNING, BranchStatus.PENDING)
        ]

    @property
    def total_papers(self) -> int:
        """Total unique papers across all branches."""
        all_paper_ids = set()
        for branch in self.branches.values():
            all_paper_ids.update(branch.accumulated_papers.keys())
        return len(all_paper_ids)

    @property
    def total_summaries(self) -> int:
        """Total validated summaries across all branches."""
        all_summary_ids = set()
        for branch in self.branches.values():
            all_summary_ids.update(branch.accumulated_summaries.keys())
        return len(all_summary_ids)

    def add_branch(self, branch: Branch) -> None:
        """Add a new branch to the loop state."""
        self.branches[branch.id] = branch
        self.updated_at = datetime.now()

    def get_branch(self, branch_id: str) -> Branch | None:
        """Get a branch by ID."""
        return self.branches.get(branch_id)

    def collect_all_hypotheses(self) -> list[ResearchHypothesis]:
        """Collect all hypotheses from all branches."""
        all_hypotheses = list(self.hypotheses)
        for branch in self.branches.values():
            all_hypotheses.extend(branch.get_all_hypotheses())
        return all_hypotheses


@dataclass
class BranchSplitResult:
    """Result of splitting a branch."""

    original_branch_id: str
    new_branch_ids: list[str]
    split_criteria: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LoopStatus:
    """Status summary for monitoring."""

    loop_id: str
    loop_number: int
    total_branches: int
    active_branches: int
    completed_branches: int
    pruned_branches: int
    total_papers: int
    total_summaries: int
    total_hypotheses: int
    total_context_used: int

    @classmethod
    def from_loop_state(cls, state: LoopState) -> LoopStatus:
        """Create status from loop state."""
        status_counts = {}
        total_context = 0
        for branch in state.branches.values():
            status_counts[branch.status] = status_counts.get(branch.status, 0) + 1
            total_context += branch.context_window_used

        return cls(
            loop_id=state.loop_id,
            loop_number=state.loop_number,
            total_branches=len(state.branches),
            active_branches=status_counts.get(BranchStatus.RUNNING, 0)
            + status_counts.get(BranchStatus.PENDING, 0),
            completed_branches=status_counts.get(BranchStatus.COMPLETED, 0),
            pruned_branches=status_counts.get(BranchStatus.PRUNED, 0),
            total_papers=state.total_papers,
            total_summaries=state.total_summaries,
            total_hypotheses=len(state.collect_all_hypotheses()),
            total_context_used=total_context,
        )
