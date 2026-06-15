# ERLA Phase 1 — Stabilize Canonical Contracts

## Purpose

Phase 1 establishes one coherent domain contract for ERLA before durable Postgres persistence, background workers, or the production frontend are implemented.

The repository currently contains several partially overlapping representations of the same concepts:

- Runtime dataclasses in `src/orchestration/`.
- Product API Pydantic models in `src/api/models.py`.
- Temporary in-memory repository state in `src/api/repository.py`.
- Postgres schema definitions in `migrations/0001_initial_product_schema.sql`.
- Prototype Convex records in `convex/schema.ts`.
- Frontend-specific types and static mock data in `viewer/`.

These representations are not fully aligned. Status enums differ, runtime IDs use short strings while the database uses UUIDs, the API models papers as session-scoped while the database separates global papers from session discovery, and partially validated summaries can currently be returned as `ValidatedSummary`.

Phase 1 eliminates these ambiguities. It does not implement Postgres persistence. It makes Phase 2 mechanical rather than forcing new domain decisions while writing the Postgres adapter.

---

## 1. Phase objective

At the end of Phase 1, ERLA must have:

1. One canonical set of domain identifiers.
2. One canonical set of status and mode enums.
3. A clear separation between global paper identity and session-specific discovery.
4. Explicit summary-generation and validation states.
5. A provenance-safe evidence model.
6. Explicit runtime failure semantics.
7. Centralized and tested state-transition rules.
8. Standard provenance metadata for model-generated artifacts.
9. Lossless mappings between canonical domain models, API schemas, runtime structures, and the planned database schema.
10. Tests that fail whenever one of these contracts drifts.

Phase 1 is complete only when a Postgres repository can be implemented from these contracts without inventing translation rules.

---

## 2. Non-goals

Do not implement in Phase 1:

- A production Postgres repository or connection pool.
- A job queue or background workers.
- Authentication or authorization.
- A production Next.js frontend.
- Automatic evidence retrieval.
- PDF chunking or embeddings.
- A full prompt registry.
- A rewrite of `MasterAgent`, `InnerLoop`, or `IterationLoop`.
- Removal of Convex or the Vite viewer.
- New paper providers or agent capabilities.
- Advanced maps or exports.

The initial SQL migration may be updated when a canonical contract requires it, but the API must not be wired to Postgres yet.

---

## 3. Canonical direction

### 3.1 Domain package

Create a domain package independent of FastAPI, Convex, and database libraries:

```text
src/domain/
  __init__.py
  ids.py
  enums.py
  papers.py
  summaries.py
  claims.py
  evidence.py
  sessions.py
  provenance.py
  transitions.py
  mappings.py
```

The exact split may be simplified if clearer.

Rules:

- Domain modules must not import FastAPI or Convex.
- Domain imports must not initialize models, network clients, or databases.
- Pydantic is appropriate for validated and serialized domain values.
- Dataclasses are appropriate only for simple runtime structures.
- Existing code must be migrated incrementally.

### 3.2 Identifier policy

Durable ERLA entities use full UUID semantics:

- User
- Project
- ResearchSession
- Branch
- Paper
- SessionPaper
- PaperDocument
- PaperChunk
- Summary
- Claim
- ClaimEvidence
- Validation
- Hypothesis
- AgentDecision
- Event
- Export
- Future Job

Provider IDs remain strings and must not be confused with internal IDs.

### 3.3 Paper identity

A paper is global. Its presence in a session or branch is contextual.

```text
Paper
  id
  canonical_key
  provider identifiers
  metadata

SessionPaper
  id
  session_id
  paper_id
  branch_id
  discovery_method
  selection_reason
  selected
  iteration_number
```

`Paper` must not contain `session_id` or `branch_id`.

### 3.4 Summary states

Use one summary model with explicit validation status:

- `not_validated`
- `validated`
- `partially_validated`
- `failed_validation`

A below-threshold summary must never be represented by a type called `ValidatedSummary`.

### 3.5 Evidence provenance

Evidence must identify its source type and a resolvable locator. Supported source types should include:

- `paper_chunk`
- `paper_abstract`
- `paper_metadata`
- `user_upload`
- `manual`
- `external_source`

Do not solve the current API/SQL mismatch by making all provenance fields optional.

### 3.6 Failure versus pruning

- `pruned` is an intentional research decision.
- `failed` is an operational execution outcome.
- Failed branches may be retried.
- Provider or LLM exceptions must not automatically prune a branch.

