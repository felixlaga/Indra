"""Scout branches, session synthesis and the shared model budget."""

import json
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from src.api.models import JobType, Paper, SessionCreate, SessionStatus
from src.api.postgres_repository import PostgresRepository
from src.api.repository import utc_now
from src.claims import EvidenceCandidate, EvidenceRetriever
from src.claims.semantic_verifier import judge_passages
from src.jobs.research_worker import ResearchWorker
from src.research.model import ModelRateLimited, ResearchModel
from src.research.models import (
    EvidenceJudgments,
    FollowUpQuestion,
    HypothesisDraft,
    PaperChunk,
    PaperSynthesis,
    ClaimDraft,
    ResearchLimits,
    ScoutPlan,
    SessionSynthesis,
    stable_id,
)
from src.research.pipeline import ResearchPipeline
from src.research.scouts import accept_plan, accept_synthesis, similar_query
from test_research_worker import postgres_dsn, repo  # noqa: F401  (shared fixtures)

ROOT_QUERY = "graph neural networks for molecules"
CHILD_QUERY = "message passing limits on molecular graphs"


def paper(key: str) -> Paper:
    return Paper(
        id=stable_id("scout-fixture", key),
        canonical_key=f"arxiv:{key}",
        title=f"Paper {key}",
        abstract=f"Finding {key} improves molecular property prediction.",
        authors=[{"name": "Author"}],
        arxiv_id=key,
        year=2025,
        created_at=utc_now(),
        updated_at=utc_now(),
    )


class Search:
    """Root finds a and b; the Scout's query finds a (already read) and c."""

    def __init__(self):
        self.queries = []

    async def __call__(self, name, query, filters, limits):
        self.queries.append((query, limits.max_papers))
        keys = ["a", "b"] if query == ROOT_QUERY else ["a", "c"]
        return [paper(k) for k in keys][: limits.max_papers]


async def full_text(p):
    return [
        PaperChunk(
            id=stable_id(p.id, "chunk"),
            paper_id=p.id,
            document_id=stable_id(p.id, "pdf"),
            chunk_index=0,
            text=p.abstract,
            page_start=1,
            page_end=1,
        )
    ], None


class ScriptedModel:
    """Answer each schema the way a well-behaved model would, recording every call."""

    def __init__(self, plan=None, synthesis=None):
        self.calls = []
        self.plan, self.synthesis = plan, synthesis

    async def generate(self, schema, instruction, data):
        self.calls.append(schema.__name__)
        if schema is PaperSynthesis:
            return PaperSynthesis(
                summary=f"Summary of {data['title']}",
                claims=[ClaimDraft(text=data["text"], claim_type="empirical_result")],
            ), {"model": "fixture"}
        if schema is EvidenceJudgments:
            return EvidenceJudgments(
                judgments=[
                    {
                        "passage": p["passage"],
                        "relation": "supports",
                        "quote": p["text"],
                        "rationale": "States the finding.",
                    }
                    for p in data["passages"]
                ]
            ), {"model": "fixture"}
        if schema is ScoutPlan:
            if isinstance(self.plan, Exception):
                raise self.plan
            return self.plan or ScoutPlan(
                assessment="Paper b leaves the mechanism open.",
                follow_ups=[
                    FollowUpQuestion(
                        query=ROOT_QUERY,
                        label="Repeat",
                        rationale="Same question again.",
                        motivation="missing_evidence",
                        motivating_claims=["C1"],
                    ),
                    FollowUpQuestion(
                        query=CHILD_QUERY,
                        label="Mechanism",
                        rationale="C1 does not explain why.",
                        motivation="mechanism",
                        motivating_claims=["C1", "C99"],
                    ),
                ],
            ), {"model": "fixture", "prompt_name": "ScoutPlan"}
        if schema is SessionSynthesis:
            claims = [c["alias"] for c in data["claims"]]
            return self.synthesis or SessionSynthesis(
                overview="Three papers report improvements.",
                hypotheses=[
                    HypothesisDraft(
                        text="Gains share one cause across datasets.",
                        rationale="C1 and C3 agree across papers.",
                        supporting_claims=claims,
                        contradicting_claims=[],
                        missing_evidence=["A controlled ablation."],
                        next_steps=["Run the ablation."],
                        testability="high",
                        risk="medium",
                    ),
                    HypothesisDraft(
                        text="Single-paper idea.",
                        rationale="Only one source.",
                        supporting_claims=claims[:1],
                        contradicting_claims=[],
                        missing_evidence=[],
                        next_steps=[],
                        testability="low",
                        risk="unknown",
                    ),
                ],
            ), {"model": "fixture", "prompt_name": "SessionSynthesis"}
        raise AssertionError(f"unexpected schema {schema.__name__}")


