# Indra — Epistemic Research Landscape Agent

Indra is an evidence-backed research navigator for scientific literature. It searches academic sources, grows branching research sessions, validates atomic claims against inspectable evidence, maps literature, surfaces uncertainty, and exports reusable research artifacts.

Indra is not primarily a generic chatbot or writing assistant. Its product surface is a research mission-control workspace for understanding a field, inspecting evidence, finding uncertainty, and leaving with useful artifacts.

## Implemented product phases

- Academic search through Semantic Scholar and arXiv.
- Composite multi-provider search with parallel, fallback, and single-source strategies.
- PDF text extraction and OpenRouter-compatible summarization.
- Recursive research orchestration with branches, loops, reflection, and hypothesis generation.
- FastAPI product API with in-memory and Postgres repositories.
- Durable background-job contracts and worker leasing primitives.
- Next.js project and session dashboard.
- Ordered, resumable event delivery with PostgreSQL notifications and bounded history reads.
- Background map/advisor computation with durable revisioned caching and a separate view worker.
- Atomic claim extraction, evidence retrieval, claim validation, and claim inspection.
- Citation/reference research maps, timelines, clusters, paper roles, and related-paper recommendations.
- Contradiction, weak-evidence, gap, open-problem, recommendation, and speculative-hypothesis analysis.
- Phase 8 exports: BibTeX, RIS, Markdown report, LaTeX outline, annotated bibliography, claim-ledger CSV/JSON, and research-map JSON.

## Architecture

```
apps/web/                        Next.js product dashboard
src/api/                         FastAPI product API
src/claims/                      claim extraction, evidence retrieval, validation
src/maps/                        research-map construction
src/analysis/                    gap, contradiction, and advisor analysis
src/exports/                     deterministic research artifact generation
src/jobs/                        durable worker boundary
src/                             research core and provider integrations
migrations/                      Postgres schema migrations
```

Runtime boundary:

```
frontend -> product API -> repository/events
                       -> durable jobs/workers -> research core -> providers
```

The frontend does not import the Python research core. Long-running research work must remain behind the durable job boundary.

## Installation

Python 3.13 or newer is required.

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

```bash
OPENROUTER_API_KEY=...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=

INDRA_REPOSITORY_BACKEND=memory
INDRA_DATABASE_URL=postgresql://user:password@localhost:5432/indra
INDRA_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

SEMANTIC_SCHOLAR_API_KEY=...
HALUGATE_URL=http://localhost:8000
```

### Variable summary

| Variable | Description | Example |
| --- | --- | --- |
| `OPENROUTER_API_KEY` | API key for the OpenRouter provider | `sk-…` |
| `OPENROUTER_BASE_URL` | Base URL for the OpenRouter API | `https://openrouter.ai/api/v1` |
| `OPENROUTER_MODEL` | Explicit model with structured-output support; required when enabling model verification | Select a supported model ID |
| `INDRA_REPOSITORY_BACKEND` | Storage backend: use `memory` for in‑memory sessions or `postgres` for durable storage | `memory` |
| `INDRA_DATABASE_URL` | Connection string used when `INDRA_REPOSITORY_BACKEND=postgres` | `postgresql://user:password@localhost:5432/indra` |
| `INDRA_CORS_ORIGINS` | Comma‑separated list of allowed origins for the API | `http://localhost:3000` |
| `INDRA_API_KEY` | Optional API key for trusted local deployments; dashboard requests must use the same value | `local-key` |
| `NEXT_PUBLIC_INDRA_API_KEY` | Dashboard API key in `apps/web/.env.local`; embedded in the browser bundle, so this is not a multi-user authentication system | `local-key` |
| `SEMANTIC_SCHOLAR_BASE_URL` | Optional provider endpoint; defaults to the public Graph API | `https://api.semanticscholar.org/graph/v1` |
| `SEMANTIC_SCHOLAR_API_KEY` | Optional key enabling higher Semantic Scholar request quotas | `api-key` |
| `HALUGATE_URL` | URL of the HaluGate hallucination-detection service used by the CLI research pipeline | `http://localhost:8000` |

## Run the API

```bash
uvicorn src.api.app:app --reload --port 8000 --timeout-graceful-shutdown 5
```

Major endpoints:

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

The default repository backend is process-local memory. Set `INDRA_REPOSITORY_BACKEND=postgres` and `INDRA_DATABASE_URL` for durable persistence.

## Run the research worker

