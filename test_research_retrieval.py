"""Query planning and paper selection: the search finds a pool, the branch chooses."""

from src.api.models import Paper, SessionCreate, SessionStatus
from src.api.repository import utc_now
from src.jobs.research_worker import ResearchWorker
from src.research.model import ModelRateLimited
from src.research.models import (
    PaperChoice,
    PaperSelection,
    PaperSynthesis,
    SearchPlan,
    stable_id,
)
from src.research.pipeline import ResearchPipeline
from src.research.providers import arxiv_query
from src.research.retrieval import (
    Candidate,
    candidate_pool,
    fallback_queries,
    needs_plan,
    rank_candidates,
    ranked_choice,
)
from test_research_scouts import reader
from test_research_worker import postgres_dsn, repo  # noqa: F401  (shared fixtures)

QUESTION = (
    "where is the field of gravitational wave lensing headed, specifically the lensing of "
    "gravitational waves. What are the gaps and where can the biggest impact be made and what "
    "is the newest direction, and what are currently the biggest unknowns and the largest "
    "contradictions."
)
# What a verbatim search for QUESTION returned in a real session.
OFF_TOPIC = [
    ("Astrophysics in 2002", "A year of results on stars, galaxies and the solar system."),
    ("Undergraduate Review, Vol. 3, 2006/2007", None),
    ("Interview with Abel Laureate John Milnor", None),
    ("Science and technology", "Essays on research policy and its biggest impact."),
]
ON_TOPIC = [
    (
        "Gravitational wave lensing as a probe of halo properties and dark matter",
        "Lensed gravitational waves constrain dark matter halos.",
    ),
    (
        "Strong lensing of gravitational waves: a review",
        "We review searches for strongly lensed gravitational-wave events.",
    ),
    (
        "Wave-optics gravitational wave lensing in modified gravity",
        "Diffraction of gravitational waves by small lenses.",
    ),
]


def paper(title, abstract=None, *, provider="openalex", key=None):
    key = key or f"{provider}:{abs(hash(title))}"
    return Paper(
        id=stable_id("retrieval-fixture", key),
        canonical_key=key,
        title=title,
        abstract=abstract,
        year=2024,
        created_at=utc_now(),
        updated_at=utc_now(),
        metadata={"provider": provider},
    )


def test_long_questions_are_planned_and_their_key_terms_name_the_subject():
    assert needs_plan(QUESTION)
    assert not needs_plan("graph neural networks for molecules")
    assert not needs_plan("The method improves accuracy.")
    assert fallback_queries(QUESTION) == ["gravitational wave lensing"]


def test_arxiv_queries_require_every_term_and_keep_phrases():
    assert arxiv_query("gravitational wave lensing") == (
        "all:gravitational AND all:wave AND all:lensing"
    )
    assert arxiv_query('"gravitational wave" lensing of halos') == (
        'all:"gravitational wave" AND all:lensing AND all:halos'
    )


def test_pool_merges_a_paper_found_by_several_queries_and_sources():
    title = ON_TOPIC[0][0]
    pool = candidate_pool(
        [
            # One source listing a paper twice is still one source.
            [paper(title, key="doi:1"), paper(title, key="doi:2"), paper("Read", key="arxiv:r")],
            [paper(title, ON_TOPIC[0][1], provider="arxiv", key="arxiv:1")],
        ],
        exclude_keys={"arxiv:r"},
        exclude_titles=set(),
    )
    (only,) = pool
    assert only.hits == 2 and only.paper.abstract == ON_TOPIC[0][1]


async def test_ranking_leaves_out_off_topic_papers_when_on_topic_ones_exist():
    candidates = [Candidate(paper(*p)) for p in OFF_TOPIC + ON_TOPIC]
    ranked = await rank_candidates(QUESTION, "gravitational wave lensing", candidates)
    chosen = ranked_choice(ranked, 5)
    assert {c.paper.title for c in chosen} == {t for t, _ in ON_TOPIC}
    # Nothing on topic: the best-ranked are still read rather than none.
    off = [Candidate(paper(*p)) for p in OFF_TOPIC]
    assert len(ranked_choice(await rank_candidates(QUESTION, "lensing", off), 2)) == 2


class Search:
    """A verbatim question finds only noise; keyword queries find the field."""

    def __init__(self):
        self.calls = []

    async def __call__(self, name, query, filters, limits):
        self.calls.append((name, query))
        if query == QUESTION:
            return [paper(*p, provider=name) for p in OFF_TOPIC]
        return [paper(*p, provider=name) for p in OFF_TOPIC[:2] + ON_TOPIC]


