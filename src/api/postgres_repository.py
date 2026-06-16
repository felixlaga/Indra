"""Postgres-backed repository for durable ERLA product state."""

from __future__ import annotations

from dataclasses import dataclass
from queue import Queue
from threading import Lock
from typing import Any, Callable, ContextManager

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
    Paper,
    Project,
    ProjectCreate,
    ResearchSession,
    RuntimeLoopBinding,
    SessionCreate,
    SessionPaperView,
    SessionSnapshot,
    SessionStatus,
    Summary,
)
from .repository import ConflictError, EventSubscription, NotFoundError, utc_now
from .research_loop import ResearchLoopBridge

ConnectionFactory = Callable[[], ContextManager[Any]]


@dataclass(frozen=True)
class InsertedEvent:
    """Event plus destination queues to notify after insert."""

    event: Event
    queues: list[Queue[Event]]


def _jsonb(value: Any) -> Any:
    """Wrap a value for jsonb adaptation when psycopg is installed."""

    try:
        from psycopg.types.json import Jsonb
    except ModuleNotFoundError:
        return value
    return Jsonb(value)


class PostgresRepository:
    """Durable repository using the Phase 2 Postgres schema."""

    def __init__(
        self,
        dsn: str,
        *,
        connection_factory: ConnectionFactory | None = None,
        loop_bridge: ResearchLoopBridge | None = None,
        claim_extractor: ClaimExtractor | None = None,
        claim_verifier: ClaimVerifier | None = None,
    ) -> None:
        if not dsn and connection_factory is None:
            raise ValueError("PostgresRepository requires a database URL")
        self._dsn = dsn
        self._connection_factory = connection_factory
        self._loop_bridge = loop_bridge or ResearchLoopBridge()
        self._claim_extractor = claim_extractor or ClaimExtractor()
        self._claim_verifier = claim_verifier or ClaimVerifier()
        self._event_subscribers: dict[str, list[Queue[Event]]] = {}
        self._lock = Lock()

    def create_project(self, payload: ProjectCreate) -> Project:
        with self._connect() as conn:
            row = self._fetch_one(
                conn,
                """
                INSERT INTO projects (title, description, field, settings)
                VALUES (%s, %s, %s, %s)
                RETURNING *
                """,
                (
                    payload.title,
                    payload.description,
                    payload.field,
                    _jsonb(payload.settings),
                ),
            )
            return _project_from_row(row)

    def list_projects(self) -> list[Project]:
        with self._connect() as conn:
            rows = self._fetch_all(
                conn,
                "SELECT * FROM projects ORDER BY created_at DESC",
            )
            return [_project_from_row(row) for row in rows]

    def get_project(self, project_id: str) -> Project:
        with self._connect() as conn:
            row = self._fetch_optional(
                conn,
                "SELECT * FROM projects WHERE id = %s",
                (project_id,),
            )
            if row is None:
                raise NotFoundError("Project not found")
            return _project_from_row(row)

    def create_session(self, payload: SessionCreate) -> ResearchSession:
        pending_events: list[InsertedEvent] = []
        with self._connect() as conn:
            if payload.project_id:
                project = self._fetch_optional(
                    conn,
                    "SELECT id FROM projects WHERE id = %s",
                    (payload.project_id,),
                )
                if project is None:
                    raise NotFoundError("Project not found")

            session_row = self._fetch_one(
                conn,
                """
                INSERT INTO research_sessions (
                  project_id, initial_query, status, source_providers,
                  filters, parameters
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    payload.project_id,
                    payload.initial_query,
                    SessionStatus.PENDING.value,
                    list(payload.source_providers),
                    _jsonb(payload.filters),
                    _jsonb(payload.parameters),
                ),
            )
            session = _session_from_row(session_row)

            runtime_loop = self._loop_bridge.create_loop(session)
            root_branch = self._loop_bridge.to_api_branch(
                session_id=session.id,
                runtime_branch=runtime_loop.root_branch,
                label="Root",
                rationale="Initial session query.",
                created_at=session.created_at,
                updated_at=session.updated_at,
            )
            self._execute(
                conn,
                """
                INSERT INTO branches (
                  id, session_id, parent_branch_id, query, label, rationale,
                  mode, status, depth, context_tokens_used, max_context_tokens
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    root_branch.id,
                    root_branch.session_id,
                    root_branch.parent_branch_id,
                    root_branch.query,
                    root_branch.label,
                    root_branch.rationale,
                    root_branch.mode.value,
                    root_branch.status.value,
                    root_branch.depth,
                    root_branch.context_tokens_used,
                    root_branch.max_context_tokens,
                ),
            )
            binding_row = self._fetch_one(
                conn,
                """
                INSERT INTO runtime_loop_bindings (
                  session_id, loop_id, loop_number, root_branch_id
                )
                VALUES (%s, %s, %s, %s)
                RETURNING *
                """,
                (
                    session.id,
                    runtime_loop.state.loop_id,
                    runtime_loop.state.loop_number,
                    runtime_loop.root_branch.id,
                ),
            )

            pending_events.append(
                self._insert_event(
                    conn,
                    session_id=session.id,
                    event_type="session_created",
                    payload={"initial_query": session.initial_query},
                )
            )
            pending_events.append(
                self._insert_event(
                    conn,
                    session_id=session.id,
                    event_type="research_loop_created",
                    payload={
                        "loop_id": runtime_loop.state.loop_id,
                        "loop_number": runtime_loop.state.loop_number,
                        "root_branch_id": runtime_loop.root_branch.id,
                    },
                )
            )
            pending_events.append(
                self._insert_event(
                    conn,
                    session_id=session.id,
                    branch_id=root_branch.id,
                    event_type="branch_created",
                    payload={"query": root_branch.query, "parent_branch_id": None},
                )
            )

            _runtime_loop_binding_from_row(binding_row)

        self._publish_inserted_events(pending_events)
        return session

    def list_sessions(self) -> list[ResearchSession]:
        with self._connect() as conn:
            rows = self._fetch_all(
                conn,
                "SELECT * FROM research_sessions ORDER BY created_at DESC",
            )
            return [_session_from_row(row) for row in rows]

    def get_session(self, session_id: str) -> ResearchSession:
        with self._connect() as conn:
            return self._get_session(conn, session_id)

    def get_session_snapshot(self, session_id: str) -> SessionSnapshot:
        with self._connect() as conn:
            session = self._get_session(conn, session_id)
            return SessionSnapshot(
                session=session,
                runtime_loop=self._get_runtime_loop_binding(conn, session_id),
                branches=self._list_branches(conn, session_id),
                papers=self._list_papers(conn, session_id),
                summaries=self._list_summaries(conn, session_id),
                claims=self._list_claims(conn, session_id),
                claim_evidence=self._list_claim_evidence_for_session(conn, session_id),
                events=self._list_events(conn, session_id),
            )

    def get_runtime_loop_binding(self, session_id: str) -> RuntimeLoopBinding:
        with self._connect() as conn:
            self._get_session(conn, session_id)
            return self._get_runtime_loop_binding(conn, session_id)

    def set_session_status(
        self,
        session_id: str,
        status: SessionStatus,
        event_type: str,
    ) -> ResearchSession:
        pending_events: list[InsertedEvent] = []
        with self._connect() as conn:
            session = self._get_session(conn, session_id)
            self._validate_session_transition(session.status, status)
            row = self._fetch_one(
                conn,
                """
                UPDATE research_sessions
                SET status = %s,
                    started_at = CASE
                      WHEN %s = 'running' AND started_at IS NULL THEN now()
                      ELSE started_at
                    END,
                    completed_at = CASE
                      WHEN %s IN ('completed', 'cancelled', 'failed') THEN now()
                      ELSE completed_at
                    END
                WHERE id = %s
                RETURNING *
                """,
                (
                    status.value,
                    status.value,
                    status.value,
                    session_id,
                ),
            )
            session = _session_from_row(row)

            if status == SessionStatus.RUNNING:
                self._execute(
                    conn,
                    """
                    UPDATE branches
                    SET status = 'running', failure_reason = NULL
                    WHERE session_id = %s AND status IN ('pending', 'paused')
                    """,
                    (session_id,),
                )
            elif status == SessionStatus.PAUSED:
                self._execute(
                    conn,
                    """
                    UPDATE branches
                    SET status = 'paused'
                    WHERE session_id = %s AND status = 'running'
                    """,
                    (session_id,),
                )

            payload = {"status": status.value}
            try:
                binding = self._get_runtime_loop_binding(conn, session_id)
            except NotFoundError:
                binding = None
            if binding:
                payload.update(
                    {
                        "loop_id": binding.loop_id,
                        "root_branch_id": binding.root_branch_id,
                    }
                )
            pending_events.append(
                self._insert_event(
                    conn,
                    session_id=session_id,
                    event_type=event_type,
                    payload=payload,
                )
            )

        self._publish_inserted_events(pending_events)
        return session

    def list_branches(self, session_id: str) -> list[Branch]:
        with self._connect() as conn:
            self._get_session(conn, session_id)
            return self._list_branches(conn, session_id)

    def get_branch(self, branch_id: str) -> Branch:
        with self._connect() as conn:
            return self._get_branch(conn, branch_id)

    def continue_branch(self, branch_id: str) -> Branch:
        pending_events: list[InsertedEvent] = []
        with self._connect() as conn:
            branch = self._get_branch(conn, branch_id)
            self._validate_branch_transition(branch.status, BranchStatus.RUNNING)
            row = self._fetch_one(
                conn,
                """
                UPDATE branches
                SET status = 'running', failure_reason = NULL
                WHERE id = %s
                RETURNING *
                """,
                (branch_id,),
            )
            branch = _branch_from_row(row)
            pending_events.append(
                self._insert_event(
                    conn,
                    session_id=branch.session_id,
                    branch_id=branch.id,
                    event_type="branch_continue_requested",
                    payload={"query": branch.query},
                )
            )
        self._publish_inserted_events(pending_events)
        return branch

    def split_branch(
        self,
        branch_id: str,
        branch_payloads: list[BranchCreate],
    ) -> list[Branch]:
        pending_events: list[InsertedEvent] = []
        with self._connect() as conn:
            parent = self._get_branch(conn, branch_id)
            if parent.status in {BranchStatus.PRUNED, BranchStatus.COMPLETED}:
                raise ConflictError(f"Cannot split a {parent.status.value} branch")
            children: list[Branch] = []
            for payload in branch_payloads:
                row = self._fetch_one(
                    conn,
                    """
                    INSERT INTO branches (
                      id, session_id, parent_branch_id, query, label, rationale,
                      mode, status, depth
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        new_uuid_str(),
                        parent.session_id,
                        parent.id,
                        payload.query,
                        payload.label,
                        payload.rationale,
                        payload.mode.value,
                        BranchStatus.PENDING.value,
                        parent.depth + 1,
                    ),
                )
                children.append(_branch_from_row(row))
            pending_events.append(
                self._insert_event(
                    conn,
                    session_id=parent.session_id,
                    branch_id=parent.id,
                    event_type="branch_split",
                    payload={"child_branch_ids": [child.id for child in children]},
                )
            )
        self._publish_inserted_events(pending_events)
        return children

    def prune_branch(self, branch_id: str) -> Branch:
        pending_events: list[InsertedEvent] = []
        with self._connect() as conn:
            branch = self._get_branch(conn, branch_id)
            self._validate_branch_transition(branch.status, BranchStatus.PRUNED)
            row = self._fetch_one(
                conn,
                """
                UPDATE branches
                SET status = 'pruned',
                    prune_reason = COALESCE(prune_reason, 'Pruned through API request.')
                WHERE id = %s
                RETURNING *
                """,
                (branch_id,),
            )
            branch = _branch_from_row(row)
            pending_events.append(
                self._insert_event(
                    conn,
                    session_id=branch.session_id,
                    branch_id=branch.id,
                    event_type="branch_pruned",
                    payload={"query": branch.query},
                )
            )
        self._publish_inserted_events(pending_events)
        return branch

    def update_branch(self, branch_id: str, payload: BranchPatch) -> Branch:
        pending_events: list[InsertedEvent] = []
        with self._connect() as conn:
            branch = self._get_branch(conn, branch_id)
            update = payload.model_dump(exclude_unset=True)
            if "status" in update:
                self._validate_branch_transition(branch.status, update["status"])
            if not update:
                return branch
            allowed = {
                "query",
                "label",
                "rationale",
                "status",
                "prune_reason",
                "failure_reason",
            }
            assignments = []
            values = []
            for field_name, value in update.items():
                if field_name not in allowed:
                    continue
                assignments.append(f"{field_name} = %s")
                values.append(value.value if hasattr(value, "value") else value)
            values.append(branch_id)
            row = self._fetch_one(
                conn,
                f"""
                UPDATE branches
                SET {", ".join(assignments)}
                WHERE id = %s
                RETURNING *
                """,
                tuple(values),
            )
            branch = _branch_from_row(row)
            pending_events.append(
                self._insert_event(
                    conn,
                    session_id=branch.session_id,
                    branch_id=branch.id,
                    event_type="branch_updated",
                    payload=payload.model_dump(exclude_unset=True, mode="json"),
                )
            )
        self._publish_inserted_events(pending_events)
        return branch

    def list_papers(self, session_id: str) -> list[SessionPaperView]:
        with self._connect() as conn:
            self._get_session(conn, session_id)
            return self._list_papers(conn, session_id)

    def get_paper(self, paper_id: str) -> Paper:
        with self._connect() as conn:
            row = self._get_paper_row(conn, paper_id)
            return _paper_from_row(row)

    def extract_claims(
        self,
        session_id: str,
        payload: ClaimExtractionRequest,
    ) -> list[Claim]:
        pending_events: list[InsertedEvent] = []
        with self._connect() as conn:
            self._get_session(conn, session_id)
            if payload.branch_id:
                branch = self._get_branch(conn, payload.branch_id)
                if branch.session_id != session_id:
                    raise NotFoundError("Branch not found")
            stored_paper_id = None
            if payload.paper_id:
                stored_paper_id = self._ensure_paper_in_session(
                    conn,
                    payload.paper_id,
                    session_id,
                )

            extracted = self._claim_extractor.extract(
                payload.source_text,
                max_claims=payload.max_claims,
            )
            claims: list[Claim] = []
            for draft in extracted:
                row = self._fetch_one(
                    conn,
                    """
                    INSERT INTO claims (
                      id, session_id, branch_id, paper_id, summary_id,
                      claim_text, claim_type, status, confidence, created_by
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        new_uuid_str(),
                        session_id,
                        payload.branch_id,
                        stored_paper_id,
                        payload.summary_id,
                        draft.text,
                        ClaimType(draft.claim_type).value,
                        ClaimStatus(draft.status).value,
                        draft.confidence,
                        payload.created_by,
                    ),
                )
                claims.append(_claim_from_row(row))

            pending_events.append(
                self._insert_event(
                    conn,
                    session_id=session_id,
                    branch_id=payload.branch_id,
                    paper_id=stored_paper_id,
                    event_type="claims_extracted",
                    payload={
                        "claim_ids": [claim.id for claim in claims],
                        "claim_count": len(claims),
                        "created_by": payload.created_by,
                        "summary_id": payload.summary_id,
                    },
                )
            )
        self._publish_inserted_events(pending_events)
        return claims

    def list_claims(self, session_id: str) -> list[Claim]:
        with self._connect() as conn:
            self._get_session(conn, session_id)
            return self._list_claims(conn, session_id)

    def get_claim(self, claim_id: str) -> Claim:
        with self._connect() as conn:
            return self._get_claim(conn, claim_id)

    def validate_claim(
        self,
        claim_id: str,
        payload: ClaimValidationRequest,
    ) -> ClaimValidationResult:
        pending_events: list[InsertedEvent] = []
        with self._connect() as conn:
            claim = self._get_claim(conn, claim_id)
            evidence_items: list[ClaimEvidence] = []
            for evidence_payload in payload.evidence:
                stored_paper_id = None
                if evidence_payload.paper_id:
                    stored_paper_id = self._ensure_paper_in_session(
                        conn,
                        evidence_payload.paper_id,
                        claim.session_id,
                    )
                row = self._fetch_one(
                    conn,
                    """
                    INSERT INTO claim_evidence (
                      id, claim_id, source_type, paper_id, chunk_id, locator,
                      metadata_field, upload_id, document_id, external_uri,
                      source_id, reviewer_id, evidence_text, relation, score,
                      page_start, page_end, section_title
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *, %s::uuid AS session_id
                    """,
                    (
                        new_uuid_str(),
                        claim.id,
                        evidence_payload.source_type.value,
                        stored_paper_id,
                        evidence_payload.chunk_id,
                        _jsonb(_locator_payload(evidence_payload, stored_paper_id)),
                        evidence_payload.metadata_field,
                        evidence_payload.upload_id,
                        evidence_payload.document_id,
                        evidence_payload.external_uri,
                        evidence_payload.source_id,
                        evidence_payload.reviewer_id,
                        evidence_payload.evidence_text,
                        evidence_payload.relation.value,
                        evidence_payload.score,
                        evidence_payload.page_start,
                        evidence_payload.page_end,
                        evidence_payload.section_title,
                        claim.session_id,
                    ),
                )
                evidence_items.append(_claim_evidence_from_row(row))

            decision = self._claim_verifier.decide(
                [
                    EvidenceInput(
                        relation=evidence.relation.value,
                        score=evidence.score,
                    )
                    for evidence in evidence_items
                ]
            )
            row = self._fetch_one(
                conn,
                """
                UPDATE claims
                SET status = %s, confidence = %s
                WHERE id = %s
                RETURNING *
                """,
                (decision.status, decision.confidence, claim.id),
            )
            claim = _claim_from_row(row)
            pending_events.append(
                self._insert_event(
                    conn,
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
            )
        self._publish_inserted_events(pending_events)
        return ClaimValidationResult(claim=claim, evidence=evidence_items)

    def list_claim_evidence(self, claim_id: str) -> list[ClaimEvidence]:
        with self._connect() as conn:
            claim = self._get_claim(conn, claim_id)
            return self._list_claim_evidence(conn, claim.id, claim.session_id)

    def list_events(self, session_id: str) -> list[Event]:
        with self._connect() as conn:
            self._get_session(conn, session_id)
            return self._list_events(conn, session_id)

    def subscribe_events(
        self,
        session_id: str,
        replay_existing: bool = True,
    ) -> EventSubscription:
        with self._connect() as conn:
            self._get_session(conn, session_id)
            replay_events = self._list_events(conn, session_id) if replay_existing else []
        queue: Queue[Event] = Queue()
        with self._lock:
            self._event_subscribers.setdefault(session_id, []).append(queue)
        return EventSubscription(
            session_id=session_id,
            replay_events=replay_events,
            queue=queue,
        )

    def unsubscribe_events(self, subscription: EventSubscription) -> None:
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

    def _connect(self) -> ContextManager[Any]:
        if self._connection_factory is not None:
            return self._connection_factory()
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Postgres backend requires psycopg. Run dependency installation "
                "before using ERLA_REPOSITORY_BACKEND=postgres."
            ) from exc
        return psycopg.connect(self._dsn, row_factory=dict_row)

    def _execute(self, conn: Any, sql: str, params: tuple = ()) -> None:
        with conn.cursor() as cur:
            cur.execute(sql, params)

    def _fetch_one(self, conn: Any, sql: str, params: tuple = ()) -> dict:
        row = self._fetch_optional(conn, sql, params)
        if row is None:
            raise NotFoundError("Record not found")
        return row

    def _fetch_optional(self, conn: Any, sql: str, params: tuple = ()) -> dict | None:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def _fetch_all(self, conn: Any, sql: str, params: tuple = ()) -> list[dict]:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    def _get_session(self, conn: Any, session_id: str) -> ResearchSession:
        row = self._fetch_optional(
            conn,
            "SELECT * FROM research_sessions WHERE id = %s",
            (session_id,),
        )
        if row is None:
            raise NotFoundError("Session not found")
        return _session_from_row(row)

    def _get_runtime_loop_binding(
        self,
        conn: Any,
        session_id: str,
    ) -> RuntimeLoopBinding:
        row = self._fetch_optional(
            conn,
            "SELECT * FROM runtime_loop_bindings WHERE session_id = %s",
            (session_id,),
        )
        if row is None:
            raise NotFoundError("Runtime loop not found")
        return _runtime_loop_binding_from_row(row)

    def _get_branch(self, conn: Any, branch_id: str) -> Branch:
        row = self._fetch_optional(conn, "SELECT * FROM branches WHERE id = %s", (branch_id,))
        if row is None:
            raise NotFoundError("Branch not found")
        return _branch_from_row(row)

    def _list_branches(self, conn: Any, session_id: str) -> list[Branch]:
        rows = self._fetch_all(
            conn,
            "SELECT * FROM branches WHERE session_id = %s ORDER BY created_at",
            (session_id,),
        )
        return [_branch_from_row(row) for row in rows]

    def _get_paper_row(self, conn: Any, paper_id: str) -> dict:
        row = self._fetch_optional(
            conn,
            """
            SELECT * FROM papers
            WHERE id::text = %s
               OR semantic_scholar_id = %s
               OR arxiv_id = %s
               OR doi = %s
               OR openalex_id = %s
            """,
            (paper_id, paper_id, paper_id, paper_id, paper_id),
        )
        if row is None:
            raise NotFoundError("Paper not found")
        return row

    def _ensure_paper_in_session(
        self,
        conn: Any,
        paper_id: str,
        session_id: str,
    ) -> str:
        paper = self._get_paper_row(conn, paper_id)
        found = self._fetch_optional(
            conn,
            """
            SELECT 1 FROM session_papers
            WHERE session_id = %s AND paper_id = %s
            """,
            (session_id, paper["id"]),
        )
        if found is None:
            raise NotFoundError("Paper not found")
        return str(paper["id"])

    def _list_papers(self, conn: Any, session_id: str) -> list[SessionPaperView]:
        rows = self._fetch_all(
            conn,
            """
            SELECT
              sp.id AS session_paper_id,
              sp.session_id,
              sp.branch_id,
              sp.paper_id,
              sp.discovery_method,
              sp.selection_reason,
              sp.selected,
              sp.iteration_number,
              sp.created_at AS session_paper_created_at,
              p.*
            FROM session_papers sp
            JOIN papers p ON p.id = sp.paper_id
            WHERE sp.session_id = %s
            ORDER BY sp.created_at
            """,
            (session_id,),
        )
        return [_session_paper_view_from_row(row) for row in rows]

    def _list_summaries(self, conn: Any, session_id: str) -> list[Summary]:
        rows = self._fetch_all(
            conn,
            "SELECT * FROM summaries WHERE session_id = %s ORDER BY created_at",
            (session_id,),
        )
        return [_summary_from_row(row) for row in rows]

    def _get_claim(self, conn: Any, claim_id: str) -> Claim:
        row = self._fetch_optional(conn, "SELECT * FROM claims WHERE id = %s", (claim_id,))
        if row is None:
            raise NotFoundError("Claim not found")
        return _claim_from_row(row)

    def _list_claims(self, conn: Any, session_id: str) -> list[Claim]:
        rows = self._fetch_all(
            conn,
            "SELECT * FROM claims WHERE session_id = %s ORDER BY created_at",
            (session_id,),
        )
        return [_claim_from_row(row) for row in rows]

    def _list_claim_evidence(
        self,
        conn: Any,
        claim_id: str,
        session_id: str,
    ) -> list[ClaimEvidence]:
        rows = self._fetch_all(
            conn,
            """
            SELECT ce.*, %s::uuid AS session_id
            FROM claim_evidence ce
            WHERE ce.claim_id = %s
            ORDER BY ce.created_at
            """,
            (session_id, claim_id),
        )
        return [_claim_evidence_from_row(row) for row in rows]

    def _list_claim_evidence_for_session(
        self,
        conn: Any,
        session_id: str,
    ) -> list[ClaimEvidence]:
        rows = self._fetch_all(
            conn,
            """
            SELECT ce.*, c.session_id
            FROM claim_evidence ce
            JOIN claims c ON c.id = ce.claim_id
            WHERE c.session_id = %s
            ORDER BY ce.created_at
            """,
            (session_id,),
        )
        return [_claim_evidence_from_row(row) for row in rows]

    def _list_events(self, conn: Any, session_id: str) -> list[Event]:
        rows = self._fetch_all(
            conn,
            "SELECT * FROM events WHERE session_id = %s ORDER BY created_at",
            (session_id,),
        )
        return [_event_from_row(row) for row in rows]

    def _insert_event(
        self,
        conn: Any,
        *,
        session_id: str,
        event_type: str,
        payload: dict,
        branch_id: str | None = None,
        paper_id: str | None = None,
        severity: str = "info",
    ) -> InsertedEvent:
        row = self._fetch_one(
            conn,
            """
            INSERT INTO events (
              id, session_id, branch_id, paper_id, event_type, severity, payload
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                new_uuid_str(),
                session_id,
                branch_id,
                paper_id,
                event_type,
                severity,
                _jsonb(payload),
            ),
        )
        event = _event_from_row(row)
        with self._lock:
            queues = list(self._event_subscribers.get(session_id, []))
        return InsertedEvent(event=event, queues=queues)

    def _publish_inserted_events(self, inserted_events: list[InsertedEvent]) -> None:
        for inserted in inserted_events:
            for queue in inserted.queues:
                queue.put_nowait(inserted.event)

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


def _project_from_row(row: dict) -> Project:
    return Project(
        id=str(row["id"]),
        title=row["title"],
        description=row.get("description"),
        field=row.get("field"),
        settings=dict(row.get("settings") or {}),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _session_from_row(row: dict) -> ResearchSession:
    return ResearchSession(
        id=str(row["id"]),
        project_id=str(row["project_id"]) if row.get("project_id") else None,
        initial_query=row["initial_query"],
        source_providers=list(row.get("source_providers") or []),
        filters=dict(row.get("filters") or {}),
        parameters=dict(row.get("parameters") or {}),
        status=SessionStatus(row["status"]),
        failure_reason=row.get("failure_reason"),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _branch_from_row(row: dict) -> Branch:
    return Branch(
        id=str(row["id"]),
        session_id=str(row["session_id"]),
        parent_branch_id=str(row["parent_branch_id"]) if row.get("parent_branch_id") else None,
        query=row["query"],
        label=row.get("label"),
        rationale=row.get("rationale"),
        mode=row["mode"],
        status=BranchStatus(row["status"]),
        prune_reason=row.get("prune_reason"),
        failure_reason=row.get("failure_reason"),
        depth=row.get("depth") or 0,
        context_tokens_used=row.get("context_tokens_used") or 0,
        max_context_tokens=row.get("max_context_tokens"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _runtime_loop_binding_from_row(row: dict) -> RuntimeLoopBinding:
    return RuntimeLoopBinding(
        session_id=str(row["session_id"]),
        loop_id=row["loop_id"],
        loop_number=row["loop_number"],
        root_branch_id=str(row["root_branch_id"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _paper_from_row(row: dict) -> Paper:
    return Paper(
        id=str(row["id"]),
        canonical_key=row.get("canonical_key") or "",
        semantic_scholar_id=row.get("semantic_scholar_id"),
        arxiv_id=row.get("arxiv_id"),
        doi=row.get("doi"),
        openalex_id=row.get("openalex_id"),
        title=row["title"],
        abstract=row.get("abstract"),
        authors=[],
        year=row.get("year"),
        venue=row.get("venue"),
        citation_count=row.get("citation_count"),
        reference_count=row.get("reference_count"),
        influential_citation_count=row.get("influential_citation_count"),
        url=row.get("url"),
        pdf_url=row.get("pdf_url"),
        open_access_pdf_url=row.get("open_access_pdf_url"),
        metadata=dict(row.get("metadata") or {}),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _session_paper_view_from_row(row: dict) -> SessionPaperView:
    paper = _paper_from_row(row)
    return SessionPaperView(
        id=str(row["session_paper_id"]),
        session_id=str(row["session_id"]),
        branch_id=str(row["branch_id"]) if row.get("branch_id") else None,
        paper_id=str(row["paper_id"]),
        discovery_method=row.get("discovery_method"),
        selection_reason=row.get("selection_reason"),
        selected=row.get("selected") or False,
        iteration_number=row.get("iteration_number"),
        paper=paper,
        created_at=row["session_paper_created_at"],
    )


def _summary_from_row(row: dict) -> Summary:
    provenance = _generation_provenance_from_row(row)
    return Summary(
        id=str(row["id"]),
        session_id=str(row["session_id"]),
        branch_id=str(row["branch_id"]) if row.get("branch_id") else None,
        paper_id=str(row["paper_id"]) if row.get("paper_id") else None,
        summary_type=row["summary_type"],
        text=row["text"],
        groundedness_score=row.get("groundedness_score"),
        validation_status=row["validation_status"],
        validation_details=dict(row.get("validation_details") or {}),
        generation_provenance=provenance,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _claim_from_row(row: dict) -> Claim:
    return Claim(
        id=str(row["id"]),
        session_id=str(row["session_id"]),
        branch_id=str(row["branch_id"]) if row.get("branch_id") else None,
        paper_id=str(row["paper_id"]) if row.get("paper_id") else None,
        summary_id=str(row["summary_id"]) if row.get("summary_id") else None,
        claim_text=row["claim_text"],
        claim_type=ClaimType(row["claim_type"]),
        status=ClaimStatus(row["status"]),
        confidence=row.get("confidence"),
        created_by=row.get("created_by"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _claim_evidence_from_row(row: dict) -> ClaimEvidence:
    return ClaimEvidence(
        id=str(row["id"]),
        claim_id=str(row["claim_id"]),
        session_id=str(row["session_id"]),
        source_type=row["source_type"],
        paper_id=str(row["paper_id"]) if row.get("paper_id") else None,
        chunk_id=str(row["chunk_id"]) if row.get("chunk_id") else None,
        metadata_field=row.get("metadata_field"),
        upload_id=row.get("upload_id"),
        document_id=row.get("document_id"),
        external_uri=row.get("external_uri"),
        source_id=row.get("source_id"),
        reviewer_id=row.get("reviewer_id"),
        evidence_text=row["evidence_text"],
        relation=row["relation"],
        score=row.get("score"),
        page_start=row.get("page_start"),
        page_end=row.get("page_end"),
        section_title=row.get("section_title"),
        created_at=row["created_at"],
    )


def _event_from_row(row: dict) -> Event:
    return Event(
        id=str(row["id"]),
        session_id=str(row["session_id"]),
        branch_id=str(row["branch_id"]) if row.get("branch_id") else None,
        paper_id=str(row["paper_id"]) if row.get("paper_id") else None,
        event_type=row["event_type"],
        payload=dict(row.get("payload") or {}),
        severity=row["severity"],
        created_at=row["created_at"],
    )


def _generation_provenance_from_row(row: dict):
    if not row.get("provider") or not row.get("model") or not row.get("prompt_name"):
        return None
    from ..domain.provenance import (
        GenerationCost,
        GenerationProvenance,
        TokenUsage,
    )

    token_usage = row.get("token_usage") or {}
    cost = row.get("cost") or {}
    return GenerationProvenance(
        provider=row["provider"],
        model=row["model"],
        prompt_name=row["prompt_name"],
        prompt_version=row.get("prompt_version") or "v1",
        temperature=row.get("temperature"),
        max_tokens=row.get("max_tokens"),
        token_usage=TokenUsage(**token_usage) if token_usage else None,
        cost=GenerationCost(**cost) if cost.get("amount") is not None else None,
        provider_request_id=row.get("provider_request_id"),
        generation_parameters=dict(row.get("generation_parameters") or {}),
        generated_at=row.get("generated_at") or utc_now(),
    )


def _locator_payload(evidence_payload: Any, stored_paper_id: str | None) -> dict:
    return {
        "source_type": evidence_payload.source_type.value,
        "paper_id": stored_paper_id,
        "chunk_id": evidence_payload.chunk_id,
        "metadata_field": evidence_payload.metadata_field,
        "upload_id": evidence_payload.upload_id,
        "document_id": evidence_payload.document_id,
        "external_uri": evidence_payload.external_uri,
        "source_id": evidence_payload.source_id,
        "reviewer_id": evidence_payload.reviewer_id,
        "page_start": evidence_payload.page_start,
        "page_end": evidence_payload.page_end,
        "section_title": evidence_payload.section_title,
    }