def start(repo, **research):
    session = repo.create_session(
        SessionCreate(
            initial_query=ROOT_QUERY,
            source_providers=["arxiv"],
            parameters={
                "research": {
                    "max_papers": 2,
                    "branch_papers": 2,
                    "max_claims": 1,
                    "max_branches": 2,
                    **research,
                }
            },
        )
    )
    repo.set_session_status(session.id, SessionStatus.RUNNING, "session_started")
    return session


async def drain(repo, pipeline, limit=10):
    worker, results = ResearchWorker(repo, pipeline), []
    for _ in range(limit):
        job = await worker.run_once()
        if job is None:
            return results
        results.append(job)
    raise AssertionError("jobs kept appearing")


def reader(repo):
    return PostgresRepository(repo._dsn) if isinstance(repo, PostgresRepository) else repo


async def test_scouts_open_a_branch_and_synthesis_keeps_cross_paper_hypotheses(repo):
    session = start(repo)
    model, search = ScriptedModel(), Search()
    jobs = await drain(
        repo, ResearchPipeline(repo, model, search=search, full_text=full_text)
    )
    assert [j.job_type for j in jobs] == [
        JobType.RESEARCH_SESSION,
        JobType.BRANCH_CONTINUE,
        JobType.SESSION_SYNTHESIS,
    ]
    assert all(j.status.value == "succeeded" for j in jobs)
    snapshot = reader(repo).get_session_snapshot(session.id)
    assert snapshot.session.status.value == "completed"

    root, child = sorted(snapshot.branches, key=lambda b: b.depth)
    assert (child.parent_branch_id, child.depth, child.query) == (root.id, 1, CHILD_QUERY)
    assert child.status.value == "completed" and child.label == "Mechanism"
    # The Scout skipped paper a, already read by the root, and read only c.
    child_titles = {p.paper.title for p in snapshot.papers if p.branch_id == child.id}
    assert child_titles == {"Paper c"}
    assert search.queries[1] == (CHILD_QUERY, 2 + 2)

    plan, synthesis = sorted(snapshot.decisions, key=lambda d: d.decision_type)
    assert plan.decision_type == "branch_split" and plan.branch_id == root.id
    assert plan.details["child_branch_ids"] == [child.id]
    assert plan.alternatives == [
        {"query": ROOT_QUERY, "reason": "Repeats an existing branch question."}
    ]
    assert plan.generation_provenance["prompt_name"] == "ScoutPlan"

    (hypothesis,) = snapshot.hypotheses
    assert hypothesis.text == "Gains share one cause across datasets."
    assert len(hypothesis.supporting_paper_ids) == 3
    assert set(hypothesis.supporting_claim_ids) == {c.id for c in snapshot.claims}
    assert hypothesis.missing_evidence == ["A controlled ablation."]
    assert hypothesis.testability == 0.9
    assert synthesis.alternatives[0]["reason"] == (
        "Supporting claims did not span two stored papers."
    )
    (overview,) = [s for s in snapshot.summaries if s.summary_type.value == "session"]
    assert overview.text == "Three papers report improvements."
    assert all(c.status.value == "supported" for c in snapshot.claims)
    # 3 paper summaries + 3 batched claim checks + 1 plan + 1 synthesis.
    assert len(model.calls) == 8


