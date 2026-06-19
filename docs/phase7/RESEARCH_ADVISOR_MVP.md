# Phase 7: Gap, contradiction, and research-advisor analysis

## Current stacked implementation

This branch starts Phase 7 on top of `phase-6-research-maps`.

Implemented so far:

- Deterministic contradiction signals from persisted contradictory evidence.
- Conservative opposing-claim candidates based on lexical overlap plus opposite negation.
- Weak-evidence detection from claim status and evidence coverage.
- Session-processing and evidence-gap signals.
- Open-problem signals derived from limitation claims and explicit gaps.
- Research-navigation recommendations.
- Explicitly speculative, low-confidence hypothesis proposals with missing evidence and next steps.
- `GET /sessions/{session_id}/analysis` through the registered research-map router.
- Focused safety tests and CI inclusion.

## Epistemic boundaries

- An opposing-claim candidate is not semantic proof of contradiction.
- A gap in the current session is not automatically a gap in the scientific field.
- Open problems are signals for review, not verified statements that a problem is genuinely open.
- Generated hypotheses are marked `speculative`, capped at low confidence, and do not claim novelty.
- Recommendations are deterministic navigation actions, not expert scientific judgement.

## Next implementation work

- Add the dashboard research-advisor panel.
- Add contradiction and gap inspectors with source links.
- Add a hypothesis inspector.
- Add tests for the complete API response and frontend states.
- Refine candidate scoring against real multi-paper sessions without treating heuristic scores as probabilities.
