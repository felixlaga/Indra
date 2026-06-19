"""Deterministic, inspectable evidence retrieval for atomic claims.

This module deliberately avoids model inference. It ranks persisted source passages by
lexical coverage and labels the relation using conservative, documented thresholds.
The result is review-ready evidence, not a claim of semantic proof.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "with",
}
_NEGATIONS = {
    "cannot",
    "didnt",
    "doesnt",
    "failed",
    "fails",
    "never",
    "no",
    "not",
    "without",
}
_SOURCE_BONUS = {
    "paper_chunk": 0.08,
    "paper_abstract": 0.04,
    "paper_metadata": 0.0,
}


@dataclass(frozen=True)
class EvidenceCandidate:
    """A persisted source passage that can be ranked for a claim."""

    source_type: str
    paper_id: str
    evidence_text: str
    chunk_id: str | None = None
    metadata_field: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    section_title: str | None = None


@dataclass(frozen=True)
class RetrievedEvidence:
    """A ranked passage and its conservative claim relation."""

    candidate: EvidenceCandidate
    relation: str
    score: float
    retrieval_score: float
    overlap_terms: tuple[str, ...]


class EvidenceRetriever:
    """Rank evidence candidates using transparent lexical coverage rules."""

    def retrieve(
        self,
        claim_text: str,
        candidates: list[EvidenceCandidate],
        *,
        top_k: int = 5,
        min_score: float = 0.15,
    ) -> list[RetrievedEvidence]:
        """Return the strongest unique passages for a claim.

        The score is the fraction of content-bearing claim terms present in a passage,
        plus a small source-hierarchy bonus. A passage must meet ``min_score`` before
        it is stored as evidence.
        """

        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        if not 0 <= min_score <= 1:
            raise ValueError("min_score must be between 0 and 1")

        claim_terms = self._terms(claim_text)
        if not claim_terms:
            return []

        ranked: list[RetrievedEvidence] = []
        seen: set[tuple[str, str, str]] = set()
        for candidate in candidates:
            text = candidate.evidence_text.strip()
            if not text:
                continue
            dedupe_key = (
                candidate.paper_id,
                candidate.source_type,
                re.sub(r"\s+", " ", text.lower()),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            evidence_terms = self._terms(text)
            overlap = claim_terms & evidence_terms
            coverage = len(overlap) / len(claim_terms)
            retrieval_score = min(
                1.0,
                coverage + _SOURCE_BONUS.get(candidate.source_type, 0.0),
            )
            if retrieval_score < min_score:
                continue

            relation, relation_score = self._relation(
                claim_terms=claim_terms,
                evidence_terms=evidence_terms,
                coverage=coverage,
            )
            ranked.append(
                RetrievedEvidence(
                    candidate=candidate,
                    relation=relation,
                    score=relation_score,
                    retrieval_score=retrieval_score,
                    overlap_terms=tuple(sorted(overlap)),
                )
            )

        ranked.sort(
            key=lambda item: (
                item.retrieval_score,
                item.score,
                _SOURCE_BONUS.get(item.candidate.source_type, 0.0),
                len(item.candidate.evidence_text),
            ),
            reverse=True,
        )
        return ranked[:top_k]

    def _relation(
        self,
        *,
        claim_terms: set[str],
        evidence_terms: set[str],
        coverage: float,
    ) -> tuple[str, float]:
        claim_negated = bool(claim_terms & _NEGATIONS)
        evidence_negated = bool(evidence_terms & _NEGATIONS)
        if coverage >= 0.55 and claim_negated != evidence_negated:
            return "contradicts", min(1.0, 0.35 + 0.65 * coverage)
        if coverage >= 0.72:
            return "supports", coverage
        if coverage >= 0.45:
            return "weakly_supports", coverage
        if coverage >= 0.25:
            return "mentions", coverage
        return "insufficient", coverage

    def _terms(self, text: str) -> set[str]:
        normalized = text.lower().replace("’", "'")
        normalized = re.sub(r"n't\b", " not", normalized)
        tokens = re.findall(r"[a-z0-9]+", normalized)
        return {
            token
            for token in tokens
            if len(token) > 2 and token not in _STOP_WORDS
        }


def split_passages(text: str, *, max_chars: int = 900) -> list[str]:
    """Split an abstract or document fragment into inspectable passages."""

    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        return []
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", compact)
        if sentence.strip()
    ]
    passages: list[str] = []
    current = ""
    for sentence in sentences or [compact]:
        proposed = f"{current} {sentence}".strip()
        if current and len(proposed) > max_chars:
            passages.append(current)
            current = sentence
        else:
            current = proposed
    if current:
        passages.append(current)
    return passages