async def test_child_at_max_depth_does_not_plan_again(repo):
    session = start(repo, max_depth=1)
    model = ScriptedModel()
    await drain(repo, ResearchPipeline(repo, model, search=Search(), full_text=full_text))
    assert model.calls.count("ScoutPlan") == 1
    assert reader(repo).get_session(session.id).status.value == "completed"


async def test_without_a_model_no_scouts_or_synthesis_and_the_reason_is_recorded(repo):
    session = start(repo)
    jobs = await drain(repo, ResearchPipeline(repo, search=Search(), full_text=full_text))
    assert [j.job_type for j in jobs] == [JobType.RESEARCH_SESSION]
    snapshot = reader(repo).get_session_snapshot(session.id)
    assert snapshot.session.status.value == "completed"
    (decision,) = snapshot.decisions
    assert decision.rationale == "Follow-up branches need a configured research model."
    assert len(snapshot.branches) == 1 and not snapshot.hypotheses


async def test_rate_limited_plan_opens_no_branches_and_still_synthesizes(repo):
    session = start(repo)
    model = ScriptedModel(plan=ModelRateLimited("The provider's daily quota was reached"))
    jobs = await drain(repo, ResearchPipeline(repo, model, search=Search(), full_text=full_text))
    assert [j.job_type for j in jobs] == [JobType.RESEARCH_SESSION, JobType.SESSION_SYNTHESIS]
    snapshot = reader(repo).get_session_snapshot(session.id)
    plan = next(d for d in snapshot.decisions if d.decision_type == "branch_split")
    assert "daily quota was reached" in plan.rationale
    assert len(snapshot.branches) == 1
    # Two root papers still support a cross-paper hypothesis.
    assert len(snapshot.hypotheses) == 1
    assert snapshot.session.status.value == "completed"


async def test_reserved_calls_keep_planning_and_synthesis_when_budget_is_tight(repo):
    # reserve = 1 call; 3 spendable split 1 per paper across root (1) and Scout (1).
    session = start(repo, max_papers=1, branch_papers=1, max_branches=1, max_model_calls=4)
    model = ScriptedModel()
    jobs = await drain(repo, ResearchPipeline(repo, model, search=Search(), full_text=full_text))
    assert model.calls == ["PaperSynthesis", "ScoutPlan", "PaperSynthesis", "SessionSynthesis"]
    assert sum(j.result.get("model_calls", 0) for j in jobs) == 4
    snapshot = reader(repo).get_session_snapshot(session.id)
    assert len(snapshot.branches) == 2
    assert all(c.status.value == "needs_review" for c in snapshot.claims)
    assert jobs[0].result["verification_mode"] == "model_partial"
    assert "share of the model-call budget" in jobs[0].result["message"]


async def test_recording_the_same_decision_twice_opens_branches_once(repo):
    session = start(repo)
    leased = repo.lease_next_job("w1", [JobType.RESEARCH_SESSION])
    root = repo.get_branch(leased.branch_id)
    plan = ScoutPlan(
        assessment="Open one.",
        follow_ups=[
            FollowUpQuestion(
                query=CHILD_QUERY,
                label="Mechanism",
                rationale="Why.",
                motivation="mechanism",
                motivating_claims=[],
            )
        ],
    )
    decision = accept_plan(
        plan,
        leased=leased,
        branch=root,
        aliases={},
        existing_queries=[root.query],
        slots=2,
        provenance={},
    )
    first = repo.record_research_decision(leased, decision, max_branches=2)
    second = repo.record_research_decision(leased, decision, max_branches=2)
    assert [b.id for b in first] == [b.id for b in second]
    jobs = [j for j in repo.list_jobs(session.id) if j.job_type == JobType.BRANCH_CONTINUE]
    assert len(jobs) == 1 and len(repo.list_branches(session.id)) == 2


