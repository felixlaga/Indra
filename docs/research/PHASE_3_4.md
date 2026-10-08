# Phases 3 and 4: event delivery and derived research views

This continues the September product audit after the executable worker and session hub. Phase 3 replaces repeated full-history event polling with ordered, bounded replay and PostgreSQL notifications. Phase 4 moves map and advisor computation out of API requests and caches revisioned results durably.

## Phase 3: ordered event delivery

Migration `0002_ordered_events.sql` backfills per-session sequence numbers in `(created_at, id)` order. A transactional counter assigns subsequent numbers. Unlike a global sequence, a later event in the same session cannot commit ahead of an earlier cursor and be skipped during replay. The event UUID remains stable; SSE frame IDs retain UUID compatibility, while clients may resume with either a UUID or a numeric sequence in `cursor`/`Last-Event-ID`. Invalid, foreign UUID, or future cursors return 409 with a reload instruction.

The API maintains one PostgreSQL LISTEN connection per process. Notifications wake session streams only after commit. Indexed reads from durable events are the source of truth: the listener reconnects and wakes subscribers after an outage, and bounded polling catches missed notifications. SSE reads 100 rows at a time and retains only its current cursor. It performs database reads outside the event loop.

`GET /sessions/{id}/events?after=0&limit=100` returns ascending pages, capped at 500 rows. `before=<sequence>` returns the nearest older page in ascending order. Dashboard snapshots include the latest 200 events, `event_cursor`, `events_has_more`, and the complete `validated_claim_ids` set. Review filters and check counts therefore remain correct when a validation event falls outside the recent window. The event and validation drawers can load older pages. The browser starts streaming from its consistent snapshot cursor and preserves ledger filters through live updates.

## Phase 4: background research views

Migration `0003_research_views.sql` adds a durable, coalesced map/advisor work queue. `GET /sessions/{id}/map` and `/analysis` return their existing models with HTTP 200 when current; otherwise they enqueue work and return HTTP 202 with status and `Retry-After`. These API handlers do not build maps or advice. The frontend polls for up to 60 seconds, cancels polling on navigation, and explains a persistent queued state. HTTP 503 exposes failed computations; the Retry action uses `POST /sessions/{id}/views/retry`.

Run `python -m src.jobs.view_worker` as a separate process against the API's Postgres database. It builds both views from a consistent snapshot and stores their source revision. Lease tokens fence results from an expired or replaced worker. The 120-second lease can be reclaimed after worker death; three abandoned attempts fail visibly until an explicit retry. A lease expiry fences writes; it does not forcibly terminate CPU work. Builder exceptions record a failure and preserve the underlying research. Materialization events do not invalidate their own cache.

Session changes invalidate cached views; progress-only heartbeats do not. Updating a shared paper's metadata invalidates all sessions referencing that paper. A computation overtaken by new input is requeued, and stale payloads are never returned as current. The queue is separate from research lifecycle jobs so completed, cancelled, paused, and pending sessions can all be inspected without changing their status. For the temporary memory backend, the API lifespan runs a background view worker in-process; this mode remains non-durable.

Postgres repository instances lazily open a pool of at most eight connections, with a five-second acquisition timeout and at most 32 waiting requests. API and standalone workers close pools on shutdown. Map ranking now keeps only the best 24 related-paper candidates and uses constant-time citation-pair lookups. Advisor comparisons tokenize each claim once and avoid comparing claims with the same negation state. These optimizations preserve existing deterministic output; heuristic contradiction candidates and hypotheses remain explicitly uncertain. Claim extraction and supplied evidence text are capped at 100,000 characters each.

## Run and upgrade

Install the updated locked dependencies with `uv sync --locked`. Stop API and worker processes before applying migrations, then restart them with the same database configuration:

```sh
export INDRA_REPOSITORY_BACKEND=postgres
export INDRA_DATABASE_URL=postgresql://localhost/indra
uv run python -m src.api.migrate
uv run uvicorn src.api.app:app --port 8000 --timeout-graceful-shutdown 5
# Separate terminals with the same environment:
uv run python -m src.jobs.research_worker
uv run python -m src.jobs.view_worker
```

Continue using `--without-vectors` for databases originally initialized in that mode. Do not edit an already-applied migration or change its vector mode. The graceful-shutdown bound allows deployment to close long-lived SSE connections; clients reconnect from their cursor. The listener requires a direct/session-compatible PostgreSQL connection supporting LISTEN, not a transaction-only proxy. Durable polling still delivers events while notification delivery is unavailable.

## Verification — October 3, 2026

- 137 backend tests passed against memory and real local PostgreSQL, including migration reruns, concurrent writes, commit/rollback ordering, cursor bounds, listener reconnection, cross-process SSE/API restart, cached-result reconstruction, global-paper invalidation, stale leases, failure/retry, and background memory previews.
- One live HaluGate model-download test is intentionally skipped unless `INDRA_RUN_LIVE_TESTS=true`. The initial unrestricted test run hit a model-cache permission failure; live model quality was not tested. No model credentials were used for this phase.
- 21 frontend tests, TypeScript checking and the production build passed. Added coverage includes queued responses, completed payloads, polling cancellation/timeouts, and review history beyond the recent event window.
- Served browser checks covered queued-view timeout and Retry after starting a separate worker, graph/advisor readiness, older validation-event loading, an older reviewed claim's filter result, live claim updates with that filter preserved, and reconnection after terminating the original API process. Browser console had no captured errors.

A local synthetic scale probe used 1,500 papers and 1,000 claims. On the same snapshot, baseline `7566cea` builders took 17.077 seconds for the map and 8.260 seconds for advice; the optimized versions took 3.203 and 0.128 seconds respectively and returned exactly equal JSON outputs. A cold HTTP map request queued work in 8.51 ms. A separate worker process built and persisted both views in 2.063 seconds. Ten subsequent map requests had a 22.57 ms median and 25.99 ms maximum. These are local single-fixture observations, not deployment or scientific-quality measurements.

Recheck with:

```sh
INDRA_TEST_ADMIN_DSN=postgresql://localhost/postgres INDRA_TEST_WITHOUT_VECTORS=1 uv run pytest -q
cd apps/web
npm ci
npm run typecheck
npm test
npm run build
```

## Next work and boundaries

Accounts/project authorization and keeping API credentials behind a server boundary are the next platform phase, followed by deployment packaging. The older `ROADMAP.md` numbering describes historical product surfaces; this document continues `docs/research/PHASE_1.md` and `PHASE_2.md`.

This slice does not implement database pagination for papers/claims, graph virtualization, asynchronous export downloads, cache eviction, or distributed model inference. The dashboard still loads full paper/claim snapshots, and explicitly loading older event pages grows browser history. Exports remain synchronous. Research views must be invalidated or versioned when future deployments change builder semantics. Recursive Scouts, OpenAlex, real cross-paper hypothesis generation, user accounts, and scientific-domain model calibration remain separate work. No deployment, push, merge, or branch-protection changes were made.
