# Indra — Evidence-backed research navigator

Indra is a research mission-control workspace for scientific literature. It searches academic sources, stores projects and sessions, exposes papers and branches, validates atomic claims against inspectable evidence, builds research maps, surfaces uncertainty, and exports reusable artifacts.

Indra is not a generic chatbot or writing editor. Its product boundary is evidence navigation: find papers, inspect state, validate claims, understand a literature map, and export artifacts that preserve uncertainty labels.

## Current status

Indra is ready for single-owner personal professional use when run as one API process, one dashboard process, and either the in-memory backend for testing or PostgreSQL for durable work. Optional local API-key protection is available through `INDRA_API_KEY`.

Enterprise features such as billing, collaboration, organization-level authorization, and multi-user account management are intentionally outside this personal deployment profile.

## Capabilities

- Academic search through Semantic Scholar and arXiv.
- Composite search strategies: single-source, parallel, and fallback.
- PDF text extraction and OpenRouter-compatible summarization.
- Recursive research sessions with branches, loops, reflection, and hypotheses.
- FastAPI product API with in-memory and PostgreSQL repositories.
- Durable background-job contracts and worker leasing primitives.
- Next.js dashboard for projects, sessions, papers, branches, claims, maps, advisor signals, and exports.
- Atomic claim extraction, evidence retrieval, claim validation, and claim inspection.
- Citation/reference research maps, timelines, clusters, paper roles, and related-paper recommendations.
- Contradiction, weak-evidence, gap, open-problem, recommendation, and speculative-hypothesis analysis.
- Exports: BibTeX, RIS, Markdown report, LaTeX outline, annotated bibliography, claim-ledger CSV/JSON, and research-map JSON.

## Architecture

```text
apps/web/                        Next.js dashboard
src/api/                         FastAPI product API
src/claims/                      claim extraction, evidence retrieval, validation
src/maps/                        research-map construction
src/analysis/                    gap, contradiction, and advisor analysis
src/exports/                     deterministic research artifact generation
src/jobs/                        durable worker boundary
src/                             research core and provider integrations
migrations/                      PostgreSQL schema migrations
```

Runtime boundary:

```text
frontend -> product API -> repository/events
                       -> durable jobs/workers -> research core -> providers
```

The frontend does not import the Python research core. Long-running research work stays behind the job boundary.

## Requirements

- Python 3.13 or newer.
- Node.js 20.9 or newer.
- `uv` for the recommended Python setup.
- PostgreSQL 16 or newer for durable sessions.

## Quick start

```bash
cp .env.example .env
uv sync
uvicorn src.api.app:app --reload --port 8000
```

In a second terminal:

```bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000/projects`.

## Environment

Root `.env`:

```bash
OPENROUTER_API_KEY=...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=anthropic/claude-3-5-sonnet
INDRA_REPOSITORY_BACKEND=memory
INDRA_DATABASE_URL=postgresql://user:password@localhost:5432/indra
INDRA_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
INDRA_API_KEY=
SEMANTIC_SCHOLAR_API_KEY=
HALUGATE_URL=http://localhost:8000
```

Dashboard `.env.local`:

```bash
NEXT_PUBLIC_INDRA_API_URL=http://localhost:8000
NEXT_PUBLIC_INDRA_API_KEY=
```

Set `INDRA_REPOSITORY_BACKEND=postgres` and `INDRA_DATABASE_URL` for durable persistence. Leave `INDRA_API_KEY` empty for trusted local development. When `INDRA_API_KEY` is set, API calls require `X-Indra-API-Key` or `Authorization: Bearer`.

## Health checks

```bash
curl http://localhost:8000/livez
curl http://localhost:8000/readyz
```

## Main API routes

- `POST /projects`, `GET /projects`, `GET /projects/{project_id}`
- `POST /sessions`, `GET /sessions`, `GET /sessions/{session_id}`
- `GET /sessions/{session_id}/state`
- `GET /sessions/{session_id}/map`
- `GET /sessions/{session_id}/analysis`
- `GET /sessions/{session_id}/exports`
- `GET /sessions/{session_id}/exports/{format_name}`
- `POST /sessions/{session_id}/start|pause|resume|cancel`
- `GET /sessions/{session_id}/branches|papers|claims|jobs|events`
- `GET /sessions/{session_id}/events/stream`
- `POST /branches/{branch_id}/continue|split|prune`
- `GET /papers/{paper_id}`
- `POST /sessions/{session_id}/claims/extract`
- `POST /claims/{claim_id}/validate`
- `POST /claims/{claim_id}/validate/auto`
- `GET /claims/{claim_id}/inspection`
- `POST /jobs/lease`, `POST /jobs/{job_id}/complete|fail`

## Verification

Backend:

```bash
python -m pytest -q test_api_cors.py test_api.py test_claim_evidence_retrieval.py test_research_map.py test_research_advice.py test_exports.py
```

Frontend:

```bash
cd apps/web
npm run typecheck
npm test
npm run build
```

## Core rule

Factual claims must be decomposed, validated, and linked to source evidence. Unsupported output remains excluded or explicitly uncertain. Hypotheses remain speculative until independently evidenced. Exports must preserve these distinctions.
