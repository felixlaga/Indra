# ERLA — Epistemic Research Landscape Agent

ERLA is a recursive research navigator for scientific literature. It searches academic paper sources, follows citation/reference structure, summarizes papers, validates generated text against source material, and grows a branching research map through autonomous Scouts.

The immediate product direction is not to become a generic AI writing assistant. ERLA should become a research mission-control dashboard: a system that helps researchers understand a field, inspect evidence, identify gaps and contradictions, and decide what to read or investigate next.

## Current repository state

This repository currently contains a Python-first research core, CLI prototype, and early realtime visualization prototype.

Implemented or partially implemented:

- Paper search through Semantic Scholar.
- Paper search through arXiv.
- Composite multi-provider search with parallel/fallback/single strategies.
- PDF text extraction through PyMuPDF.
- LLM summarization through OpenRouter-compatible APIs.
- Local and HTTP HaluGate validation.
- Recursive research orchestration with Inner Loop, Iteration Loop, Branch Manager, Master Agent, Managing Agent, Reflection Agent, and Hypothesis generation.
- FastAPI product API skeleton under `src/api` with a repository contract/factory, in-memory and Postgres repositories, runtime research-loop binding, background job contract, and process-local event streaming.
- Deterministic claim extraction and claim validation scaffolds under `src/claims`, with API endpoints for review-ready claims and supplied-evidence validation.
- Initial Postgres product schema migration under `migrations/`, including job persistence.
- Worker adapter primitives under `src/jobs` for leasing, completing, retrying, and failing durable jobs.
- Frontend dashboard shell in the Vite/React `viewer/` prototype with selectable branch and paper inspectors.
- Convex event emission client for realtime visualization.
- Convex schema/functions under `convex/` for prototype session replay state.
- Vite/React viewer under `viewer/` for prototype graph, event, and chat exploration.
- Typer CLI commands for search, fetch, and profile listing.

Not yet production-ready:

- No production web dashboard backed by the target API/database/worker architecture.
- The current dashboard shell is not yet the final `apps/web` Next.js frontend.
- No running durable product database or migration runner wired into deployment. Postgres support exists behind environment configuration, but local/dev deployment still defaults to memory.
- The product API is skeleton-only and not connected to auth, production-grade realtime infrastructure, external queue infrastructure, or real research job execution.
- No Redis/Celery-style external job queue for distributed long research runs.
- No production claim verifier, automated evidence retrieval, or durable claim-level evidence ledger. Current validation is deterministic and in-memory only.
- No finalized source-of-truth frontend architecture.
- The CLI is still the primary interface.

## Product thesis

ERLA should help a researcher move from an unclear research question to:

1. A mapped research landscape.
2. A live Scout/branch tree.
3. A paper library.
4. Validated paper summaries.
5. Atomic claims linked to evidence.
6. Gap and contradiction analysis.
7. A reading plan.
8. Evidence-backed research-direction recommendations.
9. Exportable notes, citations, and review outlines.

## Architecture summary

Current package layout:

```txt
src/
  cli.py                         Typer CLI entrypoint
  api/                           FastAPI product API skeleton
  claims/                        deterministic claim extraction/validation scaffolds
  summarize.py                   LLM paper summarization
  config/                        Pydantic config and model profiles
  semantic_scholar/              Semantic Scholar client, models, protocols, adapter
  arxiv/                         arXiv client and adapter
  paper_sources/                 composite provider and deduplication
  halugate/                      local + HTTP hallucination validation
  orchestration/                 recursive research loops and agents
  hypothesis/                    hypothesis generation and validation
  context/                       context estimation and branch splitting
  llm/                           OpenRouter adapter and LLM protocols
  storage/                       Convex realtime event client
convex/                          prototype realtime schema and functions
viewer/                          prototype Vite/React research viewer
```

Target product architecture:

```txt
apps/web/                        Next.js dashboard
apps/api/                        FastAPI product API
src/                             existing research core, migrated carefully
workers/                         background jobs
migrations/                      database migrations
docs or root *.md                source-of-truth product/engineering docs
```

The existing `src` package should be preserved as the research core for now. Do not rewrite it wholesale before the dashboard, API, durable state, and validation model are defined.

The existing `convex/` and `viewer/` directories are prototype realtime/viewer surfaces. They may inform the dashboard MVP, but they are not the final product API, durable database, worker layer, or source-of-truth frontend architecture.

## Installation

Python requirement is currently 3.13 or newer.

Recommended development setup:

```bash
uv sync
```

Alternative:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Environment variables

Create a local `.env` file. Do not commit secrets.

Required for real LLM runs:

```bash
OPENROUTER_API_KEY=...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=anthropic/claude-3-5-sonnet
```

Optional:

```bash
MODEL_PROFILE=research-fast
ERLA_REPOSITORY_BACKEND=memory
ERLA_DATABASE_URL=postgresql://user:password@localhost:5432/erla
SEMANTIC_SCHOLAR_API_KEY=...
HALUGATE_URL=http://localhost:8000
HALUGATE_DEVICE=cpu
HALUGATE_USE_SENTINEL=true
CONVEX_URL=...
```

## CLI usage

