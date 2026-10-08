"""Turn a research question into searches and choose the papers worth reading.

As in ERLA's inner loop, a branch searches a larger candidate pool than it reads
and then chooses. The model rewrites a long question into short keyword queries
and picks relevant candidates from their titles and abstracts. Without a model,
or when it fails, the question's topic terms give the query and rank the
candidates, together with sentence-embedding similarity when an embedder is set.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field

from ..api.models import Paper
from ..claims.evidence_retrieval import MIN_SEMANTIC_SCORE
from ..domain.papers import normalize_title
from .models import PaperSelection

logger = logging.getLogger(__name__)

MAX_QUERIES = 3
MAX_QUERY_CHARS = 120
# A question longer than this, or one of several sentences, is rewritten into search
# queries: sources match a pasted question poorly or reject it outright.
MAX_QUERY_WORDS = 6
# Candidates shown to the model, best-ranked first: enough to choose from, small
# enough for a free model's context.
MAX_CANDIDATES = 30
ABSTRACT_CHARS = 400
# Unread candidates kept per branch for the research map.
MAX_DISCOVERED = 60

QUERY_INSTRUCTION = (
    "Turn this research question into at most 3 short search queries for academic databases such "
    "as arXiv and OpenAlex. Each query has 2 to 6 keywords naming the subject itself, without "
    "question words or request words such as gaps, open problems, future directions, impact or "
    "state of the art. Put multi-word technical terms in double quotes. The first query states the "
    "core topic most directly; the others cover a distinct aspect of the question or an established "
    "synonym. Also state the core topic in a few words."
)
SELECTION_INSTRUCTION = (
    "You choose sources for a literature review. From the numbered candidates, choose at most "
    "{wanted} papers that will best answer the question, judging from title and abstract. Prefer "
    "papers that study the question's subject directly, include a review when one is available, "
    "and cover different aspects of the question rather than near-duplicates. Use citations and "
    "recency only to break ties. Leave out papers that are off-topic or only share a word with "
    "the question, even if you then choose fewer than {wanted}. Order the choices from most to "
    "least useful and give a one-sentence reason for each."
)

STOP_WORDS = frozenset(
    """a about above across after again against all also am among an and any are around as at
    be because been before being below between both but by can could did do does doing done
    during each either etc few for from further get got had has have having here how however i
    if in into is it its itself just made make makes may me might more most much must my no nor
    not now of off on once only onto or other our out over own per same should so some such
    than that the their them then there these they this those through to too toward towards
    under until up upon us using very via vs was we well were what whatever when where whether
    which while who whom whose why will with within without would yet you your""".split()
)
# Words that describe the answer wanted rather than the subject searched for.
_REQUEST_WORDS = frozenset(
    """area areas aspect aspects best biggest challenge challenges contradiction contradictions
    current currently direction directions emerging especially explain field fields future gap
    gaps going happening headed heading impact important key largest latest literature main
    major newest next open overview particular particularly progress promising question
    questions recent recently research review specific specifically state status today trend
    trends unknown unknowns unresolved""".split()
)
_TOKEN = re.compile(r"[a-z0-9]+")


def title_key(title: str | None) -> str:
    """A preprint and its journal version have different IDs but one title."""

    return " ".join((normalize_title(title) or "").split())


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def _same(a: str, b: str) -> bool:
    """Stems that share a long prefix: lens/lensing, molecules/molecular, gravity/gravitational."""

    shared = len(os.path.commonprefix([a, b]))
    return shared >= 6 or shared == min(len(a), len(b))


def _stems(text: str | None) -> set[str]:
    return {_stem(t) for t in _TOKEN.findall((text or "").lower()) if len(t) > 2}


def topic_terms(text: str) -> list[str]:
    """Content words of a question in order, without filler or request words."""

    terms: list[str] = []
    for word in _TOKEN.findall(text.lower().replace("’", "'")):
        if (
            len(word) < 3
            or word.isdigit()
            or word in STOP_WORDS
            or word in _REQUEST_WORDS
        ):
            continue
        if not any(_same(_stem(word), _stem(t)) for t in terms):
            terms.append(word)
    return terms


def needs_plan(query: str) -> bool:
    return len(query.split()) > MAX_QUERY_WORDS or bool(re.search(r"[.?!;]\s+\S", query))


def fallback_queries(question: str) -> list[str]:
    """The opening sentence's topic terms, which usually name the subject."""

    first = re.split(r"(?<=[.?!;])\s+", question.strip())[0]
    terms = topic_terms(first) or topic_terms(question)
    if not terms:
        return [" ".join(question.split())[:MAX_QUERY_CHARS]]
    return [" ".join(terms[:5])]