### 3.7 Generation provenance

Model-generated artifacts must be able to retain:

- Provider.
- Model.
- Prompt name.
- Prompt version.
- Generation parameters.
- Token usage.
- Cost.
- Provider request ID.
- Timestamp.

---

## 4. Work packages

| Piece | Name | Depends on |
|---|---|---|
| 1 | Contract inventory and ADRs | None |
| 2 | Canonical IDs, enums, and primitives | 1 |
| 3 | Paper and SessionPaper separation | 2 |
| 4 | Summary and validation-state redesign | 2 |
| 5 | Evidence and claim contracts | 2, 4 |
| 6 | Session, branch, and transition contracts | 2 |
| 7 | Model and prompt provenance | 2, 4 |
| 8 | API and runtime mapping layer | 3–7 |
| 9 | SQL and prototype schema alignment | 8 |
| 10 | Contract test suite and final audit | 1–9 |

Execute these in order unless a dependency explicitly permits parallel work.

---

# Piece 1 — Contract inventory and architecture decisions

## Goal

Document every representation of the core domain and record decisions before changing implementation code.

## Inspect

```text
src/api/models.py
src/api/repository.py
src/api/research_loop.py
src/orchestration/models.py
src/orchestration/master_agent.py
src/orchestration/state_store.py
src/claims/
src/hypothesis/
src/storage/convex_client.py
migrations/0001_initial_product_schema.sql
convex/schema.ts
viewer/src/
DATA_MODEL.md
VALIDATION_RULES.md
AGENT_RULES.md
ARCHITECTURE.md
PRODUCT_SPEC.md
TESTING_STRATEGY.md
```

## Create

```text
docs/phase1/CONTRACT_INVENTORY.md
docs/phase1/ADR-001-canonical-domain-model.md
docs/phase1/ADR-002-identifier-policy.md
docs/phase1/ADR-003-paper-session-separation.md
docs/phase1/ADR-004-summary-validation-states.md
docs/phase1/ADR-005-evidence-source-model.md
```

`CONTRACT_INVENTORY.md` must compare:

- Entity.
- Runtime representation.
- API representation.
- SQL representation.
- Convex representation.
- Known conflict.
- Canonical decision.
- Migration impact.

Cover at least Project, ResearchSession, Branch, Paper, SessionPaper, Summary, Claim, ClaimEvidence, Validation, Hypothesis, AgentDecision, Event, and Export.

## Acceptance criteria

- All ID and enum mismatches are documented.
- Paper/session-paper conflict is documented.
- Summary validation naming problem is documented.
- Evidence nullability conflict is documented.
- Failure versus prune behavior is documented.
- Each ADR contains context, decision, alternatives, consequences, and migration notes.
- No major implementation refactor is performed.

## Codex prompt

```text
You are working in repository felixlaga/ERLA_2.

Implement Phase 1, Piece 1: contract inventory and architecture decisions.

Objective:
Create a precise inventory of all current ERLA domain representations and record the decisions that later Phase 1 pieces will implement. Do not begin the large refactor.

Inspect at least:
- src/api/models.py
- src/api/repository.py
- src/api/research_loop.py
- src/orchestration/models.py
- src/orchestration/master_agent.py
- src/orchestration/state_store.py
- src/claims/
- src/hypothesis/
- src/storage/convex_client.py
- migrations/0001_initial_product_schema.sql
- convex/schema.ts
- viewer/src/
- DATA_MODEL.md
- VALIDATION_RULES.md
- AGENT_RULES.md
- ARCHITECTURE.md
- PRODUCT_SPEC.md
- TESTING_STRATEGY.md

Create:
- docs/phase1/CONTRACT_INVENTORY.md
- docs/phase1/ADR-001-canonical-domain-model.md
- docs/phase1/ADR-002-identifier-policy.md
- docs/phase1/ADR-003-paper-session-separation.md
- docs/phase1/ADR-004-summary-validation-states.md
- docs/phase1/ADR-005-evidence-source-model.md

Required decisions:
1. Canonical domain models live outside FastAPI, Convex, and database-specific code.
2. Durable ERLA IDs use UUID semantics.
3. Provider IDs remain provider-specific strings.
4. Paper identity is global; session discovery uses SessionPaper.
5. Summary validation distinguishes not_validated, validated, partially_validated, and failed_validation.
6. Evidence has an explicit source type and resolvable provenance.
7. Branch failure is distinct from pruning.
8. Generated artifacts support provider/model/prompt provenance.

CONTRACT_INVENTORY.md must include:
entity, runtime representation, API representation, SQL representation, Convex representation, conflict, canonical decision, migration impact.

For each ADR include:
Status, Context, Decision, Alternatives considered, Consequences, Compatibility and migration notes.

Constraints:
- Do not implement Postgres or workers.
- Do not rewrite orchestration.
- Do not remove Convex or viewer code.
- Do not change runtime behavior unless required for documentation tooling.
- Mark unresolved questions explicitly.

Validate terminology across all created files and report unresolved contradictions.
```

