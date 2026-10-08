"""Transactional, fenced research writes for Postgres."""

from ..research.models import PaperChunk, PaperResult, stable_id
from .models import Branch, Job, JobType

ACTIVE_JOBS = "status IN ('queued','running','paused')"


class PostgresResearchWrites:
    def _research_lease(self, conn, leased: Job) -> Job:
        from ..research.lease import check_lease
        from .postgres_repository import _job_from_row

        # Same lock order as pause/cancel: session first, then job.
        session = self._fetch_one(
            conn,
            "SELECT status FROM research_sessions WHERE id = %s FOR NO KEY UPDATE",
            (leased.session_id,),
        )
        job = _job_from_row(
            self._fetch_one(
                conn, "SELECT * FROM jobs WHERE id = %s FOR UPDATE", (leased.id,)
            )
        )
        check_lease(job, leased, session["status"])
        return job

    def heartbeat_research(self, leased: Job, progress: dict | None = None) -> Job:
        from .postgres_repository import _jsonb, _job_from_row

        events = []
        with self._connect() as conn:
            self._research_lease(conn, leased)
            row = self._fetch_one(
                conn,
                "UPDATE jobs SET locked_at = now(), result = result || %s WHERE id = %s RETURNING *",
                (_jsonb(progress or {}), leased.id),
            )
            if progress:
                events.append(
                    self._insert_event(
                        conn,
                        session_id=leased.session_id,
                        branch_id=leased.branch_id,
                        event_type="research_progress",
                        payload={"job_id": leased.id, **progress},
                    )
                )
        self._publish_inserted_events(events)
        return _job_from_row(row)

    def save_research_paper(self, leased: Job, result: PaperResult) -> str:
        from .postgres_repository import _jsonb

        events = []
        paper = result.paper
        with self._connect() as conn:
            self._research_lease(conn, leased)
            row = self._fetch_one(
                conn,
                """
                INSERT INTO papers (id, canonical_key, title, abstract, semantic_scholar_id, arxiv_id, doi,
                    openalex_id, year, venue, citation_count, url, open_access_pdf_url, metadata)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (canonical_key) DO UPDATE SET title=EXCLUDED.title,
                    abstract=COALESCE(EXCLUDED.abstract,papers.abstract), metadata=papers.metadata || EXCLUDED.metadata,
                    open_access_pdf_url=COALESCE(EXCLUDED.open_access_pdf_url,papers.open_access_pdf_url)
                RETURNING id
            """,
                (
                    paper.id,
                    paper.canonical_key,
                    paper.title,
                    paper.abstract,
                    paper.semantic_scholar_id,
                    paper.arxiv_id,
                    paper.doi,
                    paper.openalex_id,
                    paper.year,
                    paper.venue,
                    paper.citation_count,
                    paper.url,
                    paper.open_access_pdf_url,
                    _jsonb({**paper.metadata, "authors": paper.authors}),
                ),
            )
            paper_id = str(row["id"])
            for index, author in enumerate(paper.authors):
                self._execute(
                    conn,
                    """INSERT INTO paper_authors(id,paper_id,name,author_id,position)
                    VALUES (%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING""",
                    (
                        stable_id(paper_id, "author", str(index)),
                        paper_id,
                        author.get("name") or "Unknown",
                        author.get("author_id"),
                        index,
                    ),
                )
            self._execute(
                conn,
                """INSERT INTO session_papers(id,session_id,branch_id,paper_id,selected,discovery_method,selection_reason)
                VALUES (%s,%s,%s,%s,true,'query_search',%s) ON CONFLICT(id) DO NOTHING""",
                (
                    stable_id(leased.session_id, leased.branch_id or "", paper_id),
                    leased.session_id,
                    leased.branch_id,
                    paper_id,
                    "Selected from provider relevance ranking within the session paper limit.",
                ),
            )
            document_id = stable_id(paper_id, result.source_url or "abstract")
            self._execute(
                conn,
                """INSERT INTO paper_documents(id,paper_id,source_type,storage_uri,parse_status,parser_name,raw_text)
                VALUES (%s,%s,%s,%s,%s,'pymupdf',%s) ON CONFLICT(id) DO UPDATE SET
                parse_status=EXCLUDED.parse_status, raw_text=EXCLUDED.raw_text""",
                (
                    document_id,
                    paper_id,
                    "pdf" if result.chunks else "abstract",
                    result.source_url,
                    result.parse_status,
                    "\n\n".join(c.text for c in result.chunks) or paper.abstract,
                ),
            )
            for chunk in result.chunks:
                self._execute(
                    conn,
                    """INSERT INTO paper_chunks(id,paper_id,document_id,chunk_index,text,page_start,page_end,section_title)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING""",
                    (
                        chunk.id,
                        paper_id,
                        document_id,
                        chunk.chunk_index,
                        chunk.text,
                        chunk.page_start,
                        chunk.page_end,
                        chunk.section_title,
                    ),
                )
            if result.synthesis:
                summary_id = stable_id(leased.id, paper_id, "summary")
                provenance = result.provenance
                self._execute(
                    conn,
                    """INSERT INTO summaries(id,session_id,branch_id,paper_id,summary_type,text,validation_status,
                    provider,model,prompt_name,prompt_version,token_usage,generation_parameters)
                    VALUES (%s,%s,%s,%s,'paper',%s,'not_validated',%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING""",
                    (
                        summary_id,
                        leased.session_id,
                        leased.branch_id,
                        paper_id,
                        result.synthesis.summary,
                        provenance.get("provider"),
                        provenance.get("model"),
                        provenance.get("prompt_name"),
                        provenance.get("prompt_version"),
                        _jsonb(provenance.get("token_usage") or {}),
                        _jsonb(
                            {
                                "source_note": result.source_note,
                                "parse_status": result.parse_status,
                            }
                        ),
                    ),
                )
                for draft in result.synthesis.claims:
                    self._execute(
                        conn,
                        """INSERT INTO claims(id,session_id,branch_id,paper_id,summary_id,claim_text,claim_type,status,created_by)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'research_worker_v1') ON CONFLICT(id) DO NOTHING""",
                        (
                            stable_id(summary_id, draft.text),
                            leased.session_id,
                            leased.branch_id,
                            paper_id,
                            summary_id,
                            draft.text,
                            draft.claim_type.value,
                            "speculative"
                            if draft.claim_type.value == "hypothesis"
                            else "needs_review",
                        ),
                    )
            events.append(
                self._insert_event(
                    conn,
                    session_id=leased.session_id,
                    branch_id=leased.branch_id,
                    paper_id=paper_id,
                    event_type="paper_processed"
                    if result.synthesis
                    else "paper_discovered",
                    payload={
                        "title": paper.title,
                        "parse_status": result.parse_status,
                        "source_note": result.source_note,
                    },
                )
            )
        self._publish_inserted_events(events)
        return paper_id

    def list_paper_chunks(self, paper_id: str) -> list[PaperChunk]:
        with self._connect() as conn:
            paper = self._get_paper_row(conn, paper_id)
            rows = self._fetch_all(
                conn,
                "SELECT * FROM paper_chunks WHERE paper_id=%s ORDER BY document_id,chunk_index",
                (paper["id"],),
            )
        return [
            PaperChunk(
                **{
                    **row,
                    "id": str(row["id"]),
                    "paper_id": str(row["paper_id"]),
                    "document_id": str(row["document_id"]),
                }
            )
            for row in rows
        ]

    def validate_research_claim(self, leased, claim_id, payload):
        with self._connect() as conn:
            self._research_lease(conn, leased)
            return self.validate_claim(claim_id, payload)

    def reserve_model_call(
        self, leased: Job, *, limit: int, reserved: int = 0, job_limit: int | None = None
    ) -> str | None:
        """Count one model call against the session, or say which limit is spent.

        The session row lock taken by the lease check serializes concurrent branches.
        """

        from .postgres_repository import _jsonb

        with self._connect() as conn:
            job = self._research_lease(conn, leased)
            used = self._fetch_one(
                conn,
                "SELECT COALESCE(sum((result->>'model_calls')::int),0) AS used FROM jobs WHERE session_id=%s",
                (leased.session_id,),
            )["used"]
            mine = job.result.get("model_calls", 0)
            if used >= limit - reserved:
                return "session"
            if job_limit is not None and mine >= job_limit:
                return "branch"
            self._execute(
                conn,
                "UPDATE jobs SET locked_at=now(), result = result || %s WHERE id=%s",
                (_jsonb({"model_calls": mine + 1}), leased.id),
            )
            return None

    def record_research_decision(self, leased: Job, decision, *, max_branches: int) -> list[Branch]:
        """Store a decision and open its Scout branches with their jobs, once."""

        from .postgres_repository import _branch_from_row, _jsonb

        events = []
        with self._connect() as conn:
            self._research_lease(conn, leased)
            prior = self._fetch_optional(
                conn, "SELECT details FROM agent_decisions WHERE id=%s", (decision.id,)
            )
            if prior:
                ids = prior["details"].get("child_branch_ids", [])
                rows = self._fetch_all(
                    conn, "SELECT * FROM branches WHERE id = ANY(%s::uuid[])", (ids,)
                ) if ids else []
                return [_branch_from_row(row) for row in rows]
            existing = self._fetch_one(
                conn,
                "SELECT count(*) AS n FROM branches WHERE session_id=%s AND depth > 0",
                (leased.session_id,),
            )["n"]
            keep = decision.children[: max(0, max_branches - existing)]
            alternatives = list(decision.alternatives) + [
                {"query": c.query, "reason": "The session's branch limit was reached."}
                for c in decision.children[len(keep):]
            ]
            parent_depth = 0
            if decision.branch_id:
                parent_depth = self._fetch_one(
                    conn, "SELECT depth FROM branches WHERE id=%s", (decision.branch_id,)
                )["depth"]
            created = []
            for child in keep:
                row = self._fetch_one(
                    conn,
                    """INSERT INTO branches(id,session_id,parent_branch_id,query,label,rationale,mode,status,depth)
                    VALUES (%s,%s,%s,%s,%s,%s,'search_summarize','running',%s) RETURNING *""",
                    (
                        child.id,
                        leased.session_id,
                        decision.branch_id,
                        child.query,
                        child.label,
                        child.rationale,
                        parent_depth + 1,
                    ),
                )
                branch = _branch_from_row(row)
                created.append(branch)
                events.append(
                    self._insert_event(
                        conn,
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
                )
                _, event = self._insert_job(
                    conn,
                    session_id=leased.session_id,
                    branch_id=branch.id,
                    job_type=JobType.BRANCH_CONTINUE,
                    payload={"query": branch.query, "origin": "scout"},
                )
                events.append(event)
            text = (
                decision.decision
                if created or not decision.children
                else "No follow-up branches were opened."
            )
            details = {**decision.details, "child_branch_ids": [b.id for b in created]}
            self._insert_decision(conn, leased.session_id, decision, text, alternatives, details)
            events.append(
                self._insert_event(
                    conn,
                    session_id=leased.session_id,
                    branch_id=decision.branch_id,
                    event_type="agent_decision",
                    payload={
                        "decision_id": decision.id,
                        "decision_type": decision.decision_type,
                        "message": text,
                        "child_branch_ids": details["child_branch_ids"],
                    },
                )
            )
        self._publish_inserted_events(events)
        return created

    def _insert_decision(self, conn, session_id, decision, text, alternatives, details):
        from .postgres_repository import _jsonb

        provenance = decision.provenance or {}
        self._execute(
            conn,
            """INSERT INTO agent_decisions(id,session_id,branch_id,decision_type,input_summary,decision,
            rationale,alternatives,details,provider,model,prompt_name,prompt_version,token_usage,
            provider_request_id,generated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,CASE WHEN %s THEN now() END)
            ON CONFLICT(id) DO NOTHING""",
            (
                decision.id,
                session_id,
                decision.branch_id,
                decision.decision_type,
                decision.input_summary,
                text,
                decision.rationale,
                _jsonb(alternatives),
                _jsonb(details),
                provenance.get("provider"),
                provenance.get("model"),
                provenance.get("prompt_name"),
                provenance.get("prompt_version"),
                _jsonb(provenance.get("token_usage") or {}),
                provenance.get("provider_request_id"),
                bool(provenance),
            ),
        )

    def save_session_synthesis(self, leased: Job, record) -> None:
        """Store the session overview, kept hypotheses and their decision, once."""

        from .postgres_repository import _jsonb

        events = []
        provenance = record.provenance or {}
        with self._connect() as conn:
            self._research_lease(conn, leased)
            if self._fetch_optional(
                conn, "SELECT 1 FROM summaries WHERE id=%s", (record.summary_id,)
            ):
                return
            self._execute(
                conn,
                """INSERT INTO summaries(id,session_id,summary_type,text,validation_status,provider,model,
                prompt_name,prompt_version,token_usage,provider_request_id,generated_at)
                VALUES (%s,%s,'session',%s,'not_validated',%s,%s,%s,%s,%s,%s,now())""",
                (
                    record.summary_id,
                    leased.session_id,
                    record.overview,
                    provenance.get("provider"),
                    provenance.get("model"),
                    provenance.get("prompt_name"),
                    provenance.get("prompt_version"),
                    _jsonb(provenance.get("token_usage") or {}),
                    provenance.get("provider_request_id"),
                ),
            )
            for item in record.hypotheses:
                self._execute(
                    conn,
                    """INSERT INTO hypotheses(id,session_id,text,rationale,testability,risk_level,status,
                    provider,model,prompt_name,prompt_version,token_usage,provider_request_id,generated_at,
                    missing_evidence,next_steps)
                    VALUES (%s,%s,%s,%s,%s,%s,'draft',%s,%s,%s,%s,%s,%s,now(),%s,%s)""",
                    (
                        item.id,
                        leased.session_id,
                        item.text,
                        item.rationale,
                        item.testability,
                        item.risk,
                        provenance.get("provider"),
                        provenance.get("model"),
                        provenance.get("prompt_name"),
                        provenance.get("prompt_version"),
                        _jsonb(provenance.get("token_usage") or {}),
                        provenance.get("provider_request_id"),
                        _jsonb(item.missing_evidence),
                        _jsonb(item.next_steps),
                    ),
                )
                claim_papers = {
                    str(row["id"]): row["paper_id"]
                    for row in self._fetch_all(
                        conn,
                        "SELECT id, paper_id FROM claims WHERE id = ANY(%s::uuid[])",
                        (item.supporting_claim_ids + item.contradicting_claim_ids,),
                    )
                }
                links = [(c, "supports") for c in item.supporting_claim_ids] + [
                    (c, "contradicts") for c in item.contradicting_claim_ids
                ]
                for claim_id, relation in links:
                    self._execute(
                        conn,
                        """INSERT INTO hypothesis_support(id,hypothesis_id,claim_id,paper_id,relation)
                        VALUES (%s,%s,%s,%s,%s)""",
                        (
                            stable_id(item.id, relation, claim_id),
                            item.id,
                            claim_id,
                            claim_papers.get(claim_id),
                            relation,
                        ),
                    )
            decision = record.decision
            self._insert_decision(
                conn,
                leased.session_id,
                decision,
                decision.decision,
                decision.alternatives,
                decision.details,
            )
            events.append(
                self._insert_event(
                    conn,
                    session_id=leased.session_id,
                    event_type="session_synthesized",
                    payload={
                        "summary_id": record.summary_id,
                        "hypothesis_count": len(record.hypotheses),
                        "message": decision.decision,
                    },
                )
            )
        self._publish_inserted_events(events)

    def finish_research(self, leased: Job, *, then_synthesize: bool = False) -> Job:
        from .postgres_repository import _job_from_row

        events = []
        with self._connect() as conn:
            self._research_lease(conn, leased)
            self._execute(
                conn,
                "UPDATE branches SET status='completed' WHERE id=%s AND status='running'",
                (leased.branch_id,),
            )
            row = self._fetch_one(
                conn,
                """UPDATE jobs SET status='succeeded',locked_by=NULL,locked_at=NULL,completed_at=now()
                WHERE id=%s RETURNING *""",
                (leased.id,),
            )
            events.append(
                self._insert_event(
                    conn,
                    session_id=leased.session_id,
                    event_type="job_completed",
                    payload={"job_id": leased.id, "job_type": leased.job_type.value},
                )
            )
            active = self._fetch_optional(
                conn,
                f"SELECT id FROM jobs WHERE session_id=%s AND {ACTIVE_JOBS} LIMIT 1",
                (leased.session_id,),
            )
            synthesis = self._fetch_optional(
                conn,
                "SELECT id FROM jobs WHERE session_id=%s AND job_type='session_synthesis'",
                (leased.session_id,),
            )
            if not active and then_synthesize and not synthesis:
                # The last branch hands the session to one synthesis job.
                _, event = self._insert_job(
                    conn,
                    session_id=leased.session_id,
                    branch_id=None,
                    job_type=JobType.SESSION_SYNTHESIS,
                    payload={},
                )
                events.append(event)
            elif not active:
                self._execute(
                    conn,
                    "UPDATE research_sessions SET status='completed',completed_at=now() WHERE id=%s",
                    (leased.session_id,),
                )
                events.append(
                    self._insert_event(
                        conn,
                        session_id=leased.session_id,
                        event_type="session_completed",
                        payload={},
                    )
                )
        self._publish_inserted_events(events)
        return _job_from_row(row)

    def fail_research(self, leased: Job, error: str, retryable: bool = True) -> Job:
        with self._connect() as conn:
            current = self._research_lease(conn, leased)
            job, event = self._fail_job(
                conn, current, error=error, retryable=retryable, retry_delay_seconds=10
            )
        self._publish_inserted_events([event])
        return job
