"""OpenAlex search and citations, hybrid retrieval, and scanned-PDF handling."""

import httpx
import pymupdf
import pytest

from src.api.models import SessionCreate, SessionStatus
from src.claims import EvidenceCandidate, EvidenceRetriever
from src.claims.embeddings import LocalEmbedder, embedder_from_environment
from src.jobs.research_worker import ResearchWorker
from src.maps.builder import ResearchMapBuilder
from src.research import full_text
from src.research.models import ResearchLimits
from src.research.openalex import OpenAlexClient, abstract_text, to_product_paper
from src.research.pipeline import ResearchPipeline
from test_research_scouts import full_text as fixture_text, paper, reader
from test_research_worker import postgres_dsn, repo  # noqa: F401  (shared fixtures)

WORK = {
    "id": "https://openalex.org/W1",
    "doi": "https://doi.org/10.48550/arXiv.1706.03762",
    "title": "Attention Is All You Need",
    "publication_year": 2017,
    "authorships": [{"author": {"id": "https://openalex.org/A1", "display_name": "Ashish Vaswani"}}],
    "primary_location": {"source": {"display_name": "NeurIPS"}},
    "best_oa_location": {"pdf_url": "https://arxiv.org/pdf/1706.03762"},
    "cited_by_count": 100,
    "referenced_works": ["https://openalex.org/W2", "https://openalex.org/W3"],
    "abstract_inverted_index": {"Attention": [0], "is": [1], "enough.": [2]},
}


def test_openalex_work_maps_to_a_paper_keyed_like_the_arxiv_source():
    p = to_product_paper(WORK)
    assert p.canonical_key == "arxiv:1706.03762" and p.doi is None
    assert p.arxiv_id == "1706.03762" and p.openalex_id == "W1"
    assert p.abstract == "Attention is enough."
    assert p.authors == [{"name": "Ashish Vaswani", "author_id": "A1"}]
    assert (p.venue, p.year, p.citation_count, p.reference_count) == ("NeurIPS", 2017, 100, 2)
    assert p.metadata["references"] == ["W2", "W3"]
    assert p.open_access_pdf_url == "https://arxiv.org/pdf/1706.03762"


def test_abstract_rebuilds_word_order_and_tolerates_missing_index():
    assert abstract_text({"b": [1], "a": [0, 2]}) == "a b a"
    assert abstract_text(None) is None


async def test_search_sends_filters_and_polite_contact():
    seen = []

    def handler(request):
        seen.append(request.url.params)
        return httpx.Response(200, json={"results": [WORK, {"id": "W9"}]})

    async with OpenAlexClient(transport=httpx.MockTransport(handler), email="me@example.org") as client:
        found = await client.search(
            "transformers", limit=5, filters={"start_date": "2020", "open_access_only": True}
        )
    (params,) = seen
    assert params["search"] == "transformers" and params["per-page"] == "5"
    assert params["mailto"] == "me@example.org"
    assert params["filter"] == "from_publication_date:2020-01-01,open_access.is_oa:true"
    assert [p.openalex_id for p in found] == ["W1"]  # untitled works are skipped


async def test_lookup_matches_by_arxiv_doi_and_openalex_id():
    requests = []

    def handler(request):
        requests.append(request.url.params["filter"])
        if request.url.params["filter"].startswith("ids.openalex"):
            return httpx.Response(200, json={"results": [{**WORK, "id": "https://openalex.org/W7", "doi": None, "title": "Other"}]})
        return httpx.Response(200, json={"results": [WORK]})

    arxiv_paper = paper("1706.03762")
    other = paper("x").model_copy(
        update={"openalex_id": "W7", "arxiv_id": None, "canonical_key": "openalex:w7"}
    )
    async with OpenAlexClient(transport=httpx.MockTransport(handler), email="") as client:
        found = await client.lookup([arxiv_paper, other])
    assert requests == ["ids.openalex:w7", "doi:10.48550/arxiv.1706.03762"]
    assert found[arxiv_paper.canonical_key].metadata["references"] == ["W2", "W3"]
    assert found["openalex:w7"].openalex_id == "W7"


def test_sessions_accept_openalex_as_a_source():
    assert SessionCreate(initial_query="q", source_providers=["openalex"]).source_providers == ["openalex"]
    with pytest.raises(ValueError):
        SessionCreate(initial_query="q", source_providers=["scholar"])