---

# Piece 2 — Canonical IDs, enums, and shared primitives

## Goal

Create a lightweight canonical domain foundation and stop redeclaring primitive contracts.

## Canonical enums

At minimum:

```text
SessionStatus:
  pending, running, paused, completed, cancelled, failed

BranchStatus:
  pending, running, paused, completed, pruned, failed

BranchMode:
  search_summarize, hypothesis, synthesis, gap_analysis

SummaryType:
  paper, branch, session, field, method, contradiction, gap

SummaryValidationStatus:
  not_validated, validated, partially_validated, failed_validation

ClaimType:
  factual, methodological, empirical_result, theoretical_result,
  definition, limitation, assumption, comparison, hypothesis, recommendation

ClaimStatus:
  supported, weakly_supported, contradicted, not_found, speculative, needs_review

EvidenceRelation:
  supports, weakly_supports, contradicts, mentions, insufficient

EventSeverity:
  debug, info, warning, error, critical
```

Add other duplicated enums when centralizing them now clearly prevents drift.

## Identifier implementation

Use `uuid.UUID` directly or simple typed UUID wrappers. Provide helpers to:

- Generate UUID4.
- Parse UUID strings.
- Serialize consistently.
- Reject malformed internal IDs.

Do not hash arbitrary legacy strings into UUIDs.

## Tests

- Valid and invalid parsing.
- JSON/Pydantic serialization.
- Exact enum values.
- Compatibility adapters.
- No new truncated durable IDs.

## Acceptance criteria

- `src/domain` imports without loading ML or network dependencies.
- API models import canonical enums.
- Runtime models use canonical enums or narrow tested adapters.
- Enum values match SQL.
- New durable IDs are full UUIDs.

## Codex prompt

```text
You are working in felixlaga/ERLA_2.

Implement Phase 1, Piece 2: canonical IDs, enums, and shared primitives.

Read first:
- docs/phase1/CONTRACT_INVENTORY.md
- all Piece 1 ADRs
- src/api/models.py
- src/orchestration/models.py
- migrations/0001_initial_product_schema.sql
- convex/schema.ts

Create a lightweight src/domain package that can be imported without initializing torch, transformers, HaluGate, network clients, FastAPI applications, or Convex.

Implement:
1. Canonical UUID-based durable ID types or a simple typed UUID approach.
2. Helpers to create, parse, and serialize durable IDs.
3. Canonical enums for SessionStatus, BranchStatus, BranchMode, SummaryType,
   SummaryValidationStatus, ClaimType, ClaimStatus, EvidenceRelation, and EventSeverity.
4. Other clearly duplicated SQL enums if centralizing them now reduces drift.
5. Explicit separation between ERLA UUIDs and provider IDs such as DOI, arXiv, OpenAlex, and Semantic Scholar.

Migrate:
- src/api/models.py to import canonical enums.
- src/orchestration/models.py to import canonical BranchStatus and BranchMode, or use a narrow compatibility adapter if direct migration is unsafe.
- Any related files that only duplicate these primitives.

Rules:
- Do not generate short IDs for new durable entities.
- API serialization must produce standard UUID strings.
- Legacy conversion must be explicit and tested.
- Do not silently convert arbitrary strings into UUIDs.
- Avoid circular imports and elaborate frameworks.

Tests:
- Valid and invalid UUID parsing.
- Pydantic/JSON serialization.
- Exact enum values.
- New branch or loop durable IDs are not truncated where migrated.
- Existing relevant tests.

Do not redesign Paper, Summary, Evidence, transitions, Postgres, or workers in this piece.

Add a migration note listing any legacy string-ID compatibility that remains.
```

---

# Piece 3 — Paper and SessionPaper separation

## Goal

