"""Protocol definitions for the recursive research agent system."""

from __future__ import annotations

from typing import Protocol, runtime_checkable, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import (
        Branch,
        BranchStatus,
        InnerLoopMode,
        IterationResult,
        LoopState,
        LoopStatus,
        ResearchHypothesis,
        ValidatedSummary,
    )
    from ..semantic_scholar import PaperDetails, SearchFilters


@runtime_checkable
class InnerLoopProtocol(Protocol):
    """
    Protocol for the Inner Loop (Layer 1).

    The Inner Loop is the atomic unit that:
    1. Searches for papers
    2. Summarizes them
    3. Validates summaries with HaluGate (≥95% groundedness)
    4. Optionally generates research hypotheses

    Two variants:
    - SEARCH_SUMMARIZE: Basic search → summarize → validate
    - HYPOTHESIS: Same + generate hypotheses from validated summaries
    """

    async def search_and_summarize(
        self,
        query: str,
        filters: SearchFilters | None = None,
        limit: int = 20,
    ) -> tuple[list[PaperDetails], list[ValidatedSummary]]:
        """
        Search for papers and generate validated summaries.

        Only returns summaries that pass HaluGate at ≥95% groundedness.

        Args:
            query: Search query string
            filters: Optional search filters
            limit: Maximum papers to process

        Returns:
            Tuple of (papers_found, validated_summaries)
        """
        ...

    async def generate_hypotheses(
        self,
        summaries: list[ValidatedSummary],
        branch_id: str,
    ) -> list[ResearchHypothesis]:
        """
        Generate research hypotheses from validated summaries.

        Args:
            summaries: List of validated summaries to generate hypotheses from
            branch_id: ID of the branch these hypotheses belong to

        Returns:
            List of generated research hypotheses
        """
        ...


@runtime_checkable
class IterationLoopProtocol(Protocol):
    """
    Protocol for the Iteration Loop (Layer 2).

    The Iteration Loop expands research depth by:
    1. Running Inner Loop with initial query
    2. Finding papers that cite/reference the found papers
    3. Running Inner Loop on those new papers
    4. Repeating for exponential growth

    Citation graph traversal:
    - Iter 1: query → papers P1-P5
    - Iter 2: citations(P1-P5) → papers P6-P20
    - Iter 3: citations(P6-P20) → papers P21-P80
    """

    async def run_iteration(
        self,
        branch: Branch,
    ) -> IterationResult:
        """
        Run a single iteration on a branch.

        If this is the first iteration, searches using the branch query.
        For subsequent iterations, finds papers that cite/reference
        papers from the previous iteration.

        Args:
            branch: The branch to run iteration on

        Returns:
            IterationResult with papers found and validated summaries
        """
        ...

    async def get_citing_papers(
        self,
        paper_ids: list[str],
        limit_per_paper: int = 20,
    ) -> list[PaperDetails]:
        """
        Get papers that cite the given papers.

        Args:
            paper_ids: IDs of papers to find citations for
            limit_per_paper: Max citations to fetch per paper

        Returns:
            List of citing papers (deduplicated)
        """
        ...

    async def get_referenced_papers(
        self,
        paper_ids: list[str],
        limit_per_paper: int = 20,
    ) -> list[PaperDetails]:
        """
        Get papers referenced by the given papers.

        Args:
            paper_ids: IDs of papers to find references for
            limit_per_paper: Max references to fetch per paper

        Returns:
            List of referenced papers (deduplicated)
        """
        ...


@runtime_checkable
class BranchManagerProtocol(Protocol):
    """
    Protocol for branch management.

    Handles branch lifecycle: creation, splitting, pruning.
    """

    def create_branch(
        self,
        query: str,
        mode: InnerLoopMode,
        parent_branch_id: str | None = None,
    ) -> Branch:
        """
        Create a new research branch.

        Args:
            query: Search query for this branch
            mode: Inner loop mode (search_summarize or hypothesis)
            parent_branch_id: ID of parent branch if this is a split

        Returns:
            Newly created branch
        """
        ...

    def split_branch(
        self,
        branch: Branch,
        criteria: str,
        num_splits: int = 2,
    ) -> list[Branch]:
        """
        Split a branch when context window is nearly full.

        Uses the specified criteria to divide the research space.

        Args:
            branch: Branch to split
            criteria: How to split (e.g., "by_topic", "by_time", "by_field")
            num_splits: Number of new branches to create

        Returns:
            List of new child branches
        """
        ...

    def prune_branch(self, branch: Branch) -> None:
        """
        Mark a branch as pruned (stop further exploration).

        Args:
            branch: Branch to prune
        """
        ...

    def update_status(self, branch: Branch, status: BranchStatus) -> None:
        """
        Update branch status.

        Args:
            branch: Branch to update
            status: New status
        """
        ...