def start(repo, providers=("arxiv",)):
    session = repo.create_session(
        SessionCreate(
            initial_query="graph neural networks for molecules",
            source_providers=list(providers),
            parameters={"research": {"max_papers": 3, "max_claims": 1, "max_depth": 0, "synthesize": False}},
        )
    )
    repo.set_session_status(session.id, SessionStatus.RUNNING, "session_started")
    return session


async def test_citation_enrichment_produces_observed_map_edges(repo):
    session = start(repo)

    async def search(name, query, filters, limits):
        return [paper("a"), paper("b")]

    async def citations(papers):
        ids = {"arxiv:a": "W10", "arxiv:b": "W11"}
        return [
            p.model_copy(update={
                "openalex_id": ids[p.canonical_key],
                "metadata": {**p.metadata, "references": ["W11"] if p.canonical_key == "arxiv:a" else []},
            })
            for p in papers
        ]

    await ResearchWorker(
        repo, ResearchPipeline(repo, search=search, full_text=fixture_text, citations=citations)
    ).run_once()
    snapshot = reader(repo).get_session_snapshot(session.id)
    assert {p.paper.openalex_id for p in snapshot.papers} == {"W10", "W11"}
    research_map = ResearchMapBuilder().build(snapshot)
    by_id = {p.paper.id: p.paper.title for p in snapshot.papers}
    cites = [(by_id[e.source_paper_id], by_id[e.target_paper_id]) for e in research_map.edges if e.edge_type == "cites"]
    assert cites == [("Paper a", "Paper b")]
    assert research_map.overview.observed_citation_edge_count == 1


async def test_failed_citation_lookup_only_adds_a_warning(repo):
    session = start(repo)

    async def search(*_):
        return [paper("a")]

    async def citations(papers):
        raise httpx.ConnectError("offline")

    job = await ResearchWorker(
        repo, ResearchPipeline(repo, search=search, full_text=fixture_text, citations=citations)
    ).run_once()
    assert job.status.value == "succeeded"
    assert job.result["warnings"] == ["citations: ConnectError"]
    assert len(reader(repo).get_session_snapshot(session.id).papers) == 1


async def test_sources_are_interleaved_by_rank(repo):
    session = start(repo, providers=("arxiv", "openalex"))

    async def search(name, query, filters, limits):
        return [paper(f"{name}-{n}") for n in range(3)]

    await ResearchWorker(repo, ResearchPipeline(repo, search=search, full_text=fixture_text)).run_once()
    titles = {p.paper.title for p in reader(repo).get_session_snapshot(session.id).papers}
    assert titles == {"Paper arxiv-0", "Paper openalex-0", "Paper arxiv-1"}


class FakeEmbedder:
    """Maps texts about speed to one direction and everything else to another."""

    name = "fake"

    def __init__(self, fail=False):
        self.fail, self.calls = fail, 0

    def embed(self, texts):
        self.calls += 1
        if self.fail:
            raise OSError("model download blocked")
        return [(1.0, 0.0) if ("fast" in t or "quick" in t) else (0.0, 1.0) for t in texts]


def test_semantic_scores_find_paraphrases_that_share_no_words():
    claim = "The model trains quickly."
    candidates = [
        EvidenceCandidate(source_type="paper_chunk", paper_id="p", evidence_text="Optimization finishes fast on GPUs.", embedding=(1.0, 0.0)),
        EvidenceCandidate(source_type="paper_chunk", paper_id="p", evidence_text="The model trains on molecules.", embedding=(0.0, 1.0)),
    ]
    lexical = EvidenceRetriever().retrieve(claim, candidates, top_k=2)
    assert [r.candidate.evidence_text for r in lexical] == ["The model trains on molecules."]
    hybrid = EvidenceRetriever().retrieve(claim, candidates, top_k=2, claim_embedding=(1.0, 0.0))
    # Each passage leads one signal, so fused ranks tie and the exact wording match goes first.
    assert [(r.candidate.evidence_text, r.semantic_score) for r in hybrid] == [
        ("The model trains on molecules.", 0.0),
        ("Optimization finishes fast on GPUs.", 1.0),
    ]


