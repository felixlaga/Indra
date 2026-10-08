"""Atomic research writes for the in-process repository."""

from copy import deepcopy

from ..research.models import READ_REASON, PaperChunk, PaperResult, stable_id
from .models import (
    AgentDecision,
    Branch,
    BranchStatus,
    Claim,
    ClaimStatus,
    ClaimType,
    Hypothesis,
    Job,
    JobStatus,
    JobType,
    SessionPaper,
    Summary,
)

ACTIVE_JOB_STATUSES = {JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.PAUSED}


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
            if existing and existing.model_dump(exclude={"created_at", "updated_at"}) != paper.model_dump(exclude={"created_at", "updated_at"}):
                for session_id in sorted({link.session_id for link in self._session_papers.values() if link.paper_id == paper.id}):
                    self._create_event_unlocked(session_id, "paper_metadata_updated", {}, paper_id=paper.id)
            link_id = stable_id(leased.session_id, leased.branch_id or "", paper.id)
            prior = self._session_papers.get(link_id)
            self._session_papers[link_id] = SessionPaper(
                id=link_id,
                session_id=leased.session_id,
                branch_id=leased.branch_id,
                paper_id=paper.id,
                selected=True,
                discovery_method="query_search",
                selection_reason=result.selection_reason
                or (prior.selection_reason if prior else None)
                or READ_REASON,
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

    def reserve_model_call(
        self, leased: Job, *, limit: int, reserved: int = 0, job_limit: int | None = None
    ) -> str | None:
        """Count one model call against the session, or say which limit is spent."""

        with self._lock:
            current = self._research_lease(leased)
            used = sum(
                job.result.get("model_calls", 0)
                for job in self._list_jobs_unlocked(leased.session_id)
            )
            mine = current.result.get("model_calls", 0)
            if used >= limit - reserved:
                return "session"
            if job_limit is not None and mine >= job_limit:
                return "branch"
            current.result["model_calls"] = mine + 1
            return None

    def save_discovered_papers(self, leased: Job, papers: list, reason: str) -> int:
        """Link candidates a branch found but did not read, for the research map."""

        from .repository import utc_now

        if not papers:
            return 0
        with self._lock:
            self._research_lease(leased)
            for found in papers:
                paper = next(
                    (p for p in self._papers.values() if p.canonical_key == found.canonical_key),
                    None,
                )
                if paper is None:
                    paper = found.model_copy(deep=True)
                    self._papers[paper.id] = paper
                link_id = stable_id(leased.session_id, leased.branch_id or "", paper.id)
                self._session_papers.setdefault(
                    link_id,
                    SessionPaper(
                        id=link_id,
                        session_id=leased.session_id,
                        branch_id=leased.branch_id,
                        paper_id=paper.id,
                        selected=False,
                        discovery_method="query_search",
                        selection_reason=reason,
                        created_at=utc_now(),
                    ),
                )
            self._create_event_unlocked(
                session_id=leased.session_id,
                branch_id=leased.branch_id,
                event_type="papers_found",
                payload={"count": len(papers)},
            )
        return len(papers)

    def record_research_decision(self, leased: Job, decision, *, max_branches: int) -> list[Branch]:
        """Store a decision and open its Scout branches with their jobs, once."""

        from .repository import utc_now

        with self._lock:
            self._research_lease(leased)
            if decision.id in self._decisions:
                return [
                    self._branches[i]
                    for i in self._decisions[decision.id].details.get("child_branch_ids", [])
                    if i in self._branches
                ]
            now = utc_now()
            existing = sum(
                1 for b in self._list_branches_unlocked(leased.session_id) if b.depth > 0
            )
            keep = decision.children[: max(0, max_branches - existing)]
            alternatives = list(decision.alternatives) + [
                {"query": c.query, "reason": "The session's branch limit was reached."}
                for c in decision.children[len(keep):]
            ]
            parent = self._branches.get(decision.branch_id) if decision.branch_id else None
            created = []
            for child in keep:
                branch = Branch(
                    id=child.id,
                    session_id=leased.session_id,
                    parent_branch_id=decision.branch_id,
                    query=child.query,
                    label=child.label,
                    rationale=child.rationale,
                    status=BranchStatus.RUNNING,
                    depth=(parent.depth if parent else 0) + 1,
                    created_at=now,
                    updated_at=now,
                )
                self._branches[branch.id] = branch
                created.append(branch)
                self._create_event_unlocked(
                    session_id=leased.session_id,
                    branch_id=branch.id,
                    event_type="branch_created",
                    payload={
                        "query": branch.query,
                        "parent_branch_id": branch.parent_branch_id,
                        "origin": "scout",
                        "motivation": child.motivation,
                    },
                )
                self._enqueue_job_unlocked(
                    session_id=leased.session_id,
                    branch_id=branch.id,
                    job_type=JobType.BRANCH_CONTINUE,
                    payload={"query": branch.query, "origin": "scout"},
                )
            details = {**decision.details, "child_branch_ids": [b.id for b in created]}
            self._decisions[decision.id] = AgentDecision(
                id=decision.id,
                session_id=leased.session_id,
                branch_id=decision.branch_id,
                decision_type=decision.decision_type,
                decision=decision.decision if created or not decision.children
                else "No follow-up branches were opened.",
                rationale=decision.rationale,
                input_summary=decision.input_summary,
                alternatives=alternatives,
                details=details,
                generation_provenance=decision.provenance or None,
                created_at=now,
            )
            self._create_event_unlocked(
                session_id=leased.session_id,
                branch_id=decision.branch_id,
                event_type="agent_decision",
                payload={
                    "decision_id": decision.id,
                    "decision_type": decision.decision_type,
                    "message": self._decisions[decision.id].decision,
                    "child_branch_ids": details["child_branch_ids"],
                },
            )
            return [b.model_copy(deep=True) for b in created]

    def save_session_synthesis(self, leased: Job, record) -> None:
        """Store the session overview, kept hypotheses and their decision, once."""

        from .repository import utc_now

        with self._lock:
            self._research_lease(leased)
            if record.summary_id in self._summaries:
                return
            now = utc_now()
            self._summaries[record.summary_id] = Summary(
                id=record.summary_id,
                session_id=leased.session_id,
                summary_type="session",
                text=record.overview,
                generation_provenance=record.provenance or None,
                created_at=now,
                updated_at=now,
            )
            for item in record.hypotheses:
                self._hypotheses[item.id] = Hypothesis(
                    id=item.id,
                    session_id=leased.session_id,
                    text=item.text,
                    rationale=item.rationale,
                    testability=item.testability,
                    risk_level=item.risk,
                    supporting_claim_ids=item.supporting_claim_ids,
                    contradicting_claim_ids=item.contradicting_claim_ids,
                    supporting_paper_ids=item.supporting_paper_ids,
                    missing_evidence=item.missing_evidence,
                    next_steps=item.next_steps,
                    generation_provenance=record.provenance or None,
                    created_at=now,
                )
            decision = record.decision
            self._decisions[decision.id] = AgentDecision(
                id=decision.id,
                session_id=leased.session_id,
                decision_type=decision.decision_type,
                decision=decision.decision,
                rationale=decision.rationale,
                input_summary=decision.input_summary,
                alternatives=decision.alternatives,
                details=decision.details,
                generation_provenance=decision.provenance or None,
                created_at=now,
            )
            self._create_event_unlocked(
                session_id=leased.session_id,
                event_type="session_synthesized",
                payload={
                    "summary_id": record.summary_id,
                    "hypothesis_count": len(record.hypotheses),
                    "message": decision.decision,
                },
            )

    def finish_research(self, leased: Job, *, then_synthesize: bool = False) -> Job:
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
            jobs = self._list_jobs_unlocked(current.session_id)
            if not any(j.status in ACTIVE_JOB_STATUSES for j in jobs):
                if then_synthesize and not any(
                    j.job_type == JobType.SESSION_SYNTHESIS for j in jobs
                ):
                    # The last branch hands the session to one synthesis job.
                    self._enqueue_job_unlocked(
                        session_id=current.session_id,
                        branch_id=None,
                        job_type=JobType.SESSION_SYNTHESIS,
                        payload={},
                    )
                    return current.model_copy(deep=True)
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
