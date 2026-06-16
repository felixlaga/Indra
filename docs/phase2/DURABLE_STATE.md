# Phase 2 Durable State

Phase 2 introduces a Postgres-backed `ProductRepository` implementation while
keeping the in-memory repository as the default development backend.

## Backend Selection

Use the existing repository factory:

```bash
ERLA_REPOSITORY_BACKEND=postgres
ERLA_DATABASE_URL=postgresql://user:password@localhost:5432/erla
```

`ERLA_REPOSITORY_BACKEND=memory` remains the default.

## Implemented

- Postgres repository class at `src/api/postgres_repository.py`.
- Project, session, runtime loop binding, branch, paper read, claim, evidence,
  event, and snapshot methods matching `ProductRepository`.
- Durable event history from the `events` table.
- Process-local SSE subscribers that replay durable events on subscription.
- Runtime root branch creation persisted to `branches`.
- Runtime loop binding persisted to `runtime_loop_bindings`.
- Repository factory selection for `postgres`.
- Static row mapper tests that do not require a live database.

## Schema Additions

The initial migration now includes `runtime_loop_bindings`:

- `session_id`
- `loop_id`
- `loop_number`
- `root_branch_id`
- timestamps

This preserves the API skeleton's session-to-runtime-loop binding across
restarts without treating the runtime loop ID as a canonical durable entity.

## Deferred

- Running migrations against a live Postgres instance.
- Connection pooling.
- Background workers.
- Durable paper ingestion from research execution.
- Durable summary writes from workers.
- Cross-process realtime fanout.
- Auth-scoped user/reviewer identity.

## Verification

The repository can be imported without connecting to Postgres. Actual database
operations require `psycopg` and a migrated database URL.
