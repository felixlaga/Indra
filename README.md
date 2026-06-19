# ERLA — Epistemic Research Landscape Agent

ERLA is an evidence-backed research navigator for scientific literature. It searches academic sources, grows a branching research map, preserves session state, exposes agent and job events, and is designed to validate generated claims against inspectable evidence.

ERLA is not primarily a generic chatbot or writing assistant. The product direction is a research mission-control workspace that helps researchers understand a field, inspect papers and branch rationale, and decide what to read or investigate next.

## Current repository state

Implemented or partially implemented:

- Paper search through Semantic Scholar and arXiv.
- Composite multi-provider search with parallel, fallback, and single-source strategies.
- PDF text extraction through PyMuPDF.
- LLM summarization through OpenRouter-compatible APIs.
- Local and HTTP HaluGate validation.
- Recursive research orchestration with Inner Loop, Iteration Loop, Branch Manager, Master Agent, Managing Agent, Reflection Agent, and hypothesis generation.
- FastAPI product API under `src/api` with projects, sessions, branches, papers, claims, events, run controls, and durable job contracts.
- In-memory and Postgres repository implementations.
- Initial Postgres product schema and job persistence under `migrations/`.
- Worker adapter primitives under `src/jobs` for leasing, completing, retrying, and failing jobs.
- Deterministic claim extraction and supplied-evidence validation scaffolds under `src/claims`.
- Next.js web dashboard under `apps/web` for projects, session creation, session mission control, branch inspection, paper inspection, jobs, claims, and events.
- Legacy Convex and Vite/React visualization prototypes under `convex/` and `viewer/`.
- Typer CLI commands for search, fetch, and profile listing.

Not yet production-ready:

- Research jobs are durably queued, but the Phase 3 worker contract is not yet connected to full `MasterAgent` execution.
- The SSE stream is process-local and not resumable across API restarts.
- No authentication or multi-user authorization boundary.
- No automated evidence retrieval or production claim verifier.
- No production deployment of the Postgres repository and migration runner.
- No distributed external queue infrastructure.
- Exports, collaboration, large research maps, gap analysis, and contradiction analysis remain later roadmap phases.

## Product architecture

```text
apps/web/                        Next.js product dashboard
src/api/                         FastAPI product API
src/                             research core and provider integrations
src/jobs/                        worker adapter and durable job execution boundary
migrations/                      Postgres schema migrations
viewer/                          legacy Vite/React prototype
convex/                          legacy realtime prototype
```

Runtime boundary:

```text
frontend -> product API -> durable jobs/workers -> research core -> providers
                       -> repository/events -> frontend
```

The frontend must not import the Python research core. Long-running research work must not execute synchronously inside API handlers.

## Installation

Python 3.13 or newer is required.

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

Product API and persistence:

```bash
ERLA_REPOSITORY_BACKEND=memory
ERLA_DATABASE_URL=postgresql://user:password@localhost:5432/erla
ERLA_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

Optional provider and validation settings:

```bash
MODEL_PROFILE=research-fast
SEMANTIC_SCHOLAR_API_KEY=...
HALUGATE_URL=http://localhost:8000
HALUGATE_DEVICE=cpu
HALUGATE_USE_SENTINEL=true
CONVEX_URL=...
```

## Run the product API

```bash
uvicorn src.api.app:app --reload --port 8000
```

Important endpoints include:

- `POST /projects`, `GET /projects`, `GET /projects/{project_id}`
- `POST /sessions`, `GET /sessions`, `GET /sessions/{session_id}`
- `GET /sessions/{session_id}/state`
- `POST /sessions/{session_id}/start|pause|resume|cancel`
- `GET /sessions/{session_id}/branches|papers|claims|jobs|events`
- `GET /sessions/{session_id}/events/stream`
- `POST /branches/{branch_id}/continue|split|prune`
- `GET /papers/{paper_id}`
- `POST /sessions/{session_id}/claims/extract`
- `POST /claims/{claim_id}/validate`
- `GET /claims/{claim_id}/evidence`
- `POST /jobs/lease`, `POST /jobs/{job_id}/complete|fail`

The default repository backend is process-local memory. Use `ERLA_REPOSITORY_BACKEND=postgres` with `ERLA_DATABASE_URL` for the durable repository implementation.

## Run the web dashboard

```bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

The default frontend configuration is:

```bash
NEXT_PUBLIC_ERLA_API_URL=http://localhost:8000
```

Open `http://localhost:3000/projects`.

The Phase 4 dashboard provides:

- Searchable project portfolio and project creation.
- Project detail pages and online session creation.
- Session start, pause, resume, and cancel controls.
- Hierarchical branch inspection with continue and prune actions.
- Paper lists, in-session paper inspection, and paper detail pages.
- Live event consumption through server-sent events.
- Job status and claim-ledger panels.
- Explicit loading, empty, failure, partial-state, and disconnected-stream states.

See `docs/phase4/WEB_DASHBOARD_MVP.md` for the delivered scope and current limits.

## Verification

Frontend:

```bash
cd apps/web
npm run typecheck
npm test
npm run build
```

Backend API boundary:

```bash
pytest test_api_cors.py test_api.py
```

A GitHub Actions workflow under `.github/workflows/phase4-dashboard.yml` runs these checks for dashboard-related pull requests.

## CLI prototype

The CLI remains useful for provider and research-core development, but it is no longer the intended primary product interface.

```bash
erla profiles
erla search "wave optics gravitational wave lensing" --source semantic_scholar --limit 10
erla search "transformer attention" --source arxiv --arxiv-cat cs.LG --limit 10
erla fetch arxiv:2301.00001 --with-text
```

## HaluGate service

```bash
HALUGATE_DEVICE=cpu uvicorn src.halugate.server:app --host 0.0.0.0 --port 8001
```

The service exposes `GET /health` and `POST /validate`.

## Next engineering priorities

1. Connect durable research jobs to the existing `MasterAgent` execution path.
2. Persist and stream production events across processes.
3. Add automated evidence retrieval and a production claim verifier.
4. Add authentication and project authorization.
5. Add branch splitting controls, claim evidence inspection, and exports.
6. Deploy the Postgres repository, migration runner, API, workers, and web dashboard as one coherent product system.

## Source-of-truth documents

Before major product or architecture changes, read:

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

## Core rule

If ERLA produces a factual claim, that claim must eventually be decomposed, validated, and linked to source evidence. Unsupported or speculative output must remain explicitly labeled.
