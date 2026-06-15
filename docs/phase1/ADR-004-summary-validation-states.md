# ADR-004: Summary Validation States

Status: Accepted

## Context

Runtime code could return below-threshold generated text as `ValidatedSummary`.
That made partial output look fully eligible for downstream hypotheses.

## Decision

Summary validation status is one of:

- `not_validated`
- `validated`
- `partially_validated`
- `failed_validation`

`ValidatedSummary` is retained only as a narrow compatibility type for fully
validated summaries. `SummaryGenerationResult` preserves generated text,
groundedness, validation details, attempts, errors, and provenance for every
outcome.

## Alternatives Considered

- Drop partial output. Rejected because partial output can be useful for review.
- Rename all runtime summary classes immediately. Rejected as too broad.
- Use groundedness alone as state. Rejected because contradictions and process
failures must be represented separately.

## Consequences

- Partial and failed output can be stored without being promoted.
- Hypothesis generation defaults to validated summaries only.
- NLI contradiction prevents `validated` even with a high groundedness score.

## Compatibility And Migration Notes

Existing code that expects `ValidatedSummary` continues to receive it only when
validation passes. Phase 2 should persist all `SummaryGenerationResult` outcomes
as canonical `Summary` rows where generated text exists.
