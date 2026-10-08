"""End-to-end worker contracts, shared by memory and real Postgres backends."""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from src.api.migrate import migrate
from src.api.models import (
    ClaimValidationRequest,
    ClaimEvidenceCreate,
    Paper,
    SessionCreate,
    SessionStatus,
)
from src.api.postgres_repository import PostgresRepository
from src.api.repository import InMemoryRepository, utc_now
from src.jobs.research_worker import ResearchWorker
from src.research.lease import LeaseLost
from src.research.models import (
    PaperChunk,
    PaperResult,
    PaperSynthesis,
    ClaimDraft,
    stable_id,
)
from src.research.pipeline import ResearchPipeline


@pytest.fixture(scope="module")
def postgres_dsn():
    admin = os.getenv("INDRA_TEST_ADMIN_DSN")
    if not admin:
        pytest.skip(
            "Set INDRA_TEST_ADMIN_DSN to run isolated real-Postgres integration tests"
        )
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    name = "indra_test_" + uuid4().hex[:12]
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    values = conninfo_to_dict(admin)
    values["dbname"] = name
    dsn = make_conninfo(**values)
    try:
        migrate(dsn, without_vectors=os.getenv("INDRA_TEST_WITHOUT_VECTORS") == "1")
        migrate(dsn, without_vectors=os.getenv("INDRA_TEST_WITHOUT_VECTORS") == "1")
        yield dsn
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


@pytest.fixture(params=["memory", "postgres"])
def repo(request):
    if request.param == "memory":
        yield InMemoryRepository()
        return
    repository = PostgresRepository(request.getfixturevalue("postgres_dsn"))
    try:
        yield repository
    finally:
        with repository._connect() as conn:
            conn.execute("TRUNCATE research_sessions, papers CASCADE")


def start(repo, query="The method improves accuracy."):
    session = repo.create_session(
        SessionCreate(
            initial_query=query,
            source_providers=["arxiv"],
            parameters={"research": {"max_papers": 2, "max_claims": 1}},
        )
    )
    repo.set_session_status(session.id, SessionStatus.RUNNING, "session_started")
    return session


def paper(index=1):
    return Paper(
        id=stable_id("fixture", str(index)),
        canonical_key=f"arxiv:fixture-{index}",
        title=f"Test paper {index}",
        abstract="The method improves accuracy.",
        authors=[{"name": "Test Author"}],
        arxiv_id=f"fixture-{index}",
        year=2026,
        created_at=utc_now(),
        updated_at=utc_now(),
    )


async def source(*_):
    return [paper()]


async def text(p):
    return [
        PaperChunk(
            id=stable_id(p.id, "chunk"),
            paper_id=p.id,
            document_id=stable_id(p.id, "pdf"),
            chunk_index=0,
            text="The method improves accuracy.",
            page_start=2,
            page_end=2,
        )
    ], None


async def test_worker_persists_inspectable_results_and_completes(repo):
    session = start(repo)
    result = await ResearchWorker(
        repo, ResearchPipeline(repo, search=source, full_text=text)
    ).run_once()
    assert result.status.value == "succeeded"
    reader = (
        PostgresRepository(repo._dsn) if isinstance(repo, PostgresRepository) else repo
    )
    snapshot = reader.get_session_snapshot(session.id)
    assert snapshot.session.status.value == "completed"
    assert len(snapshot.papers) == len(snapshot.summaries) == len(snapshot.claims) == 1
    assert snapshot.papers[0].paper.authors[0]["name"] == "Test Author"
    assert snapshot.claims[0].status.value == "needs_review"
    assert snapshot.claims[0].confidence is None
    assert reader.list_paper_chunks(snapshot.papers[0].paper_id)[0].page_start == 2
    assert any(e.chunk_id and e.page_start == 2 for e in snapshot.claim_evidence)
    assert snapshot.summaries[0].generation_provenance["model"] == "source_excerpt"
    assert (
        await ResearchWorker(
            repo, ResearchPipeline(repo, search=source, full_text=text)
        ).run_once()
        is None
    )