async def test_branch_limit_is_enforced_when_decisions_are_written(repo):
    session = start(repo, max_branches=1)
    leased = repo.lease_next_job("w1", [JobType.RESEARCH_SESSION])
    root = repo.get_branch(leased.branch_id)
    plan = ScoutPlan(
        assessment="Open two.",
        follow_ups=[
            FollowUpQuestion(query=q, label=q, rationale="r", motivation="method", motivating_claims=[])
            for q in ["first distinct question", "second unrelated topic"]
        ],
    )
    decision = accept_plan(
        plan, leased=leased, branch=root, aliases={}, existing_queries=[], slots=2, provenance={}
    )
    created = repo.record_research_decision(leased, decision, max_branches=1)
    assert [b.query for b in created] == ["first distinct question"]
    (stored,) = reader(repo).get_session_snapshot(session.id).decisions
    assert stored.alternatives == [
        {"query": "second unrelated topic", "reason": "The session's branch limit was reached."}
    ]


async def test_failed_synthesis_still_completes_the_session(repo):
    session = start(repo, max_depth=0)
    model = ScriptedModel()
    await ResearchWorker(
        repo, ResearchPipeline(repo, model, search=Search(), full_text=full_text)
    ).run_once()
    leased = repo.lease_next_job("w1", [JobType.SESSION_SYNTHESIS])
    repo.fail_research(leased, "boom", retryable=False)
    assert reader(repo).get_session(session.id).status.value == "completed"


def test_concurrent_last_branches_queue_one_synthesis(postgres_dsn):  # noqa: F811
    repo = PostgresRepository(postgres_dsn)
    session = start(repo)
    root = repo.lease_next_job("w1", [JobType.RESEARCH_SESSION])
    branch = repo.get_branch(root.branch_id)
    decision = accept_plan(
        ScoutPlan(
            assessment="One more.",
            follow_ups=[
                FollowUpQuestion(
                    query=CHILD_QUERY,
                    label="x",
                    rationale="r",
                    motivation="method",
                    motivating_claims=[],
                )
            ],
        ),
        leased=root,
        branch=branch,
        aliases={},
        existing_queries=[],
        slots=1,
        provenance={},
    )
    repo.record_research_decision(root, decision, max_branches=2)
    child = repo.lease_next_job("w2", [JobType.BRANCH_CONTINUE])
    with ThreadPoolExecutor(2) as pool:
        list(
            pool.map(
                lambda job: PostgresRepository(postgres_dsn).finish_research(
                    job, then_synthesize=True
                ),
                [root, child],
            )
        )
    jobs = repo.list_jobs(session.id)
    assert sum(j.job_type == JobType.SESSION_SYNTHESIS for j in jobs) == 1
    assert repo.get_session(session.id).status.value == "running"
    with repo._connect() as conn:
        conn.execute("TRUNCATE research_sessions, papers CASCADE")


def test_concurrent_reservations_never_exceed_the_session_budget(postgres_dsn):  # noqa: F811
    repo = PostgresRepository(postgres_dsn)
    session = start(repo, max_model_calls=5)
    root = repo.lease_next_job("w1", [JobType.RESEARCH_SESSION])
    decision = accept_plan(
        ScoutPlan(
            assessment="One more.",
            follow_ups=[
                FollowUpQuestion(
                    query=CHILD_QUERY, label="x", rationale="r", motivation="method", motivating_claims=[]
                )
            ],
        ),
        leased=root,
        branch=repo.get_branch(root.branch_id),
        aliases={},
        existing_queries=[],
        slots=1,
        provenance={},
    )
    repo.record_research_decision(root, decision, max_branches=2)
    child = repo.lease_next_job("w2", [JobType.BRANCH_CONTINUE])

    def reserve(job):
        return PostgresRepository(postgres_dsn).reserve_model_call(job, limit=5)

    with ThreadPoolExecutor(8) as pool:
        outcomes = list(pool.map(reserve, [root, child] * 6))
    assert outcomes.count(None) == 5
    assert sum(j.result.get("model_calls", 0) for j in repo.list_jobs(session.id)) == 5
    with repo._connect() as conn:
        conn.execute("TRUNCATE research_sessions, papers CASCADE")


