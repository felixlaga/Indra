"""Focused tests for the Phase 6 research-map builder and route."""

from types import SimpleNamespace

from src.maps import ResearchMapBuilder


def make_paper(paper_id, title, year, citations, abstract="", semantic_id=None, metadata=None):
    return SimpleNamespace(
        id=paper_id,
        canonical_key="test:" + paper_id,
        semantic_scholar_id=semantic_id,
        arxiv_id=None,
        doi=None,
        openalex_id=None,
        title=title,
        abstract=abstract,
        year=year,
        venue="Test venue",
        citation_count=citations,
        influential_citation_count=0,
        metadata=metadata or {},
    )


def make_entry(item, branch_id, selected=False):
    return SimpleNamespace(paper=item, branch_id=branch_id, selected=selected)


def test_map_builds_observed_citation_timeline_and_roles():
    first = make_paper(
        "paper-a",
        "Foundations of Evidence Retrieval",
        2015,
        120,
        "Evidence retrieval for scientific literature navigation.",
        "S2-A",
    )
    second = make_paper(
        "paper-b",
        "Modern Evidence Retrieval Systems",
        2025,
        8,
        "Modern evidence retrieval systems for scientific literature.",
        "S2-B",
        {"references": [{"paperId": "S2-A"}]},
    )
    third = make_paper(
        "paper-c",
        "Claim Validation in Research Assistants",
        2026,
        1,
        "Claim validation and evidence retrieval in research assistants.",
    )
    root = SimpleNamespace(id="branch-root", label="Root", query="evidence systems")
    validation = SimpleNamespace(id="branch-validation", label="Validation", query="claim validation")
    snapshot = SimpleNamespace(
        session=SimpleNamespace(id="session-1"),
        papers=[
            make_entry(first, "branch-root", True),
            make_entry(second, "branch-root"),
            make_entry(third, "branch-validation"),
        ],
        branches=[root, validation],
        summaries=[],
        claims=[],
    )

    result = ResearchMapBuilder().build(snapshot)

    assert [bucket.year for bucket in result.timeline] == [2015, 2025, 2026]
    observed = [edge for edge in result.edges if edge.observed]
    assert len(observed) == 1
    assert observed[0].source_paper_id == "paper-b"
    assert observed[0].target_paper_id == "paper-a"
    roles = {node.paper_id: node.role for node in result.nodes}
    assert roles["paper-a"] == "foundational_candidate"
    assert roles["paper-c"] == "recent"


def test_similarity_is_labelled_related_not_citation():
    first = make_paper("paper-a", "Wave Optics Lensing", 2024, 4, "Wave optics gravitational lensing interference.")
    second = make_paper("paper-b", "Gravitational Lensing in Wave Optics", 2025, 2, "Gravitational lensing interference in the wave optics regime.")
    branch = SimpleNamespace(id="branch-root", label="Lensing", query="wave optics")
    snapshot = SimpleNamespace(
        session=SimpleNamespace(id="session-1"),
        papers=[make_entry(first, "branch-root"), make_entry(second, "branch-root")],
        branches=[branch],
        summaries=[],
        claims=[],
    )

    result = ResearchMapBuilder().build(snapshot)

    inferred = [edge for edge in result.edges if not edge.observed]
    assert inferred
    assert all(edge.edge_type == "related" for edge in inferred)
    assert result.overview.observed_citation_edge_count == 0


def test_branch_synthesis_uses_grounded_claims():
    item = make_paper("paper-a", "Evidence Systems", 2025, 2)
    branch = SimpleNamespace(id="branch-root", label="Evidence", query="evidence")
    supported = SimpleNamespace(
        id="claim-1",
        branch_id="branch-root",
        status="supported",
        claim_text="The paper evaluates an evidence retrieval system.",
    )
    snapshot = SimpleNamespace(
        session=SimpleNamespace(id="session-1"),
        papers=[make_entry(item, "branch-root")],
        branches=[branch],
        summaries=[],
        claims=[supported],
    )

    synthesis = ResearchMapBuilder().build(snapshot).branch_syntheses[0]

    assert synthesis.source == "validated_claims"
    assert synthesis.claim_ids == ["claim-1"]


def test_empty_session_map_endpoint():
    from fastapi.testclient import TestClient
    from src.api import create_app
    from src.api.repository import InMemoryRepository

    client = TestClient(create_app(InMemoryRepository()))
    session = client.post("/sessions", json={"initial_query": "empty research map"}).json()

    response = client.get("/sessions/" + session["id"] + "/map")

    assert response.status_code == 200
    assert response.json()["nodes"] == []
