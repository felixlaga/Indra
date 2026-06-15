# ERLA Testing Strategy

## 1. Purpose

ERLA must be trusted by researchers. Testing must cover not only code correctness, but also epistemic behavior: whether the system preserves evidence, labels uncertainty, and avoids unsupported claims.

## 2. Test categories

### 2.1 Unit tests

Use unit tests for pure logic:

- Paper normalization.
- Deduplication.
- Claim parsing.
- Branch state transitions.
- Agent output parsing.
- Config loading.
- Token estimation.
- Validation scoring.

### 2.2 Integration tests

Use integration tests for components working together:

- Search provider -> paper normalization.
- Research session -> branch creation.
- Summary -> claim extraction -> validation.
- Worker -> database -> event creation.
- API -> database.
- API -> job queue.

### 2.3 Contract tests

Use contract tests for external providers:

- Semantic Scholar adapter.
- arXiv adapter.
- HaluGate service.
- LLM provider adapter.

Mock external calls by default. Run live-provider tests only when explicitly enabled.

### 2.4 UI tests

Use UI tests for critical workflows once the frontend exists:

- Create project.
- Start session.
- See branch tree.
- Open paper inspector.
- Open claim inspector.
- Pause/resume run.
- Export.

### 2.5 Epistemic tests

Test whether ERLA handles truth-related cases correctly:

- Supported claim.
- Weakly supported claim.
- Contradicted claim.
- Unsupported claim.
- Speculative hypothesis.
- Missing source text.
- Conflicting papers.

## 3. Required test fixtures

Create fixtures for:

- Paper with abstract only.
- Paper with full text.
- Paper with no text.
- Two papers with same DOI.
- Two papers with same arXiv ID.
- Two papers with contradictory claims.
- Malformed LLM JSON.
- Empty search result.
- Failed PDF parse.
- Failed validation service.

## 4. Tests for current code

Add or preserve tests for:

- `SearchFilters.to_query_params`.
- Semantic Scholar adapter error handling.
- arXiv ID normalization.
- Composite provider deduplication.
- `BranchManager` status transitions.
- `IterationLoop` empty iteration behavior.
- `InnerLoop._parse_selection_response`.
- HaluGate `compute_groundedness`.
- Convex client event payload construction with mocked HTTP.
- Product API skeleton endpoints, session-to-runtime-loop binding, process-local event streaming, claim extraction endpoints, and supplied-evidence claim validation endpoints in `test_api.py`.
- Product API repository backend selection in `test_repository_factory.py`.
- Deterministic claim extraction behavior in `test_claim_extraction.py`.
- Deterministic claim validation behavior in `test_claim_validation.py`.
- Initial database migration structure in `test_database_schema.py`.
- Frontend dashboard shell and inspector build through `npm run build` in `viewer/`.

## 5. Agent tests

Every agent must be tested against malformed outputs.

Example cases:

- Missing required fields.
- Invalid JSON.
- Empty response.
- Out-of-range confidence.
- Paper IDs that do not exist.
- Claims without evidence.
- Hypothesis presented as fact.

Expected behavior:

- Fail gracefully.
- Store failure.
- Use fallback if safe.
- Do not promote unsupported output.

## 6. Validation tests

Validation tests must check:

- Supported claims are marked supported.
- Unsupported claims are not promoted.
- Contradictions are surfaced.
- Evidence passages are stored.
- Speculative claims remain speculative.
- Validation failure does not erase generated content.

## 7. API tests

Once the product API exists, test:

- Project CRUD.
- Session creation.
- Session-to-runtime-loop binding.
- Session start/pause/resume/cancel.
- Branch listing.
- Paper listing.
- Claim extraction.
- Claim validation.
- Claim evidence listing.
- Claim listing.
- Event listing.
- Event streaming.
- Export creation.

## 8. Worker tests

Once workers exist, test:

- Job success.
- Job failure.
- Retry.
- Timeout.
- Partial result preservation.
- Event emission.

## 9. Performance tests

At minimum, test:

- 100 papers in a session.
- 1,000 claims in claim ledger.
- Large event log pagination.
- Graph rendering payload size.
- API response time for dashboard state.

## 10. Live tests

Live external tests must be optional.

Use environment variable:

```txt
ERLA_RUN_LIVE_TESTS=true
```

Do not require live API keys for normal CI.

## 11. CI requirements

CI should run:

- Formatting.
- Type checking where configured.
- Unit tests.
- Integration tests with mocks.
- Frontend build if frontend exists.
- Backend import smoke test.

## 12. Testing rule

A feature that affects research claims, evidence, validation, or agent decisions must have tests before being considered complete.
