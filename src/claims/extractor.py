"""Deterministic atomic claim extraction for API and worker scaffolding."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedClaim:
    """A claim extracted from generated summary or synthesis text."""

    text: str
    claim_type: str
    status: str
    confidence: float | None = None


class ClaimExtractor:
    """Split text into review-ready atomic claims without validating evidence."""

    _subject_prefixes = (
        "The paper",
        "This paper",
        "The study",
        "This study",
        "The method",
        "This method",
        "The model",
        "This model",
        "The approach",
        "This approach",
    )
    _compound_verbs = (
        "compares",
        "demonstrates",
        "defines",
        "discusses",
        "evaluates",
        "finds",
        "introduces",
        "outperforms",
        "proposes",
        "reports",
        "requires",
        "shows",
        "uses",
    )

    def extract(self, source_text: str, max_claims: int = 20) -> list[ExtractedClaim]:
        """Extract atomic claims from source text."""

        claims: list[ExtractedClaim] = []
        seen: set[str] = set()
        for sentence in self._candidate_sentences(source_text):
            for claim_text in self._split_compound_claim(sentence):
                normalized = self._normalize_claim_text(claim_text)
                if not normalized or self._is_vague(normalized):
                    continue

                dedupe_key = self._dedupe_key(normalized)
                if dedupe_key in seen:
                    continue

                claim_type = self._classify(normalized)
                status = "speculative" if claim_type == "hypothesis" else "needs_review"
                claims.append(
                    ExtractedClaim(
                        text=normalized,
                        claim_type=claim_type,
                        status=status,
                    )
                )
                seen.add(dedupe_key)
                if len(claims) >= max_claims:
                    return claims
        return claims

    def _candidate_sentences(self, source_text: str) -> list[str]:
        lines = []
        for raw_line in source_text.replace("\r\n", "\n").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            line = re.sub(r"^(?:[-*•]|\d+[.)])\s+", "", line)
            lines.append(line)

        if not lines:
            lines = [source_text.strip()]

        sentences: list[str] = []
        for line in lines:
            parts = re.split(r"(?<=[.!?])\s+", line)
            sentences.extend(part.strip() for part in parts if part.strip())
        return sentences

    def _split_compound_claim(self, sentence: str) -> list[str]:
        stripped = sentence.strip().rstrip(".!?")
        if not stripped:
            return []

        for subject in self._subject_prefixes:
            prefix = f"{subject} "
            if not stripped.startswith(prefix):
                continue

            body = stripped[len(prefix):]
            fragments = self._split_subject_body(body)
            if len(fragments) <= 1:
                return [stripped]
            return [f"{subject} {fragment}" for fragment in fragments]

        if ";" in stripped:
            return [part.strip() for part in stripped.split(";") if part.strip()]
        return [stripped]

    def _split_subject_body(self, body: str) -> list[str]:
        verb_pattern = "|".join(self._compound_verbs)
        parts = re.split(
            rf",\s+(?:and\s+)?|\s+and\s+(?=(?:{verb_pattern})\b)",
            body,
        )
        return [
            re.sub(r"^and\s+", "", part.strip())
            for part in parts
            if len(part.strip().split()) >= 2
        ]

    def _normalize_claim_text(self, claim_text: str) -> str | None:
        text = re.sub(r"\s+", " ", claim_text).strip(" -–—\t")
        if not text or not any(char.isalpha() for char in text):
            return None
        if len(text.split()) < 4:
            return None
        return text if text.endswith((".", "!", "?")) else f"{text}."

    def _is_vague(self, claim_text: str) -> bool:
        lower = claim_text.lower().strip(".")
        return lower in {
            "background",
            "conclusion",
            "future work",
            "introduction",
            "related work",
        }

    def _classify(self, claim_text: str) -> str:
        lower = claim_text.lower()
        if any(term in lower for term in ("may ", "might ", "could ", "hypothesis")):
            return "hypothesis"
        if any(term in lower for term in ("limitation", "limited", "constraint")):
            return "limitation"
        if any(term in lower for term in ("assume", "assumption")):
            return "assumption"
        if any(term in lower for term in ("define", "definition", "refers to")):
            return "definition"
        if any(
            term in lower
            for term in ("baseline", "compared", "comparison", "outperform", "than")
        ):
            return "comparison"
        if any(term in lower for term in ("recommend", "should", "future work")):
            return "recommendation"
        if any(
            term in lower
            for term in ("dataset", "evaluate", "experiment", "performance", "result")
        ):
            return "empirical_result"
        if any(
            term in lower
            for term in ("algorithm", "architecture", "method", "pipeline", "system")
        ):
            return "methodological"
        if any(term in lower for term in ("proof", "theorem", "theory")):
            return "theoretical_result"
        return "factual"

    def _dedupe_key(self, claim_text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", claim_text.lower()).strip()