def test_concurrent_start_requests_enqueue_one_job(repo):
    session = repo.create_session(SessionCreate(initial_query="Idempotent start"))
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(
            pool.map(
                lambda _: repo.set_session_status(
                    session.id, SessionStatus.RUNNING, "session_started"
                ),
                range(12),
            )
        )
    assert len(repo.list_jobs(session.id)) == 1


async def test_pause_resume_fences_old_attempt_and_reuses_results(repo):
    session = start(repo)
    leased = repo.lease_next_job("same-worker").model_copy(deep=True)
    result = PaperResult(
        paper=paper(),
        synthesis=PaperSynthesis(
            summary="Excerpt",
            claims=[
                ClaimDraft(text="The method improves accuracy.", claim_type="factual")
            ],
        ),
    )
    repo.save_research_paper(leased, result)
    repo.set_session_status(session.id, SessionStatus.PAUSED, "session_paused")
    with pytest.raises(LeaseLost):
        repo.save_research_paper(leased, result)
    repo.set_session_status(session.id, SessionStatus.RUNNING, "session_resumed")
    fresh = repo.lease_next_job("same-worker").model_copy(deep=True)
    assert fresh.id == leased.id and fresh.attempts == leased.attempts + 1
    with pytest.raises(LeaseLost):
        repo.finish_research(leased)
    repo.save_research_paper(fresh, result)
    snapshot = repo.get_session_snapshot(session.id)
    assert len(snapshot.papers) == len(snapshot.summaries) == len(snapshot.claims) == 1
    repo.finish_research(fresh)


async def test_cancel_interrupts_provider_without_writing_results(repo):
    session = start(repo)
    entered = asyncio.Event()
    cancelled = asyncio.Event()

    async def slow(*_):
        entered.set()
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    worker = ResearchWorker(
        repo, ResearchPipeline(repo, search=slow), heartbeat_seconds=0.02
    )
    task = asyncio.create_task(worker.run_once())
    await entered.wait()
    repo.set_session_status(session.id, SessionStatus.CANCELLED, "session_cancelled")
    job = await asyncio.wait_for(task, 2)
    assert job.status.value == "cancelled"
    assert cancelled.is_set()
    assert not repo.list_papers(session.id)


def test_claim_status_keeps_earlier_contradicting_evidence(repo):
    session = start(repo)
    leased = repo.lease_next_job("verifier").model_copy(deep=True)
    repo.save_research_paper(
        leased,
        PaperResult(
            paper=paper(),
            synthesis=PaperSynthesis(
                summary="Excerpt",
                claims=[
                    ClaimDraft(
                        text="The method improves accuracy.", claim_type="factual"
                    )
                ],
            ),
        ),
    )
    claim = repo.list_claims(session.id)[0]
    for relation in ["contradicts", "supports"]:
        repo.validate_claim(
            claim.id,
            ClaimValidationRequest(
                evidence=[
                    ClaimEvidenceCreate(
                        evidence_text="Manual review", relation=relation
                    )
                ]
            ),
        )
    assert repo.get_claim(claim.id).status.value == "contradicted"
    repo.finish_research(leased)


async def test_provider_failure_preserves_queued_retry(repo):
    session = start(repo)

    async def broken(*_):
        raise TimeoutError("provider offline")

    result = await ResearchWorker(
        repo, ResearchPipeline(repo, search=broken)
    ).run_once()
    assert result.status.value == "queued"
    assert "All selected search providers failed" in result.last_error
    assert any(
        e.event_type == "job_retry_scheduled" for e in repo.list_events(session.id)
    )
    repo.set_session_status(session.id, SessionStatus.CANCELLED, "session_cancelled")


async def test_no_model_uses_abstract_instead_of_pdf_front_matter(repo):
    session = start(repo)

    async def front_matter(p):
        return [
            PaperChunk(
                id=stable_id(p.id, "front"),
                paper_id=p.id,
                document_id=stable_id(p.id, "front-doc"),
                chunk_index=0,
                text="Permission is granted to reproduce this manuscript.",
                page_start=1,
                page_end=1,
            )
        ], None

    await ResearchWorker(
        repo, ResearchPipeline(repo, search=source, full_text=front_matter)
    ).run_once()
    claims = repo.list_claims(session.id)
    assert claims[0].claim_text == "The method improves accuracy."
    assert "Permission" not in repo.get_session_snapshot(session.id).summaries[0].text