Separate global paper identity from session and branch discovery context.

## Canonical models

Implement:

- `Paper`
- `PaperAuthor`
- `PaperExternalIds`
- `SessionPaper`
- `PaperDiscoveryMethod`
- A combined API read view where useful.

### Paper fields

- Internal UUID.
- Canonical key.
- Semantic Scholar, arXiv, DOI, and OpenAlex IDs.
- Title, abstract, year, venue, publication date.
- Citation, reference, and influential citation counts.
- URLs and metadata.
- Timestamps.

### SessionPaper fields

- Internal UUID.
- Session ID.
- Optional branch ID.
- Paper ID.
- Discovery method.
- Selection reason.
- Selected flag.
- Iteration number.
- Timestamp.

## Canonical key precedence

1. Normalized DOI.
2. Normalized arXiv ID.
3. Semantic Scholar ID.
4. OpenAlex ID.
5. Normalized title plus year fallback.

Fuzzy title matching is a candidate deduplication heuristic, not permanent identity.

## Tests

- One paper in multiple sessions.
- One paper in multiple branches.
- Canonical-key precedence.
- DOI and arXiv normalization.
- No duplicated global metadata.
- API serialization of a session-paper view.

## Codex prompt

```text
You are working in felixlaga/ERLA_2.

Implement Phase 1, Piece 3: global Paper and contextual SessionPaper separation.

Read:
- docs/phase1/ADR-003-paper-session-separation.md
- src/domain primitives
- src/api/models.py
- src/api/repository.py
- src/semantic_scholar/models.py
- src/paper_sources/deduplication.py
- migrations/0001_initial_product_schema.sql
- DATA_MODEL.md

Implement canonical models for:
- Paper
- PaperAuthor
- PaperExternalIds or equivalent
- SessionPaper
- PaperDiscoveryMethod
- A combined read model such as SessionPaperView where useful

Rules:
- Paper must not contain session_id or branch_id.
- SessionPaper stores session_id, optional branch_id, paper_id, discovery_method,
  selection_reason, selected, iteration_number, and timestamps.
- Provider IDs are metadata, not internal IDs.
- Canonical-key precedence:
  DOI, arXiv ID, Semantic Scholar ID, OpenAlex ID, normalized title+year.
- Fuzzy matching remains only a merge heuristic.

Update API contracts so session paper listing returns global metadata plus contextual discovery metadata without putting session fields on Paper.

The in-memory repository may remain temporarily denormalized internally, but this must be hidden behind explicit mapping methods and documented.

Tests:
- Same paper in two sessions.
- Same paper in two branches.
- DOI normalization and precedence.
- arXiv normalization.
- Provider fallback.
- Title-year fallback.
- Paper, SessionPaper, and read-view serialization.
- Existing paper list and not-found behavior.

Do not implement Postgres, documents, chunks, or network calls.
Document provider-to-domain conversion and temporary repository limitations.
```

---

# Piece 4 — Summary and validation-state redesign

## Goal

Ensure partial and failed validation results are never represented as fully validated summaries.

## Canonical summary

Fields:

- ID.
- Session ID.
- Branch ID.
- Paper ID.
- Summary type.
- Text.
- Groundedness score.
- Validation status.
- Model provenance.
- Timestamps.

Optional runtime result:

```text
SummaryGenerationResult:
  summary
  validation details
  attempts
  accepted_for_downstream_use
  error
```

## Required policy

- Passes configured threshold and no disqualifying contradiction:
  `validated`.
- Useful generated output below threshold:
  `partially_validated`.
- Validation process fails:
  `failed_validation`, while preserving generated text.
- Validation not attempted:
  `not_validated`.

Hypothesis generation consumes only eligible summaries. Default: `validated` only.

## Tests

- Passing summary.
- Partial result.
- Validation exception.
- High score with contradiction.
- No source text.
- Retry behavior.
- Non-default threshold.
- Downstream filtering.

## Codex prompt

