"""Tests for the Phase 3 background job worker adapter."""

from datetime import timedelta

from src.api.models import JobStatus, JobType, SessionCreate, SessionStatus
from src.api.repository import InMemoryRepository, utc_now
from src.jobs import JobWorker


def test_job_worker_runs_registered_handler() -> None:
    repository = InMemoryRepository()
    session = repository.create_session(
        SessionCreate(initial_query="worker lifecycle")
    )
    repository.set_session_status(
        session.id,
        SessionStatus.RUNNING,
        "session_started",
    )

    worker = JobWorker(
        repository,
        worker_id="worker-1",
        handlers={
            JobType.RESEARCH_SESSION: lambda job: {
                "query": job.payload["initial_query"],
            }
        },
    )

    completed = worker.run_once()

    assert completed is not None
    assert completed.status == JobStatus.SUCCEEDED
    assert completed.result == {"query": "worker lifecycle"}


def test_job_worker_fails_without_registered_handler() -> None:
    repository = InMemoryRepository()
    session = repository.create_session(
        SessionCreate(initial_query="missing handler")
    )
    repository.set_session_status(
        session.id,
        SessionStatus.RUNNING,
        "session_started",
    )

    worker = JobWorker(repository, worker_id="worker-1")

    failed = worker.run_once()

    assert failed is not None
    assert failed.status == JobStatus.FAILED
    assert failed.last_error == "No handler registered for research_session"
    assert repository.get_session(session.id).status == SessionStatus.FAILED


def test_repository_expires_timed_out_jobs_for_retry() -> None:
    repository = InMemoryRepository()
    session = repository.create_session(
        SessionCreate(initial_query="timeout retry")
    )
    repository.set_session_status(
        session.id,
        SessionStatus.RUNNING,
        "session_started",
    )

    leased = repository.lease_next_job(worker_id="worker-1")
    assert leased is not None
    leased.locked_at = utc_now() - timedelta(seconds=leased.timeout_seconds + 1)
    repository._jobs[leased.id] = leased

    expired = repository.expire_timed_out_jobs()

    assert len(expired) == 1
    assert expired[0].status == JobStatus.QUEUED
    assert expired[0].last_error == "Job timed out after 1800 seconds"