def clean_queries(queries: list[str]) -> list[str]:
    seen, cleaned = set(), []
    for query in queries:
        query = " ".join(query.split())[:MAX_QUERY_CHARS].strip()
        key = query.lower().replace('"', "")
        if len(key) >= 3 and key not in seen:
            seen.add(key)
            cleaned.append(query)
    return cleaned[:MAX_QUERIES]


@dataclass
class Candidate:
    paper: Paper
    lexical: float = 0.0
    semantic: float | None = None
    # Result lists (one per source and query) that found this paper.
    found_in: set[int] = field(default_factory=set)

    @property
    def hits(self) -> int:
        return max(1, len(self.found_in))

    @property
    def score(self) -> float:
        base = (
            self.lexical
            if self.semantic is None
            else (self.lexical + max(self.semantic, 0.0)) / 2
        )
        # Found by several queries or sources: a small, capped signal of centrality.
        return base + 0.05 * min(self.hits - 1, 2)

    @property
    def on_topic(self) -> bool:
        return self.lexical > 0 or (
            self.semantic is not None and self.semantic >= MIN_SEMANTIC_SCORE
        )


def candidate_pool(
    results: list[list[Paper]], *, exclude_keys: set[str], exclude_titles: set[str]
) -> list[Candidate]:
    """Interleave result lists by rank and merge duplicates across queries and sources."""

    by_key: dict[str, Candidate] = {}
    by_title: dict[str, Candidate] = {}
    depth = max((len(r) for r in results), default=0)
    for rank in range(depth):
        for number, ranked in enumerate(results):
            if rank >= len(ranked):
                continue
            paper = ranked[rank]
            title = title_key(paper.title)
            if paper.canonical_key in exclude_keys or title in exclude_titles:
                continue
            found = by_key.get(paper.canonical_key) or by_title.get(title)
            if found is None:
                found = by_key[paper.canonical_key] = by_title[title] = Candidate(paper)
            found.found_in.add(number)
            if not found.paper.abstract and paper.abstract:
                found.paper = found.paper.model_copy(update={"abstract": paper.abstract})
    return list(by_key.values())


def lexical_relevance(terms: list[str], paper: Paper) -> float:
    """Share of topic terms in the title (full weight) or abstract (partial weight)."""

    if not terms:
        return 0.0
    title, abstract = _stems(paper.title), _stems(paper.abstract)
    score = 0.0
    for term in terms:
        stem = _stem(term)
        if any(_same(stem, word) for word in title):
            score += 1.0
        elif any(_same(stem, word) for word in abstract):
            score += 0.6
    return score / len(terms)


async def rank_candidates(
    question: str, topic: str, candidates: list[Candidate], embedder=None
) -> list[Candidate]:
    terms = topic_terms(topic) or topic_terms(question)
    for candidate in candidates:
        candidate.lexical = lexical_relevance(terms, candidate.paper)
    if embedder is not None and candidates:
        texts = [question] + [
            f"{c.paper.title}. {(c.paper.abstract or '')[:1000]}" for c in candidates
        ]
        try:
            vectors = await asyncio.to_thread(embedder.embed, texts)
        except Exception as exc:
            # Lexical ranking still works; a broken embedder must not stop the search.
            logger.warning("Candidate embedding failed; ranking by terms: %s", exc)
        else:
            question_vector = vectors[0]
            for candidate, vector in zip(candidates, vectors[1:]):
                candidate.semantic = sum(a * b for a, b in zip(question_vector, vector))
    return sorted(candidates, key=lambda c: c.score, reverse=True)


def ranked_choice(ranked: list[Candidate], wanted: int) -> list[Candidate]:
    """The best-ranked candidates, leaving out off-topic ones whenever on-topic ones exist."""

    on_topic = [c for c in ranked if c.on_topic]
    return (on_topic or ranked)[:wanted]


def landscape(ranked: list[Candidate]) -> list[Candidate]:
    """On-topic candidates, best first, that the map shows around the papers read."""

    return [c for c in ranked if c.on_topic][:MAX_DISCOVERED]


def selection_input(question: str, shown: list[Candidate], wanted: int) -> dict:
    return {
        "question": question,
        "choose_at_most": wanted,
        "candidates": [
            {
                "candidate": number,
                "title": c.paper.title,
                "year": c.paper.year,
                "venue": c.paper.venue,
                "citations": c.paper.citation_count,
                "abstract": (c.paper.abstract or "")[:ABSTRACT_CHARS] or None,
            }
            for number, c in enumerate(shown, 1)
        ],
    }


def accept_selection(
    selection: PaperSelection, shown: list[Candidate], wanted: int
) -> list[tuple[Candidate, str]]:
    """Valid, distinct choices in the model's order; unknown numbers are dropped."""

    chosen, seen = [], set()
    for choice in selection.selected:
        if 1 <= choice.candidate <= len(shown) and choice.candidate not in seen:
            seen.add(choice.candidate)
            chosen.append((shown[choice.candidate - 1], choice.reason.strip()))
    return chosen[:wanted]