@runtime_checkable
class StateStoreProtocol(Protocol):
    """
    Protocol for state persistence.

    Manages in-memory (or persistent) state for the research loop.
    """

    def save_state(self, state: LoopState) -> None:
        """
        Save loop state.

        Args:
            state: State to save
        """
        ...

    def load_state(self, loop_id: str) -> LoopState | None:
        """
        Load loop state by ID.

        Args:
            loop_id: ID of the loop to load

        Returns:
            LoopState if found, None otherwise
        """
        ...

    def list_loops(self) -> list[str]:
        """
        List all loop IDs.

        Returns:
            List of loop IDs
        """
        ...

    def delete_state(self, loop_id: str) -> bool:
        """
        Delete loop state.

        Args:
            loop_id: ID of the loop to delete

        Returns:
            True if deleted, False if not found
        """
        ...


@runtime_checkable
class MasterAgentProtocol(Protocol):
    """
    Protocol for the Master Agent (Layer 3).

    The Master Agent orchestrates the entire research loop:
    - Manages branches and context windows
    - Decides when to split, prune, or switch modes
    - Launches Big Loop 2 with generated hypotheses

    Tool interface:
    - run_iteration: Run one iteration on a branch
    - split_branch: Split when context >80% full
    - switch_mode: Enable hypothesis generation
    - launch_research_loop: Start Big Loop 2
    - prune_branch: Stop low-value branches
    - get_status: Check papers/context per branch
    """

    async def run_iteration(
        self,
        branch_id: str,
        mode: InnerLoopMode | None = None,
    ) -> IterationResult:
        """
        Run one iteration on a branch.

        Args:
            branch_id: ID of branch to run iteration on
            mode: Optional mode override for this iteration

        Returns:
            IterationResult from the iteration
        """
        ...

    async def split_branch(
        self,
        branch_id: str,
        criteria: str,
    ) -> list[str]:
        """
        Split a branch into multiple child branches.

        Args:
            branch_id: ID of branch to split
            criteria: Split criteria (e.g., "by_topic", "by_time")

        Returns:
            List of new branch IDs
        """
        ...

    def switch_mode(
        self,
        branch_id: str,
        mode: InnerLoopMode,
    ) -> None:
        """
        Switch the mode of a branch.

        Args:
            branch_id: ID of branch to update
            mode: New mode
        """
        ...

    async def launch_research_loop(
        self,
        hypothesis_ids: list[str],
    ) -> str:
        """
        Launch Big Loop 2 seeded with hypotheses.

        Takes research hypotheses from the current loop and
        starts a new loop using them as queries.

        Args:
            hypothesis_ids: IDs of hypotheses to use as seeds

        Returns:
            ID of the new loop
        """
        ...

    def prune_branch(self, branch_id: str) -> None:
        """
        Prune a branch (stop exploration).

        Args:
            branch_id: ID of branch to prune
        """
        ...

    def get_status(
        self,
        branch_id: str | None = None,
    ) -> LoopStatus | dict:
        """
        Get status of the loop or a specific branch.

        Args:
            branch_id: Optional branch ID for branch-specific status

        Returns:
            LoopStatus or branch-specific status dict
        """
        ...


@runtime_checkable
class HypothesisGeneratorProtocol(Protocol):
    """Protocol for hypothesis generation."""

    async def generate(
        self,
        summaries: list[ValidatedSummary],
        context: str | None = None,
    ) -> list[ResearchHypothesis]:
        """
        Generate research hypotheses from validated summaries.

        Args:
            summaries: List of validated summaries
            context: Optional additional context

        Returns:
            List of generated hypotheses
        """
        ...


@runtime_checkable
class HypothesisValidatorProtocol(Protocol):
    """Protocol for hypothesis validation."""

    async def validate(
        self,
        hypothesis: ResearchHypothesis,
        supporting_summaries: list[ValidatedSummary],
    ) -> tuple[bool, float]:
        """
        Validate a hypothesis against its supporting summaries.

        Args:
            hypothesis: Hypothesis to validate
            supporting_summaries: Summaries that support the hypothesis

        Returns:
            Tuple of (is_valid, confidence_score)
        """
        ...


@runtime_checkable
class ContextEstimatorProtocol(Protocol):
    """Protocol for token/context estimation."""

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        ...

    def estimate_paper_tokens(self, paper: PaperDetails) -> int:
        """
        Estimate tokens for a paper's content.

        Args:
            paper: Paper to estimate

        Returns:
            Estimated token count
        """
        ...

    def estimate_summary_tokens(self, summary: ValidatedSummary) -> int:
        """
        Estimate tokens for a summary.

        Args:
            summary: Summary to estimate

        Returns:
            Estimated token count
        """
        ...


@runtime_checkable
class CitationProviderProtocol(Protocol):
    """Protocol for citation graph traversal."""

    async def get_citations(
        self,
        paper_id: str,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get papers that cite the given paper.

        Args:
            paper_id: ID of the paper
            limit: Maximum citations to return

        Returns:
            List of citing paper data
        """
        ...

    async def get_references(
        self,
        paper_id: str,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get papers referenced by the given paper.

        Args:
            paper_id: ID of the paper
            limit: Maximum references to return

        Returns:
            List of referenced paper data
        """
        ...
