"""Worker-side adapter for durable ERLA jobs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..api.models import Job, JobType
from ..api.repository import ProductRepository

JobHandler = Callable[[Job], dict[str, Any] | None]


class JobWorker:
    """Lease and execute one durable background job at a time."""

    def __init__(
        self,
        repository: ProductRepository,
        *,
        worker_id: str,
        handlers: dict[JobType, JobHandler] | None = None,
        job_types: list[JobType] | None = None,
    ) -> None:
        if not worker_id:
            raise ValueError("worker_id is required")
        self._repository = repository
        self._worker_id = worker_id
        self._handlers = handlers or {}
        self._job_types = job_types

    def run_once(self) -> Job | None:
        """Lease one job, run its handler, and persist the outcome."""

        job = self._repository.lease_next_job(
            worker_id=self._worker_id,
            job_types=self._job_types,
        )
        if job is None:
            return None

        handler = self._handlers.get(job.job_type)
        if handler is None:
            return self._repository.fail_job(
                job.id,
                f"No handler registered for {job.job_type.value}",
                retryable=False,
            )

        try:
            result = handler(job) or {}
        except Exception as exc:
            return self._repository.fail_job(job.id, str(exc), retryable=True)

        return self._repository.complete_job(job.id, result=result)
