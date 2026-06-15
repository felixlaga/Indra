"""Pure lifecycle transition rules for sessions and branches."""

from __future__ import annotations

from dataclasses import dataclass

from .enums import BranchStatus, SessionStatus


class InvalidTransitionError(ValueError):
    """Raised when a lifecycle transition violates the canonical contract."""


SESSION_TRANSITIONS: dict[SessionStatus, frozenset[SessionStatus]] = {
    SessionStatus.PENDING: frozenset({SessionStatus.RUNNING, SessionStatus.CANCELLED}),
    SessionStatus.RUNNING: frozenset(
        {
            SessionStatus.PAUSED,
            SessionStatus.COMPLETED,
            SessionStatus.FAILED,
            SessionStatus.CANCELLED,
        }
    ),
    SessionStatus.PAUSED: frozenset(
        {SessionStatus.RUNNING, SessionStatus.FAILED, SessionStatus.CANCELLED}
    ),
    SessionStatus.FAILED: frozenset({SessionStatus.RUNNING}),
    SessionStatus.COMPLETED: frozenset(),
    SessionStatus.CANCELLED: frozenset(),
}

BRANCH_TRANSITIONS: dict[BranchStatus, frozenset[BranchStatus]] = {
    BranchStatus.PENDING: frozenset(
        {BranchStatus.RUNNING, BranchStatus.PRUNED, BranchStatus.FAILED}
    ),
    BranchStatus.RUNNING: frozenset(
        {
            BranchStatus.PAUSED,
            BranchStatus.COMPLETED,
            BranchStatus.PRUNED,
            BranchStatus.FAILED,
        }
    ),
    BranchStatus.PAUSED: frozenset(
        {BranchStatus.RUNNING, BranchStatus.PRUNED, BranchStatus.FAILED}
    ),
    BranchStatus.FAILED: frozenset({BranchStatus.RUNNING}),
    BranchStatus.COMPLETED: frozenset(),
    BranchStatus.PRUNED: frozenset(),
}


@dataclass(frozen=True)
class TransitionDecision:
    """A validated lifecycle transition."""

    current: str
    target: str
    retry: bool = False


def validate_session_transition(
    current: SessionStatus,
    target: SessionStatus,
) -> TransitionDecision:
    """Validate a session status transition."""

    if current == target:
        return TransitionDecision(current=current.value, target=target.value)
    allowed = SESSION_TRANSITIONS[current]
    if target not in allowed:
        raise InvalidTransitionError(
            f"Invalid session transition: {current.value} -> {target.value}"
        )
    return TransitionDecision(
        current=current.value,
        target=target.value,
        retry=current == SessionStatus.FAILED and target == SessionStatus.RUNNING,
    )


def validate_branch_transition(
    current: BranchStatus,
    target: BranchStatus,
) -> TransitionDecision:
    """Validate a branch status transition."""

    if current == target:
        return TransitionDecision(current=current.value, target=target.value)
    allowed = BRANCH_TRANSITIONS[current]
    if target not in allowed:
        raise InvalidTransitionError(
            f"Invalid branch transition: {current.value} -> {target.value}"
        )
    return TransitionDecision(
        current=current.value,
        target=target.value,
        retry=current == BranchStatus.FAILED and target == BranchStatus.RUNNING,
    )