```text
You are working in felixlaga/ERLA_2.

Implement Phase 1, Piece 4: summary and validation-state redesign.

Read:
- docs/phase1/ADR-004-summary-validation-states.md
- VALIDATION_RULES.md
- src/orchestration/models.py
- src/orchestration/inner_loop.py
- src/orchestration/iteration_loop.py
- src/hypothesis/generator.py
- src/hypothesis/validator.py
- src/summarize.py
- src/api/models.py
- migrations/0001_initial_product_schema.sql

Fix the current semantic bug where a below-threshold summary can be returned as ValidatedSummary.

Implement:
1. Canonical Summary aligned with SQL.
2. SummaryValidationStatus:
   not_validated, validated, partially_validated, failed_validation.
3. Structured generation/validation result containing generated text, validation status,
   groundedness, details/error, attempt count, and downstream eligibility.
4. Replace or deprecate ValidatedSummary so partial results cannot use that type.
5. Preserve generated text when validation fails or falls below threshold.
6. Hypothesis generation defaults to validated summaries only.
7. Configured threshold is authoritative; do not use 0.7 as an implicit validated state.
8. NLI contradiction prevents validated status even with a high score.

Tests:
- Above threshold and no contradiction.
- Below threshold with useful text.
- Validation exception after generation.
- Contradiction with high score.
- Missing source text.
- Retry behavior.
- Non-default threshold.
- Hypothesis exclusion of partial/failed summaries.
- Serialization and API values.

Do not discard partial output or broadly rewrite InnerLoop.
Document downstream eligibility and any compatibility alias.
```

---

# Piece 5 — Evidence and provenance-safe claim contracts

## Goal

Resolve the API/SQL evidence mismatch and ensure every evidence item has resolvable provenance.

## Models

Implement:

- `EvidenceSourceType`
- `EvidenceLocator`
- `ClaimEvidence`
- `ValidationRecord`
- `ManualClaimReview`

## Source rules

- `paper_chunk`: requires `paper_id` and `chunk_id`.
- `paper_abstract`: requires `paper_id`.
- `paper_metadata`: requires `paper_id` and metadata field.
- `user_upload`: requires upload/document reference.
- `external_source`: requires resolvable URI or source ID.
- `manual`: requires reviewer provenance and remains distinct from source evidence.

Manual acceptance or rejection must not overwrite original automatic validation.

## Tests

- Valid and invalid locator combinations.
- Page ranges.
- Contradiction priority.
- Mentions and insufficient do not promote.
- Manual review preserves automatic state.
- API validation errors.

## Codex prompt

```text
You are working in felixlaga/ERLA_2.

Implement Phase 1, Piece 5: provenance-safe evidence and claim contracts.

Read:
- docs/phase1/ADR-005-evidence-source-model.md
- VALIDATION_RULES.md
- AGENT_RULES.md
- src/domain models
- src/api/models.py
- src/api/repository.py
- src/claims/extractor.py
- src/claims/validator.py
- migrations/0001_initial_product_schema.sql

Resolve:
- API ClaimEvidenceCreate currently permits paper_id=None.
- SQL currently requires paper_id.
- Product requirements permit papers, abstracts, metadata, uploads, external sources, and manual review.

Implement canonical:
- EvidenceSourceType
- EvidenceLocator
- ClaimEvidence
- ValidationRecord
- ManualClaimReview

Source types:
paper_chunk, paper_abstract, paper_metadata, user_upload, manual, external_source.

Validation:
- paper_chunk requires paper_id and chunk_id
- paper_abstract requires paper_id
- paper_metadata requires paper_id and metadata field name
- user_upload requires upload/document reference
- external_source requires a resolvable URI or source identifier
- manual requires reviewer provenance
- page_end cannot precede page_start
- scores remain within 0..1

Claim rules:
- Preserve session, branch, paper, and summary links.
- Automatic ClaimStatus remains separate from manual review.
- Manual review must not erase original automatic validation.
- Deterministic precedence remains contradiction, support, weak support;
  mentions and insufficient never promote.

Adapt API models, in-memory repository handling, deterministic verifier inputs, tests,
documentation, and the SQL migration only as necessary.

Preferred SQL direction:
Add explicit source_type and source locator representation. Do not merely make paper_id nullable without an alternative source identity.

Deliver tests for all source types, malformed locators, manual review, contradictory evidence,
empty evidence, mention-only evidence, and page validation.
```

---

# Piece 6 — Session, branch, and transition contracts

## Goal

Centralize lifecycle rules and separate execution failure from research pruning.

## Session baseline

```text
pending -> running, cancelled
running -> paused, completed, failed, cancelled
paused -> running, failed, cancelled
failed -> explicit retry path
completed -> terminal
cancelled -> terminal
```

## Branch baseline

