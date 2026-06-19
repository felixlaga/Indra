from types import SimpleNamespace

from src.analysis import ResearchAdviceBuilder


def make_claim(claim_id, text, status="supported", claim_type="factual"):
    return SimpleNamespace(
        id=claim_id,
        claim_text=text,
        status=status,
        claim_type=claim_type,
        confidence=0.7,
        paper_id="p1",
        branch_id="b1",
    )


def make_snapshot(claims, evidence=()):
    return SimpleNamespace(
        session=SimpleNamespace(id="s1"),
        claims=list(claims),
        claim_evidence=list(evidence),
        papers=[],
        branches=[SimpleNamespace(id="b1", label="Branch", query="topic")],
    )


def make_map():
    return SimpleNamespace(
        nodes=[],
        overview=SimpleNamespace(observed_citation_edge_count=0),
    )


def test_persisted_conflict_is_visible():
    item = make_claim("c1", "The method improves accuracy.", status="contradicted")
    evidence = SimpleNamespace(claim_id="c1", relation="contradicts", score=0.9)
    result = ResearchAdviceBuilder().build(make_snapshot([item], [evidence]), make_map())
    assert result.contradictions[0].status == "observed"
    assert result.weak_evidence[0].priority == "high"


def test_generated_hypotheses_remain_speculative():
    item = make_claim(
        "c1",
        "Current studies are limited by small sample sizes.",
        claim_type="limitation",
    )
    result = ResearchAdviceBuilder().build(make_snapshot([item]), make_map())
    assert result.hypotheses
    assert all(proposal.status == "speculative" for proposal in result.hypotheses)
    assert all(proposal.confidence <= 0.45 for proposal in result.hypotheses)
