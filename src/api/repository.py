"""Temporary in-memory repository for the ERLA product API skeleton."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from queue import Queue
from threading import Lock
from typing import TYPE_CHECKING, Protocol

from ..claims import ClaimExtractor, ClaimVerifier, EvidenceInput
from ..domain.ids import new_uuid_str
from ..domain.transitions import (
    InvalidTransitionError,
    validate_branch_transition,
    validate_session_transition,
)
from .models import (
    Branch,
    BranchCreate,
    BranchPatch,
    BranchStatus,
    Claim,
    ClaimEvidence,
    ClaimExtractionRequest,
    ClaimStatus,
    ClaimType,
    ClaimValidationRequest,
    ClaimValidationResult,
    Event,
    Job,
    JobStatus,
    JobType,
    Paper,
    Project,
    ProjectCreate,
    ResearchSession,
    RuntimeLoopBinding,
    SessionCreate,
    SessionPaper,
    SessionPaperView,
    SessionSnapshot,
    SessionStatus,
    Summary,
)
from .research_loop import ResearchLoopBridge

if TYPE_CHECKING:
    from ..orchestration.models import LoopState


class RepositoryError(Exception):
    """Base repository error."""


class NotFoundError(RepositoryError):
    """Raised when an entity cannot be found."""


class ConflictError(RepositoryError):
    """Raised when a requested state transition is invalid."""


@dataclass(frozen=True)
class EventSubscription:
    """Process-local subscription to a session event stream."""

    session_id: str
    replay_events: list[Event]
    queue: Queue[Event]


class ProductRepository(Protocol):
    """Repository contract required by the product API routes."""

    def create_project(self, payload: ProjectCreate) -> Project: ...

    def list_projects(self) -> list[Project]: ...

    def get_project(self, project_id: str) -> Project: ...

    def create_session(self, payload: SessionCreate) -> ResearchSession: ...

    def list_sessions(self) -> list[ResearchSession]: ...

    def get_session(self, session_id: str) -> ResearchSession: ...

    def get_session_snapshot(self, session_id: str) -> SessionSnapshot: ...

    def get_runtime_loop_binding(self, session_id: str) -> RuntimeLoopBinding: ...

    def list_jobs(self, session_id: str) -> list[Job]: ...

    def get_job(self, job_id: str) -> Job: ...

    def lease_next_job(
        self,
        worker_id: str,
        job_types: list[JobType] | None = None,
    ) -> Job | None: ...

    def complete_job(self, job_id: str, result: dict | None = None) -> Job: ...

    def fail_job(
        self,
        job_id: str,
        error: str,
        retryable: bool = True,
        retry_delay_seconds: int = 60,
    ) -> Job: ...

    def expire_timed_out_jobs(self) -> list[Job]: ...

    def set_session_status(
        self,
        session_id: str,
        status: SessionStatus,
        event_type: str,
    ) -> ResearchSession: ...

    def list_branches(self, session_id: str) -> list[Branch]: ...

    def get_branch(self, branch_id: str) -> Branch: ...

    def continue_branch(self, branch_id: str) -> Branch: ...

    def split_branch(
        self,
        branch_id: str,
        branch_payloads: list[BranchCreate],
    ) -> list[Branch]: ...

    def prune_branch(self, branch_id: str) -> Branch: ...

    def update_branch(self, branch_id: str, payload: BranchPatch) -> Branch: ...

    def list_papers(self, session_id: str) -> list[SessionPaperView]: ...

    def get_paper(self, paper_id: str) -> Paper: ...

    def extract_claims(
        self,
        session_id: str,
        payload: ClaimExtractionRequest,
    ) -> list[Claim]: ...

    def list_claims(self, session_id: str) -> list[Claim]: ...

    def get_claim(self, claim_id: str) -> Claim: ...

    def validate_claim(
        self,
        claim_id: str,
        payload: ClaimValidationRequest,
    ) -> ClaimValidationResult: ...

    def list_claim_evidence(self, claim_id: str) -> list[ClaimEvidence]: ...

    def list_events(self, session_id: str) -> list[Event]: ...

    def subscribe_events(
        self,
        session_id: str,
        replay_existing: bool = True,
    ) -> EventSubscription: ...

    def unsubscribe_events(self, subscription: EventSubscription) -> None: ...


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class InMemoryRepository:
    """Process-local repository used until durable storage is added."""

    def __init__(
        self,
        loop_bridge: ResearchLoopBridge | None = None,
        claim_extractor: ClaimExtractor | None = None,
        claim_verifier: ClaimVerifier | None = None,
    ) -> None:
        self._projects: dict[str, Project] = {}
        self._sessions: dict[str, ResearchSession] = {}
        self._branches: dict[str, Branch] = {}
        self._papers: dict[str, Paper] = {}
        self._session_papers: dict[str, SessionPaper] = {}
        self._summaries: dict[str, Summary] = {}
        self._claims: dict[str, Claim] = {}
        self._claim_evidence: dict[str, ClaimEvidence] = {}
        self._jobs: dict[str, Job] = {}
        self._events: dict[str, Event] = {}
        self._event_subscribers: dict[str, list[Queue[Event]]] = {}
        self._runtime_loop_bindings: dict[str, RuntimeLoopBinding] = {}
        self._runtime_loop_states: dict[str, LoopState] = {}
        self._loop_bridge = loop_bridge or ResearchLoopBridge()
        self._claim_extractor = claim_extractor or ClaimExtractor()
        self._claim_verifier = claim_verifier or ClaimVerifier()
        self._lock = Lock()

    def create_project(self, payload: ProjectCreate) -> Project:
        """Create a project."""

        with self._lock:
            now = utc_now()
            project = Project(
                id=self._new_id("proj"),
                title=payload.title,
                description=payload.description,
                field=payload.field,
                settings=deepcopy(payload.settings),
                created_at=now,
                updated_at=now,
            )
            self._projects[project.id] = project
            return project

    def list_projects(self) -> list[Project]:
        """List projects."""

        with self._lock:
            return list(self._projects.values())

    def get_project(self, project_id: str) -> Project:
        """Get a project."""

        with self._lock:
            try:
                return self._projects[project_id]
            except KeyError as exc:
                raise NotFoundError("Project not found") from exc

    def create_session(self, payload: SessionCreate) -> ResearchSession:
        """Create a research session and root branch."""

        with self._lock:
            if payload.project_id and payload.project_id not in self._projects:
                raise NotFoundError("Project not found")

            now = utc_now()
            session = ResearchSession(
                id=self._new_id("sess"),
                project_id=payload.project_id,
                initial_query=payload.initial_query,
                source_providers=list(payload.source_providers),
                filters=deepcopy(payload.filters),
                parameters=deepcopy(payload.parameters),
                status=SessionStatus.PENDING,
                created_at=now,
                updated_at=now,
            )
            self._sessions[session.id] = session

            runtime_loop = self._loop_bridge.create_loop(session)
            root_branch = self._loop_bridge.to_api_branch(
                session_id=session.id,
                runtime_branch=runtime_loop.root_branch,
                label="Root",
                rationale="Initial session query.",
                created_at=now,
                updated_at=now,
            )
            self._branches[root_branch.id] = root_branch
            self._runtime_loop_states[session.id] = runtime_loop.state
            self._runtime_loop_bindings[session.id] = RuntimeLoopBinding(
                session_id=session.id,
                loop_id=runtime_loop.state.loop_id,
                loop_number=runtime_loop.state.loop_number,
                root_branch_id=runtime_loop.root_branch.id,
                created_at=now,
                updated_at=now,
            )

            self._create_event_unlocked(
                session_id=session.id,
                event_type="session_created",
                payload={"initial_query": session.initial_query},
            )
            self._create_event_unlocked(
                session_id=session.id,
                event_type="research_loop_created",
                payload={
                    "loop_id": runtime_loop.state.loop_id,
                    "loop_number": runtime_loop.state.loop_number,
                    "root_branch_id": runtime_loop.root_branch.id,
                },
            )
            self._create_event_unlocked(
                session_id=session.id,
                branch_id=root_branch.id,
                event_type="branch_created",
                payload={"query": root_branch.query, "parent_branch_id": None},
            )
            return session

    def list_sessions(self) -> list[ResearchSession]:
        """List sessions."""

        with self._lock:
            return list(self._sessions.values())

    def get_session(self, session_id: str) -> ResearchSession:
        """Get a session."""

        with self._lock:
            return self._get_session_unlocked(session_id)

    def get_session_snapshot(self, session_id: str) -> SessionSnapshot:
        """Get reconstructable session state."""

        with self._lock:
            session = self._get_session_unlocked(session_id)
            return SessionSnapshot(
                session=session,
                runtime_loop=self._runtime_loop_bindings.get(session_id),
                branches=self._list_branches_unlocked(session_id),
                jobs=self._list_jobs_unlocked(session_id),
                papers=self._list_papers_unlocked(session_id),
                summaries=self._list_summaries_unlocked(session_id),
                claims=self._list_claims_unlocked(session_id),
                claim_evidence=self._list_claim_evidence_for_session_unlocked(
                    session_id
                ),
                events=self._list_events_unlocked(session_id),
            )

    def get_runtime_loop_binding(self, session_id: str) -> RuntimeLoopBinding:
        """Get the runtime loop binding for a session."""

        with self._lock:
            self._get_session_unlocked(session_id)
            try:
                return self._runtime_loop_bindings[session_id]
            except KeyError as exc:
                raise NotFoundError("Runtime loop not found") from exc

    def list_jobs(self, session_id: str) -> list[Job]:
        """List durable jobs for a session."""

        with self._lock:
            self._get_session_unlocked(session_id)
            return self._list_jobs_unlocked(session_id)

    def get_job(self, job_id: str) -> Job:
        """Get a background job."""

        with self._lock:
            return self._get_job_unlocked(job_id)

    def lease_next_job(
        self,
        worker_id: str,
        job_types: list[JobType] | None = None,
    ) -> Job | None:
        """Lease the next runnable job for a worker."""

        with self._lock:
            self._expire_timed_out_jobs_unlocked()
            requested_types = set(job_types or [])
            now = utc_now()
            candidates = [
                job
                for job in self._jobs.values()
                if job.status == JobStatus.QUEUED
                and job.run_at <= now
                and (not requested_types or job.job_type in requested_types)
            ]
            if not candidates:
                return None

            job = sorted(
                candidates,
                key=lambda candidate: (
                    -candidate.priority,
                    candidate.run_at,
                    candidate.created_at,
                ),
            )[0]
            job.status = JobStatus.RUNNING
            job.attempts += 1
            job.locked_by = worker_id
            job.locked_at = now
            job.updated_at = now
            self._jobs[job.id] = job
            self._create_event_unlocked(
                session_id=job.session_id,
                branch_id=job.branch_id,
                event_type="job_started",
                payload={
                    "job_id": job.id,
                    "job_type": job.job_type.value,
                    "attempt": job.attempts,
                    "worker_id": worker_id,
                },
            )
            return job

    def complete_job(self, job_id: str, result: dict | None = None) -> Job:
        """Mark a leased job as succeeded."""

        with self._lock:
            job = self._get_job_unlocked(job_id)
            if job.status != JobStatus.RUNNING:
                raise ConflictError("Only running jobs can be completed")
            now = utc_now()
            job.status = JobStatus.SUCCEEDED
            job.result = deepcopy(result or {})
            job.locked_by = None
            job.locked_at = None
            job.completed_at = now
            job.updated_at = now
            self._jobs[job.id] = job
            self._create_event_unlocked(
                session_id=job.session_id,
                branch_id=job.branch_id,
                event_type="job_completed",
                payload={
                    "job_id": job.id,
                    "job_type": job.job_type.value,
                    "attempts": job.attempts,
                },
            )
            return job

    def fail_job(
        self,
        job_id: str,
        error: str,
        retryable: bool = True,
        retry_delay_seconds: int = 60,
    ) -> Job:
        """Fail a running job and retry it when attempts remain."""

        with self._lock:
            job = self._get_job_unlocked(job_id)
            if job.status != JobStatus.RUNNING:
                raise ConflictError("Only running jobs can fail")
            return self._fail_job_unlocked(
                job,
                error=error,
                retryable=retryable,
                retry_delay_seconds=retry_delay_seconds,
            )

    def expire_timed_out_jobs(self) -> list[Job]:
        """Expire running jobs whose lease exceeded their timeout."""

        with self._lock:
            return self._expire_timed_out_jobs_unlocked()

    def set_session_status(
        self,
        session_id: str,
        status: SessionStatus,
        event_type: str,
    ) -> ResearchSession:
        """Set a session status for run-control endpoints."""

        with self._lock:
            session = self._get_session_unlocked(session_id)
            self._validate_session_transition(session.status, status)

            now = utc_now()
            session.status = status
            session.updated_at = now
            if status == SessionStatus.RUNNING and session.started_at is None:
                session.started_at = now
            if status in {
                SessionStatus.COMPLETED,
                SessionStatus.CANCELLED,
                SessionStatus.FAILED,
            }:
                session.completed_at = now
            self._sessions[session.id] = session

            if status == SessionStatus.RUNNING:
                for branch in self._list_branches_unlocked(session.id):
                    if branch.status in {BranchStatus.PENDING, BranchStatus.PAUSED}:
                        branch.status = BranchStatus.RUNNING
                        branch.updated_at = now
                        self._branches[branch.id] = branch

            if status == SessionStatus.PAUSED:
                for branch in self._list_branches_unlocked(session.id):
                    if branch.status == BranchStatus.RUNNING:
                        branch.status = BranchStatus.PAUSED
                        branch.updated_at = now
                        self._branches[branch.id] = branch

            event_payload = {"status": status.value}
            binding = self._runtime_loop_bindings.get(session.id)
            if binding:
                event_payload.update(
                    {
                        "loop_id": binding.loop_id,
                        "root_branch_id": binding.root_branch_id,
                    }
                )

            self._create_event_unlocked(
                session_id=session.id,
                event_type=event_type,
                payload=event_payload,
            )
            if event_type == "session_started":
                self._enqueue_job_unlocked(
                    session_id=session.id,
                    branch_id=event_payload.get("root_branch_id"),
                    job_type=JobType.RESEARCH_SESSION,
                    payload={
                        "initial_query": session.initial_query,
                        **event_payload,
                    },
                )
            elif event_type == "session_paused":
                self._pause_session_jobs_unlocked(session.id)
            elif event_type == "session_resumed":
                self._resume_session_jobs_unlocked(session.id)
            elif event_type == "session_cancelled":
                self._cancel_session_jobs_unlocked(session.id)
            return session

    def list_branches(self, session_id: str) -> list[Branch]:
        """List branches for a session."""

        with self._lock:
            self._get_session_unlocked(session_id)
            return self._list_branches_unlocked(session_id)

    def get_branch(self, branch_id: str) -> Branch:
        """Get a branch."""

        with self._lock:
            return self._get_branch_unlocked(branch_id)

    def continue_branch(self, branch_id: str) -> Branch:
        """Record a request to continue a branch without running work inline."""

        with self._lock:
            branch = self._get_branch_unlocked(branch_id)
            self._validate_branch_transition(branch.status, BranchStatus.RUNNING)

            branch.status = BranchStatus.RUNNING
            branch.failure_reason = None
            branch.updated_at = utc_now()
            self._branches[branch.id] = branch
            self._create_event_unlocked(
                session_id=branch.session_id,
                branch_id=branch.id,
                event_type="branch_continue_requested",
                payload={"query": branch.query},
            )
            self._enqueue_job_unlocked(
                session_id=branch.session_id,
                branch_id=branch.id,
                job_type=JobType.BRANCH_CONTINUE,
                payload={"query": branch.query},
            )
            return branch

    def split_branch(
        self,
        branch_id: str,
        branch_payloads: list[BranchCreate],
    ) -> list[Branch]:
        """Create child branches from a parent branch."""

        with self._lock:
            parent = self._get_branch_unlocked(branch_id)
            if parent.status in {BranchStatus.PRUNED, BranchStatus.COMPLETED}:
                raise ConflictError(f"Cannot split a {parent.status.value} branch")

            now = utc_now()
            children: list[Branch] = []
            for payload in branch_payloads:
                child = Branch(
                    id=self._new_id("branch"),
                    session_id=parent.session_id,
                    parent_branch_id=parent.id,
                    query=payload.query,
                    label=payload.label,
                    rationale=payload.rationale,
                    mode=payload.mode,
                    status=BranchStatus.PENDING,
                    depth=parent.depth + 1,
                    created_at=now,
                    updated_at=now,
                )
                self._branches[child.id] = child
                children.append(child)

            self._create_event_unlocked(
                session_id=parent.session_id,
                branch_id=parent.id,
                event_type="branch_split",
                payload={"child_branch_ids": [child.id for child in children]},
            )
            return children

    def prune_branch(self, branch_id: str) -> Branch:
        """Prune a branch."""

        with self._lock:
            branch = self._get_branch_unlocked(branch_id)
            self._validate_branch_transition(branch.status, BranchStatus.PRUNED)
            branch.status = BranchStatus.PRUNED
            branch.prune_reason = branch.prune_reason or "Pruned through API request."
            branch.updated_at = utc_now()
            self._branches[branch.id] = branch
            self._create_event_unlocked(
                session_id=branch.session_id,
                branch_id=branch.id,
                event_type="branch_pruned",
                payload={"query": branch.query},
            )
            return branch

    def update_branch(self, branch_id: str, payload: BranchPatch) -> Branch:
        """Update branch metadata."""

        with self._lock:
            branch = self._get_branch_unlocked(branch_id)
            update = payload.model_dump(exclude_unset=True)
            event_payload = payload.model_dump(exclude_unset=True, mode="json")
            if "status" in update:
                self._validate_branch_transition(branch.status, update["status"])
            for field_name, value in update.items():
                setattr(branch, field_name, value)
            branch.updated_at = utc_now()
            self._branches[branch.id] = branch
            self._create_event_unlocked(
                session_id=branch.session_id,
                branch_id=branch.id,
                event_type="branch_updated",
                payload=event_payload,
            )
            return branch

    def list_papers(self, session_id: str) -> list[SessionPaperView]:
        """List papers for a session."""

        with self._lock:
            self._get_session_unlocked(session_id)
            return self._list_papers_unlocked(session_id)

    def get_paper(self, paper_id: str) -> Paper:
        """Get a paper by internal API ID or provider paper ID."""

        with self._lock:
            return self._get_paper_unlocked(paper_id)

    def extract_claims(
        self,
        session_id: str,
        payload: ClaimExtractionRequest,
    ) -> list[Claim]:
        """Extract review-ready atomic claims from source text."""

        with self._lock:
            self._get_session_unlocked(session_id)
            if payload.branch_id:
                branch = self._get_branch_unlocked(payload.branch_id)
                if branch.session_id != session_id:
                    raise NotFoundError("Branch not found")
            if payload.paper_id:
                self._ensure_paper_in_session_unlocked(payload.paper_id, session_id)

            now = utc_now()
            extracted = self._claim_extractor.extract(
                payload.source_text,
                max_claims=payload.max_claims,
            )
            claims: list[Claim] = []
            for draft in extracted:
                claim = Claim(
                    id=self._new_id("claim"),
                    session_id=session_id,
                    branch_id=payload.branch_id,
                    paper_id=payload.paper_id,
                    summary_id=payload.summary_id,
                    claim_text=draft.text,
                    claim_type=ClaimType(draft.claim_type),
                    status=ClaimStatus(draft.status),
                    confidence=draft.confidence,
                    created_by=payload.created_by,
                    created_at=now,
                    updated_at=now,
                )
                self._claims[claim.id] = claim
                claims.append(claim)

            self._create_event_unlocked(
                session_id=session_id,
                branch_id=payload.branch_id,
                paper_id=payload.paper_id,
                event_type="claims_extracted",
                payload={
                    "claim_ids": [claim.id for claim in claims],
                    "claim_count": len(claims),
                    "created_by": payload.created_by,
                    "summary_id": payload.summary_id,
                },
            )
            return claims

    def list_claims(self, session_id: str) -> list[Claim]:
        """List claims for a session."""

        with self._lock:
            self._get_session_unlocked(session_id)
            return self._list_claims_unlocked(session_id)

    def get_claim(self, claim_id: str) -> Claim:
        """Get a claim."""

        with self._lock:
            return self._get_claim_unlocked(claim_id)

    def validate_claim(
        self,
        claim_id: str,
        payload: ClaimValidationRequest,
    ) -> ClaimValidationResult:
        """Validate a claim against supplied evidence."""

        with self._lock:
            claim = self._get_claim_unlocked(claim_id)
            now = utc_now()
            evidence_items: list[ClaimEvidence] = []
            for evidence_payload in payload.evidence:
                if evidence_payload.paper_id:
                    self._ensure_paper_in_session_unlocked(
                        evidence_payload.paper_id,
                        claim.session_id,
                    )

                evidence = ClaimEvidence(
                    id=self._new_id("evd"),
                    claim_id=claim.id,
                    session_id=claim.session_id,
                    source_type=evidence_payload.source_type,
                    paper_id=evidence_payload.paper_id,
                    chunk_id=evidence_payload.chunk_id,
                    metadata_field=evidence_payload.metadata_field,
                    upload_id=evidence_payload.upload_id,
                    document_id=evidence_payload.document_id,
                    external_uri=evidence_payload.external_uri,
                    source_id=evidence_payload.source_id,
                    reviewer_id=evidence_payload.reviewer_id,
                    evidence_text=evidence_payload.evidence_text,
                    relation=evidence_payload.relation,
                    score=evidence_payload.score,
                    page_start=evidence_payload.page_start,
                    page_end=evidence_payload.page_end,
                    section_title=evidence_payload.section_title,
                    created_at=now,
                )
                self._claim_evidence[evidence.id] = evidence
                evidence_items.append(evidence)

            decision = self._claim_verifier.decide(
                [
                    EvidenceInput(
                        relation=evidence.relation.value,
                        score=evidence.score,
                    )
                    for evidence in evidence_items
                ]
            )
            claim.status = ClaimStatus(decision.status)
            claim.confidence = decision.confidence
            claim.updated_at = now
            self._claims[claim.id] = claim

            self._create_event_unlocked(
                session_id=claim.session_id,
                branch_id=claim.branch_id,
                paper_id=claim.paper_id,
                event_type="claim_validated",
                payload={
                    "claim_id": claim.id,
                    "status": claim.status.value,
                    "confidence": claim.confidence,
                    "evidence_ids": [evidence.id for evidence in evidence_items],
                    "validator_type": payload.validator_type,
                    "notes": payload.notes,
                },
            )
            return ClaimValidationResult(
                claim=claim,
                evidence=evidence_items,
            )

    def list_claim_evidence(self, claim_id: str) -> list[ClaimEvidence]:
        """List evidence attached to a claim."""

        with self._lock:
            self._get_claim_unlocked(claim_id)
            return self._list_claim_evidence_unlocked(claim_id)

    def list_events(self, session_id: str) -> list[Event]:
        """List session events."""

        with self._lock:
            self._get_session_unlocked(session_id)
            return self._list_events_unlocked(session_id)

    def subscribe_events(
        self,
        session_id: str,
        replay_existing: bool = True,
    ) -> EventSubscription:
        """Subscribe to a process-local event stream for a session."""

        with self._lock:
            self._get_session_unlocked(session_id)
            queue: Queue[Event] = Queue()
            replay_events = (
                self._list_events_unlocked(session_id) if replay_existing else []
            )
            self._event_subscribers.setdefault(session_id, []).append(queue)
            return EventSubscription(
                session_id=session_id,
                replay_events=replay_events,
                queue=queue,
            )

    def unsubscribe_events(self, subscription: EventSubscription) -> None:
        """Remove a process-local event stream subscription."""

        with self._lock:
            subscribers = self._event_subscribers.get(subscription.session_id)
            if not subscribers:
                return
            try:
                subscribers.remove(subscription.queue)
            except ValueError:
                return
            if not subscribers:
                del self._event_subscribers[subscription.session_id]

    def _get_session_unlocked(self, session_id: str) -> ResearchSession:
        try:
            return self._sessions[session_id]
        except KeyError as exc:
            raise NotFoundError("Session not found") from exc

    def _get_branch_unlocked(self, branch_id: str) -> Branch:
        try:
            return self._branches[branch_id]
        except KeyError as exc:
            raise NotFoundError("Branch not found") from exc

    def _get_paper_unlocked(self, paper_id: str) -> Paper:
        for paper in self._papers.values():
            external_ids = {
                paper.semantic_scholar_id,
                paper.arxiv_id,
                paper.doi,
                paper.openalex_id,
            }
            if paper.id == paper_id or paper_id in external_ids:
                return paper
        raise NotFoundError("Paper not found")

    def _get_claim_unlocked(self, claim_id: str) -> Claim:
        try:
            return self._claims[claim_id]
        except KeyError as exc:
            raise NotFoundError("Claim not found") from exc

    def _get_job_unlocked(self, job_id: str) -> Job:
        try:
            return self._jobs[job_id]
        except KeyError as exc:
            raise NotFoundError("Job not found") from exc

    def _list_branches_unlocked(self, session_id: str) -> list[Branch]:
        return [
            branch
            for branch in self._branches.values()
            if branch.session_id == session_id
        ]

    def _list_jobs_unlocked(self, session_id: str) -> list[Job]:
        jobs = [
            job
            for job in self._jobs.values()
            if job.session_id == session_id
        ]
        return sorted(jobs, key=lambda job: (job.created_at, job.id))

    def _enqueue_job_unlocked(
        self,
        *,
        session_id: str,
        branch_id: str | None,
        job_type: JobType,
        payload: dict,
        priority: int = 0,
        max_attempts: int = 3,
        timeout_seconds: int = 1800,
        run_at: datetime | None = None,
    ) -> Job:
        now = utc_now()
        job = Job(
            id=self._new_id("job"),
            session_id=session_id,
            branch_id=branch_id,
            job_type=job_type,
            status=JobStatus.QUEUED,
            payload=deepcopy(payload),
            result={},
            priority=priority,
            attempts=0,
            max_attempts=max_attempts,
            timeout_seconds=timeout_seconds,
            run_at=run_at or now,
            created_at=now,
            updated_at=now,
        )
        self._jobs[job.id] = job
        self._create_event_unlocked(
            session_id=session_id,
            branch_id=branch_id,
            event_type="job_queued",
            payload={
                "job_id": job.id,
                "job_type": job.job_type.value,
                "run_at": job.run_at.isoformat(),
                "max_attempts": job.max_attempts,
                "timeout_seconds": job.timeout_seconds,
            },
        )
        return job

    def _pause_session_jobs_unlocked(self, session_id: str) -> None:
        for job in self._list_jobs_unlocked(session_id):
            if job.status not in {JobStatus.QUEUED, JobStatus.RUNNING}:
                continue
            job.status = JobStatus.PAUSED
            job.locked_by = None
            job.locked_at = None
            job.updated_at = utc_now()
            self._jobs[job.id] = job
            self._create_event_unlocked(
                session_id=session_id,
                branch_id=job.branch_id,
                event_type="job_paused",
                payload={"job_id": job.id, "job_type": job.job_type.value},
            )

    def _resume_session_jobs_unlocked(self, session_id: str) -> None:
        for job in self._list_jobs_unlocked(session_id):
            if job.status != JobStatus.PAUSED:
                continue
            job.status = JobStatus.QUEUED
            job.updated_at = utc_now()
            self._jobs[job.id] = job
            self._create_event_unlocked(
                session_id=session_id,
                branch_id=job.branch_id,
                event_type="job_resumed",
                payload={"job_id": job.id, "job_type": job.job_type.value},
            )

    def _cancel_session_jobs_unlocked(self, session_id: str) -> None:
        for job in self._list_jobs_unlocked(session_id):
            if job.status not in {
                JobStatus.QUEUED,
                JobStatus.RUNNING,
                JobStatus.PAUSED,
            }:
                continue
            now = utc_now()
            job.status = JobStatus.CANCELLED
            job.locked_by = None
            job.locked_at = None
            job.completed_at = now
            job.updated_at = now
            self._jobs[job.id] = job
            self._create_event_unlocked(
                session_id=session_id,
                branch_id=job.branch_id,
                event_type="job_cancelled",
                payload={"job_id": job.id, "job_type": job.job_type.value},
            )

    def _fail_job_unlocked(
        self,
        job: Job,
        *,
        error: str,
        retryable: bool,
        retry_delay_seconds: int,
    ) -> Job:
        now = utc_now()
        job.last_error = error
        job.locked_by = None
        job.locked_at = None
        job.updated_at = now
        if retryable and job.attempts < job.max_attempts:
            job.status = JobStatus.QUEUED
            job.run_at = now + timedelta(seconds=retry_delay_seconds)
            self._jobs[job.id] = job
            self._create_event_unlocked(
                session_id=job.session_id,
                branch_id=job.branch_id,
                event_type="job_retry_scheduled",
                payload={
                    "job_id": job.id,
                    "job_type": job.job_type.value,
                    "attempts": job.attempts,
                    "max_attempts": job.max_attempts,
                    "error": error,
                    "run_at": job.run_at.isoformat(),
                },
                severity="warning",
            )
            return job

        job.status = JobStatus.FAILED
        job.completed_at = now
        self._jobs[job.id] = job
        self._mark_job_target_failed_unlocked(job, error)
        self._create_event_unlocked(
            session_id=job.session_id,
            branch_id=job.branch_id,
            event_type="job_failed",
            payload={
                "job_id": job.id,
                "job_type": job.job_type.value,
                "attempts": job.attempts,
                "max_attempts": job.max_attempts,
                "error": error,
            },
            severity="error",
        )
        return job

    def _expire_timed_out_jobs_unlocked(self) -> list[Job]:
        now = utc_now()
        expired: list[Job] = []
        for job in list(self._jobs.values()):
            if job.status != JobStatus.RUNNING or job.locked_at is None:
                continue
            deadline = job.locked_at + timedelta(seconds=job.timeout_seconds)
            if deadline >= now:
                continue
            error = f"Job timed out after {job.timeout_seconds} seconds"
            job.last_error = error
            job.locked_by = None
            job.locked_at = None
            job.updated_at = now
            if job.attempts < job.max_attempts:
                job.status = JobStatus.QUEUED
                job.run_at = now
                retried = True
                severity = "warning"
            else:
                job.status = JobStatus.TIMED_OUT
                job.completed_at = now
                retried = False
                severity = "error"
                self._mark_job_target_failed_unlocked(job, error)
            self._jobs[job.id] = job
            expired.append(job)
            self._create_event_unlocked(
                session_id=job.session_id,
                branch_id=job.branch_id,
                event_type="job_timed_out",
                payload={
                    "job_id": job.id,
                    "job_type": job.job_type.value,
                    "attempts": job.attempts,
                    "max_attempts": job.max_attempts,
                    "retried": retried,
                    "error": error,
                },
                severity=severity,
            )
        return expired

    def _mark_job_target_failed_unlocked(self, job: Job, error: str) -> None:
        now = utc_now()
        if job.job_type == JobType.RESEARCH_SESSION:
            session = self._sessions.get(job.session_id)
            if session is not None:
                session.status = SessionStatus.FAILED
                session.failure_reason = error
                session.completed_at = now
                session.updated_at = now
                self._sessions[session.id] = session
        if job.branch_id:
            branch = self._branches.get(job.branch_id)
            if branch is not None:
                branch.status = BranchStatus.FAILED
                branch.failure_reason = error
                branch.updated_at = now
                self._branches[branch.id] = branch

    def _list_papers_unlocked(self, session_id: str) -> list[SessionPaperView]:
        views: list[SessionPaperView] = []
        for session_paper in self._session_papers.values():
            if session_paper.session_id != session_id:
                continue
            paper = self._papers.get(session_paper.paper_id)
            if paper is None:
                continue
            views.append(
                SessionPaperView(
                    id=session_paper.id,
                    session_id=session_paper.session_id,
                    branch_id=session_paper.branch_id,
                    paper_id=paper.id,
                    discovery_method=session_paper.discovery_method,
                    selection_reason=session_paper.selection_reason,
                    selected=session_paper.selected,
                    iteration_number=session_paper.iteration_number,
                    paper=paper,
                    created_at=session_paper.created_at,
                )
            )
        return sorted(views, key=lambda view: view.created_at)

    def _list_summaries_unlocked(self, session_id: str) -> list[Summary]:
        summaries = [
            summary
            for summary in self._summaries.values()
            if summary.session_id == session_id
        ]
        return sorted(summaries, key=lambda summary: summary.created_at)

    def _ensure_paper_in_session_unlocked(
        self,
        paper_id: str,
        session_id: str,
    ) -> None:
        paper = self._get_paper_unlocked(paper_id)
        for session_paper in self._session_papers.values():
            if (
                session_paper.session_id == session_id
                and session_paper.paper_id == paper.id
            ):
                return
        raise NotFoundError("Paper not found")

    def _list_claims_unlocked(self, session_id: str) -> list[Claim]:
        claims = [
            claim
            for claim in self._claims.values()
            if claim.session_id == session_id
        ]
        return sorted(claims, key=lambda claim: claim.created_at)

    def _list_claim_evidence_unlocked(self, claim_id: str) -> list[ClaimEvidence]:
        evidence = [
            item
            for item in self._claim_evidence.values()
            if item.claim_id == claim_id
        ]
        return sorted(evidence, key=lambda item: item.created_at)

    def _list_claim_evidence_for_session_unlocked(
        self,
        session_id: str,
    ) -> list[ClaimEvidence]:
        evidence = [
            item
            for item in self._claim_evidence.values()
            if item.session_id == session_id
        ]
        return sorted(evidence, key=lambda item: item.created_at)

    def _list_events_unlocked(self, session_id: str) -> list[Event]:
        events = [
            event
            for event in self._events.values()
            if event.session_id == session_id
        ]
        return sorted(events, key=lambda event: event.created_at)

    def _create_event_unlocked(
        self,
        session_id: str,
        event_type: str,
        payload: dict,
        branch_id: str | None = None,
        paper_id: str | None = None,
        severity: str = "info",
    ) -> Event:
        event = Event(
            id=self._new_id("evt"),
            session_id=session_id,
            branch_id=branch_id,
            paper_id=paper_id,
            event_type=event_type,
            payload=payload,
            severity=severity,
            created_at=utc_now(),
        )
        self._events[event.id] = event
        self._publish_event_unlocked(event)
        return event

    def _publish_event_unlocked(self, event: Event) -> None:
        subscribers = self._event_subscribers.get(event.session_id, [])
        for subscriber in list(subscribers):
            subscriber.put_nowait(event)

    def _validate_session_transition(
        self,
        current: SessionStatus,
        target: SessionStatus,
    ) -> None:
        try:
            validate_session_transition(current, target)
        except InvalidTransitionError as exc:
            raise ConflictError(str(exc)) from exc

    def _validate_branch_transition(
        self,
        current: BranchStatus,
        target: BranchStatus,
    ) -> None:
        try:
            validate_branch_transition(current, target)
        except InvalidTransitionError as exc:
            raise ConflictError(str(exc)) from exc

    def _new_id(self, prefix: str) -> str:
        return new_uuid_str()
