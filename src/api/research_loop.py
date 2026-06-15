"""Bridge product API sessions to the existing research-loop runtime models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from ..context.splitter import BranchSplitter
from ..orchestration.branch_manager import BranchManager
from ..orchestration.models import (
    Branch as RuntimeBranch,
    BranchStatus as RuntimeBranchStatus,
    InnerLoopMode,
    LoopState,
)
from ..semantic_scholar.models import SearchFilters
from .models import (
    Branch,
    BranchMode,
    BranchStatus,
    ResearchSession,
)


@dataclass(frozen=True)
class RuntimeLoop:
    """Runtime loop state created for a product API session."""

    state: LoopState
    root_branch: RuntimeBranch


class ResearchLoopBridge:
    """Create lightweight runtime loop state without running research jobs."""

    def __init__(self, branch_manager: BranchManager | None = None) -> None:
        self._branch_manager = branch_manager or BranchManager(BranchSplitter())

    def create_loop(self, session: ResearchSession) -> RuntimeLoop:
        """Create an orchestration LoopState and root branch for a session."""

        now = datetime.now()
        filters = self._build_filters(session.filters)
        state = LoopState(
            loop_id=f"loop_{uuid4().hex[:8]}",
            loop_number=1,
            session_filters=filters,
            created_at=now,
            updated_at=now,
        )
        root_branch = self._branch_manager.create_branch(
            query=session.initial_query,
            mode=InnerLoopMode.SEARCH_SUMMARIZE,
            filters=filters,
        )
        root_branch.status = RuntimeBranchStatus.PENDING
        state.add_branch(root_branch)
        return RuntimeLoop(state=state, root_branch=root_branch)

    def to_api_branch(
        self,
        session_id: str,
        runtime_branch: RuntimeBranch,
        label: str | None = None,
        rationale: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> Branch:
        """Project a runtime branch into the API branch model."""

        created_at = created_at or runtime_branch.created_at
        updated_at = updated_at or runtime_branch.updated_at
        return Branch(
            id=runtime_branch.id,
            session_id=session_id,
            parent_branch_id=runtime_branch.parent_branch_id,
            query=runtime_branch.query,
            label=label,
            rationale=rationale,
            mode=BranchMode(runtime_branch.mode.value),
            status=BranchStatus(runtime_branch.status.value),
            depth=0 if runtime_branch.parent_branch_id is None else 1,
            context_tokens_used=runtime_branch.context_window_used,
            max_context_tokens=runtime_branch.max_context_window,
            created_at=created_at,
            updated_at=updated_at,
        )

    def _build_filters(self, filters: dict) -> SearchFilters | None:
        if not filters:
            return None
        return SearchFilters.model_validate(filters)
