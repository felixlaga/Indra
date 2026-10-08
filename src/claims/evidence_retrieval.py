"""Deterministic, inspectable evidence retrieval for atomic claims.

This module only ranks source passages. Semantic judgments belong to the verifier;
word overlap never implies support, contradiction, or factual confidence.
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
    # Unit-length passage embedding, when semantic retrieval is enabled.
    embedding: tuple[float, ...] | None = None


@dataclass(frozen=True)
class RetrievedEvidence:
    """A ranked passage and its conservative claim relation."""

    candidate: EvidenceCandidate
    relation: str
    score: float
    retrieval_score: float
    overlap_terms: tuple[str, ...]
    semantic_score: float | None = None


# Cosine similarity a passage needs to qualify on meaning alone, for unit-length
# sentence embeddings. It only nominates passages; the verifier still judges them.
# With all-MiniLM-L6-v2, relevant scientific paraphrases score about 0.45-0.55 and
# unrelated passages from the same field 0.2 or less.
MIN_SEMANTIC_SCORE = 0.35
_RRF_K = 60


def _cosine(left, right) -> float:
    return sum(a * b for a, b in zip(left, right))


class EvidenceRetriever:
    """Rank evidence candidates using transparent lexical coverage rules."""

    def retrieve(
        self,
        claim_text: str,
        candidates: list[EvidenceCandidate],
        *,
        top_k: int = 5,
        min_score: float = 0.15,
        claim_embedding: tuple[float, ...] | None = None,
    ) -> list[RetrievedEvidence]:
        """Return the strongest unique passages for a claim.

        The score is the fraction of content-bearing claim terms present in a passage,
        plus a small source-hierarchy bonus. A passage must meet ``min_score`` before
        it is stored as evidence.

        With ``claim_embedding``, a passage also qualifies on meaning (cosine ≥
        ``MIN_SEMANTIC_SCORE``) and lexical and semantic ranks are fused with
        reciprocal rank fusion, so paraphrases are found without dropping exact matches.
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
            semantic = (
                _cosine(claim_embedding, candidate.embedding)
                if claim_embedding is not None and candidate.embedding is not None
                else None
            )
            if retrieval_score < min_score and (
                semantic is None or semantic < MIN_SEMANTIC_SCORE
            ):
                continue

            relation, relation_score = "mentions", 0.0
            ranked.append(
                RetrievedEvidence(
                    candidate=candidate,
                    relation=relation,
                    score=relation_score,
                    retrieval_score=retrieval_score,
                    overlap_terms=tuple(sorted(overlap)),
                    semantic_score=semantic,
                )
            )

        def lexical_key(item):
            return (
                item.retrieval_score,
                item.score,
                _SOURCE_BONUS.get(item.candidate.source_type, 0.0),
                len(item.candidate.evidence_text),
            )

        ranked.sort(key=lexical_key, reverse=True)
        if any(item.semantic_score is not None for item in ranked):
            lexical_rank = {id(item): n for n, item in enumerate(ranked)}
            by_meaning = sorted(
                ranked, key=lambda item: item.semantic_score or -1.0, reverse=True
            )
            semantic_rank = {id(item): n for n, item in enumerate(by_meaning)}
            ranked.sort(
                key=lambda item: (
                    -(
                        1 / (_RRF_K + lexical_rank[id(item)])
                        + 1 / (_RRF_K + semantic_rank[id(item)])
                    ),
                    lexical_rank[id(item)],
                )
            )
        return ranked[:top_k]

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
