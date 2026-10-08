"""Large sessions: compact snapshots, compression, and versioned view caches."""

import gzip

from fastapi.testclient import TestClient

from src.api import create_app
from src.api import view_repository
from src.api.models import ClaimEvidenceCreate, ClaimExtractionRequest, ClaimValidationRequest
from src.api.postgres_repository import PostgresRepository
from src.api.repository import InMemoryRepository
from src.api.view_routes import research_view
from src.jobs.view_worker import ViewWorker
from test_platform import session
from test_research_worker import postgres_dsn, repo  # noqa: F401  (shared fixtures)


def reader(repo):
    return PostgresRepository(repo._dsn) if isinstance(repo, PostgresRepository) else repo


def session_with_evidence():
    repo = InMemoryRepository()
    s = session(repo)
    claim = repo.extract_claims(
        s.id, ClaimExtractionRequest(source_text="The method improves accuracy on every benchmark.")
    )[0]
    repo.validate_claim(
        claim.id,
        ClaimValidationRequest(
            evidence=[
                ClaimEvidenceCreate(
                    evidence_text="A long passage. " * 200,
                    relation="supports",
                    reviewer_id="tester",
                )
            ]
        ),
    )
    return repo, s


def test_compact_snapshots_keep_only_what_the_dashboard_counts():
    repo, s = session_with_evidence()
    with TestClient(create_app(repo, run_memory_views=False)) as client:
        full = client.get(f"/sessions/{s.id}/state").json()
        compact = client.get(f"/sessions/{s.id}/state?compact=true").json()
    assert "evidence_text" in full["claim_evidence"][0]
    assert set(compact["claim_evidence"][0]) == {"id", "claim_id", "paper_id", "relation", "source_type"}
    assert compact["claims"] == full["claims"] and compact["event_cursor"] == full["event_cursor"]


def test_large_responses_are_compressed_for_clients_that_accept_gzip():
    repo, s = session_with_evidence()
    with TestClient(create_app(repo, run_memory_views=False)) as client:
        zipped = client.get(
            f"/sessions/{s.id}/state", headers={"Accept-Encoding": "gzip"}
        )
        plain = client.get(f"/sessions/{s.id}/state", headers={"Accept-Encoding": "identity"})
    assert zipped.headers["content-encoding"] == "gzip"
    assert "content-encoding" not in plain.headers
    assert zipped.json() == plain.json()
    assert len(gzip.compress(plain.content)) < len(plain.content) / 5


def test_views_cached_by_older_builders_are_rebuilt(repo, monkeypatch):
    s = session(repo)
    repo.request_views(s.id)
    ViewWorker(repo).run_once()
    stored = reader(repo)
    assert research_view(stored, s.id, "analysis").status_code == 200
    # A deployment that changes builder output must not serve the old cached result.
    monkeypatch.setattr(view_repository, "BUILDER_VERSION", view_repository.BUILDER_VERSION + 1)
    import src.jobs.view_worker as view_worker

    monkeypatch.setattr(view_worker, "BUILDER_VERSION", view_repository.BUILDER_VERSION)
    assert research_view(stored, s.id, "analysis").status_code == 202
    assert stored.request_views(s.id)["status"] == "queued"
    ViewWorker(repo).run_once()
    rebuilt = stored.request_views(s.id)
    assert rebuilt["status"] == "ready"
    assert rebuilt["result"]["builder_version"] == view_repository.BUILDER_VERSION
    assert research_view(stored, s.id, "analysis").status_code == 200
