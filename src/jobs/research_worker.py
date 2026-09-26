"""Executable durable research worker; API requests only enqueue jobs."""

import argparse
import asyncio
import logging
import os
import signal
from uuid import uuid4

from dotenv import load_dotenv

from ..api.models import JobType
from ..api.repository_factory import create_repository
from ..research.lease import LeaseLost
from ..research.model import ResearchModel
from ..research.pipeline import ResearchPipeline

logger = logging.getLogger(__name__)


class ResearchWorker:
    def __init__(self, repository, pipeline, *, worker_id=None, heartbeat_seconds=2):
        self.repository, self.pipeline = repository, pipeline
        self.worker_id = worker_id or f"research-{uuid4()}"
        self.heartbeat_seconds = heartbeat_seconds

    async def run_once(self):
        leased = self.repository.lease_next_job(
            self.worker_id, [JobType.RESEARCH_SESSION, JobType.BRANCH_CONTINUE]
        )
        if leased is None:
            return None
        leased = leased.model_copy(deep=True)
        task = asyncio.create_task(self.pipeline.run(leased))
        try:
            async with asyncio.timeout(leased.timeout_seconds):
                while not task.done():
                    done, _ = await asyncio.wait({task}, timeout=self.heartbeat_seconds)
                    self.repository.heartbeat_research(leased)
                await task
                return self.repository.finish_research(leased)
        except LeaseLost:
            logger.info("Job %s was paused, cancelled, or re-leased", leased.id)
            return self.repository.get_job(leased.id)
        except asyncio.CancelledError:
            try:
                self.repository.fail_research(
                    leased, "Worker stopped; preserved partial results", retryable=True
                )
            except LeaseLost:
                pass
            raise
        except Exception as exc:
            logger.exception("Research job %s failed", leased.id)
            try:
                return self.repository.fail_research(
                    leased,
                    f"{type(exc).__name__}: {str(exc)[:500]}",
                    retryable=not isinstance(exc, ValueError),
                )
            except LeaseLost:
                return self.repository.get_job(leased.id)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def serve(once=False, poll_seconds=2):
    repository = create_repository()
    if os.getenv("INDRA_REPOSITORY_BACKEND", "memory") not in {
        "postgres",
        "postgresql",
    }:
        raise ValueError(
            "Standalone workers require INDRA_REPOSITORY_BACKEND=postgres so API and worker share durable state"
        )
    worker = ResearchWorker(
        repository, ResearchPipeline(repository, ResearchModel.from_environment())
    )
    current = asyncio.current_task()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, current.cancel)
    while True:
        job = await worker.run_once()
        if once:
            return
        if job is None:
            await asyncio.sleep(poll_seconds)


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Run Indra's durable research worker")
    parser.add_argument(
        "--once", action="store_true", help="Process at most one available job"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(serve(once=args.once))
    except asyncio.CancelledError:
        pass


if __name__ == "__main__":
    main()