```text
pending -> running, pruned, failed
running -> paused, completed, pruned, failed
paused -> running, pruned, failed
failed -> explicit retry path
completed -> terminal unless explicitly reopened
pruned -> terminal unless explicitly restored
```

## Required behavior

- Pure shared transition validators.
- Typed invalid-transition errors.
- API and runtime use the same rules.
- Execution exceptions result in `failed`.
- Prune and failure reasons are separate.

## Codex prompt

```text
You are working in felixlaga/ERLA_2.

Implement Phase 1, Piece 6: canonical session and branch transitions.

Read:
- src/domain enums
- src/api/repository.py
- src/api/routes.py
- src/orchestration/models.py
- src/orchestration/branch_manager.py
- src/orchestration/master_agent.py
- migrations/0001_initial_product_schema.sql
- AGENT_RULES.md

Create shared pure transition rules, preferably in src/domain/transitions.py.

Requirements:
1. Session and branch transitions are validated centrally.
2. Invalid transitions raise typed domain errors.
3. API and runtime call the same policy.
4. Operational failure maps to failed, never pruned.
5. Pruned remains an intentional research decision with rationale.
6. Failed entities retain an error reason and have an explicit retry policy.
7. Terminal states are protected.
8. Transition functions perform no repository I/O.

Use the transition matrices in the Phase 1 plan as the baseline.
Inspect current behavior before changing it, especially run_auto exception handling.

Add reason/error fields where needed and map invalid API transitions to HTTP 409.

Tests:
- Table-driven allowed transitions.
- Disallowed transitions.
- Terminal states.
- Retry.
- Prune rationale versus failure reason.
- API start/pause/resume/cancel.
- Runtime iteration exception produces failed.

Do not add workers. Pause and cancel remain state-only in this phase.
Document the final transition matrix and deferred run-attempt decisions.
```

---

# Piece 7 — Model and prompt provenance

## Goal

Standardize provenance for generated summaries, hypotheses, validations, and agent decisions.

## Canonical model

```text
GenerationProvenance:
  provider
  model
  prompt_name
  prompt_version
  temperature
  max_tokens
  token_usage
  cost
  provider_request_id
  generated_at
```

Cost must identify currency and whether it is estimated or provider-reported. Never store secrets.

## Adapter direction

Introduce a structured completion result while retaining compatibility for callers expecting `complete(...) -> str`.

## Codex prompt

```text
You are working in felixlaga/ERLA_2.

Implement Phase 1, Piece 7: model and prompt provenance metadata.

Read:
- CODE_STYLE.md
- AGENT_RULES.md
- src/llm/protocols.py
- src/llm/adapters.py
- src/summarize.py
- src/orchestration/inner_loop.py
- src/orchestration/managing_agent.py
- src/hypothesis/generator.py
- src/api/models.py
- migrations/0001_initial_product_schema.sql

Create canonical provenance models with:
provider, model, prompt_name, prompt_version, temperature, max_tokens,
token usage, cost, provider request ID, generated timestamp.

Requirements:
- Summary, Hypothesis, AgentDecision, and model-backed Validation can carry provenance.
- Prompt version is first-class.
- Never store API keys, headers, or secret-bearing requests.
- Missing usage and cost are valid.
- Cost identifies currency and estimated/provider-reported status.
- Preserve compatibility for complete(...) -> str.

Preferred design:
Introduce LLMCompletion with text and provenance, plus complete_structured() or a compatibility wrapper.

Migrate enough paths to prove the contract:
- paper summarization
- hypothesis generation
- managing-agent outputs or decision records

Do not build a full prompt registry. Assign stable prompt names and initial versions.

Tests:
- Serialization.
- Missing usage/cost.
- Invalid negative tokens/cost.
- Prompt version retention.
- Text-only compatibility.
- Mocked summary or hypothesis includes provenance.

Document prompt naming/versioning and fields Phase 2 must persist.
```

---

# Piece 8 — API and runtime mapping layer

## Goal

Create explicit conversion boundaries between provider data, canonical domain data, runtime data, and API schemas.

## Required mappings

- Provider paper → canonical Paper.
- Paper + SessionPaper → API view.
- Runtime Branch → canonical Branch.
- Canonical Branch → API Branch.
- Runtime summary result → canonical Summary.
- Canonical Summary → API Summary.
- Canonical Claim/Evidence → API.
- Runtime Hypothesis → canonical Hypothesis.
- Canonical Event → API Event.

Mappings must not invent metadata or generate random IDs during reads.

