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
OPENROUTER_MODEL=anthropic/claude-3-5-sonnet

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
| `OPENROUTER_MODEL` | Model name used with OpenRouter | `anthropic/claude-3-5-sonnet` |
| `INDRA_REPOSITORY_BACKEND` | Storage backend: use `memory` for in‑memory sessions or `postgres` for durable storage | `memory` |
| `INDRA_DATABASE_URL` | Connection string used when `INDRA_REPOSITORY_BACKEND=postgres` | `postgresql://user:password@localhost:5432/indra` |
| `INDRA_CORS_ORIGINS` | Comma‑separated list of allowed origins for the API | `http://localhost:3000` |
| `SEMANTIC_SCHOLAR_API_KEY` | Optional key enabling higher Semantic Scholar request quotas | `api-key` |
| `HALUGATE_URL` | URL of the HALUGate service for PDF retrieval | `http://localhost:8000` |

## Run the API

```bash
uvicorn src.api.app:app --reload --port 8000
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

## Run the dashboard

```bash
cd apps/web
cp .env.example .env.local
npm install
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
  -d '{"name": "Example project"}'
```

This returns a JSON object containing the new `project_id`.

2. Launch a research session within that project:

```bash
curl -X POST http://localhost:8000/sessions \
  -H 'Content-Type: application/json' \
  -d '{"project_id": "<PROJECT_ID>", "query": "What is the role of quantum entanglement in photosynthesis?"}'
```

Record the returned `session_id`.

3. Monitor session state:

```bash
curl http://localhost:8000/sessions/<SESSION_ID>/state
```

Once the session has progressed, you can extract and validate claims or view research maps:

```bash
# extract claims
curl -X POST http://localhost:8000/sessions/<SESSION_ID>/claims/extract

# validate a specific claim
curl -X POST http://localhost:8000/claims/<CLAIM_ID>/validate
```

This quick start demonstrates the core workflow: create a project, start a session, follow its progress, and interact with claims and evidence.

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
python -m pytest -q \
  test_api_cors.py \
  test_api.py \
  test_claim_evidence_retrieval.py \
  test_research_map.py \
  test_research_advice.py \
  test_exports.py
```

Implementation notes:

- `docs/phase4/WEB_DASHBOARD_MVP.md`
- `docs/phase5/CLAIM_VALIDATION_MVP.md`
- `docs/phase6/RESEARCH_MAPS_MVP.md`
- `docs/phase7/RESEARCH_ADVISOR_MVP.md`
- `docs/phase8/EXPORTS_MVP.md`

## Production-hardening work still required

- Connect durable research jobs to full `MasterAgent` execution.
- Replace process-local SSE with resumable cross-process events.
- Add authentication and project authorization.
- Expose full-text paper chunks to evidence retrieval.
- Add calibrated domain-specific inference where appropriate.
- Deploy Postgres, migrations, API, workers, and dashboard as one system.
- Add large-session caching and asynchronous export jobs if session scale requires them.

## Core rule

Factual claims must be decomposed, validated, and linked to source evidence. Unsupported output remains excluded or explicitly uncertain. Hypotheses remain speculative until independently evidenced. Exports must preserve these distinctions.
