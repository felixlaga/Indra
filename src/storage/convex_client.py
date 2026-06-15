"""Convex HTTP client for Research Agent realtime events."""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from ..orchestration.models import (
        ValidatedSummary,
        ResearchHypothesis,
        IterationResult,
        Branch,
    )
    from ..semantic_scholar import PaperDetails

logger = logging.getLogger(__name__)


@dataclass
class ConvexConfig:
    """Configuration for Convex client."""

    url: str = field(default_factory=lambda: os.getenv("CONVEX_URL", ""))
    timeout: float = 30.0

    @property
    def is_configured(self) -> bool:
        """Check if Convex is properly configured."""
        return bool(self.url)


class ConvexClient:
    """HTTP client for Convex backend.

    Provides methods to stream research events to the Convex realtime database.
    Events are used by the Three.js frontend to visualize the research graph.
    """

    def __init__(self, config: ConvexConfig | None = None):
        """Initialize the Convex client.

        Args:
            config: Convex configuration. If None, loads from environment.
        """
        self.config = config or ConvexConfig()
        self._client: httpx.AsyncClient | None = None
        self._session_doc_id: str | None = None
        self._session_string_id: str | None = None
        self._enabled = self.config.is_configured

    @property
    def enabled(self) -> bool:
        """Check if Convex streaming is enabled."""
        return self._enabled and self._client is not None

    @property
    def session_id(self) -> str | None:
        """Get the current Convex session document ID."""
        return self._session_doc_id

    async def connect(self) -> None:
        """Connect to Convex backend."""
        if not self.config.is_configured:
            logger.warning("Convex not configured (CONVEX_URL not set), streaming disabled")
            return

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            headers={"Content-Type": "application/json"},
        )
        logger.info(f"Connected to Convex at {self.config.url}")

    async def disconnect(self) -> None:
        """Disconnect from Convex backend."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Disconnected from Convex")

    async def __aenter__(self) -> "ConvexClient":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    async def mutation(self, function: str, args: dict[str, Any]) -> Any:
        """Execute a Convex mutation.

        Args:
            function: Function path (e.g., "sessions:create")
            args: Arguments to pass to the function

        Returns:
            The mutation result value
        """
        if not self._client:
            return None

        try:
            response = await self._client.post(
                f"{self.config.url}/api/mutation",
                json={"path": function, "args": args, "format": "json"},
            )
            response.raise_for_status()
            return response.json().get("value")
        except httpx.HTTPStatusError as e:
            logger.error(f"Convex mutation failed: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Convex mutation error: {e}")
            raise

    async def query(self, function: str, args: dict[str, Any]) -> Any:
        """Execute a Convex query.

        Args:
            function: Function path (e.g., "sessions:get")
            args: Arguments to pass to the function

        Returns:
            The query result value
        """
        if not self._client:
            return None

        try:
            response = await self._client.post(
                f"{self.config.url}/api/query",
                json={"path": function, "args": args, "format": "json"},
            )
            response.raise_for_status()
            return response.json().get("value")
        except httpx.HTTPStatusError as e:
            logger.error(f"Convex query failed: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Convex query error: {e}")
            raise

    # ==========================================================================
    # Session Management
    # ==========================================================================

    async def create_session(
        self,
        session_id: str,
        initial_query: str,
        parameters: dict[str, Any] | None = None,
    ) -> str | None:
        """Create a new research session.

        Args:
            session_id: Unique session identifier (loop_id)
            initial_query: The initial research query
            parameters: Optional research parameters to store

        Returns:
            The Convex document ID for the session
        """
        args = {
            "sessionId": session_id,
            "initialQuery": initial_query,
        }
        if parameters:
            args["parameters"] = parameters

        result = await self.mutation("sessions:create", args)
        self._session_doc_id = result
        self._session_string_id = session_id
        logger.info(f"Created Convex session: {result}")
        return result

    async def update_session_status(
        self, status: str
    ) -> None:
        """Update the session status.

        Args:
            status: New status (pending, running, completed, failed)
        """
        if not self._session_string_id:
            return

        await self.mutation(
            "sessions:updateStatus",
            {"sessionId": self._session_string_id, "status": status},
        )

    # ==========================================================================
    # Event Emission
    # ==========================================================================

    async def emit_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        branch_id: str | None = None,
    ) -> None:
        """Emit a realtime event.

        Args:
            event_type: Type of event (e.g., "branch_created", "papers_found")
            payload: Event payload data
            branch_id: Optional associated branch ID
        """
        if not self._session_doc_id:
            return

        event_args: dict[str, Any] = {
            "sessionId": self._session_doc_id,
            "eventType": event_type,
            "payload": payload,
        }
        if branch_id is not None:
            event_args["branchId"] = branch_id

        await self.mutation("events:emit", event_args)

    # ==========================================================================
    # Branch Events
    # ==========================================================================

    async def emit_branch_created(
        self,
        branch_id: str,
        query: str,
        mode: str,
        parent_id: str | None = None,
    ) -> None:
        """Emit branch created event and create branch record.

        Args:
            branch_id: Unique branch identifier
            query: The search query for this branch
            mode: Branch mode (search_summarize or hypothesis)
            parent_id: Optional parent branch ID
        """
        if not self._session_doc_id:
            return

        # Create branch record - only include parentBranchId if it's not None
        branch_args: dict[str, Any] = {
            "sessionId": self._session_doc_id,
            "branchId": branch_id,
            "query": query,
            "mode": mode,
        }
        if parent_id is not None:
            branch_args["parentBranchId"] = parent_id

        await self.mutation("branches:create", branch_args)

        # Emit event
        event_payload: dict[str, Any] = {
            "branchId": branch_id,
            "query": query,
            "mode": mode,
        }
        if parent_id is not None:
            event_payload["parentBranchId"] = parent_id

        await self.emit_event("branch_created", event_payload, branch_id)

    async def emit_branch_status_changed(
        self,
        branch_id: str,
        status: str,
        context_used: int | None = None,
        paper_count: int | None = None,
        summary_count: int | None = None,
    ) -> None:
        """Emit branch status change event.

        Args:
            branch_id: Branch identifier
            status: New status
            context_used: Optional context window tokens used
            paper_count: Optional total paper count
            summary_count: Optional total summary count
        """
        # Update branch record
        update_args: dict[str, Any] = {"branchId": branch_id, "status": status}
        if context_used is not None:
            update_args["contextWindowUsed"] = context_used
        if paper_count is not None:
            update_args["paperCount"] = paper_count
        if summary_count is not None:
            update_args["summaryCount"] = summary_count

        await self.mutation("branches:update", update_args)

        # Emit event
        await self.emit_event(
            "branch_status_changed",
            {
                "branchId": branch_id,
                "status": status,
                "contextUsed": context_used,
                "paperCount": paper_count,
                "summaryCount": summary_count,
            },
            branch_id,
        )

    # ==========================================================================
    # Paper Events
    # ==========================================================================

    async def emit_papers_found(
        self,
        branch_id: str,
        papers: list["PaperDetails"],
        iteration: int,
    ) -> None:
        """Emit papers found event.

        Args:
            branch_id: Branch that found the papers
            papers: List of paper details
            iteration: Iteration number
        """
        if not self._session_doc_id:
            return

        # Create paper records (batch) - filter out None values for optional fields
        paper_records = []
        for p in papers:
            record: dict[str, Any] = {
                "sessionId": self._session_doc_id,
                "branchId": branch_id,
                "paperId": p.paper_id,
                "authors": [
                    {k: v for k, v in {"authorId": a.author_id, "name": a.name}.items() if v is not None}
                    for a in (p.authors or [])[:5]
                ],
                "iterationNumber": iteration,
            }
            # Only add optional fields if they have values
            if p.title is not None:
                record["title"] = p.title
            if p.abstract is not None:
                record["abstract"] = p.abstract[:500]
            if p.year is not None:
                record["year"] = p.year
            if p.citation_count is not None:
                record["citationCount"] = p.citation_count
            if p.venue is not None:
                record["venue"] = p.venue
            paper_records.append(record)

        if paper_records:
            await self.mutation("papers:createBatch", {"papers": paper_records})

        # Emit event with summary
        await self.emit_event(
            "papers_found",
            {
                "count": len(papers),
                "iterationNumber": iteration,
                "papers": [
                    {"paperId": p.paper_id, "title": p.title} for p in papers[:5]
                ],
            },
            branch_id,
        )

    # ==========================================================================
    # Summary Events
    # ==========================================================================

    async def emit_summary_validated(
        self,
        branch_id: str,
        summary: "ValidatedSummary",
        iteration: int,
    ) -> None:
        """Emit summary validated event.

        Args:
            branch_id: Branch that generated the summary
            summary: The validated summary
            iteration: Iteration number
        """
        if not self._session_doc_id:
            return

        # Create summary record
        await self.mutation(
            "summaries:create",
            {
                "sessionId": self._session_doc_id,
                "branchId": branch_id,
                "paperId": summary.paper_id,
                "paperTitle": summary.paper_title,
                "summary": summary.summary,
                "groundedness": summary.groundedness,
                "iterationNumber": iteration,
            },
        )

        # Emit event
        await self.emit_event(
            "summary_validated",
            {
                "paperId": summary.paper_id,
                "paperTitle": summary.paper_title,
                "groundedness": summary.groundedness,
            },
            branch_id,
        )

    async def emit_summaries_batch(
        self,
        branch_id: str,
        summaries: list["ValidatedSummary"],
        iteration: int,
    ) -> None:
        """Emit multiple summaries at once.

        Args:
            branch_id: Branch that generated the summaries
            summaries: List of validated summaries
            iteration: Iteration number
        """
        if not self._session_doc_id or not summaries:
            return

        # Create summary records (batch)
        summary_records = [
            {
                "sessionId": self._session_doc_id,
                "branchId": branch_id,
                "paperId": s.paper_id,
                "paperTitle": s.paper_title,
                "summary": s.summary,
                "groundedness": s.groundedness,
                "iterationNumber": iteration,
            }
            for s in summaries
        ]

        await self.mutation("summaries:createBatch", {"summaries": summary_records})

        # Emit event
        await self.emit_event(
            "summaries_validated",
            {
                "count": len(summaries),
                "iterationNumber": iteration,
                "summaries": [
                    {
                        "paperId": s.paper_id,
                        "paperTitle": s.paper_title,
                        "groundedness": s.groundedness,
                    }
                    for s in summaries[:5]
                ],
            },
            branch_id,
        )

    # ==========================================================================
    # Hypothesis Events
    # ==========================================================================

    async def emit_hypothesis_generated(
        self,
        branch_id: str,
        hypothesis: "ResearchHypothesis",
        iteration: int,
    ) -> None:
        """Emit hypothesis generated event.

        Args:
            branch_id: Branch that generated the hypothesis
            hypothesis: The research hypothesis
            iteration: Iteration number
        """
        if not self._session_doc_id:
            return

        # Create hypothesis record
        await self.mutation(
            "hypotheses:create",
            {
                "sessionId": self._session_doc_id,
                "branchId": branch_id,
                "hypothesisId": hypothesis.id,
                "text": hypothesis.text,
                "supportingPaperIds": hypothesis.supporting_paper_ids,
                "confidence": hypothesis.confidence,
                "iterationNumber": iteration,
            },
        )

        # Emit event
        await self.emit_event(
            "hypothesis_generated",
            {
                "hypothesisId": hypothesis.id,
                "text": hypothesis.text,
                "confidence": hypothesis.confidence,
                "supportingPaperCount": len(hypothesis.supporting_paper_ids),
            },
            branch_id,
        )

    async def emit_hypotheses_batch(
        self,
        branch_id: str,
        hypotheses: list["ResearchHypothesis"],
        iteration: int,
    ) -> None:
        """Emit multiple hypotheses at once.

        Args:
            branch_id: Branch that generated the hypotheses
            hypotheses: List of research hypotheses
            iteration: Iteration number
        """
        if not self._session_doc_id or not hypotheses:
            return

        # Create hypothesis records (batch)
        hypothesis_records = [
            {
                "sessionId": self._session_doc_id,
                "branchId": branch_id,
                "hypothesisId": h.id,
                "text": h.text,
                "supportingPaperIds": h.supporting_paper_ids,
                "confidence": h.confidence,
                "iterationNumber": iteration,
            }
            for h in hypotheses
        ]

        await self.mutation("hypotheses:createBatch", {"hypotheses": hypothesis_records})

        # Emit event
        await self.emit_event(
            "hypotheses_generated",
            {
                "count": len(hypotheses),
                "iterationNumber": iteration,
                "hypotheses": [
                    {
                        "hypothesisId": h.id,
                        "text": h.text[:100],
                        "confidence": h.confidence,
                    }
                    for h in hypotheses[:5]
                ],
            },
            branch_id,
        )

    # ==========================================================================
    # Iteration Events
    # ==========================================================================

    async def emit_iteration_result(
        self,
        branch_id: str,
        result: "IterationResult",
    ) -> None:
        """Emit a complete iteration result.

        This is a convenience method that emits all events for an iteration.

        Args:
            branch_id: Branch that completed the iteration
            result: The iteration result
        """
        iteration = result.iteration_number

        # Emit papers found
        if result.papers_found:
            await self.emit_papers_found(branch_id, result.papers_found, iteration)

        # Emit summaries
        if result.summaries:
            await self.emit_summaries_batch(branch_id, result.summaries, iteration)

        # Emit hypotheses (if in hypothesis mode)
        if result.hypotheses:
            await self.emit_hypotheses_batch(branch_id, result.hypotheses, iteration)

        # Emit iteration complete event
        await self.emit_event(
            "iteration_completed",
            {
                "iterationNumber": iteration,
                "papersFound": len(result.papers_found),
                "summariesValidated": len(result.summaries),
                "hypothesesGenerated": len(result.hypotheses) if result.hypotheses else 0,
                "contextTokensUsed": result.context_tokens_used,
            },
            branch_id,
        )
