"""Compute durable research maps and advice outside API request handlers."""

import argparse
import logging
import os
import time

from dotenv import load_dotenv

from ..analysis import ResearchAdviceBuilder
from ..api.repository_factory import create_repository
from ..api.repository import ProductRepository
from ..api.view_repository import BUILDER_VERSION
from ..maps import ResearchMapBuilder

logger = logging.getLogger(__name__)


class ViewWorker:
    def __init__(self, repository: ProductRepository):
        self.repository = repository

    def run_once(self) -> dict | None:
        leased = self.repository.lease_views()
        if leased is None:
            return None
        try:
            snapshot = self.repository.get_session_snapshot(
                str(leased["session_id"]), event_limit=0
            )
            research_map = ResearchMapBuilder().build(
                snapshot,
                self.repository.list_discovered_papers(str(leased["session_id"])),
            )
            advice = ResearchAdviceBuilder().build(snapshot, research_map)
            self.repository.finish_views(
                leased,
                {
                    "map": research_map.model_dump(mode="json"),
                    "analysis": advice.model_dump(mode="json"),
                    "builder_version": BUILDER_VERSION,
                },
            )
        except Exception:
            logger.exception(
                "Research view computation failed for %s", leased["session_id"]
            )
            self.repository.finish_views(
                leased,
                error="Research view computation failed. Retry to rebuild; partial research is preserved.",
            )
        return leased


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Build queued research views")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if os.getenv("INDRA_REPOSITORY_BACKEND", "memory") not in {
        "postgres",
        "postgresql",
    }:
        raise ValueError(
            "Standalone view workers require INDRA_REPOSITORY_BACKEND=postgres"
        )
    logging.basicConfig(level=logging.INFO)
    repository = create_repository()
    worker = ViewWorker(repository)
    try:
        while True:
            job = worker.run_once()
            if args.once:
                return
            if job is None:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        repository.close()


if __name__ == "__main__":
    main()
