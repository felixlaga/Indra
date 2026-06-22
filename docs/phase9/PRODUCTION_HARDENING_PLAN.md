# Phase 9: Production Hardening Plan

## Overview

This document outlines the work required to take the Indra research navigator from the Phase 8 exports milestone to a robust production service. The plan is divided into logical phases with suggested pull requests (PRs) for each group of tasks. Teams can execute phases sequentially or overlap them as resources allow. Each PR should include unit/integration tests, documentation updates and follow the coding standards defined in `CODE_STYLE.md`.

## Phase 9.1: Integrate durable background jobs with the research core

- **Goal** – Connect the existing durable job queue to the complete `MasterAgent` and research‑core orchestration so that long‑running actions (search, summarization, claim extraction, validation, map construction) run in the worker process instead of the API.
- **Tasks**:
  - Extend `src/jobs/worker.py` to call the research core functions for search, summarization, claim extraction, validation, citation graph building, gap and contradiction analysis and export generation.
  - Ensure jobs emit events via the repository so that the dashboard updates in real time.
  - Add tests for worker job execution and partial‑result preservation.
- **Suggested PR** – `connect-workers-to-research-core`

## Phase 9.2: Resumable cross‑process event streaming

- **Goal** – Replace the process‑local Server‑Sent Events (SSE) stream with a durable, resumable event mechanism suitable for multi‑process deployments.
- **Tasks**:
  - Select an event transport (for example Postgres `LISTEN/NOTIFY`, Redis Pub/Sub or a message broker) and implement an `EventPublisher`/`EventSubscriber` abstraction.
  - Modify the API SSE endpoint to accept a `cursor` parameter so clients can resume streams.
  - Store events durably and use the chosen transport to push new events to connected clients.
  - Update frontend code to reconnect with the cursor.
  - Add tests that restart the API process and confirm that the frontend receives a continuous event stream.
- **Suggested PR** – `resumable-event-stream`

## Phase 9.3: Authentication and authorization

- **Goal** – Introduce user accounts and per‑project authorization so that multiple researchers can safely use the same deployment.
- **Tasks**:
  - Add `users` and `memberships` tables to the database; integrate JWT or session‑based authentication.
  - Protect API endpoints with authentication middleware; require authenticated users to own or be a member of a project to access it.
  - Update the dashboard to support sign‑in, sign‑up and sign‑out.
  - Add role‑based authorization checks for project and session actions.
- **Suggested PR** – `auth-and-permissions`

## Phase 9.4: Full‑text evidence retrieval and calibrated claim verification

- **Goal** – Enhance claim validation by retrieving full‑text passages and using calibrated inference models to verify claims.
- **Tasks**:
  - Expose full‑text paper chunks from the repository for evidence retrieval via the API.
  - Integrate a retrieval model (for example dense vector search) to select relevant passages for each claim.
  - Replace the deterministic `ClaimVerifier` with a model‑based verifier calibrated on scientific text; provide configuration for base model and calibration data.
  - Update tests to cover retrieval and verification edge cases.
- **Suggested PR** – `full-text-evidence-and-verification`

## Phase 9.5: Deployment, scalability and observability

- **Goal** – Package Indra for deployment and ensure it scales to large sessions.
- **Tasks**:
  - Provide Dockerfiles and container‑compose setup for the API, workers, database and frontend.
  - Add caching for large sessions and export results (for example Redis or file storage) to avoid recomputation.
  - Offload heavy export generation to background jobs and allow users to download when ready.
  - Integrate metrics and structured logging; add health and readiness endpoints.
  - Update documentation with deployment instructions and recommended resource sizes.
- **Suggested PR** – `deployment-and-scalability`

## Phase 9.6: Rename environment variables and configuration to Indra

- **Goal** – Complete the rebranding from ERLA to Indra across all environment variables, headers and metadata.
- **Tasks**:
  - Rename `ERLA_REPOSITORY_BACKEND`, `ERLA_DATABASE_URL`, `ERLA_CORS_ORIGINS` and all other `ERLA_*` variables to `INDRA_*`.
  - Rename `NEXT_PUBLIC_ERLA_API_URL` to `NEXT_PUBLIC_INDRA_API_URL` and update the frontend to use the new variable.
  - Change HTTP headers such as `X-ERLA-Validation-Preserved` to `X-Indra-Validation-Preserved`.
  - Update the CLI name, script entry point and project metadata.
- **Suggested PR** – `rename-to-indra`
