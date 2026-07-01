"""Tests for Phase 8 research artifact exports."""

import csv
from io import StringIO
import json

from fastapi.testclient import TestClient

from src.api import create_app
from src.api.models import Paper, SessionPaper
from src.api.repository import InMemoryRepository, utc_now


FORMATS = {
    "bibtex": "erla-bibliography.bib",
    "ris": "erla-bibliography.ris",
    "report-markdown": "erla-research-report.md",
    "literature-review-latex": "erla-literature-review.tex",
    "annotated-bibliography": "erla-annotated-bibliography.md",
    "claim-ledger-csv": "erla-claim-ledger.csv",
    "claim-ledger-json": "erla-claim-ledger.json",
    "research-map-json": "erla-research-map.json",
}


def seed_session(client: TestClient, repository: InMemoryRepository):
    session = client.post(
        "/sessions",
        json={"initial_query": "evidence-backed research exports"},
    ).json()
    branch = client.get(f"/sessions/{session['id']}/branches").json()[0]
    now = utc_now()
    paper = Paper(
        id="paper-export",
        canonical_key="doi:10.1000/export",
        doi="10.1000/export",
        title="Evidence-Backed Research Exports",
        abstract="The study evaluates evidence-backed research exports.",
        authors=[{"name": "Ada Researcher"}],
        year=2026,
        venue="Research Systems",
        citation_count=4,
        metadata={},
        created_at=now,
        updated_at=now,
    )
    repository._papers[paper.id] = paper
    session_paper = SessionPaper(
        id="session-paper-export",
        session_id=session["id"],
        branch_id=branch["id"],
        paper_id=paper.id,
        discovery_method="query_search",
        selection_reason="Directly relevant to export validation",
        selected=True,
        iteration_number=1,
        created_at=now,
    )
    repository._session_papers[session_paper.id] = session_paper
    claims = client.post(
        f"/sessions/{session['id']}/claims/extract",
        json={
            "paper_id": paper.id,
            "branch_id": branch["id"],
            "source_text": (
                "The study evaluates evidence-backed research exports. "
                "This approach may improve future literature reviews."
            ),
        },
    ).json()
    factual = next(claim for claim in claims if claim["status"] != "speculative")
    validated = client.post(
        f"/claims/{factual['id']}/validate/auto",
        json={"top_k": 3, "min_score": 0.15},
    )
    assert validated.status_code == 200
    return session, paper, claims


def test_export_catalog_lists_every_roadmap_artifact():
    repository = InMemoryRepository()
    client = TestClient(create_app(repository))
    session = client.post("/sessions", json={"initial_query": "catalog"}).json()

    response = client.get(f"/sessions/{session['id']}/exports")

    assert response.status_code == 200
    artifacts = response.json()["artifacts"]
    assert {artifact["format"] for artifact in artifacts} == set(FORMATS)
    assert all(artifact["preserves_validation_status"] for artifact in artifacts)


def test_every_export_downloads_with_attachment_and_validation_header():
    repository = InMemoryRepository()
    client = TestClient(create_app(repository))
    session, _, _ = seed_session(client, repository)

    for format_name, filename in FORMATS.items():
        response = client.get(f"/sessions/{session['id']}/exports/{format_name}")
        assert response.status_code == 200, format_name
        assert filename in response.headers["content-disposition"]
        assert response.headers["x-indra-validation-preserved"] == "true"
        assert response.text.strip(), format_name


def test_claim_exports_preserve_status_and_unsupported_labels():
    repository = InMemoryRepository()
    client = TestClient(create_app(repository))
    session, _, claims = seed_session(client, repository)
    speculative = next(claim for claim in claims if claim["status"] == "speculative")

    csv_response = client.get(
        f"/sessions/{session['id']}/exports/claim-ledger-csv"
    )
    rows = list(csv.DictReader(StringIO(csv_response.text)))
    row_by_id = {row["claim_id"]: row for row in rows}
    assert row_by_id[speculative["id"]]["status"] == "speculative"
    assert row_by_id[speculative["id"]]["supported_for_synthesis"] == "False"

    json_response = client.get(
        f"/sessions/{session['id']}/exports/claim-ledger-json"
    )
    payload = json_response.json()
    claim_by_id = {claim["id"]: claim for claim in payload["claims"]}
    assert claim_by_id[speculative["id"]]["status"] == "speculative"
    assert claim_by_id[speculative["id"]]["supported_for_synthesis"] is False

    report = client.get(
        f"/sessions/{session['id']}/exports/report-markdown"
    ).text
    assert "[SPECULATIVE]" in report
    assert "Unsupported" in report


def test_bibliography_and_map_exports_are_parseable():
    repository = InMemoryRepository()
    client = TestClient(create_app(repository))
    session, paper, _ = seed_session(client, repository)

    bibtex = client.get(f"/sessions/{session['id']}/exports/bibtex").text
    assert "@article{" in bibtex
    assert paper.title in bibtex
    assert paper.doi in bibtex

    ris = client.get(f"/sessions/{session['id']}/exports/ris").text
    assert "TY  - JOUR" in ris
    assert "ER  -" in ris

    research_map = client.get(
        f"/sessions/{session['id']}/exports/research-map-json"
    ).json()
    assert research_map["session_id"] == session["id"]
    assert research_map["nodes"][0]["paper_id"] == paper.id


def test_unknown_export_format_returns_404():
    repository = InMemoryRepository()
    client = TestClient(create_app(repository))
    session = client.post("/sessions", json={"initial_query": "unknown"}).json()

    response = client.get(f"/sessions/{session['id']}/exports/not-a-format")

    assert response.status_code == 404
