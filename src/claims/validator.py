"""Deterministic claim validation decisions from explicit evidence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceInput:
    """Evidence relation supplied to the deterministic claim verifier."""

    relation: str
    score: float | None = None


@dataclass(frozen=True)
class ClaimValidationDecision:
    """Status decision for a claim after evidence review."""

    status: str
    confidence: float | None = None


class ClaimVerifier:
    """Assign claim status from explicit evidence relations."""

    def decide(self, evidence: list[EvidenceInput]) -> ClaimValidationDecision:
        """Decide a claim status from evidence relations."""

        if not evidence:
            return ClaimValidationDecision(status="not_found")

        if self._has_relation(evidence, "contradicts"):
            return ClaimValidationDecision(
                status="contradicted",
                confidence=self._max_score(evidence, "contradicts"),
            )

        if self._has_relation(evidence, "supports"):
            return ClaimValidationDecision(
                status="supported",
                confidence=self._max_score(evidence, "supports"),
            )

        if self._has_relation(evidence, "weakly_supports"):
            return ClaimValidationDecision(
                status="weakly_supported",
                confidence=self._max_score(evidence, "weakly_supports"),
            )

        mentions_score = self._max_score(evidence, "mentions")
        if mentions_score is not None:
            return ClaimValidationDecision(
                status="not_found",
                confidence=mentions_score,
            )

        return ClaimValidationDecision(
            status="not_found",
            confidence=self._max_score(evidence, "insufficient"),
        )

    def _has_relation(self, evidence: list[EvidenceInput], relation: str) -> bool:
        return any(item.relation == relation for item in evidence)

    def _max_score(
        self,
        evidence: list[EvidenceInput],
        relation: str,
    ) -> float | None:
        scores = [
            item.score
            for item in evidence
            if item.relation == relation and item.score is not None
        ]
        return max(scores) if scores else None