The CLI is a developer/prototype interface, not the final product UX.

List config profiles:

```bash
erla profiles
```

Search Semantic Scholar:

```bash
erla search "wave optics gravitational wave lensing" --source semantic_scholar --limit 10
```

Search arXiv:

```bash
erla search "transformer attention" --source arxiv --arxiv-cat cs.LG --limit 10
```

Search multiple providers:

```bash
erla search "LLM reasoning" --source semantic_scholar --source arxiv --strategy parallel --limit 20
```

Fetch paper metadata:

```bash
erla fetch arxiv:2301.00001
```

Fetch with PDF text extraction when available:

```bash
erla fetch arxiv:2301.00001 --with-text
```

## Product API skeleton

The product API is an early boundary for projects, sessions, branches, papers, claims, claim evidence, events, jobs, and run controls. It depends on a `ProductRepository` contract and creates the configured backend through `ERLA_REPOSITORY_BACKEND`, which defaults to `memory`. A Postgres-backed repository exists behind `ERLA_REPOSITORY_BACKEND=postgres` and `ERLA_DATABASE_URL`, but production deployment is still deferred.

Session creation now creates a lightweight runtime `LoopState` and root branch through the existing research-core orchestration models. This binds product sessions to the current research loop shape. Run controls create durable job records rather than running long research work in API handlers; real research-core execution still needs worker handlers.

Session events can be streamed over server-sent events from the in-memory event log. The stream replays current session events and publishes new process-local events, but it is not durable, resumable across API restarts, or a replacement for the future database-backed realtime layer.

Claim validation accepts explicitly supplied evidence passages, stores process-local evidence records, updates claim status using deterministic relation rules, and emits `claim_validated`. It does not retrieve evidence automatically, call a production verifier, or persist evidence beyond the in-memory API process.

Run locally:

```bash
uvicorn src.api.app:app --reload
```

Implemented skeleton endpoints include:

- `POST /projects`, `GET /projects`, `GET /projects/{project_id}`
- `POST /sessions`, `GET /sessions`, `GET /sessions/{session_id}`
- `POST /sessions/{session_id}/start|pause|resume|cancel`
- `GET /sessions/{session_id}/state`, `GET /sessions/{session_id}/loop`, `GET /sessions/{session_id}/jobs`
- `GET /jobs/{job_id}`, `POST /jobs/lease`, `POST /jobs/expire`
- `POST /jobs/{job_id}/complete`, `POST /jobs/{job_id}/fail`
- `GET /sessions/{session_id}/branches`, `GET /sessions/{session_id}/papers`, `GET /sessions/{session_id}/events`
- `GET /sessions/{session_id}/events/stream`
- `POST /sessions/{session_id}/claims/extract`, `GET /sessions/{session_id}/claims`
- `POST /claims/{claim_id}/validate`, `GET /claims/{claim_id}/evidence`
- `GET /branches/{branch_id}`, `PATCH /branches/{branch_id}`
- `POST /branches/{branch_id}/continue|split|prune`
- `GET /papers/{paper_id}`, `GET /claims/{claim_id}`

## HaluGate service

Run validation service locally:

```bash
HALUGATE_DEVICE=cpu uvicorn src.halugate.server:app --host 0.0.0.0 --port 8000
```

The HaluGate service exposes:

- `GET /health`
- `POST /validate`

For production, move heavy validation to a separately deployed service with batching, caching, timeouts, and GPU support where appropriate.

## Development direction

The next engineering milestone is a web dashboard MVP backed by durable state and worker-driven research execution. With the API skeleton, repository contract/factory, Postgres repository, job contract, initial schema migration, prototype dashboard shell, session-to-loop binding, process-local event streaming, selectable branch/paper inspectors, deterministic claim extraction, and supplied-evidence claim validation in place, remaining work is:

1. Connect worker handlers to the existing `MasterAgent`/research-core execution path.
2. Add external queue/deployment infrastructure if multi-process workers need Redis/Celery-style coordination.
3. Implement automated evidence retrieval and production claim verification.
4. Decide whether to migrate the dashboard shell to Next.js under `apps/web` or formalize the existing `viewer/`.
5. Connect session execution to the existing `MasterAgent` orchestration through workers.
6. Add branch tree, claim inspector, evidence passage viewer, and richer event log interactions.

## Source-of-truth docs

Read these files before making product or architecture changes:

- `PRODUCT_SPEC.md`
- `ARCHITECTURE.md`
- `DATA_MODEL.md`
- `VALIDATION_RULES.md`
- `AGENT_RULES.md`
- `UI_UX_SPEC.md`
- `ROADMAP.md`
- `TESTING_STRATEGY.md`
- `CODE_STYLE.md`
- `CODEX.md`

## Non-goals for the next milestone

Do not prioritize:

- A full AI writing editor.
- Payment system.
- Browser extension.
- Mobile app.
- Enterprise admin dashboard.
- Fancy 3D visualization before usable graph navigation.
- Major refactors that do not unblock the dashboard or validation layer.

## Core rule

If ERLA produces a factual claim, that claim must eventually be decomposed, validated, and linked to source evidence. Unsupported or speculative output must be labeled as such.