## Codex prompt

```text
You are working in felixlaga/ERLA_2.

Implement Phase 1, Piece 8: explicit provider, runtime, domain, and API mappings.

Read all canonical models and inspect:
- src/api/models.py
- src/api/repository.py
- src/api/research_loop.py
- src/orchestration/models.py
- src/semantic_scholar/models.py
- src/arxiv/adapters.py
- src/paper_sources/composite.py
- src/hypothesis/
- src/claims/

Implement explicit mappings for:
- provider paper -> canonical Paper
- Paper + SessionPaper -> API session-paper view
- runtime Branch -> canonical Branch
- canonical Branch -> API Branch
- runtime summary result -> canonical Summary
- canonical Summary -> API Summary
- canonical Claim and ClaimEvidence -> API schemas
- runtime ResearchHypothesis -> canonical Hypothesis
- canonical Event -> API Event

Rules:
- Do not invent factual metadata.
- Missing optional data remains None.
- Missing required data raises typed MappingError.
- Read mappings never create random IDs.
- Creation mappings receive an ID factory explicitly.
- Preserve timestamps, statuses, external IDs, and provenance.
- Mapping code performs no network or database I/O.

Refactor the in-memory repository and research-loop bridge to use these mappings where practical.

Tests:
- Provider conversion.
- Domain-to-API.
- Runtime branch conversion.
- Summary status preservation.
- Evidence source preservation.
- Hypothesis provenance.
- Round trips where lossless.
- Required-data errors.
- No random ID generation during reads.

Add a mapping matrix to docs/phase1.
```

---

# Piece 9 — Align SQL and prototype schemas

## Goal

Make the initial SQL migration accurately represent the canonical contracts. Convex remains a prototype projection.

## Likely SQL changes

- Evidence source and locator fields.
- Summary provenance.
- Hypothesis provenance.
- Failure reason fields.
- Prompt versions.
- Manual review representation.
- Validation traces.
- Constraints and indexes.

Do not add a jobs table in Phase 1.

## Codex prompt

```text
You are working in felixlaga/ERLA_2.

Implement Phase 1, Piece 9: align the SQL migration and prototype schemas.

Read:
- all docs/phase1 ADRs
- all src/domain models
- src/api/models.py
- migrations/0001_initial_product_schema.sql
- test_database_schema.py
- convex/schema.ts
- DATA_MODEL.md

Compare every canonical durable model to SQL.

Update SQL to represent:
- UUID identifiers
- canonical statuses and modes
- Paper versus SessionPaper
- Summary validation status
- generation provenance
- evidence source types and locators
- automatic validation records
- separate manual review
- failure reasons where canonical
- hypothesis and agent-decision provenance

Preserve existing intent where possible. Add constraints and indexes needed for enforcement.
Do not implement Postgres access or a jobs table.

Convex:
Treat it as a projection, not source of truth.
Either align essential statuses/fields or document exactly what it drops.
Do not expand it into a second production schema.

Tests:
- Extend static schema tests for columns, checks, indexes, and source constraints.
- Add Python-enum versus SQL check alignment tests where practical.
- Prove the ClaimEvidence nullability conflict is resolved.
- Verify Summary, Branch, and Session status values.

Update DATA_MODEL.md and add a Convex schema-difference note.
State explicitly whether real Postgres migration execution remains Phase 2.
```

---

# Piece 10 — Contract tests, cleanup, and final audit

## Goal

Prove the contracts are coherent, remove obsolete duplicates, and determine whether Phase 2 can begin.

## Required tests

- UUID creation, parsing, serialization.
- Exact enum values.
- Paper/SessionPaper separation.
- Summary validation semantics.
- Evidence locator rules.
- Manual versus automatic validation.
- Session and branch transition matrices.
- Failure is not pruning.
- Provider/runtime/domain/API mappings.
- Provenance retention.
- SQL/Python alignment.
- No random IDs in read mappings.

## Cleanup

- Remove duplicate enums.
- Remove misleading old types or deprecate narrowly.
- Fix imports and cycles.
- Preserve prototypes but mark their role.
- Run Python tests and viewer build when affected.

## Completion report

Create:

```text
docs/phase1/PHASE1_COMPLETION_REPORT.md
```

Include:

- Completed work.
- Canonical entity and enum lists.
- Identifier policy.
- Mapping architecture.
- SQL alignment.
- Commands and exact test results.
- Remaining compatibility adapters.
- Known limitations.
- Deferred work.
- Phase 2 readiness and blockers.

