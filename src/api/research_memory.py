"""Atomic research writes for the in-process repository."""

from copy import deepcopy

from ..research.models import PaperChunk, PaperResult, stable_id
from .models import (
    BranchStatus,
    Claim,
    ClaimStatus,
    ClaimType,
    Job,
    JobStatus,
    SessionPaper,
    Summary,
)


class MemoryResearchWrites:
    def _research_lease(self, leased: Job) -> Job:
        from ..research.lease import check_lease

        current = self._get_job_unlocked(leased.id)
        check_lease(
            current, leased, self._get_session_unlocked(leased.session_id).status
        )
        return current

    def heartbeat_research(self, leased: Job, progress: dict | None = None) -> Job:
        from .repository import utc_now

        with self._lock:
            current = self._research_lease(leased)
            current.locked_at = current.updated_at = utc_now()
            if progress:
                current.result.update(deepcopy(progress))
                self._create_event_unlocked(
                    session_id=current.session_id,
                    branch_id=current.branch_id,
                    event_type="research_progress",
                    payload={"job_id": current.id, **progress},
                )
            return current.model_copy(deep=True)

    def save_research_paper(self, leased: Job, result: PaperResult) -> str:
        from .repository import utc_now

        with self._lock:
            self._research_lease(leased)
            paper = result.paper.model_copy(deep=True)
            existing = next(
                (
                    p
                    for p in self._papers.values()
                    if p.canonical_key == paper.canonical_key
                ),
                None,
            )
            if existing:
                paper.id = existing.id
                paper.created_at = existing.created_at
            self._papers[paper.id] = paper
            link_id = stable_id(leased.session_id, leased.branch_id or "", paper.id)
            self._session_papers[link_id] = SessionPaper(
                id=link_id,
                session_id=leased.session_id,
                branch_id=leased.branch_id,
                paper_id=paper.id,
                selected=True,
                discovery_method="query_search",
                selection_reason="Selected from provider relevance ranking within the session paper limit.",
                created_at=utc_now(),
            )
            for chunk in result.chunks:
                self._paper_chunks[chunk.id] = chunk.model_copy(
                    update={"paper_id": paper.id}
                )
            if result.synthesis:
                summary_id = stable_id(leased.id, paper.id, "summary")
                now = utc_now()
                self._summaries[summary_id] = Summary(
                    id=summary_id,
                    session_id=leased.session_id,
                    branch_id=leased.branch_id,
                    paper_id=paper.id,
                    summary_type="paper",
                    text=result.synthesis.summary,
                    generation_provenance=result.provenance or None,
                    validation_details={
                        "source_note": result.source_note,
                        "parse_status": result.parse_status,
                    },
                    created_at=now,
                    updated_at=now,
                )
                for draft in result.synthesis.claims:
                    claim_id = stable_id(summary_id, draft.text)
                    if claim_id not in self._claims:
                        self._claims[claim_id] = Claim(
                            id=claim_id,
                            session_id=leased.session_id,
                            branch_id=leased.branch_id,
                            paper_id=paper.id,
                            summary_id=summary_id,
                            claim_text=draft.text,
                            claim_type=draft.claim_type,
                            status=ClaimStatus.SPECULATIVE
                            if draft.claim_type == ClaimType.HYPOTHESIS
                            else ClaimStatus.NEEDS_REVIEW,
                            created_by="research_worker_v1",
                            created_at=now,
                            updated_at=now,
                        )
            self._create_event_unlocked(
                session_id=leased.session_id,
                branch_id=leased.branch_id,
                paper_id=paper.id,
                event_type="paper_processed"
                if result.synthesis
                else "paper_discovered",
                payload={
                    "title": paper.title,
                    "parse_status": result.parse_status,
                    "source_note": result.source_note,
                },
            )
            return paper.id

    def list_paper_chunks(self, paper_id: str) -> list[PaperChunk]:
        with self._lock:
            paper = self._get_paper_unlocked(paper_id)
            return sorted(
                [
                    c.model_copy(deep=True)
                    for c in self._paper_chunks.values()
                    if c.paper_id == paper.id
                ],
                key=lambda c: (c.document_id, c.chunk_index),
            )

    def validate_research_claim(self, leased, claim_id, payload):
        with self._lock:
            self._research_lease(leased)
            return self.validate_claim(claim_id, payload)

    def finish_research(self, leased: Job) -> Job:
        from .repository import utc_now
        from .models import SessionStatus

        with self._lock:
            current = self._research_lease(leased)
            now = utc_now()
            if current.branch_id:
                branch = self._get_branch_unlocked(current.branch_id)
                if branch.status == BranchStatus.RUNNING:
                    branch.status, branch.updated_at = BranchStatus.COMPLETED, now
            current.status = JobStatus.SUCCEEDED
            current.locked_at = current.locked_by = None
            current.completed_at = current.updated_at = now
            self._create_event_unlocked(
                session_id=current.session_id,
                event_type="job_completed",
                payload={"job_id": current.id, "job_type": current.job_type.value},
            )
            if not any(
                j.status in {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.PAUSED}
                for j in self._list_jobs_unlocked(current.session_id)
            ):
                session = self._get_session_unlocked(current.session_id)
                session.status, session.completed_at, session.updated_at = (
                    SessionStatus.COMPLETED,
                    now,
                    now,
                )
                self._create_event_unlocked(
                    session_id=current.session_id,
                    event_type="session_completed",
                    payload={},
                )
            return current.model_copy(deep=True)

    def fail_research(self, leased: Job, error: str, retryable: bool = True) -> Job:
        with self._lock:
            current = self._research_lease(leased)
            return self._fail_job_unlocked(
                current, error=error, retryable=retryable, retry_delay_seconds=10
            )
