"""Tests for deterministic claim validation decisions."""

from src.claims import ClaimVerifier, EvidenceInput


def test_claim_verifier_supports_claim_from_supporting_evidence():
    verifier = ClaimVerifier()

    decision = verifier.decide([EvidenceInput(relation="supports", score=0.92)])

    assert decision.status == "supported"
    assert decision.confidence == 0.92


def test_claim_verifier_contradiction_takes_priority():
    verifier = ClaimVerifier()

    decision = verifier.decide(
        [
            EvidenceInput(relation="supports", score=0.81),
            EvidenceInput(relation="contradicts", score=0.74),
        ]
    )

    assert decision.status == "contradicted"
    assert decision.confidence == 0.74


def test_claim_verifier_marks_missing_evidence_not_found():
    verifier = ClaimVerifier()

    decision = verifier.decide([])

    assert decision.status == "not_found"
    assert decision.confidence is None


def test_claim_verifier_does_not_promote_mentions():
    verifier = ClaimVerifier()

    decision = verifier.decide(
        [
            EvidenceInput(relation="mentions", score=0.0),
            EvidenceInput(relation="insufficient", score=0.66),
        ]
    )

    assert decision.status == "not_found"
    assert decision.confidence == 0.0