async def test_empty_search_finishes_without_fabricating_papers(repo):
    session = start(repo)

    async def empty(*_):
        return []

    result = await ResearchWorker(repo, ResearchPipeline(repo, search=empty)).run_once()
    assert result.status.value == "succeeded"
    assert not repo.list_papers(session.id)
    assert not repo.list_claims(session.id)


async def test_failed_second_summary_preserves_first_and_retry_skips_it(repo):
    from src.research.models import PaperSynthesis

    session = start(repo)

    class Model:
        def __init__(self):
            self.summarized = []
            self.fail = True

        async def generate(self, schema, instruction, source_data):
            assert schema is PaperSynthesis
            title = source_data["title"]
            self.summarized.append(title)
            if title.endswith("2") and self.fail:
                raise RuntimeError("Temporary model failure")
            return PaperSynthesis(summary="Persisted summary", claims=[]), {}

    async def two(*_):
        return [paper(1), paper(2)]

    model = Model()
    worker = ResearchWorker(
        repo, ResearchPipeline(repo, model, search=two, full_text=text)
    )
    failed = await worker.run_once()
    assert failed.status.value == "queued"
    assert len(repo.get_session_snapshot(session.id).summaries) == 1
    model.fail = False
    if isinstance(repo, PostgresRepository):
        with repo._connect() as conn:
            conn.execute("UPDATE jobs SET run_at=now() WHERE id=%s", (failed.id,))
    else:
        repo._jobs[failed.id].run_at = utc_now()
    completed = await worker.run_once()
    assert completed.status.value == "succeeded"
    assert model.summarized.count("Test paper 1") == 1
    snapshot = repo.get_session_snapshot(session.id)
    assert len(snapshot.papers) == len(snapshot.summaries) == 2


