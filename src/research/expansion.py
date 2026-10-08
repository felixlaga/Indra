"""Grow a session's paper network along citations, like a literature snowball.

Backward, the works the session's papers cite most often are the field's shared
foundations. Forward, the works citing them show where the field went next, both
the most influential and the newest. A deeper search on the session's own queries
adds what the citation trail misses. Candidates are ranked by relevance to the
question and by how strongly they connect to the session, and kept as papers
found but not read.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from math import log1p
from typing import Literal

from ..api.models import Paper
from .retrieval import Candidate, rank_candidates, title_key

MAX_EXPANSION = 200
# Seeds whose citing works are fetched: read papers first, then the most cited.
CITER_SEEDS = 50
SEARCH_DEPTH = 50
# Cited by this many session papers: a shared foundation, kept even when its title
# shares no word with the question.
FOUNDATION_CITATIONS = 3

Method = Literal["reference", "citation", "query_search"]


@dataclass
class Lead:
    """A paper reached by expansion and how it connects to the session."""

    paper: Paper
    method: Method
    query: str | None = None
    cited_by: int = 0  # session papers that cite it
    cites: int = 0  # session papers it cites
    rank: Candidate | None = None

    @property
    def links(self) -> int:
        return self.cited_by + self.cites

    @property
    def score(self) -> float:
        relevance = self.rank.score if self.rank else 0.0
        network = min(1.0, log1p(self.links) / log1p(8))
        return 0.65 * relevance + 0.35 * network

    @property
    def kept(self) -> bool:
        on_topic = self.rank is not None and self.rank.on_topic
        return on_topic or self.cited_by >= FOUNDATION_CITATIONS

    def reason(self) -> str:
        if self.method == "reference":
            return f"Cited by {self.cited_by} papers in this session"
        if self.method == "citation":
            return f"Cites {self.cites} papers in this session"
        return f"Found by searching “{self.query}” more deeply"


async def gather_leads(
    client, seeds: list[Paper], queries: list[str], *, want: int, filters: dict
) -> list[Lead]:
    """Candidate papers one citation step from the session, plus deeper search hits."""

    seed_ids = {p.openalex_id for p in seeds if p.openalex_id}
    referenced = Counter(
        ref
        for paper in seeds
        for ref in set((paper.metadata or {}).get("references") or [])
        if ref and ref not in seed_ids
    )
    top_references = [work for work, _ in referenced.most_common(min(3 * want, 200))]
    citer_seeds = [
        p.openalex_id
        for p in sorted(seeds, key=lambda p: -(p.citation_count or 0))
        if p.openalex_id
    ][:CITER_SEEDS]
    per_sort = min(200, 2 * want)
    references, influential, newest, *searched = await asyncio.gather(
        client.works(top_references),
        client.citing(citer_seeds, limit=per_sort, sort="cited_by_count:desc"),
        client.citing(citer_seeds, limit=per_sort, sort="publication_date:desc"),
        *(client.search(q, limit=SEARCH_DEPTH, filters=filters) for q in queries),
    )
    leads = [Lead(p, "reference") for p in references]
    leads += [Lead(p, "citation") for p in influential + newest]
    for query, found in zip(queries, searched):
        leads += [Lead(p, "query_search", query=query) for p in found]
    for lead in leads:
        lead.cited_by = referenced.get(lead.paper.openalex_id or "", 0)
        lead.cites = len(set((lead.paper.metadata or {}).get("references") or []) & seed_ids)
    return leads


def merge_leads(leads: list[Lead], *, known_keys: set[str], known_titles: set[str]) -> list[Lead]:
    """One lead per paper not yet in the session; citation evidence wins over search."""

    priority = {"reference": 0, "citation": 1, "query_search": 2}
    by_key: dict[str, Lead] = {}
    by_title: dict[str, Lead] = {}
    for lead in sorted(leads, key=lambda lead: priority[lead.method]):
        title = title_key(lead.paper.title)
        if lead.paper.canonical_key in known_keys or title in known_titles:
            continue
        if (found := by_key.get(lead.paper.canonical_key) or by_title.get(title)) is None:
            by_key[lead.paper.canonical_key] = by_title[title] = lead
        elif not found.paper.abstract and lead.paper.abstract:
            found.paper = found.paper.model_copy(update={"abstract": lead.paper.abstract})
    return list(by_key.values())


async def choose_leads(
    leads: list[Lead], *, question: str, topic: str, want: int, embedder=None
) -> list[Lead]:
    """The best-connected relevant leads, at most ``want``."""

    candidates = [Candidate(lead.paper) for lead in leads]
    await rank_candidates(question, topic, candidates, embedder)
    for lead, candidate in zip(leads, candidates):
        lead.rank = candidate
    kept = [lead for lead in leads if lead.kept]
    return sorted(kept, key=lambda lead: lead.score, reverse=True)[:want]
