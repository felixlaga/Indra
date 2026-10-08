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
    assert response.status_code == 202
    from src.jobs.view_worker import ViewWorker
    ViewWorker(client.app.state.repository).run_once()
    response = client.get("/sessions/" + session["id"] + "/map")
    assert response.status_code == 200
    assert response.json()["nodes"] == []


def test_discovered_papers_join_the_map_without_counting_as_read():
    read = make_paper("paper-a", "Lensed gravitational waves", 2024, 10, "", "S2-A")
    found = make_paper(
        "paper-b",
        "Wave optics of lensed gravitational waves",
        2025,
        3,
        "",
        "S2-B",
        {"references": [{"paperId": "S2-A"}]},
    )
    snapshot = SimpleNamespace(
        session=SimpleNamespace(id="session-1"),
        papers=[make_entry(read, "branch-root", True)],
        branches=[SimpleNamespace(id="branch-root", label="Root", query="lensing")],
        summaries=[],
        claims=[],
    )
    discovered = [
        SimpleNamespace(
            paper=found, branch_id="branch-root", selected=False, selection_reason="Found"
        ),
        # A discovered copy of a paper that was read elsewhere stays a read node.
        SimpleNamespace(paper=read, branch_id="branch-other", selected=False),
    ]
    result = ResearchMapBuilder().build(snapshot, discovered)
    nodes = {node.paper_id: node for node in result.nodes}
    assert nodes["paper-a"].read and not nodes["paper-b"].read
    assert nodes["paper-b"].selection_reason == "Found"
    assert [(e.source_paper_id, e.target_paper_id) for e in result.edges if e.observed] == [
        ("paper-b", "paper-a")
    ]
    assert result.overview.paper_count == 1
    assert result.overview.discovered_paper_count == 1


def test_field_insight_finds_citation_themes_foundations_and_frontier():
    from src.maps.insight import field_insight
    from src.maps.models import ResearchMapEdge, ResearchMapNode

    def node(pid, year, citations=0):
        return ResearchMapNode(
            paper_id=pid, title=pid, year=year, cluster_id="c", role="established",
            citation_count=citations,
        )

    def cites(source, target):
        return ResearchMapEdge(
            id=f"cites:{source}:{target}", source_paper_id=source, target_paper_id=target,
            edge_type="cites", observed=True, provenance="test",
        )

    nodes = [node("a1", 2010, 500), node("a2", 2024), node("a3", 2025), node("a4", 2026)]
    nodes += [node("b1", 2005, 90), node("b2", 2008), node("b3", 2012), node("lone", 2026)]
    edges = [cites(x, "a1") for x in ("a2", "a3", "a4")] + [cites("a4", "a3")]
    edges += [cites("b2", "b1"), cites("b3", "b1"), cites("b3", "b2")]
    texts = {n: "wave optics microlensing" for n in ("a1", "a2", "a3", "a4")}
    texts |= {n: "hubble constant sirens" for n in ("b1", "b2", "b3")}

    insight = field_insight(nodes, edges, texts)
    lensing, sirens = insight.themes
    assert sorted(lensing.paper_ids) == ["a1", "a2", "a3", "a4"] and lensing.emerging
    assert sorted(sirens.paper_ids) == ["b1", "b2", "b3"] and not sirens.emerging
    assert "microlensing" in lensing.keywords and "hubble" in sirens.keywords
    assert lensing.key_paper_id == "a1"
    assert insight.foundation_ids == ["a1", "b1"]
    assert insight.frontier_ids == ["a4", "a3"]
    by_id = {n.paper_id: n for n in nodes}
    assert by_id["a1"].in_network_citations == 3 and by_id["a4"].cites_in_network == 2
    assert by_id["lone"].theme_id is None
    assert "cited by 3 papers here" in insight.summary
