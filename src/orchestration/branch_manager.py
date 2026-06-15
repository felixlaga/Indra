"""Branch management for the research loop."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Branch, BranchStatus, InnerLoopMode, LoopState
    from ..context.splitter import BranchSplitter, SplitStrategy
    from ..config.loader import BranchConfig
    from ..semantic_scholar import SearchFilters

logger = logging.getLogger(__name__)


class BranchManager:
    """
    Manages branch lifecycle: creation, splitting, pruning.

    Handles:
    - Creating new branches
    - Splitting branches when context is full
    - Pruning low-value branches
    - Status transitions
    """

    def __init__(
        self,
        splitter: BranchSplitter,
        config: BranchConfig | None = None,
    ):
        """
        Initialize the branch manager.

        Args:
            splitter: Branch splitter for dividing branches
            config: Branch configuration
        """
        self.splitter = splitter

        # Load config with defaults
        if config is None:
            from ..config.loader import BranchConfig
            config = BranchConfig()

        self.max_context_window = config.max_context_window
        self.split_threshold = config.context_split_threshold
        self.min_papers_for_hypothesis = config.min_papers_for_hypothesis_mode
        self.max_branches = config.max_branches

    def create_branch(
        self,
        query: str,
        mode: InnerLoopMode,
        parent_branch_id: str | None = None,
        max_context: int | None = None,
        filters: SearchFilters | None = None,
    ) -> Branch:
        """
        Create a new research branch.

        Args:
            query: Search query for this branch
            mode: Inner loop mode (search_summarize or hypothesis)
            parent_branch_id: ID of parent branch if this is a split
            max_context: Override max context window
            filters: Optional search filters for paper retrieval

        Returns:
            Newly created branch
        """
        from .models import Branch, BranchStatus

        branch_id = str(uuid.uuid4())[:8]

        branch = Branch(
            id=branch_id,
            query=query,
            mode=mode,
            status=BranchStatus.PENDING,
            parent_branch_id=parent_branch_id,
            filters=filters,
            max_context_window=max_context or self.max_context_window,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        logger.info(
            f"Created branch {branch_id}: query='{query[:50]}...', "
            f"mode={mode.value}, parent={parent_branch_id}"
        )

        return branch

    def split_branch(
        self,
        branch: Branch,
        strategy: SplitStrategy | None = None,
        num_splits: int = 2,
    ) -> list[Branch]:
        """
        Split a branch when context window is nearly full.

        Uses the splitter to divide the research space into
        coherent sub-branches.

        Args:
            branch: Branch to split
            strategy: Split strategy (auto-suggested if None)
            num_splits: Number of new branches to create

        Returns:
            List of new child branches
        """
        from .models import BranchStatus

        if strategy is None:
            strategy = self.splitter.suggest_strategy(branch)

        logger.info(
            f"Splitting branch {branch.id} using strategy {strategy.value} "
            f"into {num_splits} branches"
        )

        # Perform the split
        result = self.splitter.split(branch, strategy, num_splits)

        # Create new branches for each group
        new_branches = []
        for i, (group, query, label) in enumerate(
            zip(result.groups, result.group_queries, result.group_labels)
        ):
            # Create child branch (inherits filters from parent)
            child = self.create_branch(
                query=query,
                mode=branch.mode,
                parent_branch_id=branch.id,
                filters=branch.filters,
            )

            # Copy relevant papers from parent
            for paper_id in group:
                if paper_id in branch.accumulated_papers:
                    child.accumulated_papers[paper_id] = branch.accumulated_papers[paper_id]
                if paper_id in branch.accumulated_summaries:
                    child.accumulated_summaries[paper_id] = branch.accumulated_summaries[paper_id]

            new_branches.append(child)
            logger.info(
                f"Created child branch {child.id}: '{label}' "
                f"with {len(group)} papers"
            )

        # Mark original branch as completed (split)
        branch.status = BranchStatus.COMPLETED
        branch.updated_at = datetime.now()

        return new_branches

    def prune_branch(self, branch: Branch, reason: str = "") -> None:
        """
        Mark a branch as pruned (stop further exploration).

        Args:
            branch: Branch to prune
            reason: Optional reason for pruning
        """
        from .models import BranchStatus

        branch.status = BranchStatus.PRUNED
        branch.updated_at = datetime.now()

        logger.info(
            f"Pruned branch {branch.id}: {reason or 'no reason given'}"
        )

    def update_status(self, branch: Branch, status: BranchStatus) -> None:
        """
        Update branch status.

        Args:
            branch: Branch to update
            status: New status
        """
        old_status = branch.status
        branch.status = status
        branch.updated_at = datetime.now()

        logger.debug(
            f"Branch {branch.id} status: {old_status.value} -> {status.value}"
        )

    def should_split(self, branch: Branch) -> bool:
        """
        Check if a branch should be split based on context threshold.

        NOTE: This is the fallback check used when the managing agent is not enabled.
        When the managing agent is enabled, it makes autonomous decisions about splitting
        and this method is not used.

        The threshold is a soft recommendation at 80%, not a hard requirement.

        Args:
            branch: Branch to check

        Returns:
            True if branch should be split (context >= threshold)
        """
        return branch.context_utilization >= self.split_threshold

    def get_context_warning(self, branch: Branch) -> str | None:
        """
        Get a warning message if context usage is getting high.

        This provides soft guardrails rather than hard thresholds.

        Args:
            branch: Branch to check

        Returns:
            Warning message if context is above 70%, None otherwise
        """
        utilization = branch.context_utilization

        if utilization >= 0.90:
            return f"CRITICAL: Context at {utilization:.0%} - action needed soon"
        elif utilization >= 0.80:
            return f"HIGH: Context at {utilization:.0%} - consider splitting or wrapping up"
        elif utilization >= 0.70:
            return f"MODERATE: Context at {utilization:.0%} - be mindful of remaining capacity"

        return None

    def should_enable_hypothesis_mode(self, branch: Branch) -> bool:
        """
        Check if a branch should switch to hypothesis mode.

        Args:
            branch: Branch to check

        Returns:
            True if branch has enough papers for hypothesis generation
        """
        from .models import InnerLoopMode

        if branch.mode == InnerLoopMode.HYPOTHESIS:
            return False  # Already in hypothesis mode

        return len(branch.accumulated_papers) >= self.min_papers_for_hypothesis

    def can_create_more_branches(self, state: LoopState) -> bool:
        """
        Check if more branches can be created.

        Args:
            state: Current loop state

        Returns:
            True if under the branch limit
        """
        active_branches = len([
            b for b in state.branches.values()
            if b.status.value in ("pending", "running")
        ])
        return active_branches < self.max_branches

    def get_next_branch(self, state: LoopState) -> Branch | None:
        """
        Get the next branch to process.

        Prioritizes:
        1. Running branches (continue work)
        2. Pending branches (start new work)
        3. None if all completed/pruned

        Args:
            state: Current loop state

        Returns:
            Next branch to process, or None
        """
        from .models import BranchStatus

        # First, find any running branch
        for branch in state.branches.values():
            if branch.status == BranchStatus.RUNNING:
                return branch

        # Then, find a pending branch
        for branch in state.branches.values():
            if branch.status == BranchStatus.PENDING:
                return branch

        return None

    def get_branch_stats(self, branch: Branch) -> dict:
        """
        Get statistics for a branch.

        Args:
            branch: Branch to analyze

        Returns:
            Dict with branch statistics
        """
        return {
            "id": branch.id,
            "query": branch.query,
            "mode": branch.mode.value,
            "status": branch.status.value,
            "iterations": len(branch.iterations),
            "papers": len(branch.accumulated_papers),
            "summaries": len(branch.accumulated_summaries),
            "hypotheses": len(branch.get_all_hypotheses()),
            "context_used": branch.context_window_used,
            "context_max": branch.max_context_window,
            "context_utilization": f"{branch.context_utilization:.1%}",
            "parent": branch.parent_branch_id,
        }

    def get_all_stats(self, state: LoopState) -> dict:
        """
        Get statistics for all branches in a loop.

        Args:
            state: Loop state

        Returns:
            Dict with overall and per-branch statistics
        """
        from .models import BranchStatus

        branches_by_status = {}
        for status in BranchStatus:
            branches_by_status[status.value] = []

        for branch in state.branches.values():
            branches_by_status[branch.status.value].append(branch.id)

        return {
            "loop_id": state.loop_id,
            "loop_number": state.loop_number,
            "total_branches": len(state.branches),
            "branches_by_status": branches_by_status,
            "total_papers": state.total_papers,
            "total_summaries": state.total_summaries,
            "total_hypotheses": len(state.collect_all_hypotheses()),
            "branches": [
                self.get_branch_stats(b)
                for b in state.branches.values()
            ],
        }