class Model:
    def __init__(self, plan=None, choose=None):
        self.calls, self.plan, self.choose = [], plan, choose

    async def generate(self, schema, instruction, data):
        self.calls.append(schema.__name__)
        if schema is SearchPlan:
            if isinstance(self.plan, Exception):
                raise self.plan
            return SearchPlan(
                topic="gravitational-wave lensing",
                queries=[
                    '"gravitational wave" lensing',
                    "lensed gravitational waves",
                    '"Gravitational wave" lensing',
                ],
            ), {"model": "fixture"}
        if schema is PaperSelection:
            titles = [c["title"] for c in data["candidates"]]
            wanted = self.choose or [ON_TOPIC[1][0], ON_TOPIC[0][0]]
            numbers = [titles.index(t) + 1 for t in wanted if t in titles]
            return PaperSelection(
                assessment="Two lensing papers cover detection and dark matter.",
                selected=[PaperChoice(candidate=n, reason=f"Reason {n}.") for n in numbers]
                + [PaperChoice(candidate=99, reason="Not a candidate.")],
            ), {"model": "fixture", "prompt_name": "PaperSelection"}
        if schema is PaperSynthesis:
            return PaperSynthesis(summary=f"About {data['title']}", claims=[]), {
                "model": "fixture"
            }
        raise AssertionError(f"unexpected schema {schema.__name__}")


async def no_text(_paper):
    return [], None


def start(repo, providers=("openalex", "arxiv")):
    session = repo.create_session(
        SessionCreate(
            initial_query=QUESTION,
            source_providers=list(providers),
            parameters={"research": {"max_papers": 3, "max_depth": 0, "synthesize": False}},
        )
    )
    repo.set_session_status(session.id, SessionStatus.RUNNING, "session_started")
    return session


async def test_model_plans_queries_and_chooses_papers_with_reasons(repo):
    session = start(repo)
    search, model = Search(), Model()
    job = await ResearchWorker(
        repo, ResearchPipeline(repo, model, search=search, full_text=no_text)
    ).run_once()
    assert job.status.value == "succeeded"
    queries = ['"gravitational wave" lensing', "lensed gravitational waves"]
    assert sorted(search.calls) == sorted((n, q) for n in ("openalex", "arxiv") for q in queries)
    assert job.result["query_method"] == "model"

    snapshot = reader(repo).get_session_snapshot(session.id)
    titles = [p.paper.title for p in snapshot.papers]
    assert sorted(titles) == sorted([ON_TOPIC[1][0], ON_TOPIC[0][0]])
    (decision,) = [d for d in snapshot.decisions if d.decision_type == "paper_selection"]
    assert decision.details["method"] == "model"
    assert decision.details["queries"] == queries
    assert [s["title"] for s in decision.details["selected"]] == [ON_TOPIC[1][0], ON_TOPIC[0][0]]
    assert all(s["reason"].startswith("Reason") for s in decision.details["selected"])
    assert decision.rationale == "Two lensing papers cover detection and dark matter."
    assert model.calls[:2] == ["SearchPlan", "PaperSelection"]


async def test_without_a_model_key_terms_search_and_ranking_drops_noise(repo):
    session = start(repo, providers=("openalex",))
    search = Search()
    job = await ResearchWorker(
        repo, ResearchPipeline(repo, search=search, full_text=no_text)
    ).run_once()
    assert search.calls == [("openalex", "gravitational wave lensing")]
    assert job.result["query_method"] == "key_terms"
    titles = {p.paper.title for p in reader(repo).get_session_snapshot(session.id).papers}
    assert titles == {t for t, _ in ON_TOPIC}


async def test_rate_limited_planning_falls_back_and_stops_model_use(repo):
    session = start(repo, providers=("openalex",))
    model = Model(plan=ModelRateLimited("The provider's daily quota was reached"))
    job = await ResearchWorker(
        repo, ResearchPipeline(repo, model, search=Search(), full_text=no_text)
    ).run_once()
    assert model.calls == ["SearchPlan"]
    assert job.result["model_stop_kind"] == "ModelRateLimited"
    assert job.result["search_queries"] == ["gravitational wave lensing"]
    snapshot = reader(repo).get_session_snapshot(session.id)
    assert {p.paper.title for p in snapshot.papers} == {t for t, _ in ON_TOPIC}


async def test_a_selection_without_valid_candidates_uses_the_ranking(repo):
    session = start(repo, providers=("openalex",))
    model = Model(choose=["Not in the pool"])
    await ResearchWorker(
        repo, ResearchPipeline(repo, model, search=Search(), full_text=no_text)
    ).run_once()
    snapshot = reader(repo).get_session_snapshot(session.id)
    (decision,) = [d for d in snapshot.decisions if d.decision_type == "paper_selection"]
    assert decision.details["method"] == "ranking"
    assert {p.paper.title for p in snapshot.papers} == {t for t, _ in ON_TOPIC}
