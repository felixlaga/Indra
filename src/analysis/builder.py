"""Deterministic Phase 7 gap, contradiction, and research-advice analysis.

The builder consumes persisted session state. It emits inspectable signals and
conservative candidates; it does not claim that lexical opposition proves a
scientific contradiction, that missing session evidence proves a field-wide gap,
or that generated hypotheses are novel or correct.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import re
from typing import Any

from .models import (
    AdvisorRecommendation,
    ContradictionCandidate,
    HypothesisProposal,
    OpenProblem,
    ResearchAdvice,
    ResearchAdviceOverview,
    ResearchGap,
    WeakEvidenceItem,
)

_STOP_WORDS = {
    "about", "after", "also", "among", "and", "are", "based", "been", "between",
    "both", "can", "could", "from", "for", "have", "into", "its", "may", "might",
    "more", "not", "our", "paper", "results", "show", "study", "than", "that", "the",
    "their", "these", "this", "through", "using", "was", "were", "which", "with",
}
_NEGATIONS = {"cannot", "didnt", "doesnt", "failed", "fails", "never", "no", "not", "without"}
_WEAK_STATUSES = {"weakly_supported", "not_found", "needs_review", "contradicted"}
_GROUNDED_STATUSES = {"supported", "weakly_supported"}


class ResearchAdviceBuilder:
    """Construct conservative research-navigation signals from durable state."""

    def build(self, snapshot: Any, research_map: Any) -> ResearchAdvice:
        claims = list(snapshot.claims)
        evidence_by_claim: dict[str, list[Any]] = defaultdict(list)
        for evidence in snapshot.claim_evidence:
            evidence_by_claim[str(evidence.claim_id)].append(evidence)

        contradictions = self._contradictions(claims, evidence_by_claim)
        weak_evidence = self._weak_evidence(claims, evidence_by_claim)
        gaps = self._gaps(snapshot, research_map, weak_evidence)
        open_problems = self._open_problems(claims, gaps)
        recommendations = self._recommendations(contradictions, weak_evidence, gaps)
        hypotheses = self._hypotheses(open_problems)
        return ResearchAdvice(
            session_id=str(snapshot.session.id),
            contradictions=contradictions,
            weak_evidence=weak_evidence,
            gaps=gaps,
            open_problems=open_problems,
            recommendations=recommendations,
            hypotheses=hypotheses,
            overview=self._overview(
                contradictions,
                weak_evidence,
                gaps,
                open_problems,
                hypotheses,
            ),
        )

    def _contradictions(
        self,
        claims: list[Any],
        evidence_by_claim: dict[str, list[Any]],
    ) -> list[ContradictionCandidate]:
        results: list[ContradictionCandidate] = []
        for claim in claims:
            status = self._value(claim.status)
            contradictory_evidence = [
                evidence
                for evidence in evidence_by_claim.get(str(claim.id), [])
                if self._value(evidence.relation) == "contradicts"
            ]
            if status == "contradicted" or contradictory_evidence:
                results.append(
                    ContradictionCandidate(
                        id=self._id("evidence-contradiction", str(claim.id)),
                        kind="evidence_contradiction",
                        status="observed",
                        claim_ids=[str(claim.id)],
                        paper_ids=self._compact([getattr(claim, "paper_id", None)]),
                        branch_ids=self._compact([getattr(claim, "branch_id", None)]),
                        description=claim.claim_text,
                        rationale=(
                            "The persisted claim status or attached evidence records a "
                            "contradicting source relation. This does not by itself identify "
                            "which scientific assumptions explain the conflict."
                        ),
                        score=max(
                            [float(item.score or 0.7) for item in contradictory_evidence]
                            or [float(getattr(claim, "confidence", None) or 0.7)]
                        ),
                    )
                )

        for index, left in enumerate(claims):
            for right in claims[index + 1 :]:
                left_terms = self._terms(left.claim_text)
                right_terms = self._terms(right.claim_text)
                union = left_terms | right_terms
                similarity = len(left_terms & right_terms) / len(union) if union else 0.0
                if similarity < 0.45:
                    continue
                if self._negated(left.claim_text) == self._negated(right.claim_text):
                    continue
                results.append(
                    ContradictionCandidate(
                        id=self._id("opposing-claims", str(left.id), str(right.id)),
                        kind="opposing_claim_candidate",
                        status="candidate",
                        claim_ids=[str(left.id), str(right.id)],
                        paper_ids=self._compact([
                            getattr(left, "paper_id", None),
                            getattr(right, "paper_id", None),
                        ]),
                        branch_ids=self._compact([
                            getattr(left, "branch_id", None),
                            getattr(right, "branch_id", None),
                        ]),
                        description=f"{left.claim_text} ↔ {right.claim_text}",
                        rationale=(
                            "The claims have strong lexical overlap and opposite negation. "
                            "This is a review candidate, not proof of a scientific contradiction."
                        ),
                        score=round(min(0.85, similarity), 4),
                    )
                )
        return sorted(results, key=lambda item: (item.status != "observed", -item.score))

    def _weak_evidence(
        self,
        claims: list[Any],
        evidence_by_claim: dict[str, list[Any]],
    ) -> list[WeakEvidenceItem]:
        items: list[WeakEvidenceItem] = []
        for claim in claims:
            status = self._value(claim.status)
            evidence = evidence_by_claim.get(str(claim.id), [])
            if status not in _WEAK_STATUSES and evidence:
                continue
            if status == "contradicted":
                reason = "The claim has persisted contradictory evidence and cannot be used as fact."
                priority = "high"
            elif status == "not_found":
                reason = "No sufficiently relevant source passage has been found."
                priority = "high"
            elif status == "weakly_supported":
                reason = "Only partial support is currently stored."
                priority = "medium"
            elif status == "needs_review":
                reason = "The claim has not completed evidence review."
                priority = "medium"
            else:
                reason = "No evidence passages are attached to this claim."
                priority = "medium"
            items.append(
                WeakEvidenceItem(
                    claim_id=str(claim.id),
                    claim_text=claim.claim_text,
                    claim_status=status,
                    confidence=getattr(claim, "confidence", None),
                    paper_id=self._optional(getattr(claim, "paper_id", None)),
                    branch_id=self._optional(getattr(claim, "branch_id", None)),
                    evidence_count=len(evidence),
                    reason=reason,
                    priority=priority,
                )
            )
        priority_order = {"high": 0, "medium": 1, "low": 2}
        return sorted(items, key=lambda item: (priority_order[item.priority], item.claim_id))

    def _gaps(
        self,
        snapshot: Any,
        research_map: Any,
        weak_evidence: list[WeakEvidenceItem],
    ) -> list[ResearchGap]:
        gaps: list[ResearchGap] = []
        for item in weak_evidence:
            gaps.append(
                ResearchGap(
                    id=self._id("claim-gap", item.claim_id),
                    gap_type="claim_evidence",
                    title="Claim requires stronger evidence",
                    description=item.claim_text,
                    score=0.9 if item.priority == "high" else 0.65,
                    claim_ids=[item.claim_id],
                    paper_ids=self._compact([item.paper_id]),
                    branch_ids=self._compact([item.branch_id]),
                    caveat="This is a gap in the current session evidence, not necessarily in the research field.",
                )
            )

        grounded_by_branch: Counter[str] = Counter()
        claims_by_paper: Counter[str] = Counter()
        for claim in snapshot.claims:
            if claim.paper_id:
                claims_by_paper[str(claim.paper_id)] += 1
            if claim.branch_id and self._value(claim.status) in _GROUNDED_STATUSES:
                grounded_by_branch[str(claim.branch_id)] += 1

        papers_by_branch: Counter[str] = Counter(
            str(entry.branch_id) for entry in snapshot.papers if entry.branch_id
        )
        for branch in snapshot.branches:
            branch_id = str(branch.id)
            if papers_by_branch[branch_id] and grounded_by_branch[branch_id] == 0:
                gaps.append(
                    ResearchGap(
                        id=self._id("branch-grounding", branch_id),
                        gap_type="branch_grounding",
                        title=f"No grounded synthesis for {branch.label or branch.query}",
                        description=(
                            f"The branch contains {papers_by_branch[branch_id]} papers but no "
                            "supported or weakly supported claims."
                        ),
                        score=0.72,
                        paper_ids=[
                            str(entry.paper_id)
                            for entry in snapshot.papers
                            if str(entry.branch_id) == branch_id
                        ],
                        branch_ids=[branch_id],
                        caveat="This measures session processing coverage, not scientific importance.",
                    )
                )

        for entry in snapshot.papers:
            paper_id = str(entry.paper_id)
            if claims_by_paper[paper_id] == 0:
                gaps.append(
                    ResearchGap(
                        id=self._id("paper-coverage", paper_id),
                        gap_type="paper_claim_coverage",
                        title="Paper has no extracted claims",
                        description=entry.paper.title,
                        score=0.5,
                        paper_ids=[paper_id],
                        branch_ids=self._compact([entry.branch_id]),
                        caveat="The paper may still be relevant; it has not yet been processed into the claim ledger.",
                    )
                )

        if research_map.nodes and research_map.overview.observed_citation_edge_count == 0:
            gaps.append(
                ResearchGap(
                    id=self._id("citation-metadata", str(snapshot.session.id)),
                    gap_type="citation_metadata",
                    title="No session-local citation paths were resolved",
                    description=(
                        "The current persisted metadata did not resolve citation or reference "
                        "paths between papers in this session."
                    ),
                    score=0.4,
                    paper_ids=[node.paper_id for node in research_map.nodes],
                    caveat="This can reflect incomplete provider metadata, not an absence of citations.",
                )
            )
        return sorted(gaps, key=lambda item: (-item.score, item.id))

    def _open_problems(self, claims: list[Any], gaps: list[ResearchGap]) -> list[OpenProblem]:
        problems: list[OpenProblem] = []
        for claim in claims:
            claim_type = self._value(claim.claim_type)
            if claim_type not in {"limitation", "recommendation", "hypothesis"}:
                continue
            source = "limitation_claim" if claim_type == "limitation" else "recommendation_claim"
            problems.append(
                OpenProblem(
                    id=self._id("claim-problem", str(claim.id)),
                    text=claim.claim_text,
                    source=source,
                    score=0.7 if claim_type == "limitation" else 0.55,
                    claim_ids=[str(claim.id)],
                    paper_ids=self._compact([getattr(claim, "paper_id", None)]),
                    branch_ids=self._compact([getattr(claim, "branch_id", None)]),
                    missing_evidence=["Independent evidence that the issue remains unresolved"],
                )
            )

        for gap in gaps[:12]:
            if gap.gap_type == "claim_evidence":
                text = f"What evidence would resolve the claim: {gap.description}"
            elif gap.gap_type == "branch_grounding":
                text = (
                    "Which validated findings would establish the core conclusions for "
                    f"{gap.title.removeprefix('No grounded synthesis for ')}?"
                )
            elif gap.gap_type == "paper_claim_coverage":
                text = f"Which verifiable claims from {gap.description} are relevant to the session question?"
            else:
                text = "Which citation and reference paths are missing from the currently persisted session metadata?"
            problems.append(
                OpenProblem(
                    id=self._id("gap-problem", gap.id),
                    text=text,
                    source="gap_signal",
                    score=min(0.65, gap.score),
                    claim_ids=gap.claim_ids,
                    paper_ids=gap.paper_ids,
                    branch_ids=gap.branch_ids,
                    missing_evidence=[gap.caveat],
                )
            )
        unique: dict[str, OpenProblem] = {}
        for problem in problems:
            unique[self._normalize(problem.text)] = problem
        return sorted(unique.values(), key=lambda item: (-item.score, item.id))[:20]

    def _recommendations(
        self,
        contradictions: list[ContradictionCandidate],
        weak_evidence: list[WeakEvidenceItem],
        gaps: list[ResearchGap],
    ) -> list[AdvisorRecommendation]:
        recommendations: list[AdvisorRecommendation] = []
        for item in contradictions[:5]:
            recommendations.append(
                AdvisorRecommendation(
                    id=self._id("review-contradiction", item.id),
                    priority="high" if item.status == "observed" else "medium",
                    title="Review conflicting evidence",
                    action="Inspect the linked claims and source passages before synthesis.",
                    rationale=item.rationale,
                    claim_ids=item.claim_ids,
                    paper_ids=item.paper_ids,
                    branch_ids=item.branch_ids,
                )
            )
        for item in weak_evidence[:8]:
            recommendations.append(
                AdvisorRecommendation(
                    id=self._id("strengthen-claim", item.claim_id),
                    priority=item.priority,
                    title="Strengthen or remove a weak claim",
                    action=(
                        "Retrieve additional passages, narrow the wording, or keep the "
                        "claim excluded from factual synthesis."
                    ),
                    rationale=item.reason,
                    claim_ids=[item.claim_id],
                    paper_ids=self._compact([item.paper_id]),
                    branch_ids=self._compact([item.branch_id]),
                )
            )
        for gap in gaps:
            if gap.gap_type not in {"branch_grounding", "paper_claim_coverage", "citation_metadata"}:
                continue
            recommendations.append(
                AdvisorRecommendation(
                    id=self._id("address-gap", gap.id),
                    priority="medium" if gap.score >= 0.6 else "low",
                    title=gap.title,
                    action=(
                        "Continue the relevant branch and extract evidence-backed claims."
                        if gap.gap_type != "citation_metadata"
                        else "Enrich persisted citation/reference metadata before interpreting graph sparsity."
                    ),
                    rationale=gap.description + " " + gap.caveat,
                    claim_ids=gap.claim_ids,
                    paper_ids=gap.paper_ids,
                    branch_ids=gap.branch_ids,
                )
            )
        priority_order = {"high": 0, "medium": 1, "low": 2}
        return sorted(recommendations, key=lambda item: (priority_order[item.priority], item.id))[:18]

    def _hypotheses(self, problems: list[OpenProblem]) -> list[HypothesisProposal]:
        proposals: list[HypothesisProposal] = []
        for problem in problems[:8]:
            text = problem.text.strip()
            if not text.endswith("?"):
                text = (
                    "A testable investigation should determine whether "
                    + text[0].lower()
                    + text[1:].rstrip(".")
                    + "."
                )
            proposals.append(
                HypothesisProposal(
                    id=self._id("hypothesis", problem.id),
                    text=text,
                    rationale=(
                        "Generated from an inspectable open-problem signal. It is a planning "
                        "proposal, not a validated fact or a claim of novelty."
                    ),
                    confidence=round(min(0.45, max(0.2, problem.score * 0.6)), 3),
                    testability=(
                        0.6
                        if any(
                            token in text.lower()
                            for token in ["whether", "which", "what", "determine", "measure"]
                        )
                        else 0.4
                    ),
                    source_open_problem_id=problem.id,
                    supporting_claim_ids=problem.claim_ids,
                    supporting_paper_ids=problem.paper_ids,
                    missing_evidence=problem.missing_evidence,
                    next_steps=[
                        "Define a measurable outcome and comparison condition.",
                        "Retrieve independent sources that bear directly on the proposal.",
                        "Record null or contradictory evidence before increasing confidence.",
                    ],
                )
            )
        return proposals

    def _overview(
        self,
        contradictions: list[ContradictionCandidate],
        weak_evidence: list[WeakEvidenceItem],
        gaps: list[ResearchGap],
        open_problems: list[OpenProblem],
        hypotheses: list[HypothesisProposal],
    ) -> ResearchAdviceOverview:
        return ResearchAdviceOverview(
            text=(
                f"The current session contains {len(contradictions)} contradiction signals, "
                f"{len(weak_evidence)} weak-evidence claims, and {len(gaps)} processing or "
                f"evidence gaps. ERLA derived {len(open_problems)} open-problem signals and "
                f"{len(hypotheses)} explicitly speculative hypothesis proposals."
            ),
            contradiction_count=len(contradictions),
            gap_count=len(gaps),
            weak_evidence_count=len(weak_evidence),
            open_problem_count=len(open_problems),
            hypothesis_count=len(hypotheses),
            caveats=[
                "Lexical opposition is a contradiction candidate, not semantic proof.",
                "Session coverage gaps are not automatically field-wide research gaps.",
                "Open problems and hypotheses remain speculative until independently evidenced.",
                "Recommendations are deterministic navigation actions, not expert scientific judgement.",
            ],
        )

    def _terms(self, text: str) -> set[str]:
        normalized = re.sub(r"n't\b", " not", text.lower().replace("’", "'"))
        return {
            token
            for token in re.findall(r"[a-z0-9]+", normalized)
            if len(token) > 2 and token not in _STOP_WORDS
        }

    def _negated(self, text: str) -> bool:
        normalized = re.sub(r"n't\b", " not", text.lower().replace("’", "'"))
        return bool(set(re.findall(r"[a-z0-9]+", normalized)) & _NEGATIONS)

    def _value(self, value: Any) -> str:
        return str(getattr(value, "value", value))

    def _optional(self, value: Any) -> str | None:
        return str(value) if value else None

    def _compact(self, values: list[Any]) -> list[str]:
        return list(dict.fromkeys(str(value) for value in values if value))

    def _normalize(self, text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

    def _id(self, prefix: str, *parts: str) -> str:
        digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]
        return f"{prefix}:{digest}"
