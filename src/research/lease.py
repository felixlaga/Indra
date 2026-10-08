"""Fenced worker identity: an expired attempt cannot write newer work."""

from ..api.models import Job, JobStatus, JobType, SessionStatus
from ..api.repository import ConflictError


class LeaseLost(ConflictError):
    """The job was paused, cancelled, expired, or leased by another attempt."""


def check_lease(current: Job, leased: Job, session_status: SessionStatus) -> None:
    # Expanding the paper network also works on a finished session.
    allowed = {SessionStatus.RUNNING} | (
        {SessionStatus.COMPLETED}
        if current.job_type == JobType.NETWORK_EXPANSION
        else set()
    )
    if (
        current.status != JobStatus.RUNNING
        or session_status not in allowed
        or current.locked_by != leased.locked_by
        or current.attempts != leased.attempts
    ):
        raise LeaseLost("Research job lease is no longer active")
