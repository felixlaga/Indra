# Phase 1 Contract Inventory

This inventory records the current ERLA representations and the canonical
decision implemented by Phase 1. The canonical contracts live in `src/domain`.

| Entity | Runtime representation | API representation | SQL representation | Convex representation | Known conflict | Canonical decision | Migration impact |
|---|---|---|---|---|---|---|---|
| Project | None in orchestration runtime | `src/api/models.py::Project` | `projects` | None | API used string IDs; SQL uses UUID | Durable Project IDs are UUID strings at API edge and UUID in domain/SQL | In-memory repository now creates UUID strings |
| ResearchSession | `LoopState` is runtime-only and not a product session | `ResearchSession` | `research_sessions` | `sessions` projection | Runtime loop ID is not durable session ID | Product session is canonical; runtime loop binding remains compatibility | Postgres adapter persists product session, not `loop_*` IDs |
| Branch | `src/orchestration/models.py::Branch` | `Branch` | `branches` | `branches` projection | Runtime previously used truncated IDs and no failed state | Branch uses UUID semantics, canonical statuses, failure/prune reasons | Existing runtime branch creation now uses full UUID strings |
| Paper | Provider `PaperDetails` and old API session-scoped `Paper` | `Paper` global plus `SessionPaperView` | `papers` | `papers` projection stores session context | API put session and branch fields on Paper | Paper is global; SessionPaper stores discovery context | Repository now separates `_papers` and `_session_papers` |
| SessionPaper | None explicit in runtime | `SessionPaper`, `SessionPaperView` | `session_papers` | Folded into `papers` projection | Prototype mixed paper metadata and discovery context | SessionPaper is the only session/branch discovery record | Postgres adapter should map list-session-papers to read view |
| Summary | `ValidatedSummary`, `SummaryGenerationResult` | `Summary` | `summaries` | `summaries` projection | Partial output could be typed as `ValidatedSummary` | Summary has explicit validation status; `ValidatedSummary` is validated-only compatibility | Hypothesis generation defaults to validated summaries only |
| Claim | Extracted claim dataclass, API `Claim` | `Claim` | `claims` | None | API enums duplicated SQL | Claim types/statuses come from canonical enums | Static SQL tests compare canonical values |
| ClaimEvidence | `EvidenceInput` relation/score only | `ClaimEvidenceCreate`, `ClaimEvidence` | `claim_evidence` | None | API allowed nullable paper without source alternative; SQL required paper | Evidence has `source_type` and source-specific locator fields | SQL adds source constraints and locator fields |
| Validation | HaluGate result objects, deterministic claim verifier result | `ClaimValidationResult` plus domain `ValidationRecord` | `validations` | Chat validation projection | No canonical target/status/provenance | ValidationRecord stores target, validator, status, score, raw result, provenance | Phase 2 persists automatic validation records |
| ManualClaimReview | None | Domain model only | `manual_claim_reviews` | None | Manual override could erase automatic status | Manual review is separate from automatic validation | Add table; no endpoint yet |
| Hypothesis | `ResearchHypothesis` | Domain `Hypothesis` mapping | `hypotheses` | `hypotheses` projection | Runtime IDs may be strings; no provenance | UUID durable Hypothesis plus generation provenance | Runtime keeps compatibility; mapper requires UUID or explicit lookup |
| AgentDecision | Managing agent recommendations | Domain `AgentDecision` | `agent_decisions` | Event payloads only | Decision provenance was ad hoc | Decisions can carry GenerationProvenance | Phase 2 stores decision provenance columns |
| Event | API `Event` | `Event` | `events` | `events` projection | Severity duplicated as raw string | Event severity is canonical enum | API model imports canonical enum |
| Export | None implemented | Domain `Export` | `exports` | None | Roadmap-only entity | Export contract remains durable UUID/status/type | Implementation deferred |

## ID Mismatches

- Product API entities previously used prefixed short strings such as `sess_*`.
- Runtime branch IDs were truncated UUIDs.
- SQL always used `uuid`.
- Convex stores projection IDs as strings or Convex document IDs.

Decision: durable product entities use UUID semantics. Provider IDs remain
provider-specific strings and are never parsed as internal UUIDs.

## Enum Mismatches

- API duplicated session, branch, claim, and evidence enums.
- Runtime branch status lacked `failed`.
- Convex session status lacked `paused` and `cancelled`; branch status lacked `failed`.

Decision: canonical enums live in `src/domain/enums.py`. Convex is aligned for
essential projection statuses but remains non-canonical.

## Paper Conflict

The old API `Paper` carried `session_id`, `branch_id`, and provider `paper_id`.
SQL already separated `papers` from `session_papers`.

Decision: `Paper` is global. `SessionPaper` stores session and branch discovery
context. `SessionPaperView` is the API read view that combines them.

## Summary Conflict

The runtime returned below-threshold useful output as `ValidatedSummary`.

Decision: `ValidatedSummary` now rejects partial or failed validation. Runtime
attempts are represented by `SummaryGenerationResult`, preserving generated text,
groundedness, validation details, attempts, errors, and provenance.

## Evidence Nullability Conflict

The API allowed `paper_id=None`; SQL required `paper_id`. Product requirements
need paper chunks, abstracts, metadata, uploads, external sources, and manual
review.

Decision: `ClaimEvidence` has an explicit `source_type` and source-specific
locator. SQL makes `paper_id` nullable only when another resolvable locator is
required by constraint.

## Failure Versus Pruning

Runtime `run_auto` pruned branches after operational exceptions.

Decision: operational exceptions produce `failed` with `failure_reason`. Pruning
is intentional and records `prune_reason`.

## Unresolved Questions

- Durable Postgres repository implementation remains Phase 2.
- Runtime `LoopState.loop_id` remains a non-durable compatibility ID.
- Convex still drops several production fields and is documented as a projection.
