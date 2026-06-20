# Phase 7: Gap, contradiction, and research-advisor MVP

## Status

Implemented as a stacked pull request on `phase-6-research-maps`.

## Delivered

- Deterministic contradiction signals from persisted contradictory evidence.
- Conservative opposing-claim candidates based on lexical overlap plus opposite negation.
- Weak-evidence detection from claim status and evidence coverage.
- Claim-evidence, branch-grounding, paper-processing, and citation-metadata gap signals.
- Open-problem signals derived from limitation claims and explicit session gaps.
- Prioritized research-navigation recommendations.
- Explicitly speculative, low-confidence hypothesis proposals with missing evidence and next steps.
- `GET /sessions/{session_id}/analysis` through the registered research-map router.
- Research-advisor dashboard under `/sessions/{session_id}/advisor`.
- Tabs for recommendations, contradictions, gaps, and hypotheses.
- Source links to claim evidence, papers, and the Phase 6 research map.
- Weak-evidence triage table.
- Session shortcuts for both the research map and research advisor.
- Focused safety tests and CI inclusion.

## Epistemic boundaries

- An opposing-claim candidate is not semantic proof of contradiction.
- A gap in the current session is not automatically a gap in the scientific field.
- Open problems are signals for review, not verified statements that a problem is genuinely open.
- Generated hypotheses are marked `speculative`, capped at confidence `0.45`, and do not claim novelty.
- Recommendations are deterministic navigation actions, not expert scientific judgement.
- Heuristic scores are ranking signals, not calibrated probabilities.

## Analysis endpoint

```http
GET /sessions/{session_id}/analysis
```

The response contains:

- `contradictions`
- `weak_evidence`
- `gaps`
- `open_problems`
- `recommendations`
- `hypotheses`
- `overview`

## Hypothesis contract

Every generated proposal includes:

- `status = speculative`
- capped confidence
- testability estimate
- risk label
- source open-problem ID
- supporting claim and paper IDs
- missing evidence
- concrete next steps

These records are research-planning artifacts, not validated claims.

## Verification

```bash
python -m pytest -q \
  test_api_cors.py \
  test_api.py \
  test_claim_evidence_retrieval.py \
  test_research_map.py \
  test_research_advice.py

cd apps/web
npm run typecheck
npm test
npm run build
```

## Known limits

- Lexical contradiction candidates do not perform calibrated natural-language inference.
- Gap detection measures the retrieved session corpus and processing state, not the entire scientific field.
- Hypotheses are deterministic transformations of open-problem signals rather than model-generated domain insights.
- Persistent hypothesis records, user approval workflows, scoring calibration, and large-session analysis caching remain later hardening work.
