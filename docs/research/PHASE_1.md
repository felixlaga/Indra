# Phase 1: executable research sessions

This is the next implementation phase from the September product audit. It is separate from the older API-skeleton and canonical-contract phase names.

## What now runs

The dashboard Start action enqueues one durable research job. A separate worker searches the chosen sources, selects a bounded set of papers, fetches their open-access PDFs, persists page-numbered passages, generates a summary and atomic claims, then retrieves and judges evidence across the session's papers. The API does not execute that pipeline in the request handler.

With no model key, the same worker runs search and PDF extraction, saves an explicitly labelled source excerpt, extracts review-ready claims from the abstract, and leaves relevant evidence as `needs_review` with no confidence score. Without an abstract, the excerpt uses normalized PDF text. This fallback is not model validation.

`ResearchPipeline` reuses the existing arXiv/Semantic Scholar adapters, canonical identities, claim extractor, evidence retriever, repository and lifecycle contracts. It replaces the product's missing handler with one bounded pipeline. The legacy `MasterAgent` CLI's recursive branch and hypothesis orchestration is not run by this first product worker.

## Run locally

Create a new database for Indra and configure both processes with the same connection string:

```sh
export INDRA_REPOSITORY_BACKEND=postgres
export INDRA_DATABASE_URL=postgresql://localhost/indra
python -m src.api.migrate
python -m uvicorn src.api.app:app --port 8000
```

In a second terminal with the same environment:

```sh
python -m src.jobs.research_worker
```

For Postgres without pgvector, initialize using `python -m src.api.migrate --without-vectors`. This explicit mode substitutes a nullable float array for the unused embedding column; retrieval currently ranks lexical matches and does not use vector operations. Use the same mode on subsequent migration runs. The migration ledger checks source checksums and prevents silently changing the chosen mode. Existing manually created databases need a reviewed migration adoption; the runner does not guess their state.

Run `npm ci && npm run dev` in `apps/web`. The default source is arXiv, which can run without a provider key. Semantic Scholar remains selectable and may rate-limit its shared unauthenticated pool. Failed providers produce visible warnings while successful sources can still complete.

Enable structured model research by setting `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` in the API and worker environment. Choose an endpoint supporting JSON schema. Calls require strict structured output and validate the result locally; they do not fall back to free-form model text. See [OpenRouter structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs).

## Reliability and trust boundaries

- Start is serialized and idempotent. Pause/resume reuses the durable job. Lease owner plus attempt number fence worker writes and completion. Heartbeats renew the lease; cancellation cancels in-flight asynchronous work. The job also has an absolute attempt timeout.
- Paper identities, discovery links, summaries and claims use stable IDs. A retry skips already persisted summaries and resumes verification checkpoints; a failed later paper does not discard earlier results.
- Session parameters under `parameters.research` bound paper count (default 5, maximum 20), claims per paper (default 5, maximum 10), input size and provider timeouts. `max_model_calls` defaults to 30 (maximum 100), is reserved durably before each model call, and includes verification. Failed requests count against the budget. Each response is capped at 3,000 output tokens. This is a request/token bound, not a currency-denominated billing limit.
- Reaching the budget, or a provider rate limit or daily quota (HTTP 429 that a single wait of up to 30 seconds does not clear), stops model use for the rest of the run instead of failing it. Remaining papers keep labelled source excerpts, remaining claims get retrieved passages without a judgment, and the session completes with `verification_mode: model_partial` and a message naming the reason and how many claims were left for review. A malformed answer or a non-verbatim quote for one claim leaves only that claim for review.
- Tests remove `OPENROUTER_*` variables, because `load_dotenv()` searches parent directories and would otherwise use a developer's real key. Set `INDRA_RUN_LIVE_TESTS=true` to opt in.
- PDFs are capped at 20 MB, 300 pages and one million extracted characters. HTTP redirects are checked for private/local addresses. Scanned/encrypted/unavailable PDFs fall back explicitly to abstract coverage. Page numbers come from the PDF parser. Section titles remain unset rather than invented.
- Retrieval scores are rankings, never truth confidence. Model judgments must quote a verbatim source passage to support or contradict a claim. Missing or malformed model output cannot promote it. Historical evidence is included in subsequent status decisions; contradictions remain visible.
- All candidate passages are treated as untrusted data in model prompts. Hypotheses remain speculative. Source excerpts and generated summaries remain unvalidated unless separately reviewed; validated claims do not automatically validate the entire summary.
- The paper page exposes persisted passages. The session shows queue/progress state and model-free review status. SSE polls durable events, supports cursor resume, and reconnects in the browser. This supports separate processes; LISTEN/NOTIFY and scalable event pagination remain later improvements.

## Verification

```sh
python -m pytest -q
INDRA_TEST_ADMIN_DSN=postgresql://localhost/postgres INDRA_TEST_WITHOUT_VECTORS=1 python -m pytest -q test_research_worker.py
cd apps/web && npm test && npm run typecheck && npm run build
```

Postgres integration tests create and remove a uniquely named test database. They cover concurrent starts, stale leases, pause/resume, cancellation, durable reads, partial-result retries, evidence aggregation, model budgets, and cross-process SSE including API restart. CI uses a pgvector-enabled Postgres service; the local run used Postgres 18 with explicit vector-free mode.

Local verification on September 27, 2026 passed all 118 backend tests (including real Postgres integration), 10 frontend tests, TypeScript checking and the production build. A separate API and worker completed a real arXiv search for `Attention Is All You Need`, persisted 28 passages across 15 PDF pages and three review claims, and displayed the results in the browser after an API restart. This run used the explicit no-model fallback.

The checked-in synthetic semantic regression set includes all four failures reproduced in the audit, numeric/directional comparisons, missing evidence and prompt injection. Run it against a configured model with:

```sh
python -m src.research.evaluate > verification-report.json
```

That command makes 12 model requests and exits nonzero on mismatches. It is a regression probe, not scientific-domain calibration. Live model quality/calibration has not been established without provider credentials. Do not describe fixture-based tests as live model accuracy evidence.

## Remaining after this phase

Recursive Scout orchestration, OpenAlex, domain calibration, cross-paper hypothesis generation, vector retrieval, full session-hub redesign, user accounts, deployment packaging, and large-session scaling remain separate work. Nothing here deploys, merges branches, or enables GitHub branch protection.
