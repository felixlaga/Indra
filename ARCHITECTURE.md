# ERLA Architecture

## 1. Current architecture

ERLA currently has a Python package under `src/` with a CLI-first research agent prototype, plus early Convex/Vite realtime visualization pieces.

Current major modules:

```txt
src/cli.py                         Typer CLI: search, fetch, profiles
src/api/                            FastAPI product API skeleton with repository contract/factory, in-memory repository, runtime loop bridge, and event stream
src/config/loader.py               Pydantic config models
src/config/factory.py              backend/provider factory functions
src/config/models.yaml             model/profile presets
src/semantic_scholar/              Semantic Scholar client, adapter, models, protocols
src/arxiv/                         arXiv client and adapter
src/paper_sources/                 composite search provider and deduplication
src/summarize.py                   LLM paper summarization
src/halugate/                      local + HTTP HaluGate validation
src/orchestration/                 InnerLoop, IterationLoop, MasterAgent, BranchManager, StateStore, ManagingAgent, ReflectionAgent
src/hypothesis/                    hypothesis generation/validation
src/context/                       context estimation and branch splitting
src/llm/                           OpenRouter adapter and LLM protocols
src/storage/                       Convex realtime event client
convex/                            prototype realtime schema and functions
viewer/                            prototype Vite/React research viewer
migrations/                        initial Postgres product schema migration
```

The existing `convex/` and `viewer/` directories are useful prototypes for dashboard shell, replay, graph, event, and chat exploration. They are not yet the final dashboard architecture or durable product state layer.

This architecture is valuable but not yet a production product architecture. The main missing layers are:

- Production product API backed by Postgres repositories.
- Production web dashboard.
- Durable database runtime and repository layer.
- Background job queue.
- Claim-level evidence model.
- Auth/project/session model.
- Production-grade realtime state sync.

## 2. Architectural goal

Evolve ERLA from a CLI prototype into a durable online research workspace while preserving the existing research-core logic.

The target system must support:

- Long-running research sessions.
- Live dashboard updates.
- Durable project/session state.
- Background jobs.
- Multi-provider paper search.
- PDF parsing and chunking.
- Source-grounded summarization.
- Claim extraction and validation.
- Citation/reference graph traversal.
- User-controlled branch exploration.
- Exportable research artifacts.

## 3. Target architecture

Recommended target layout:

```txt
apps/
  web/                            Next.js dashboard
  api/                            FastAPI product API

src/                              existing research core, kept import-compatible initially
  config/
  semantic_scholar/
  arxiv/
  paper_sources/
  summarize.py
  halugate/
  orchestration/
  hypothesis/
  context/
  llm/
  storage/

workers/                          background job entrypoints
migrations/                       database migrations
tests/                            unit and integration tests
```

Do not rewrite the existing `src` package before the product API and dashboard exist. Refactor incrementally.

Do not treat the current `viewer/` or `convex/` prototype structure as the final frontend, API, or persistence boundary. Migrate or replace those pieces deliberately once the product API and durable state model are established.

The current dashboard shell lives in `viewer/` so it can build against the existing Vite/React setup. It includes selectable branch and paper inspector states for the dashboard MVP prototype. The target frontend architecture remains open until the project decides whether to migrate that shell to Next.js under `apps/web` or standardize on the existing viewer stack.

## 4. Runtime boundaries

The intended boundary is:

```txt
frontend -> product API -> job queue -> research core -> providers/services
                         -> database/events -> frontend
```

Rules:

- The frontend must not import or call research-core Python code.
- The API must not run long research jobs synchronously.
- Workers may call research-core modules.
- Research-core modules should not depend on frontend or web API code.
- HaluGate must remain separately deployable.

## 5. Backend services

### 5.1 Product API

Add a product API using FastAPI.

An initial skeleton currently exists under `src/api/`. It exposes project, session, branch, paper, claim extraction, supplied-evidence claim validation, event, run-control, and server-sent event stream endpoints through a `ProductRepository` contract. A repository factory selects the backend with `ERLA_REPOSITORY_BACKEND`; the only implemented backend is a process-local in-memory repository. Session creation creates a lightweight runtime `LoopState` and root branch via the existing orchestration models, and exposes that binding through `GET /sessions/{session_id}/loop`. The stream replays current events and publishes new process-local events. Claim extraction currently uses a deterministic scaffold and marks claims as `needs_review` or `speculative`; claim validation accepts explicit evidence passages and applies deterministic relation rules, but it does not retrieve evidence, call a production verifier, or persist evidence durably. This skeleton establishes the API and persistence boundaries only; it does not provide durable state, auth, workers, production-grade realtime infrastructure, or real research execution.

Responsibilities:

- Project CRUD.
- Session CRUD.
- Run controls.
- Branch controls.
- Claim extraction.
- Claim validation.
- Claim evidence retrieval.
- Paper, summary, claim, hypothesis retrieval.
- Export creation.
- Event streaming endpoint.

Suggested initial location:

```txt
apps/api/
```

If keeping everything inside one Python package is easier initially, use:

```txt
src/api/
```

but keep it logically separate from `src/orchestration`.

### 5.2 HaluGate service

The existing `src/halugate/server.py` is a validation microservice. Keep it separate from the product API.

Responsibilities:

- `GET /health`
- `POST /validate`
- later: batched production claim validation
- later: cached validation by source hash + claim hash

### 5.3 Worker service

Add a worker layer for long jobs.

Responsibilities:

- Search papers.
- Fetch metadata.
- Download PDFs.
- Parse PDFs.
- Chunk text.
- Generate summaries.
- Extract claims.
- Validate claims.
- Traverse citations/references.
- Generate hypotheses.
- Generate exports.

Acceptable initial job queues:

