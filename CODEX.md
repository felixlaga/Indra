# CODEX Instructions for ERLA

## 1. Mission

Build ERLA into an evidence-backed research navigator.

ERLA is not primarily a generic chatbot or AI writing autocomplete product. It is a research mission-control dashboard that explores literature, maps research fields, validates claims, detects gaps, and advises researchers.

## 2. Source-of-truth documents

Before coding, read:

1. `PRODUCT_SPEC.md`
2. `ARCHITECTURE.md`
3. `DATA_MODEL.md`
4. `VALIDATION_RULES.md`
5. `AGENT_RULES.md`
6. `UI_UX_SPEC.md`
7. `ROADMAP.md`
8. `TESTING_STRATEGY.md`
9. `CODE_STYLE.md`
10. `CODEX.md`

If implementation conflicts with these documents, update the documents first or explain the conflict.

## 3. Current repo facts

This repo currently has:

- Python package under `src/`.
- Typer CLI in `src/cli.py`.
- FastAPI product API skeleton in `src/api`.
- Product API routes depend on a `ProductRepository` contract, with backend selection through `ERLA_REPOSITORY_BACKEND`; only the `memory` backend is implemented.
- Session creation is wired to a lightweight runtime `LoopState` and root branch through `src/api/research_loop.py`.
- Process-local server-sent event streaming is available at `GET /sessions/{session_id}/events/stream`.
- Deterministic claim extraction lives in `src/claims` and is exposed by `POST /sessions/{session_id}/claims/extract`.
- Deterministic supplied-evidence claim validation lives in `src/claims` and is exposed by `POST /claims/{claim_id}/validate` plus `GET /claims/{claim_id}/evidence`.
- Initial Postgres product schema migration in `migrations/`.
- Prototype dashboard shell in `viewer/` with selectable branch and paper inspectors.
- Config profiles in `src/config/models.yaml`.
- Semantic Scholar provider.
- arXiv provider.
- Composite provider.
- Summarization through OpenRouter-compatible LLMs.
- HaluGate local and HTTP validation.
- Recursive orchestration with InnerLoop, IterationLoop, MasterAgent, BranchManager, ManagingAgent, ReflectionAgent, and Hypothesis generation.
- Convex realtime event client.
- Prototype Convex schema/functions under `convex/`.
- Prototype Vite/React viewer under `viewer/`.

Do not assume there is already a production dashboard, running database, job queue, Postgres-backed repository implementation, automated evidence retrieval, production-grade claim verifier, durable evidence ledger, production-grade event stream, or durable API layer. Treat `src/api`, `migrations/`, `viewer/`, and `convex/` as prototype/skeleton/foundation surfaces unless the source-of-truth docs say otherwise.

## 4. Core product rule

Do not add features that make ERLA a generic chat or writing app before the research navigation workflow is solid.

Prioritize:

- Dashboard.
- Durable state.
- Branch control.
- Paper inspection.
- Claim validation.
- Evidence display.
- Gap analysis.
- Research advising.
- Export.

## 5. Engineering rule

No major feature is complete unless it has:

- Backend implementation.
- Durable state if needed.
- API endpoint if user-facing.
- UI if user-facing.
- Events if long-running.
- Tests.
- Error handling.
- Documentation update.

## 6. Architecture boundaries

Respect this target boundary:

```txt
frontend -> product API -> workers -> research core -> providers/services
                         -> database/events -> frontend
```

Rules:

- Frontend must not call research-core directly.
- API must not run long jobs synchronously.
- Workers may call research-core.
- Research-core should not depend on frontend code.
- HaluGate should remain separately deployable.

## 7. Current code migration

Preserve useful current code:

- `src/semantic_scholar`.
- `src/arxiv`.
- `src/paper_sources`.
- `src/summarize.py`.
- `src/halugate`.
- `src/orchestration`.
- `src/hypothesis`.
- `src/context`.
- `src/llm`.
- `src/storage` where useful.

Do not treat the CLI-first structure as final product architecture.

## 8. Feature implementation order

Default order follows `ROADMAP.md`:

1. Upload or correct the root-level source-of-truth doc bundle.
2. Replace README and `pyproject.toml` metadata.
3. Add product API skeleton.
4. Add database schema and migrations.
5. Add frontend dashboard shell.
6. Wire session creation to the existing research loop.
7. Add event streaming.
8. Add paper and branch inspectors.
9. Add claim extraction.
10. Add claim validation.

The initial scaffold for the immediate priority list now exists, and the first durable-state boundary is the API repository contract/factory. Follow the roadmap phases for the next production work: implement a Postgres-backed repository, workers, dashboard hardening, automated evidence retrieval, and production claim verification.

Do not skip durable state and build only UI mockups.

## 9. Agent implementation rules

All agents must follow `AGENT_RULES.md`.

Use structured outputs.

Store consequential decisions.

Do not invent citations, papers, source passages, or novelty claims.

## 10. Validation implementation rules

All validation-related features must follow `VALIDATION_RULES.md`.

Generated factual content must become atomic claims and be validated.

Unsupported claims must be marked as unsupported or speculative.

The UI must expose evidence.

## 11. UI implementation rules

The dashboard is the primary interface.

Do not make CLI the primary workflow.

Use a serious, dense, research-oriented UI.

Do not build decorative visualizations that are not useful.

The user must always be able to inspect:

- Branch rationale.
- Paper summary.
- Claim evidence.
- Agent decisions.
- Job failures.

## 12. Data rules

Use durable storage for product state.

Do not rely on in-memory state for sessions.

Do not overwrite important generated artifacts without versioning.

Do not delete failed jobs silently.

Do not duplicate papers when external IDs match.

## 13. Error handling

Every external call must handle failure.

External calls include:

- LLM provider.
- Semantic Scholar.
- arXiv.
- PDF download.
- PDF parsing.
- Validation service.
- Database.
- Realtime service.

Failures should create visible events and preserve partial progress.

## 14. Testing requirements

Add tests for:

- Search provider normalization.
- Paper deduplication.
- Branch state transitions.
- Agent output parsing.
- Claim extraction.
- Claim validation.
- Validation failure handling.
- API endpoints.
- Background job retry behavior.

## 15. Commit style

Use focused commits.

Good commit examples:

- `Update README and project metadata`
- `Add project and session API models`
- `Implement branch event stream`
- `Add claim ledger table and migration`
- `Create session dashboard shell`

Bad commit examples:

- `stuff`
- `updates`
- `fix`
- `massive changes`

## 16. When uncertain

If requirements are unclear:

1. Check the source-of-truth docs.
2. Choose the option that improves evidence traceability.
3. Avoid speculative product expansion.
4. Leave a clear TODO with rationale.
5. Do not invent behavior silently.

## 17. Definition of done

A task is done only when:

- Code works.
- Tests pass or test limitations are documented.
- User-facing behavior is visible.
- Errors are handled.
- State is durable where needed.
- Documentation is updated if behavior changed.
