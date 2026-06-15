"""Tests for deterministic claim extraction."""

from src.claims import ClaimExtractor


def test_claim_extractor_splits_compound_paper_claims():
    extractor = ClaimExtractor()

    claims = extractor.extract(
        (
            "The paper introduces a retrieval method, evaluates the method on "
            "several datasets, outperforms baseline systems, and discusses "
            "limitations."
        )
    )

    assert [claim.text for claim in claims] == [
        "The paper introduces a retrieval method.",
        "The paper evaluates the method on several datasets.",
        "The paper outperforms baseline systems.",
        "The paper discusses limitations.",
    ]
    assert [claim.claim_type for claim in claims] == [
        "methodological",
        "empirical_result",
        "comparison",
        "limitation",
    ]
    assert {claim.status for claim in claims} == {"needs_review"}


def test_claim_extractor_marks_speculative_claims():
    extractor = ClaimExtractor()

    claims = extractor.extract("The model may improve evidence navigation.")

    assert len(claims) == 1
    assert claims[0].claim_type == "hypothesis"
    assert claims[0].status == "speculative"
