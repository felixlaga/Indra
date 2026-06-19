# Phase 4: Web dashboard MVP

## Status

Implemented as a Next.js application under `apps/web`.

## Scope delivered

- `/projects`: searchable project portfolio with API-derived session, paper, and claim metrics.
- `/projects/[projectId]`: project workspace, session creation, recent sessions, and saved-paper overview.
- `/sessions/[sessionId]`: mission-control dashboard backed by `GET /sessions/{id}/state`.
- Session start, pause, resume, and cancel controls.
- Clickable hierarchical branch tree with branch continuation and pruning controls.
- Session paper list and paper inspector.
- `/papers/[paperId]`: durable paper metadata and abstract inspection.
- Live server-sent event consumption with chronological event log.
- Background job and claim-ledger panels.
- Explicit loading, empty, disconnected-stream, API-error, and partial-state handling.
- Browser CORS boundary on the FastAPI application.
- Vercel configuration moved from the legacy Vite viewer to `apps/web`.

## Architecture

The frontend calls only the product API. It does not import the Python research core or Convex prototype code.

```text
apps/web -> src/api -> ProductRepository -> memory or Postgres
                     -> durable jobs -> workers
```

The API base URL is configured with:

```bash
NEXT_PUBLIC_ERLA_API_URL=http://localhost:8000
```

Allowed browser origins are configured on the API with a comma-separated value:

```bash
ERLA_CORS_ORIGINS=http://localhost:3000,https://your-dashboard.example
```

## Local development

Terminal 1:

```bash
uvicorn src.api.app:app --reload --port 8000
```

Terminal 2:

```bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000/projects`.

## Verification

Frontend checks:

```bash
cd apps/web
npm run typecheck
npm test
npm run build
```

Backend checks:

```bash
pytest test_api_cors.py test_api.py
```

The branch-tree unit tests exercise hierarchy construction and orphan preservation. The CORS tests verify that the default dashboard origin is permitted while an unconfigured origin is not granted browser access.

## Known limits

- Phase 3 worker contracts exist, but real research-core execution still depends on worker handlers. The dashboard therefore renders persisted results faithfully but does not fabricate papers or progress.
- The current event stream remains process-local and is not resumable across API restarts.
- Authentication, collaboration, exports, large-graph rendering, and production realtime infrastructure remain later work.
- The legacy `viewer/` and `convex/` directories remain as prototypes; `apps/web` is now the canonical product frontend.
