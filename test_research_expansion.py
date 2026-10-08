"""Growing a session's paper network along citations, outside the research lifecycle."""

import asyncio

import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.api.models import Paper, SessionCreate, SessionStatus
from src.api.repository import ConflictError, InMemoryRepository, utc_now
from src.jobs.research_worker import ResearchWorker
from src.research.expansion import Lead, choose_leads, merge_leads
from src.research.models import PaperResult, stable_id
from src.research.pipeline import ResearchPipeline
from test_research_scouts import reader
from test_research_worker import postgres_dsn, repo  # noqa: F401  (shared fixtures)

QUESTION = "gravitational wave lensing"


def paper(key, title, *, refs=(), abstract=None, year=2024, citations=10):
    return Paper(
        id=stable_id("expansion-fixture", key),
        canonical_key=f"openalex:{key.lower()}",
        openalex_id=key,
        title=title,
        abstract=abstract,
        year=year,
        citation_count=citations,
        metadata={"provider": "openalex", "references": list(refs)},
        created_at=utc_now(),
        updated_at=utc_now(),
    )


# The session read S1 and S2; both cite F (a foundation) and X (off-topic).
SEEDS = [
    paper("S1", "Strong lensing of gravitational waves", refs=["F", "X", "S2"]),
    paper("S2", "Wave optics in gravitational wave lensing", refs=["F", "X", "Y"]),
]
WORKS = {
    "F": paper("F", "Gravitational lenses", year=1992, citations=900),
    "X": paper("X", "Numerical recipes", year=1986, citations=5000),
    "Y": paper("Y", "Lensed gravitational wave detection rates", year=2018),
}
CITERS = [
    paper("C1", "Microlensing of gravitational waves by subhalos", refs=["S1", "S2"], year=2026),
    paper("C2", "A survey of dark energy", refs=["S1"], year=2025),
]


class FakeOpenAlex:
    def __init__(self):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def works(self, ids):
        self.calls.append(("works", tuple(sorted(ids))))
        return [WORKS[i] for i in ids if i in WORKS]

    async def citing(self, ids, *, limit, sort):
        self.calls.append(("citing", sort))
        return list(CITERS)

    async def search(self, query, *, limit, filters=None):
        self.calls.append(("search", query))
        return [paper("Q1", "Gravitational wave lensing beyond general relativity")]


def test_leads_rank_by_relevance_and_connection():
    leads = [
        Lead(WORKS["F"], "reference", cited_by=2),
        Lead(WORKS["X"], "reference", cited_by=2),
        Lead(CITERS[0], "citation", cites=3),
        Lead(CITERS[1], "citation", cites=1),
    ]

    chosen = asyncio.run(choose_leads(leads, question=QUESTION, topic=QUESTION, want=10))
    assert [lead.paper.openalex_id for lead in chosen] == ["C1", "F"]
    assert chosen[0].reason() == "Cites 3 papers in this session"
    assert chosen[1].reason() == "Cited by 2 papers in this session"
    # A paper cited by three session papers is a foundation even off-topic.
    foundation = Lead(WORKS["X"], "reference", cited_by=3)
    assert asyncio.run(choose_leads([foundation], question=QUESTION, topic=QUESTION, want=5))


def test_merging_prefers_citation_evidence_and_skips_known_papers():
    searched = Lead(WORKS["F"], "query_search", query="q")
    referenced = Lead(WORKS["F"], "reference", cited_by=2)
    known = Lead(SEEDS[0], "citation")
    merged = merge_leads(
        [searched, referenced, known],
        known_keys={SEEDS[0].canonical_key},
        known_titles=set(),
    )
    assert [(lead.paper.openalex_id, lead.method) for lead in merged] == [("F", "reference")]


def start(repo):
    session = repo.create_session(
        SessionCreate(
            initial_query=QUESTION,
            source_providers=["openalex"],
            parameters={"research": {"max_papers": 2, "max_depth": 0, "synthesize": False}},
        )
    )
    repo.set_session_status(session.id, SessionStatus.RUNNING, "session_started")
    return session