## Codex prompt

```text
You are working in felixlaga/ERLA_2.

Implement Phase 1, Piece 10: final contract tests, cleanup, and audit.

Read:
- all docs/phase1 files
- all src/domain files
- modified API, orchestration, claims, hypothesis, and migration files
- TESTING_STRATEGY.md
- CODE_STYLE.md

Audit Pieces 1–9 against implementation. Do not assume documentation is correct.

Add or complete tests for:
1. UUID creation, parsing, serialization.
2. Exact canonical enums.
3. Paper and SessionPaper separation.
4. Summary statuses.
5. Partial summaries never represented as validated.
6. Evidence source/locator validation.
7. Manual review preserves automatic validation.
8. Session and branch transitions.
9. Operational failure produces failed, not pruned.
10. Provider -> domain mappings.
11. Runtime -> domain mappings.
12. Domain -> API mappings.
13. Provenance retention.
14. SQL checks and columns align.
15. API Paper lacks session_id and branch_id.
16. Read mappings never generate random IDs.

Cleanup:
- Remove obsolete duplicate enums.
- Remove misleading types or mark narrow aliases deprecated.
- Fix circular imports and import-time side effects.
- Ensure src/domain imports without heavy services.
- Update stale docs.
- Do not remove prototypes solely because they are non-canonical.

Run:
- full Python tests
- backend import smoke tests
- viewer npm build if TypeScript or Convex changed
- configured lint/type checks

Create docs/phase1/PHASE1_COMPLETION_REPORT.md containing:
- final canonical entities and enums
- identifier policy
- mapping architecture
- SQL alignment
- exact commands and test results
- compatibility adapters
- limitations and deferred work
- Phase 2 readiness
- remaining blockers

Do not conceal failures. Phase 2 may begin only if canonical enums and SQL agree,
durable IDs are UUIDs, Paper/SessionPaper are separate, summary semantics are correct,
evidence provenance is resolvable, transitions are centralized, mappings are explicit,
and contract tests pass.
```

---

## 5. Cross-piece rules

Every Codex piece must follow these rules:

1. Inspect the current implementation and outputs of previous pieces before editing.
2. Keep changes scoped and reviewable.
3. Preserve behavior unless the behavior violates the canonical contract.
4. Do not use silent compatibility fallbacks.
5. Put domain translation in named mappers, not route handlers or UI components.
6. Keep domain imports lightweight.
7. Preserve failed validation, contradictions, partial output, original automatic validation, and decision rationale.
8. Add tests for every changed epistemic or lifecycle contract.
9. State unresolved issues rather than guessing.
10. Report exact test commands and results.

---

## 6. Review checkpoints

After Piece 2:
- Review ID and enum choices before downstream work.

After Pieces 3–5:
- Review entity boundaries and migration implications.

After Piece 6:
- Review lifecycle matrices against intended UI controls.

After Piece 8:
- Verify mappings are genuinely lossless.

After Piece 9:
- Treat the migration as the proposed Phase 2 storage contract.

After Piece 10:
- Do not begin Phase 2 unless the completion report and tests support readiness.

---

## 7. Definition of done

- [ ] Canonical domain package exists.
- [ ] Durable IDs use UUID semantics.
- [ ] Provider IDs are separate.
- [ ] Canonical enums are shared.
- [ ] SQL enums match Python.
- [ ] Paper is global.
- [ ] SessionPaper stores discovery context.
- [ ] Summary validation states are explicit.
- [ ] Partial summaries are not typed as validated.
- [ ] Failed validation preserves output.
- [ ] Evidence always has resolvable provenance.
- [ ] Manual review is separate from automatic validation.
- [ ] Branch failure is separate from pruning.
- [ ] Transitions are centralized.
- [ ] Model and prompt provenance contracts exist.
- [ ] Mappings are explicit.
- [ ] SQL represents canonical durable fields.
- [ ] Convex is documented as a projection.
- [ ] Contract and drift tests pass.
- [ ] Completion report confirms Phase 2 readiness.

---

## 8. Expected result

After Phase 1, ERLA will still use temporary in-memory execution. It will not yet be durable. However, the repository will have one stable vocabulary and one coherent data contract.

That enables Phase 2 to focus on:

```text
Implementing durable Postgres storage without redesigning the domain while writing the adapter.
```
