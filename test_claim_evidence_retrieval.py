"""Tests for Phase 5 claim-level evidence retrieval and inspection."""

from fastapi.testclient import TestClient

from src.api import create_app
from src.api.models import Paper, SessionPaper
from src.api.repository import InMemoryRepository, utc_now
from src.claims import EvidenceCandidate, EvidenceRetriever


def _seed_paper(
    repository: InMemoryRepository,
    *,
    session_id: str,
    branch_id: str,
    paper_id: str,
    title: str,
    abstract: str,
) -> Paper:
    now = utc_now()
    paper = Paper(
        id=paper_id,
        canonical_key=f"test:{paper_id}",
        title=title,
        abstract=abstract,
        authors=[{"name": "A. Researcher"}],
        year=2026,
        venue="Evidence Systems",
        citation_count=4,
        metadata={},
        created_at=now,
        updated_at=now,
    )
    repository._papers[paper.id] = paper
    session_paper = SessionPaper(
        id=f"session-{paper_id}",
        session_id=session_id,
        branch_id=branch_id,
        paper_id=paper.id,
        discovery_method="query_search",
        selection_reason="Test evidence source",
        selected=True,
        iteration_number=1,
        created_at=now,
    )
    repository._session_papers[session_paper.id] = session_paper
    return paper


def test_retriever_supports_and_contradicts_only_with_strong_overlap():
    retriever = EvidenceRetriever()
    support = retriever.retrieve(
        "The paper introduces a retrieval method for evidence navigation.",
        [
            EvidenceCandidate(
                source_type="paper_abstract",
                paper_id="paper-1",
                evidence_text=(
                    "The paper introduces a retrieval method for evidence navigation."
                ),
            )
        ],
    )
    assert support[0].relation == "supports"
    assert support[0].score == 1.0

    contradiction = retriever.retrieve(
        "The method does not improve accuracy.",
        [
            EvidenceCandidate(
                source_type="paper_abstract",
                paper_id="paper-2",
                evidence_text="The method does improve accuracy.",
            )
        ],
    )
    assert contradiction[0].relation == "contradicts"


def test_retriever_discards_unrelated_passages():
    evidence = EvidenceRetriever().retrieve(
        "The model improves gravitational-wave parameter estimation.",
        [
            EvidenceCandidate(
                source_type="paper_abstract",
                paper_id="paper-1",
                evidence_text="We study crop yields under changing rainfall patterns.",
            )
        ],
    )
    assert evidence == []


def test_auto_validation_stores_evidence_and_exposes_trace():
    repository = InMemoryRepository()
    client = TestClient(create_app(repository))
    session = client.post(
        "/sessions",
        json={"initial_query": "evidence-grounded research navigation"},
    ).json()
    branch = client.get(f"/sessions/{session['id']}/branches").json()[0]
    paper = _seed_paper(
        repository,
        session_id=session["id"],
        branch_id=branch["id"],
        paper_id="paper-support",
        title="Evidence-Grounded Research Navigation",
        abstract=(
            "The paper introduces a retrieval method for evidence navigation. "
            "The method is evaluated on scientific literature datasets."
        ),
    )
    claim = client.post(
        f"/sessions/{session['id']}/claims/extract",
        json={
            "paper_id": paper.id,
            "branch_id": branch["id"],
            "source_text": (
                "The paper introduces a retrieval method for evidence navigation."
            ),
        },
    ).json()[0]

    response = client.post(
        f"/claims/{claim['id']}/validate/auto",
        json={"top_k": 3, "min_score": 0.15},
    )

    assert response.status_code == 200
    result = response.json()
    inspection = result["inspection"]
    assert inspection["claim"]["status"] == "supported"
    assert result["candidates_considered"] >= 4
    assert result["evidence_retrieved"] >= 1
    assert inspection["evidence"][0]["source_type"] == "paper_abstract"
    assert inspection["evidence"][0]["relation"] == "supports"
    assert inspection["validations"][0]["validator_type"] == "claim_evidence"
    assert inspection["paper"]["id"] == paper.id

    read_response = client.get(f"/claims/{claim['id']}/inspection")
    assert read_response.status_code == 200
    assert read_response.json()["validations"][0]["evidence_ids"]


def test_auto_validation_marks_missing_evidence_not_found():
    repository = InMemoryRepository()
    client = TestClient(create_app(repository))
    session = client.post(
        "/sessions",
        json={"initial_query": "unsupported claim handling"},
    ).json()
    branch = client.get(f"/sessions/{session['id']}/branches").json()[0]
    paper = _seed_paper(
        repository,
        session_id=session["id"],
        branch_id=branch["id"],
        paper_id="paper-unrelated",
        title="Agricultural Rainfall Models",
        abstract="We study crop yields under changing rainfall patterns.",
    )
    claim = client.post(
        f"/sessions/{session['id']}/claims/extract",
        json={
            "paper_id": paper.id,
            "source_text": "The model proves a theorem about quantum gravity.",
        },
    ).json()[0]

    response = client.post(f"/claims/{claim['id']}/validate/auto", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["inspection"]["claim"]["status"] == "not_found"
    assert result["evidence_retrieved"] == 0
    assert result["inspection"]["evidence"] == []


def test_speculative_claims_are_not_auto_promoted():
    repository = InMemoryRepository()
    client = TestClient(create_app(repository))
    session = client.post(
        "/sessions",
        json={"initial_query": "speculative claim policy"},
    ).json()
    claim = client.post(
        f"/sessions/{session['id']}/claims/extract",
        json={"source_text": "This method may improve future research navigation."},
    ).json()[0]
    assert claim["status"] == "speculative"

    response = client.post(f"/claims/{claim['id']}/validate/auto", json={})

    assert response.status_code == 409
    assert "not automatically promoted" in response.json()["detail"]
