"""Scout planning and session synthesis: model proposals checked against stored evidence.

The model sees claims by short alias (C1, C2…), never raw IDs. Proposals are
accepted only when they reference stored claims, stay within the session's
branch limits, and do not repeat an existing branch question.
"""

import re

from .models import (
    DecisionRecord,
    HypothesisRecord,
    ScoutBranchDraft,
    ScoutPlan,
    SessionSynthesis,
    stable_id,
)

PLAN_INSTRUCTION = (
    "You direct a literature review. Given one research branch's checked claims, decide whether "
    "follow-up searches would materially improve the answer to the session question. Propose at most "
    "{slots} follow-up search queries, each targeting one concrete open issue in these findings: an "
    "unresolved contradiction, a claim with missing evidence, an unexplained mechanism, a method "
    "comparison, a stated limitation, or a closely adjacent area. Each query must be a short academic "
    "search query, different from the existing branch queries. Cite motivating claims by alias. "
    "Propose none if the findings already answer the question or the claims are too thin."
)
SYNTHESIS_INSTRUCTION = (
    "Write an overview of what these checked claims establish about the session question, separating "
    "supported findings from contradicted, unchecked and speculative ones. Then propose at most 5 "
    "testable hypotheses that connect findings from different papers. Each hypothesis must cite "
    "supporting claims by alias from at least two different papers, cite contradicting claims when "
    "they exist, state what evidence is missing, and give concrete next steps. Do not present a "
    "hypothesis as established. Use only the supplied claims."
)
TESTABILITY = {"low": 0.3, "medium": 0.6, "high": 0.9}
MAX_PLAN_CLAIMS = 40
MAX_SYNTHESIS_CLAIMS = 80
# Checked claims first: they carry the most information for planning and synthesis.
STATUS_ORDER = {
    "contradicted": 0,
    "supported": 1,
    "weakly_supported": 2,
    "not_found": 3,
    "needs_review": 4,
    "speculative": 5,
}


def _terms(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}


def similar_query(a: str, b: str, threshold: float = 0.7) -> bool:
    left, right = _terms(a), _terms(b)
    if not left or not right:
        return a.strip().lower() == b.strip().lower()
    return len(left & right) / len(left | right) >= threshold


def claim_table(claims, papers_by_id, limit):
    """Alias claims for the model, most informative first."""

    ordered = sorted(
        claims,
        key=lambda c: (STATUS_ORDER.get(c.status.value, 9), c.created_at, c.id),
    )[:limit]
    aliases, rows = {}, []
    for number, claim in enumerate(ordered, 1):
        alias = f"C{number}"
        aliases[alias] = claim
        paper = papers_by_id.get(claim.paper_id)
        rows.append(
            {
                "alias": alias,
                "claim": claim.claim_text,
                "type": claim.claim_type.value,
                "status": claim.status.value,
                "paper": paper.title if paper else None,
                "year": paper.year if paper else None,
            }
        )
    return aliases, rows


def plan_input(session, branch, claims, papers_by_id, existing_queries, slots):
    aliases, rows = claim_table(claims, papers_by_id, MAX_PLAN_CLAIMS)
    return aliases, {
        "session_question": session.initial_query,
        "branch_query": branch.query,
        "existing_branch_queries": existing_queries,
        "follow_up_slots": slots,
        "claims": rows,
    }


