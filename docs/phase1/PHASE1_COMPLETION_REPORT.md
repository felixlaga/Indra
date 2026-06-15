# Phase 1 Completion Report

## Completed Work

- Created canonical domain package under `src/domain`.
- Added UUID helpers, provider ID separation, canonical enums, paper/session-paper
  models, summary models, evidence locator models, lifecycle transitions,
  provenance models, and mapping helpers.
- Migrated API models to canonical enums.
- Split API paper contracts into global `Paper`, contextual `SessionPaper`, and
  combined `SessionPaperView`.
- Updated in-memory repository IDs to UUID strings.
- Added branch `failed`, `failure_reason`, and `prune_reason` semantics.
- Changed runtime branch creation from truncated IDs to full UUID strings.
- Changed runtime operational exceptions to mark branches `failed` instead of
  pruning them.
- Added `SummaryGenerationResult` and made `ValidatedSummary` validated-only.
- Added structured LLM provenance through `LLMCompletion`.
- Added domain-to-API mapping functions and provider/runtime-to-domain mapping
  functions.
- Updated SQL migration for evidence locators, manual reviews, generation
  provenance, failure/prune reasons, and canonical status fields.
- Aligned essential Convex projection statuses while documenting it as
  non-canonical.
- Added Phase 1 contract tests in `test_phase1_contracts.py`.

## Canonical Entities

- Project
- ResearchSession
- Branch
- Paper
- SessionPaper
- Summary
- Claim
- ClaimEvidence
- ValidationRecord
- ManualClaimReview
- Hypothesis
- AgentDecision
- Event
- Export

## Canonical Enums

- `SessionStatus`: pending, running, paused, completed, cancelled, failed
- `BranchStatus`: pending, running, paused, completed, pruned, failed
- `BranchMode`: search_summarize, hypothesis, synthesis, gap_analysis
- `SummaryType`: paper, branch, session, field, method, contradiction, gap
- `SummaryValidationStatus`: not_validated, validated, partially_validated, failed_validation
- `ClaimType`: factual, methodological, empirical_result, theoretical_result,
  definition, limitation, assumption, comparison, hypothesis, recommendation
- `ClaimStatus`: supported, weakly_supported, contradicted, not_found, speculative, needs_review
- `EvidenceRelation`: supports, weakly_supports, contradicts, mentions, insufficient
- `EvidenceSourceType`: paper_chunk, paper_abstract, paper_metadata,
  user_upload, manual, external_source
- `EventSeverity`: debug, info, warning, error, critical

## Identifier Policy

Durable ERLA entities use UUID semantics and serialize as lowercase UUID
strings at the API edge. Provider IDs remain strings in explicit external ID
fields. Legacy runtime loop IDs are compatibility IDs and are not the durable
session identity.

## Mapping Architecture

- Provider and runtime mappings into domain live in `src/domain/mappings.py`.
- Domain-to-API projections live in `src/api/mappings.py`.
- Read mappings do not create random IDs.
- Creation mappings require an existing ID or explicit ID factory.
- Missing required metadata raises `MappingError`.

## SQL Alignment

`migrations/0001_initial_product_schema.sql` now includes:

- Canonical status values.
- Global paper and session-paper separation.
- Summary validation status.
- Generation provenance columns for summaries, validations, hypotheses, and
  agent decisions.
- Evidence `source_type`, locator fields, and source-specific constraints.
- Separate `manual_claim_reviews`.
- `failure_reason` and `prune_reason`.

Real Postgres execution and repository wiring remain Phase 2.

## Compatibility Adapters

- `ValidatedSummary` remains for old runtime callers, but now rejects partial or
  failed validation states.
- `InnerLoopMode` is a compatibility alias to canonical `BranchMode`.
- The in-memory repository remains temporary and does not populate paper/session
  paper records from workers yet.
- Convex remains a projection and intentionally drops durable contract detail.
- API evidence without a source type defaults to manual `api_user` provenance
  until auth-backed reviewer identity exists.

## Verification Results

Commands run:

- `python -m pytest test_phase1_contracts.py -q`
  - Result: failed because the system Python has no `pytest` module.
- `uv run pytest test_phase1_contracts.py -q`
  - Result: blocked because `uv` needed cache access outside the sandbox and the
    approval path was rejected by the environment usage limit.
- `python -m compileall src/domain src/api src/orchestration src/hypothesis src/llm test_phase1_contracts.py`
  - Result: passed.
- `python -c "import src.domain; print('domain import ok')"`
  - Result: passed.
- `python -c "from src.api.repository import InMemoryRepository; ... create_project ..."`
  - Result: passed; new project ID was a UUID string.
- `python -c "from src.api.repository import InMemoryRepository; ... create_session ..."`
  - Result: passed; session and root branch IDs were UUID strings.
- `npm run build` in `viewer/`
  - Result: passed.
- `python -c "... compare SessionStatus, BranchStatus, SummaryValidationStatus against migration ..."`
  - Result: passed; no missing SQL values.
- API/domain validator smoke commands for malformed evidence locator and secret
  provenance:
  - Result: both failed with expected Pydantic validation errors.

## Known Limitations

- Full Python pytest suite was not run because dependency execution through
  `uv` was blocked by environment approval/usage limits.
- Some tracked `__pycache__` files were touched by compile/import checks. A
  cleanup restore was requested but blocked by the same approval/usage limit.
- No Postgres repository, worker queue, auth, automatic evidence retrieval, or
  production frontend was implemented.
- Runtime `LoopState.loop_id` remains a non-durable compatibility ID.

## Deferred Work

- Implement Postgres repository behind `ProductRepository`.
- Add row mappers for all canonical domain models.
- Persist automatic validation records and manual review records through API
  endpoints.
- Connect worker-driven research execution to durable sessions, branches,
  papers, summaries, claims, evidence, events, hypotheses, and decisions.
- Replace default `api_user` manual provenance with authenticated reviewer
  identity.

## Phase 2 Readiness

The source contract work needed for Phase 2 is implemented: canonical enums and
SQL agree by inspection, durable IDs are UUID-shaped, Paper and SessionPaper are
separate, summary semantics are explicit, evidence provenance is resolvable,
transitions are centralized, and mappings are explicit.

Phase 2 should begin only after the full Python test suite is rerun in an
environment where `uv run pytest` can access its dependency cache.
