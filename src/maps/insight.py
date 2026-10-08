"""Field structure read from a session's citation network.

Themes are communities of papers that cite each other, found by modularity
(Louvain, seeded so results repeat) and named by the words that set them apart
from the other themes. Foundations are the papers the network cites most; the frontier is the
newest work that builds on it. Everything is computed from stored metadata, so
it describes the retrieved network, not the whole field.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from math import log
from statistics import median

import networkx as nx

from .models import FieldInsight, ResearchMapEdge, ResearchMapNode, ResearchTheme

MIN_THEME_SIZE = 3
MAX_THEMES = 12
MAX_LIST = 8
_GENERIC = {
    "about", "after", "also", "among", "analysis", "and", "approach", "are", "based",
    "been", "between", "both", "can", "case", "from", "for", "have", "into", "its",
    "method", "methods", "model", "models", "more", "new", "non", "our", "paper",
    "results", "show", "studies", "study", "than", "that", "the", "their", "these",
    "this", "through", "towards", "under", "using", "via", "was", "were", "which",
    "with", "without", "first", "two", "one", "use", "effect", "effects", "general",
}


def _words(text: str) -> list[str]:
    return [
        w
        for w in re.findall(r"[a-z][a-z0-9-]+", text.lower())
        if len(w) > 2 and w not in _GENERIC
    ]


def communities(paper_ids: list[str], edges: list[ResearchMapEdge]) -> dict[str, str]:
    """Louvain modularity communities over citation links, seeded for repeatable themes.

    Label propagation merges a densely cited field into one community; modularity
    still separates its sub-areas.
    """

    graph = nx.Graph()
    graph.add_nodes_from(paper_ids)
    known = set(paper_ids)
    graph.add_edges_from(
        (e.source_paper_id, e.target_paper_id)
        for e in edges
        if e.observed and e.source_paper_id in known and e.target_paper_id in known
    )
    order = {pid: i for i, pid in enumerate(paper_ids)}
    label: dict[str, str] = {}
    for group in nx.community.louvain_communities(graph, seed=0):
        first = min(group, key=order.__getitem__)
        for pid in group:
            label[pid] = first
    return label


def field_insight(
    nodes: list[ResearchMapNode], edges: list[ResearchMapEdge], texts: dict[str, str]
) -> FieldInsight:
    """Themes, foundations and frontier of the session's paper network.

    Sets each node's ``theme_id``, ``in_network_citations`` and ``cites_in_network``.
    """

    cites = [e for e in edges if e.observed and e.edge_type == "cites"]
    cited_by = Counter(e.target_paper_id for e in cites)
    citing = Counter(e.source_paper_id for e in cites)
    for node in nodes:
        node.in_network_citations = cited_by[node.paper_id]
        node.cites_in_network = citing[node.paper_id]

    labels = communities([n.paper_id for n in nodes], cites)
    groups: dict[str, list[ResearchMapNode]] = defaultdict(list)
    for node in nodes:
        groups[labels[node.paper_id]].append(node)
    kept = sorted(
        (g for g in groups.values() if len(g) >= MIN_THEME_SIZE),
        key=lambda g: (-len(g), min(n.paper_id for n in g)),
    )[:MAX_THEMES]

    # Words that set a theme apart: common in it and much rarer across the network.
    term_counts = [Counter(w for n in g for w in set(_words(texts.get(n.paper_id, "")))) for g in kept]
    overall = sum(term_counts, Counter())
    total = sum(len(g) for g in kept)
    years = [n.year for n in nodes if n.year]
    latest = max(years) if years else None
    themes: list[ResearchTheme] = []
    for index, (group, counts) in enumerate(zip(kept, term_counts)):
        if len(kept) == 1:
            weight = {term: float(count) for term, count in counts.items()}
        else:
            weight = {}
            for term, count in counts.items():
                lift = (count / len(group)) / (overall[term] / total)
                if count >= max(2, 0.1 * len(group)) and lift > 1.1:
                    weight[term] = count * log(lift)
        keywords: list[str] = []
        for term, _ in sorted(weight.items(), key=lambda kv: (-kv[1], kv[0])):
            # "strong" and "strongly" name one idea.
            if len(keywords) < 4 and not any(term[:5] == k[:5] for k in keywords):
                keywords.append(term)
        dated = sorted(n.year for n in group if n.year)
        recent = sum(1 for y in dated if latest is not None and y >= latest - 2)
        key = max(group, key=lambda n: (n.in_network_citations, n.citation_count, n.paper_id))
        theme = ResearchTheme(
            id=f"theme-{index + 1}",
            label=" · ".join(k.capitalize() for k in keywords[:3]) or f"Theme {index + 1}",
            keywords=keywords,
            paper_ids=[n.paper_id for n in group],
            read_count=sum(1 for n in group if n.read),
            earliest_year=dated[0] if dated else None,
            latest_year=dated[-1] if dated else None,
            median_year=int(median(dated)) if dated else None,
            recent_share=round(recent / len(dated), 2) if dated else 0.0,
            emerging=bool(dated) and len(group) >= 4 and recent / len(dated) >= 0.5,
            key_paper_id=key.paper_id,
        )
        themes.append(theme)
        for node in group:
            node.theme_id = theme.id

    foundations = [
        n.paper_id
        for n in sorted(nodes, key=lambda n: (-n.in_network_citations, -n.citation_count, n.paper_id))
        if n.in_network_citations >= 2
    ][:MAX_LIST]
    frontier = [
        n.paper_id
        for n in sorted(
            (n for n in nodes if latest is not None and n.year and n.year >= latest - 1),
            key=lambda n: (-n.cites_in_network, -(n.year or 0), n.paper_id),
        )
        if n.cites_in_network >= 1
    ][:MAX_LIST]

    by_id = {n.paper_id: n for n in nodes}
    parts = [f"The network has {len(nodes)} papers"]
    if themes:
        parts[0] += f" in {len(themes)} citation themes"
    if foundations:
        top = by_id[foundations[0]]
        parts.append(
            f"Its most cited foundation is “{top.title}”"
            + (f" ({top.year})" if top.year else "")
            + f", cited by {top.in_network_citations} papers here"
        )
    emerging = [t.label for t in themes if t.emerging]
    if emerging:
        parts.append("Emerging, with most papers from the last three years: " + "; ".join(emerging))
    if frontier:
        parts.append(f"{len(frontier)} recent papers build directly on this network")
    return FieldInsight(
        summary=". ".join(parts) + ".",
        themes=themes,
        foundation_ids=foundations,
        frontier_ids=frontier,
    )
