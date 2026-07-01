# Indra installation and usage guide

This guide describes the current personal professional deployment path for Indra.

## Requirements

- Python 3.13 or newer.
- Node.js 20.9 or newer.
- `uv` for Python dependency management.
- PostgreSQL 16 or newer for durable work.

## Backend setup

```bash
cp .env.example .env
uv sync
uvicorn src.api.app:app --reload --port 8000
```

Use the in-memory repository for quick local testing:

```bash
INDRA_REPOSITORY_BACKEND=memory
```

Use PostgreSQL for work you want to keep:

```bash
INDRA_REPOSITORY_BACKEND=postgres
INDRA_DATABASE_URL=postgresql://user:password@localhost:5432/indra
```

The API exposes these operational endpoints:

```bash
curl http://localhost:8000/livez
curl http://localhost:8000/readyz
```

## Optional local access protection

Set an Indra API key in the API process when you do not want open local access:

```bash
INDRA_API_KEY=your-local-key
```

Then pass the same value in requests:

```bash
curl -H "X-Indra-API-Key: your-local-key" http://localhost:8000/projects
```

For the web dashboard, put the same value in `apps/web/.env.local`:

```bash
NEXT_PUBLIC_INDRA_API_URL=http://localhost:8000
NEXT_PUBLIC_INDRA_API_KEY=your-local-key
```

This is intended for personal deployments. Do not expose a browser-shipped key as a multi-user security boundary.

## Dashboard setup

```bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000/projects`.

## Typical workflow

1. Create a project.
2. Create a research session with an initial query.
3. Start the session.
4. Run a worker or persist results through the API.
5. Inspect branches, papers, events, jobs, and claims.
6. Open the research map and advisor panels.
7. Export a BibTeX bibliography, Markdown report, LaTeX outline, annotated bibliography, claim ledger, or research-map JSON.

## Verification

Run backend checks:

```bash
python -m pytest -q test_api_cors.py test_api.py test_claim_evidence_retrieval.py test_research_map.py test_research_advice.py test_exports.py
```

Run dashboard checks:

```bash
cd apps/web
npm run typecheck
npm test
npm run build
```

## Current deployment profile

Indra is ready for a single-owner personal research service when run behind local machine access or a trusted reverse proxy. The implemented Phase 9 work adds explicit health endpoints, optional API key protection, environment templates, and dashboard request support.

Multi-user accounts, organization authorization, billing, and collaboration remain intentionally out of scope for this deployment profile.