async def test_sse_observes_another_process_and_resumes_after_restart(postgres_dsn):
    import socket
    import subprocess
    import sys
    import httpx

    repo = PostgresRepository(postgres_dsn)
    session = repo.create_session(
        SessionCreate(initial_query="Cross-process event test")
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = {
        **os.environ,
        "INDRA_REPOSITORY_BACKEND": "postgres",
        "INDRA_DATABASE_URL": postgres_dsn,
        "INDRA_API_KEY": "",
    }
    base = f"http://127.0.0.1:{port}"

    def launch():
        return subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "src.api.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    async def ready(client):
        for _ in range(100):
            try:
                if (await client.get(base + "/health")).status_code == 200:
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.05)
        raise AssertionError("Test API did not start")

    process = launch()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await ready(client)
            url = (
                base
                + f"/sessions/{session.id}/events/stream?replay=false&heartbeat_seconds=0.1"
            )
            async with client.stream("GET", url) as response:
                repo.set_session_status(
                    session.id, SessionStatus.RUNNING, "session_started"
                )
                async for line in response.aiter_lines():
                    if line.startswith("id: "):
                        cursor = line[4:]
                        break
            process.terminate()
            process.wait(timeout=10)
            repo.set_session_status(session.id, SessionStatus.PAUSED, "session_paused")
            expected = repo.list_events(session.id)[-1].id
            process = launch()
            await ready(client)
            observed = []
            async with client.stream(
                "GET", url, headers={"Last-Event-ID": cursor}
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("id: "):
                        observed.append(line[4:])
                        if line[4:] == expected:
                            break
            assert expected in observed and cursor not in observed
    finally:
        process.terminate()
        process.wait(timeout=10)


async def test_model_budget_also_limits_verification(repo):
    session = repo.create_session(
        SessionCreate(
            initial_query="Bound model spending",
            source_providers=["arxiv"],
            parameters={
                "research": {"max_papers": 1, "max_claims": 1, "max_model_calls": 1}
            },
        )
    )
    repo.set_session_status(session.id, SessionStatus.RUNNING, "session_started")

    class Model:
        calls = 0

        async def generate(self, *_):
            self.calls += 1
            return PaperSynthesis(
                summary="Summary",
                claims=[
                    ClaimDraft(
                        text="The method improves accuracy.", claim_type="factual"
                    )
                ],
            ), {}

    model = Model()
    result = await ResearchWorker(
        repo, ResearchPipeline(repo, model, search=source, full_text=text)
    ).run_once()
    assert model.calls == 1
    # Running out of budget finishes the session and leaves the rest for review.
    assert result.status.value == "succeeded"
    assert result.result["model_calls"] == 1
    assert result.result["verification_mode"] == "model_partial"
    assert "budget of 1 was reached" in result.result["message"]
    assert "1 claims were left for review" in result.result["message"]
    assert repo.get_session(session.id).status.value == "completed"
    claim = repo.list_claims(session.id)[0]
    assert claim.status.value == "needs_review"
    assert result.result["review_claim_ids"] == [claim.id]
    assert repo.list_claim_evidence(claim.id)


class ScriptedModel:
    """Return a synthesis first, then the given outcomes for later calls."""

    def __init__(self, *later):
        self.later, self.calls = list(later), 0

    async def generate(self, schema, *_):
        self.calls += 1
        if self.calls == 1:
            return PaperSynthesis(
                summary="Summary",
                claims=[
                    ClaimDraft(
                        text="The method improves accuracy.", claim_type="factual"
                    )
                ],
            ), {}
        outcome = self.later.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return schema.model_validate(outcome), {}


async def test_invalid_verification_answer_leaves_claim_for_review(repo):
    session = start(repo)
    model = ScriptedModel(
        {"relation": "supports", "quote": "invented quote", "rationale": "Made up."}
    )
    result = await ResearchWorker(
        repo, ResearchPipeline(repo, model, search=source, full_text=text)
    ).run_once()
    assert result.status.value == "succeeded"
    assert result.result["verification_mode"] == "model_partial"
    assert "Some model answers were invalid" in result.result["message"]
    claim = repo.list_claims(session.id)[0]
    assert claim.status.value == "needs_review"
    evidence = repo.list_claim_evidence(claim.id)
    assert evidence and all(e.relation.value == "mentions" for e in evidence)
    assert repo.get_session(session.id).status.value == "completed"


async def test_rate_limit_stops_model_use_and_completes(repo):
    from src.research.model import ModelRateLimited

    session = start(repo)
    model = ScriptedModel(ModelRateLimited("The provider's daily quota was reached"))
    result = await ResearchWorker(
        repo, ResearchPipeline(repo, model, search=source, full_text=text)
    ).run_once()
    assert result.status.value == "succeeded"
    assert result.result["model_stop_reason"] == "The provider's daily quota was reached"
    assert "daily quota was reached" in result.result["message"]
    assert repo.list_claims(session.id)[0].status.value == "needs_review"
    assert model.calls == 2


async def test_rate_limit_during_synthesis_keeps_a_labelled_excerpt(repo):
    from src.research.model import ModelRateLimited

    class Limited:
        calls = 0

        async def generate(self, *_):
            self.calls += 1
            raise ModelRateLimited("The provider's daily quota was reached")

    session = start(repo)
    model = Limited()
    result = await ResearchWorker(
        repo, ResearchPipeline(repo, model, search=source, full_text=text)
    ).run_once()
    assert result.status.value == "succeeded"
    assert model.calls == 1
    summary = repo.get_session_snapshot(session.id).summaries[0]
    assert summary.text.startswith("Source excerpt (not model-validated)")


async def test_nul_characters_from_pdfs_and_providers_are_stored_without_them(repo):
    session = start(repo)

    async def nul_source(*_):
        p = paper()
        p.abstract = "The method improves\x00 accuracy."
        return [p]

    async def nul_text(p):
        chunks, note = await text(p)
        chunks[0].text = "The method\x00 improves accuracy."
        return chunks, note

    result = await ResearchWorker(
        repo, ResearchPipeline(repo, search=nul_source, full_text=nul_text)
    ).run_once()
    assert result.status.value == "succeeded"
    stored = repo.get_session_snapshot(session.id)
    assert "\x00" not in stored.papers[0].paper.abstract
    assert "\x00" not in repo.list_paper_chunks(stored.papers[0].paper_id)[0].text
