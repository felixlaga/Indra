# Phase 3 Background Jobs

Phase 3 introduces a durable job contract between the product API and future
worker processes. The API still does not run research work inline.

## Implemented

- Canonical `JobType` and `JobStatus` enums.
- API `Job` models for enqueue state, leases, completion, failure, retries,
  timeouts, and worker results.
- `jobs` table in the initial Postgres migration.
- `ProductRepository` methods for listing, getting, leasing, completing,
  failing, retrying, cancelling, pausing, resuming, and expiring jobs.
- In-memory backend support for local tests and development.
- Postgres backend support for durable job records and durable job events.
- Worker-facing endpoints:
  - `GET /sessions/{session_id}/jobs`
  - `GET /jobs/{job_id}`
  - `POST /jobs/lease`
  - `POST /jobs/expire`
  - `POST /jobs/{job_id}/complete`
  - `POST /jobs/{job_id}/fail`
- Run-control integration:
  - session start enqueues a `research_session` job
  - branch continue enqueues a `branch_continue` job
  - session pause pauses queued/running jobs
  - session resume requeues paused jobs
  - session cancel cancels queued/running/paused jobs
- `src/jobs/worker.py`, a small worker adapter that leases one job and
  completes or fails it through registered handlers.

## Event Contract

Job operations create visible session events:

- `job_queued`
- `job_started`
- `job_completed`
- `job_retry_scheduled`
- `job_failed`
- `job_timed_out`
- `job_paused`
- `job_resumed`
- `job_cancelled`

Failures and terminal timeouts preserve the job record, store `last_error`, and
mark the affected session or branch failed when the job is tied to that target.

## Deferred

- Real research-core job handlers for `research_session` and `branch_continue`.
- A continuously running worker process entrypoint.
- External distributed queue infrastructure such as Redis, Dramatiq, RQ, Celery,
  or Arq.
- Worker heartbeats and worker registry.
- Dashboard job controls and failure inspector.
- Job pagination and event pagination for large sessions.