def accept_plan(plan: ScoutPlan, *, leased, branch, aliases, existing_queries, slots, provenance):
    """Turn a model plan into a decision record with bounded, deduplicated child branches."""

    children, dropped, taken = [], [], list(existing_queries)
    for follow in plan.follow_ups:
        reason = None
        claims = [aliases[a].id for a in follow.motivating_claims if a in aliases]
        if len(children) >= slots:
            reason = "The session's branch limit was reached."
        elif any(similar_query(follow.query, q) for q in taken):
            reason = "Repeats an existing branch question."
        elif follow.motivating_claims and not claims:
            reason = "Cited claims that do not exist in this branch."
        if reason:
            dropped.append({"query": follow.query, "reason": reason})
            continue
        taken.append(follow.query)
        children.append(
            ScoutBranchDraft(
                id=stable_id(leased.id, "scout", follow.query.strip().lower()),
                query=follow.query.strip(),
                label=follow.label.strip(),
                rationale=follow.rationale.strip(),
                motivation=follow.motivation,
                motivating_claim_ids=claims,
            )
        )
    if children:
        decision = f"Opened {len(children)} follow-up branch{'es' if len(children) != 1 else ''}."
    else:
        decision = "No follow-up branches were opened."
    return DecisionRecord(
        id=stable_id(leased.id, "scout-decision"),
        branch_id=branch.id,
        decision_type="branch_split",
        decision=decision,
        rationale=plan.assessment,
        input_summary=f"{len(aliases)} claims from branch “{branch.query}”.",
        alternatives=dropped,
        details={"child_branch_ids": [c.id for c in children]},
        provenance=provenance,
        children=children,
    )


def skipped_plan(leased, branch, reason: str) -> DecisionRecord:
    return DecisionRecord(
        id=stable_id(leased.id, "scout-decision"),
        branch_id=branch.id,
        decision_type="branch_split",
        decision="No follow-up branches were opened.",
        rationale=reason,
    )


def skipped_synthesis(leased, reason: str) -> DecisionRecord:
    return DecisionRecord(
        id=stable_id(leased.id, "synthesis-decision"),
        decision_type="hypothesis_generation",
        decision="No session synthesis was written.",
        rationale=reason,
    )


def synthesis_input(session, branches, claims, papers_by_id):
    aliases, rows = claim_table(claims, papers_by_id, MAX_SYNTHESIS_CLAIMS)
    return aliases, {
        "session_question": session.initial_query,
        "branch_queries": [b.query for b in branches if b.status.value != "pruned"],
        "claims": rows,
    }


def _texts(values, limit=300):
    return [v.strip()[:limit] for v in values if v.strip()]


def accept_synthesis(synthesis: SessionSynthesis, *, leased, session, aliases, provenance):
    """Keep only hypotheses whose cited support spans at least two stored papers."""

    accepted, dropped = [], []
    for draft in synthesis.hypotheses:
        support = [aliases[a] for a in dict.fromkeys(draft.supporting_claims) if a in aliases]
        against = [aliases[a] for a in dict.fromkeys(draft.contradicting_claims) if a in aliases]
        papers = list(dict.fromkeys(c.paper_id for c in support if c.paper_id))
        if len(papers) < 2:
            dropped.append(
                {
                    "hypothesis": draft.text,
                    "reason": "Supporting claims did not span two stored papers.",
                }
            )
            continue
        accepted.append(
            HypothesisRecord(
                id=stable_id(leased.id, "hypothesis", draft.text.strip().lower()),
                text=draft.text.strip(),
                rationale=draft.rationale.strip(),
                testability=TESTABILITY[draft.testability],
                risk=draft.risk,
                supporting_claim_ids=[c.id for c in support],
                contradicting_claim_ids=[c.id for c in against],
                supporting_paper_ids=papers,
                missing_evidence=_texts(draft.missing_evidence),
                next_steps=_texts(draft.next_steps),
            )
        )
    decision = DecisionRecord(
        id=stable_id(leased.id, "synthesis-decision"),
        decision_type="hypothesis_generation",
        decision=f"Kept {len(accepted)} of {len(synthesis.hypotheses)} proposed hypotheses.",
        rationale="Hypotheses must cite stored claims from at least two papers; all remain speculative.",
        input_summary=f"{len(aliases)} claims across the session.",
        alternatives=dropped,
        details={"hypothesis_ids": [h.id for h in accepted]},
        provenance=provenance,
    )
    return accepted, decision
