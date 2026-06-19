"""Deterministic construction of session-level research maps.

The builder uses only persisted paper metadata, branch assignments, summaries, and
claim state. Citation edges are created only when provider metadata identifies a
paper that is already present in the same session. Lexical similarity is labelled
as an inferred ``related`` relation and is never presented as a citation.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from math import log1p
import re
from statistics import median
from typing import Any, Iterable

from .models import (
    BranchMapSynthesis,
    FieldOverview,
    RelatedPaperRecommendation,
    ResearchMap,
    ResearchMapCluster,
    ResearchMapEdge,
    ResearchMapNode,
    ResearchTimelineBucket,
)

_STOP_WORDS = {
    "about", "after", "also", "among", "and", "are", "based", "been", "between",
    "both", "can", "from", "for", "have", "into", "its", "method", "methods",
    "model", "models", "more", "our", "paper", "results", "show", "study", "than",
    "that", "the", "their", "these", "this", "through", "using", "was", "were",
    "which", "with", "without",
}
_REFERENCE_KEYS = {
    "references", "reference_ids", "referenceids", "reference_papers",
    "referencepapers", "cited_papers", "citedpapers",
}
_CITATION_KEYS = {
    "citations", "citation_ids", "citationids", "citing_papers", "citingpapers",
}
_RELATED_KEYS = {"related", "related_papers", "relatedpapers"}
_IDENTIFIER_KEYS = {
    "id", "paper_id", "paperid", "semantic_scholar_id", "semanticscholarid",
    "corpusid", "doi", "arxiv_id", "arxivid", "openalex_id", "openalexid",
}
_NORMALIZED_REFERENCE_KEYS = {re.sub(r"[^a-z]", "", item) for item in _REFERENCE_KEYS}
_NORMALIZED_CITATION_KEYS = {re.sub(r"[^a-z]", "", item) for item in _CITATION_KEYS}
_NORMALIZED_RELATED_KEYS = {re.sub(r"[^a-z]", "", item) for item in _RELATED_KEYS}
_NORMALIZED_IDENTIFIER_KEYS = {re.sub(r"[^a-z]", "", item) for item in _IDENTIFIER_KEYS}


class ResearchMapBuilder:
    """Build an auditable literature landscape from a session snapshot."""

    def build(self, snapshot: Any) -> ResearchMap:
        session_id = str(snapshot.session.id)
        entries = list(snapshot.papers)
        branches = {str(branch.id): branch for branch in snapshot.branches}
        paper_by_id = {str(entry.paper.id): entry for entry in entries}
        clusters = self._clusters(entries, branches)
        cluster_by_paper = {
            paper_id: cluster.id
            for cluster in clusters
            for paper_id in cluster.paper_ids
        }
        roles = self._roles(entries)
        nodes = [
            ResearchMapNode(
                paper_id=str(entry.paper.id),
                title=entry.paper.title,
                year=entry.paper.year,
                venue=entry.paper.venue,
                branch_id=str(entry.branch_id) if entry.branch_id else None,
                cluster_id=cluster_by_paper.get(str(entry.paper.id), "cluster-unassigned"),
                role=roles[str(entry.paper.id)][0],
                foundational_score=roles[str(entry.paper.id)][1],
                citation_count=max(0, entry.paper.citation_count or 0),
                influential_citation_count=max(
                    0, entry.paper.influential_citation_count or 0
                ),
                selected=bool(entry.selected),
            )
            for entry in entries
        ]
        observed_edges = self._observed_edges(entries)
        recommendations = self._recommendations(entries, observed_edges)
        inferred_edges = [
            ResearchMapEdge(
                id=f"related:{item.source_paper_id}:{item.target_paper_id}",
                source_paper_id=item.source_paper_id,
                target_paper_id=item.target_paper_id,
                edge_type="related",
                observed=False,
                score=item.score,
                provenance="session-local lexical similarity",
            )
            for item in recommendations
            if not self._pair_has_edge(
                observed_edges, item.source_paper_id, item.target_paper_id
            )
        ]
        edges = observed_edges + inferred_edges
        timeline = self._timeline(nodes)
        syntheses = self._branch_syntheses(snapshot, branches, paper_by_id)
        overview = self._overview(snapshot, nodes, edges, clusters)
        return ResearchMap(
            session_id=session_id,
            nodes=nodes,
            edges=edges,
            clusters=clusters,
            timeline=timeline,
            recommendations=recommendations,
            branch_syntheses=syntheses,
            overview=overview,
        )

    def _roles(self, entries: list[Any]) -> dict[str, tuple[str, float]]:
        if not entries:
            return {}
        known_years = [entry.paper.year for entry in entries if entry.paper.year]
        max_year = max(known_years) if known_years else None
        min_year = min(known_years) if known_years else None
        recent_cutoff = (max_year - 2) if max_year is not None else None

        raw_citations = [
            log1p(max(0, entry.paper.citation_count or 0))
            + 0.5 * log1p(max(0, entry.paper.influential_citation_count or 0))
            for entry in entries
        ]
        max_citation_signal = max(raw_citations, default=0.0)
        scored: list[tuple[str, float, bool]] = []
        for entry, citation_signal in zip(entries, raw_citations):
            paper_id = str(entry.paper.id)
            year = entry.paper.year
            if year is None or max_year is None or min_year is None:
                age_signal = 0.0
            elif max_year == min_year:
                age_signal = 0.5
            else:
                age_signal = (max_year - year) / (max_year - min_year)
            citation_normalized = (
                citation_signal / max_citation_signal if max_citation_signal else 0.0
            )
            score = max(0.0, min(1.0, 0.55 * age_signal + 0.45 * citation_normalized))
            is_recent = bool(
                year is not None and recent_cutoff is not None and year >= recent_cutoff
            )
            scored.append((paper_id, score, is_recent))

        eligible = sorted(
            (item for item in scored if not item[2]),
            key=lambda item: item[1],
            reverse=True,
        )
        foundational_ids: set[str] = set()
        if eligible:
            signals = [item[1] for item in eligible]
            threshold = median(signals)
            target_count = max(1, round(len(entries) * 0.2))
            foundational_ids = {
                paper_id
                for paper_id, score, _ in eligible[:target_count]
                if score >= threshold
            }

        result: dict[str, tuple[str, float]] = {}
        score_by_id = {
            candidate_id: (score, recent)
            for candidate_id, score, recent in scored
        }
        for entry in entries:
            paper_id = str(entry.paper.id)
            score, is_recent = score_by_id[paper_id]
            if entry.paper.year is None:
                role = "undated"
            elif paper_id in foundational_ids:
                role = "foundational_candidate"
            elif is_recent:
                role = "recent"
            else:
                role = "established"
            result[paper_id] = (role, score)
        return result

    def _clusters(
        self,
        entries: list[Any],
        branches: dict[str, Any],
    ) -> list[ResearchMapCluster]:
        grouped: dict[str, list[Any]] = defaultdict(list)
        for entry in entries:
            group_id = str(entry.branch_id) if entry.branch_id else "unassigned"
            grouped[group_id].append(entry)

        clusters: list[ResearchMapCluster] = []
        for group_id, group_entries in grouped.items():
            keywords = self._top_terms(
                " ".join(
                    f"{entry.paper.title} {entry.paper.abstract or ''}"
                    for entry in group_entries
                ),
                limit=4,
            )
            branch = branches.get(group_id)
            branch_label = getattr(branch, "label", None) if branch else None
            branch_query = getattr(branch, "query", None) if branch else None
            if branch_label and branch_label.lower() not in {"root", "untitled branch"}:
                label = branch_label
            elif keywords:
                label = " · ".join(term.title() for term in keywords[:2])
            elif branch_query:
                label = str(branch_query)[:64]
            else:
                label = "Unassigned papers"
            clusters.append(
                ResearchMapCluster(
                    id=f"cluster-{group_id}",
                    label=label,
                    paper_ids=[str(entry.paper.id) for entry in group_entries],
                    branch_id=None if group_id == "unassigned" else group_id,
                    keywords=keywords,
                )
            )
        return sorted(clusters, key=lambda cluster: cluster.label.lower())

    def _observed_edges(self, entries: list[Any]) -> list[ResearchMapEdge]:
        identifier_index = self._identifier_index(entries)
        edges: dict[tuple[str, str, str], ResearchMapEdge] = {}
        for entry in entries:
            paper_id = str(entry.paper.id)
            metadata = entry.paper.metadata or {}
            for key, value in self._walk_metadata(metadata):
                normalized_key = re.sub(r"[^a-z]", "", key.rsplit(".", 1)[-1].lower())
                relation: str | None = None
                reverse = False
                if normalized_key in _NORMALIZED_REFERENCE_KEYS:
                    relation = "cites"
                elif normalized_key in _NORMALIZED_CITATION_KEYS:
                    relation = "cites"
                    reverse = True
                elif normalized_key in _NORMALIZED_RELATED_KEYS:
                    relation = "related"
                if relation is None:
                    continue
                for target in self._relation_items(value):
                    matched = self._resolve_target(target, identifier_index)
                    if not matched or matched == paper_id:
                        continue
                    source_id, target_id = (matched, paper_id) if reverse else (paper_id, matched)
                    if relation == "related" and source_id > target_id:
                        source_id, target_id = target_id, source_id
                    edge_key = (source_id, target_id, relation)
                    edges[edge_key] = ResearchMapEdge(
                        id=f"{relation}:{source_id}:{target_id}",
                        source_paper_id=source_id,
                        target_paper_id=target_id,
                        edge_type=relation,
                        observed=True,
                        provenance=f"paper metadata field: {key}",
                    )
        return sorted(edges.values(), key=lambda edge: edge.id)

    def _recommendations(
        self,
        entries: list[Any],
        observed_edges: list[ResearchMapEdge],
    ) -> list[RelatedPaperRecommendation]:
        terms = {
            str(entry.paper.id): self._terms(
                f"{entry.paper.title} {entry.paper.abstract or ''}"
            )
            for entry in entries
        }
        branch_by_paper = {
            str(entry.paper.id): str(entry.branch_id) if entry.branch_id else None
            for entry in entries
        }
        candidates: list[RelatedPaperRecommendation] = []
        paper_ids = sorted(terms)
        for index, source_id in enumerate(paper_ids):
            for target_id in paper_ids[index + 1 :]:
                shared = terms[source_id] & terms[target_id]
                union = terms[source_id] | terms[target_id]
                lexical = len(shared) / len(union) if union else 0.0
                same_branch = (
                    branch_by_paper[source_id] is not None
                    and branch_by_paper[source_id] == branch_by_paper[target_id]
                )
                observed = self._pair_has_edge(observed_edges, source_id, target_id)
                score = min(
                    1.0,
                    lexical + (0.12 if same_branch else 0) + (0.18 if observed else 0),
                )
                if score < 0.16:
                    continue
                reasons = []
                if observed:
                    reasons.append("explicit session citation/reference relation")
                if same_branch:
                    reasons.append("explored in the same research branch")
                if shared:
                    reasons.append(f"shared terms: {', '.join(sorted(shared)[:5])}")
                candidates.append(
                    RelatedPaperRecommendation(
                        source_paper_id=source_id,
                        target_paper_id=target_id,
                        score=round(score, 4),
                        reason="; ".join(reasons) or "session-local lexical similarity",
                        shared_terms=sorted(shared)[:8],
                    )
                )
        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates[:24]

    def _timeline(self, nodes: list[ResearchMapNode]) -> list[ResearchTimelineBucket]:
        years: dict[int, list[str]] = defaultdict(list)
        for node in nodes:
            if node.year is not None:
                years[node.year].append(node.paper_id)
        return [
            ResearchTimelineBucket(year=year, paper_ids=sorted(years[year]))
            for year in sorted(years)
        ]

    def _branch_syntheses(
        self,
        snapshot: Any,
        branches: dict[str, Any],
        paper_by_id: dict[str, Any],
    ) -> list[BranchMapSynthesis]:
        summaries_by_branch: dict[str, list[Any]] = defaultdict(list)
        for summary in snapshot.summaries:
            if summary.branch_id:
                summary_type = getattr(summary.summary_type, "value", summary.summary_type)
                if summary_type == "branch":
                    summaries_by_branch[str(summary.branch_id)].append(summary)
        claims_by_branch: dict[str, list[Any]] = defaultdict(list)
        for claim in snapshot.claims:
            if claim.branch_id:
                claims_by_branch[str(claim.branch_id)].append(claim)
        papers_by_branch: dict[str, list[str]] = defaultdict(list)
        for paper_id, entry in paper_by_id.items():
            if entry.branch_id:
                papers_by_branch[str(entry.branch_id)].append(paper_id)

        result: list[BranchMapSynthesis] = []
        for branch_id, branch in branches.items():
            label = branch.label or branch.query or "Untitled branch"
            summaries = summaries_by_branch.get(branch_id, [])
            if summaries:
                summary = summaries[-1]
                validation = getattr(
                    summary.validation_status,
                    "value",
                    summary.validation_status,
                )
                result.append(
                    BranchMapSynthesis(
                        branch_id=branch_id,
                        label=label,
                        text=summary.text,
                        source="persisted_summary",
                        validation_status=str(validation),
                        paper_ids=sorted(papers_by_branch.get(branch_id, [])),
                    )
                )
                continue

            grounded_claims = [
                claim
                for claim in claims_by_branch.get(branch_id, [])
                if getattr(claim.status, "value", claim.status)
                in {"supported", "weakly_supported"}
            ]
            if grounded_claims:
                result.append(
                    BranchMapSynthesis(
                        branch_id=branch_id,
                        label=label,
                        text=" ".join(claim.claim_text for claim in grounded_claims[:4]),
                        source="validated_claims",
                        validation_status="claim_level",
                        paper_ids=sorted(papers_by_branch.get(branch_id, [])),
                        claim_ids=[str(claim.id) for claim in grounded_claims[:4]],
                    )
                )
                continue

            all_claims = claims_by_branch.get(branch_id, [])
            result.append(
                BranchMapSynthesis(
                    branch_id=branch_id,
                    label=label,
                    text=(
                        f"This branch contains {len(papers_by_branch.get(branch_id, []))} "
                        f"session papers and {len(all_claims)} extracted claims. "
                        "No grounded branch synthesis has been persisted yet."
                    ),
                    source="structural_fallback",
                    paper_ids=sorted(papers_by_branch.get(branch_id, [])),
                )
            )
        return sorted(result, key=lambda item: item.label.lower())

    def _overview(
        self,
        snapshot: Any,
        nodes: list[ResearchMapNode],
        edges: list[ResearchMapEdge],
        clusters: list[ResearchMapCluster],
    ) -> FieldOverview:
        years = [node.year for node in nodes if node.year is not None]
        foundational = [node for node in nodes if node.role == "foundational_candidate"]
        recent = [node for node in nodes if node.role == "recent"]
        observed_citations = [
            edge for edge in edges if edge.observed and edge.edge_type == "cites"
        ]
        status_counts = Counter(
            str(getattr(claim.status, "value", claim.status))
            for claim in snapshot.claims
        )
        if nodes:
            year_phrase = (
                f" from {min(years)} to {max(years)}" if years else " with unknown dates"
            )
            text = (
                f"The session contains {len(nodes)} papers{year_phrase}, grouped into "
                f"{len(clusters)} explainable clusters. {len(foundational)} papers are "
                f"session-relative foundational candidates and {len(recent)} are recent "
                f"relative to the newest retrieved paper. {len(observed_citations)} "
                "citation/reference paths are supported by persisted provider metadata."
            )
        else:
            text = (
                "No papers have been persisted for this session, so no research "
                "landscape can be constructed."
            )
        return FieldOverview(
            text=text,
            paper_count=len(nodes),
            cluster_count=len(clusters),
            edge_count=len(edges),
            observed_citation_edge_count=len(observed_citations),
            foundational_candidate_count=len(foundational),
            recent_paper_count=len(recent),
            earliest_year=min(years) if years else None,
            latest_year=max(years) if years else None,
            claim_status_counts=dict(sorted(status_counts.items())),
            caveats=[
                "Foundational labels are session-relative candidates, not quality judgements.",
                "Related edges are lexical recommendations unless marked observed.",
                "Citation paths appear only when persisted provider metadata resolves to another session paper.",
            ],
        )

    def _identifier_index(self, entries: list[Any]) -> dict[str, str]:
        index: dict[str, str] = {}
        for entry in entries:
            paper = entry.paper
            paper_id = str(paper.id)
            values = [
                paper_id,
                paper.canonical_key,
                paper.semantic_scholar_id,
                paper.arxiv_id,
                paper.doi,
                paper.openalex_id,
                paper.title,
            ]
            for value in values:
                if value:
                    index[self._normalize_identifier(str(value))] = paper_id
            title_year = f"{paper.title}|{paper.year or ''}"
            index[self._normalize_identifier(title_year)] = paper_id
        return index

    def _resolve_target(self, value: Any, index: dict[str, str]) -> str | None:
        candidates: list[str] = []
        if isinstance(value, str):
            candidates.append(value)
        elif isinstance(value, dict):
            for key, item in value.items():
                normalized_key = re.sub(r"[^a-z]", "", str(key).lower())
                if normalized_key in _NORMALIZED_IDENTIFIER_KEYS:
                    if isinstance(item, (str, int)):
                        candidates.append(str(item))
                if normalized_key == "externalids" and isinstance(item, dict):
                    candidates.extend(str(candidate) for candidate in item.values() if candidate)
            title = value.get("title")
            year = value.get("year")
            if title:
                candidates.append(str(title))
                candidates.append(f"{title}|{year or ''}")
        for candidate in candidates:
            match = index.get(self._normalize_identifier(candidate))
            if match:
                return match
        return None

    def _walk_metadata(self, value: Any, prefix: str = "") -> Iterable[tuple[str, Any]]:
        if isinstance(value, dict):
            for key, child in value.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                yield path, child
                yield from self._walk_metadata(child, path)

    def _relation_items(self, value: Any) -> list[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, dict):
            return list(value.values())
        if isinstance(value, (str, int)):
            return [value]
        return []

    def _pair_has_edge(
        self,
        edges: list[ResearchMapEdge],
        left: str,
        right: str,
    ) -> bool:
        return any(
            {edge.source_paper_id, edge.target_paper_id} == {left, right}
            for edge in edges
        )

    def _top_terms(self, text: str, *, limit: int) -> list[str]:
        counts = Counter(
            token
            for token in re.findall(r"[a-z0-9]+", text.lower())
            if len(token) > 2 and token not in _STOP_WORDS
        )
        return [term for term, _ in counts.most_common(limit)]

    def _terms(self, text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-z0-9]+", text.lower())
            if len(token) > 2 and token not in _STOP_WORDS
        }

    def _normalize_identifier(self, value: str) -> str:
        value = value.strip().lower()
        value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value)
        value = re.sub(r"^doi:\s*", "", value)
        value = re.sub(r"^arxiv:\s*", "", value)
        return re.sub(r"[^a-z0-9./|-]+", "", value)