- Dramatiq + Redis.
- RQ + Redis.
- Celery + Redis.
- Arq + Redis.

## 6. Frontend architecture

Recommended stack:

- Next.js.
- TypeScript.
- Tailwind.
- shadcn/ui.
- TanStack Query.
- React Flow for the Scout tree.
- Cytoscape.js or Sigma.js for larger citation graphs.

Main pages:

```txt
/projects
/projects/[projectId]
/sessions/[sessionId]
/papers/[paperId]
/settings
```

Dashboard layout:

```txt
Top bar:
  session query, status, run controls, export

Left sidebar:
  project/session controls, filters, branch list

Center:
  Scout tree, citation graph, timeline, claim map

Right inspector:
  selected branch/paper/claim/hypothesis

Bottom drawer:
  events, validation trace, jobs
```

## 7. Persistence

The existing `StateStore` is in-memory and has only simplified JSON serialization. It is useful for a prototype but must not be the production source of truth.

Use Postgres as the durable product database.

Use pgvector for embeddings when semantic retrieval is added.

An initial schema migration exists at `migrations/0001_initial_product_schema.sql`. It creates the product tables and indexes. A `ProductRepository` contract and backend factory now exist in `src/api`, but no Postgres repository or migration runner is wired yet.

Use object storage for:

- PDFs.
- parsed text.
- exports.
- large cached model outputs.

Convex may stay as a realtime event sink or frontend sync layer, but the durable source of truth should be the product database unless the project intentionally standardizes on Convex for persistence too.

## 8. Event model

All long-running actions must emit events.

Event examples:

- `session_created`
- `session_started`
- `session_paused`
- `session_resumed`
- `session_cancelled`
- `branch_created`
- `branch_started`
- `branch_completed`
- `branch_pruned`
- `search_started`
- `papers_found`
- `paper_selected`
- `paper_fetched`
- `pdf_parsed`
- `summary_generated`
- `summary_validated`
- `claims_extracted`
- `claim_validated`
- `hypothesis_generated`
- `agent_decision`
- `export_created`
- `job_failed`

Every event should include:

- ID.
- Session ID.
- Optional branch ID.
- Optional paper ID.
- Event type.
- Payload.
- Timestamp.
- Severity.
- Source component.

## 9. Research pipeline

Target pipeline:

```txt
User query
  -> create session
  -> create root branch
  -> search candidate papers
  -> select papers
  -> fetch metadata and text
  -> chunk papers
  -> summarize papers
  -> validate summaries
  -> extract atomic claims
  -> validate claims against evidence
  -> store supported/weak/contradicted/speculative claims
  -> update branch state
  -> traverse citations/references
  -> continue/split/prune/wrap branch
  -> synthesize landscape
  -> generate hypotheses and reading plan
```

## 10. Provider abstraction

The existing provider abstraction is good and should be preserved.

Required provider methods:

- `search_papers(query, filters, limit)`
- `fetch_papers(paper_ids)`
- `fetch_papers_with_text(paper_ids)`
- `get_citations(paper_id, limit)`
- `get_references(paper_id, limit)`
- `get_citations_batch(paper_ids, limit_per_paper)`
- `get_references_batch(paper_ids, limit_per_paper)`

Current providers:

- Semantic Scholar.
- arXiv.
- Composite provider.

Future providers:

- OpenAlex.
- Crossref.
- PubMed.
- DOI resolver.
- User-uploaded PDFs.
- Zotero library.

## 11. Agent components

Current agents/components:

- InnerLoop.
- IterationLoop.
- MasterAgent.
- BranchManager.
- ManagingAgent.
- ReflectionAgent.
- HypothesisGenerator.
- Deterministic ClaimExtractor scaffold.
- Deterministic ClaimVerifier scaffold.

Target additional agents/components:

- SearchPlanner.
- PaperSelector as independent component.
- Production ClaimVerifier with evidence retrieval.
- LLM-assisted ClaimExtractor.
- ContradictionDetector.
- ResearchAdvisor.
- ExportSynthesizer.

## 12. API endpoints

Suggested initial API:

```txt
POST   /projects
GET    /projects
GET    /projects/{project_id}

POST   /sessions
GET    /sessions/{session_id}
GET    /sessions/{session_id}/loop
POST   /sessions/{session_id}/start
POST   /sessions/{session_id}/pause
POST   /sessions/{session_id}/resume
POST   /sessions/{session_id}/cancel

GET    /sessions/{session_id}/events
GET    /sessions/{session_id}/events/stream
GET    /sessions/{session_id}/branches
GET    /sessions/{session_id}/papers
GET    /sessions/{session_id}/claims
POST   /sessions/{session_id}/claims/extract
GET    /sessions/{session_id}/hypotheses

POST   /branches/{branch_id}/continue
POST   /branches/{branch_id}/split
POST   /branches/{branch_id}/prune
PATCH  /branches/{branch_id}

GET    /papers/{paper_id}
GET    /claims/{claim_id}
POST   /claims/{claim_id}/validate
GET    /claims/{claim_id}/evidence
GET    /hypotheses/{hypothesis_id}

POST   /sessions/{session_id}/exports
GET    /exports/{export_id}
```

## 13. Error handling

Every job must have:

- Retry policy.
- Timeout.
- Failure event.
- User-visible error.
- Internal error log.
- Partial-result preservation.

Never discard an entire session because one paper failed.

## 14. Migration plan

1. Keep current `src` import paths working.
2. Add product API around existing research core.
3. Add Postgres schema and repositories.
4. Replace in-memory session state gradually.
5. Add job queue.
6. Add frontend dashboard.
7. Add production claim extraction and claim validation.
8. Add exports.
9. Only then consider deeper package reorganization.