async def search(name, query, filters, limits):
    return list(SEEDS)


async def no_text(_paper):
    return [], None


def pipeline(repo, client=None):
    return ResearchPipeline(
        repo, search=search, full_text=no_text, expansion_client=lambda: client or FakeOpenAlex()
    )


async def test_expansion_adds_connected_papers_to_a_finished_session(repo):
    session = start(repo)
    await ResearchWorker(repo, pipeline(repo)).run_once()
    assert reader(repo).get_session(session.id).status == SessionStatus.COMPLETED

    job = repo.request_network_expansion(session.id, 50)
    assert repo.request_network_expansion(session.id, 100).id == job.id
    client = FakeOpenAlex()
    done = await ResearchWorker(repo, pipeline(repo, client)).run_once()
    assert done.id == job.id and done.status.value == "succeeded"
    assert done.result["added"] == 4

    store = reader(repo)
    assert store.get_session(session.id).status == SessionStatus.COMPLETED
    found = {p.paper.title: p for p in store.list_discovered_papers(session.id)}
    assert set(found) == {
        "Gravitational lenses",
        "Lensed gravitational wave detection rates",
        "Microlensing of gravitational waves by subhalos",
        "Gravitational wave lensing beyond general relativity",
    }
    assert found["Gravitational lenses"].discovery_method == "reference"
    assert found["Gravitational lenses"].selection_reason == "Cited by 2 papers in this session"
    assert found["Microlensing of gravitational waves by subhalos"].discovery_method == "citation"
    # Read papers are unchanged.
    assert {p.paper.title for p in store.list_papers(session.id)} == {s.title for s in SEEDS}
    (decision,) = [d for d in store.get_session_snapshot(session.id).decisions if d.details.get("expansion")]
    assert decision.details["added"] == 4
    assert ("citing", "publication_date:desc") in client.calls
    # A new expansion can be requested once the last one finished.
    assert repo.request_network_expansion(session.id, 50).id != job.id


async def test_research_finishing_ignores_a_queued_expansion(repo):
    session = start(repo)
    worker = ResearchWorker(repo, pipeline(repo))
    leased = repo.lease_next_job(worker.worker_id)
    repo.save_research_paper(leased, PaperResult(paper=SEEDS[0]))
    expansion = repo.request_network_expansion(session.id, 20)
    repo.finish_research(leased)
    # The session finishes on its research jobs; the expansion still runs afterwards.
    assert reader(repo).get_session(session.id).status == SessionStatus.COMPLETED
    done = await worker.run_once()
    assert done.id == expansion.id and done.status.value == "succeeded"


def test_expansion_needs_a_started_session_with_papers(repo):
    session = repo.create_session(SessionCreate(initial_query=QUESTION))
    with pytest.raises(ConflictError):
        repo.request_network_expansion(session.id, 50)
    repo.set_session_status(session.id, SessionStatus.RUNNING, "session_started")
    with pytest.raises(ConflictError):
        repo.request_network_expansion(session.id, 50)


def test_expand_route_validates_size_and_state():
    client = TestClient(create_app(InMemoryRepository()))
    session = client.post("/sessions", json={"initial_query": QUESTION}).json()
    assert client.post(f"/sessions/{session['id']}/expand", json={"papers": 500}).status_code == 422
    assert client.post(f"/sessions/{session['id']}/expand", json={"papers": 50}).status_code == 409


def test_expand_route_returns_the_queued_job(repo):
    session = start(repo)
    leased = repo.lease_next_job("worker")
    repo.save_research_paper(leased, PaperResult(paper=SEEDS[0]))
    repo.finish_research(leased)
    client = TestClient(create_app(repo))
    response = client.post(f"/sessions/{session.id}/expand", json={"papers": 100})
    assert response.status_code == 200
    assert response.json()["job_type"] == "network_expansion"
    assert response.json()["payload"] == {"papers": 100}
