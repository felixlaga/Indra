"""Transactional, fenced research writes for Postgres."""

from ..research.models import PaperChunk, PaperResult, stable_id
from .models import Job


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

    def finish_research(self, leased: Job) -> Job:
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
                "SELECT id FROM jobs WHERE session_id=%s AND status IN ('queued','running','paused') LIMIT 1",
                (leased.session_id,),
            )
            if not active:
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