async def test_passage_embeddings_are_stored_and_used_for_checking(repo):
    session = start(repo)

    async def search(*_):
        return [paper("fast")]

    embedder = FakeEmbedder()
    await ResearchWorker(
        repo, ResearchPipeline(repo, search=search, full_text=fixture_text, embedder=embedder)
    ).run_once()
    stored = reader(repo)
    snapshot = stored.get_session_snapshot(session.id)
    (chunk,) = stored.list_paper_chunks(snapshot.papers[0].paper_id)
    assert chunk.embedding == [1.0, 0.0]
    assert "embedding" not in chunk.model_dump()
    (validation,) = [e for e in snapshot.events if e.event_type == "claim_validated"]
    assert '"retrieval": "hybrid:fake"' in validation.payload["notes"]


async def test_embedding_failure_falls_back_to_lexical_retrieval(repo):
    session = start(repo)

    async def search(*_):
        return [paper("a")]

    job = await ResearchWorker(
        repo,
        ResearchPipeline(repo, search=search, full_text=fixture_text, embedder=FakeEmbedder(fail=True)),
    ).run_once()
    assert job.status.value == "succeeded"
    assert job.result["embedding_warning"] == "Semantic retrieval disabled (OSError)"
    assert reader(repo).get_session(session.id).status.value == "completed"


def test_embeddings_are_off_unless_a_model_is_named(monkeypatch):
    monkeypatch.delenv("INDRA_EMBEDDING_MODEL", raising=False)
    assert embedder_from_environment() is None
    monkeypatch.setenv("INDRA_EMBEDDING_MODEL", "off")
    assert embedder_from_environment() is None
    monkeypatch.setenv("INDRA_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    embedder = embedder_from_environment()
    assert isinstance(embedder, LocalEmbedder) and embedder._model is None  # loads lazily
    assert embedder_from_environment() is embedder


def _scanned_pdf(pages=1) -> bytes:
    document = pymupdf.open()
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 8, 8), False)
    for _ in range(pages):
        document.new_page().insert_image(pymupdf.Rect(0, 0, 100, 100), pixmap=pixmap)
    return document.tobytes()


def test_scanned_pages_without_tesseract_are_explained(monkeypatch):
    monkeypatch.setattr(full_text, "ocr_available", lambda: False)
    report = {}
    chunks = full_text.extract_pdf(_scanned_pdf(2), "p", "https://example.org/a.pdf", report)
    assert chunks == [] and report == {"scanned": 2, "ocr": 0}
    note = full_text.scan_note(chunks, report)
    assert note.startswith("The PDF contains no extractable text")
    assert "2 scanned page(s) were not read because OCR needs Tesseract installed." in note


def test_scanned_pages_are_read_with_ocr_up_to_the_limit(monkeypatch):
    monkeypatch.setattr(full_text, "ocr_available", lambda: True)
    monkeypatch.setattr(full_text, "_ocr_text", lambda page: f"Recognised text on page {page.number + 1}.\x00")
    monkeypatch.setattr(full_text, "MAX_OCR_PAGES", 1)
    report = {}
    chunks = full_text.extract_pdf(_scanned_pdf(2), "p", "https://example.org/a.pdf", report)
    assert [(c.text, c.page_start) for c in chunks] == [("Recognised text on page 1.", 1)]
    note = full_text.scan_note(chunks, report)
    assert "1 scanned page(s) were read with OCR" in note
    assert "1 scanned page(s) were not read because the OCR page limit was reached." in note


def test_limits_still_validate_with_new_sources():
    assert ResearchLimits().max_papers == 5


async def test_preprint_and_journal_versions_with_one_title_are_read_once(repo):
    session = start(repo, providers=("arxiv", "openalex"))

    async def search(name, query, filters, limits):
        twin = paper(f"{name}-twin").model_copy(update={"title": "Longer Attention Span: Sparse Graphs!"})
        if name == "openalex":
            twin = twin.model_copy(update={"title": "Longer attention span — sparse graphs"})
        return [twin, paper(f"{name}-other")]

    await ResearchWorker(repo, ResearchPipeline(repo, search=search, full_text=fixture_text)).run_once()
    titles = sorted(p.paper.title for p in reader(repo).get_session_snapshot(session.id).papers)
    assert titles == ["Longer Attention Span: Sparse Graphs!", "Paper arxiv-other", "Paper openalex-other"]