def test_limits_reserve_planning_calls_and_split_the_rest_by_papers():
    limits = ResearchLimits(max_model_calls=30)
    assert limits.reserved_model_calls() == 2
    assert limits.branch_model_calls(root=True) == 28 * 5 // 14
    assert limits.branch_model_calls(root=False) == 28 * 3 // 14
    single = ResearchLimits(max_model_calls=30, max_depth=0, synthesize=False)
    assert single.reserved_model_calls() == 0
    assert single.branch_model_calls(root=True) == 30


def test_similar_queries_are_detected_by_shared_terms():
    assert similar_query("Graph neural networks for molecules", "graph neural networks molecules")
    assert not similar_query("graph neural networks for molecules", "protein folding with diffusion")


class _Leased:
    id = "job-fixture"


class _Claim:
    def __init__(self, cid, paper_id):
        self.id, self.paper_id = cid, paper_id


def test_synthesis_drops_unknown_aliases_and_single_paper_support():
    aliases = {"C1": _Claim("c1", "p1"), "C2": _Claim("c2", "p2"), "C3": _Claim("c3", "p1")}
    draft = dict(
        rationale="r", contradicting_claims=["C9"], missing_evidence=[" x ", ""], next_steps=[],
        testability="medium", risk="low",
    )
    synthesis = SessionSynthesis(
        overview="o",
        hypotheses=[
            HypothesisDraft(text="Two papers", supporting_claims=["C1", "C2", "C7"], **draft),
            HypothesisDraft(text="One paper", supporting_claims=["C1", "C3"], **draft),
        ],
    )
    kept, decision = accept_synthesis(
        synthesis, leased=_Leased(), session=None, aliases=aliases, provenance={}
    )
    (only,) = kept
    assert only.supporting_claim_ids == ["c1", "c2"]
    assert only.contradicting_claim_ids == []
    assert only.missing_evidence == ["x"] and only.testability == 0.6
    assert decision.decision == "Kept 1 of 2 proposed hypotheses."


def _retrieved(*passages):
    return [
        EvidenceRetriever().retrieve(
            "The method improves accuracy.",
            [EvidenceCandidate(source_type="paper_abstract", paper_id=f"p{i}", evidence_text=text)],
            min_score=0,
        )[0]
        for i, text in enumerate(passages)
    ]


def _model(content):
    return ResearchModel(
        "fixture-key",
        "fixture-model",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {"finish_reason": "stop", "message": {"content": json.dumps(content)}}
                    ]
                },
            )
        ),
    )


async def test_batch_judging_maps_each_passage_and_leaves_omitted_ones_unjudged():
    retrieved = _retrieved("The method improves accuracy.", "Accuracy fell sharply.", "Unrelated.")
    model = _model(
        {
            "judgments": [
                {"passage": 1, "relation": "supports", "quote": "The method improves accuracy.", "rationale": "Direct."},
                {"passage": 2, "relation": "contradicts", "quote": "Accuracy fell sharply.", "rationale": "Opposite."},
            ]
        }
    )
    results = await judge_passages("The method improves accuracy.", retrieved, model)
    assert [e.relation.value for e, _ in results] == ["supports", "contradicts", "mentions"]
    assert results[2][1]["rationale"].startswith("The model did not judge")


@pytest.mark.parametrize(
    "judgments",
    [
        [{"passage": 1, "relation": "supports", "quote": "invented", "rationale": "x"}],
        [{"passage": 4, "relation": "insufficient", "quote": "", "rationale": "x"}],
        [
            {"passage": 1, "relation": "insufficient", "quote": "", "rationale": "x"},
            {"passage": 1, "relation": "insufficient", "quote": "", "rationale": "x"},
        ],
    ],
)
async def test_batch_judging_rejects_invented_quotes_and_bad_passage_numbers(judgments):
    with pytest.raises(ValueError):
        await judge_passages(
            "The method improves accuracy.",
            _retrieved("The method improves accuracy."),
            _model({"judgments": judgments}),
        )