The API and standalone workers must use the same Postgres database. Initialize it with `python -m src.api.migrate` (or `--without-vectors` on Postgres without pgvector), then run `python -m src.jobs.research_worker` and `python -m src.jobs.view_worker` in separate terminals. The view worker prepares and caches maps and advisor results; the dashboard shows pending work and supports retries. See [Phase 1](docs/research/PHASE_1.md) for research bounds, [Phase 2](docs/research/PHASE_2.md) for the session hub, and [Phases 3–4](docs/research/PHASE_3_4.md) for event delivery, migration instructions, caching, and verification.

## Run the dashboard

```bash
cd apps/web
cp .env.example .env.local
npm ci
npm run dev
```

Open `http://localhost:3000/projects`.

The dashboard includes:

- project and session workspaces;
- session lifecycle controls and live events;
- branch, paper, job, claim, and evidence inspectors;
- research maps and timelines;
- research-advisor recommendations, contradiction and gap review, hypotheses, and weak-evidence triage;
- export center at `/sessions/{session_id}/exports`.

## Quick start workflow

Here is a small example illustrating how to create a project, run a research session and inspect its state using the API.  These examples assume the API server is running on `http://localhost:8000`:

1. Create a new project:

```bash
curl -X POST http://localhost:8000/projects \
  -H 'Content-Type: application/json' \
  -d '{"title": "Example project"}'
```

This returns the new project; its `id` is the project ID.

2. Create a research session within that project:

```bash
curl -X POST http://localhost:8000/sessions \
  -H 'Content-Type: application/json' \
  -d '{"project_id": "<PROJECT_ID>", "initial_query": "What is the role of quantum coherence in photosynthesis?"}'
```

The returned `id` is the session ID. New sessions are `pending`.

3. Start the session and monitor its state:

```bash
curl -X POST http://localhost:8000/sessions/<SESSION_ID>/start
curl http://localhost:8000/sessions/<SESSION_ID>/state
```

Starting a session queues one `research_session` job. Run `python -m src.jobs.research_worker` in a separate terminal with the same Postgres configuration as the API. The worker searches, persists selected papers and PDF passages, extracts claims, and completes the session. See [Phase 1 setup and verification](docs/research/PHASE_1.md). Without a model key, claims remain explicitly unreviewed.

4. Extract claims from text and validate one against the session's papers:

```bash
# extract atomic claims
curl -X POST http://localhost:8000/sessions/<SESSION_ID>/claims/extract \
  -H 'Content-Type: application/json' \
  -d '{"source_text": "Quantum coherence persists for hundreds of femtoseconds in the FMO complex."}'

# retrieve evidence and validate one claim
curl -X POST http://localhost:8000/claims/<CLAIM_ID>/validate/auto \
  -H 'Content-Type: application/json' \
  -d '{}'
```

When `INDRA_API_KEY` is set, add `-H "X-Indra-API-Key: <key>"` to every request.

## Phase 8 export formats

| Format | Endpoint suffix |
| --- | --- |
| BibTeX | `bibtex` |
| RIS | `ris` |
| Markdown research report | `report-markdown` |
| LaTeX literature‑review outline | `literature-review-latex` |
| Annotated bibliography | `annotated-bibliography` |
| Claim ledger CSV | `claim-ledger-csv` |
| Claim ledger JSON | `claim-ledger-json` |
| Research map JSON | `research-map-json` |

Claim-bearing exports preserve status, confidence, evidence relationships, and synthesis eligibility. Unsupported, contradicted, speculative, and unreviewed statements remain explicitly labelled.

## Verification

Frontend:

```bash
cd apps/web
npm run typecheck
npm test
npm run build
```

Backend:

```bash
python -m pytest -q
```

Implementation notes:

- `docs/phase4/WEB_DASHBOARD_MVP.md`
- `docs/phase5/CLAIM_VALIDATION_MVP.md`
- `docs/phase6/RESEARCH_MAPS_MVP.md`
- `docs/phase7/RESEARCH_ADVISOR_MVP.md`
- `docs/phase8/EXPORTS_MVP.md`

## Production-hardening work still required

- Expand the bounded product worker into recursive Scout and hypothesis orchestration.
- Add database pagination for paper/claim snapshots and graph virtualization for larger sessions.
- Add authentication and project authorization.
- Add dense/vector retrieval and scanned-document handling beyond page-numbered PDF text.
- Add calibrated domain-specific inference where appropriate.
- Deploy Postgres, migrations, API, workers, and dashboard as one system.
- Add cache eviction/versioning and asynchronous export jobs if session scale requires them.

## Core rule

Factual claims must be decomposed, validated, and linked to source evidence. Unsupported output remains excluded or explicitly uncertain. Hypotheses remain speculative until independently evidenced. Exports must preserve these distinctions.
