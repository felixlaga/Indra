# ERLA Roadmap

## Product direction

ERLA should become the best research navigator and epistemic research assistant: a dashboard that maps a field, explores literature through autonomous Scouts, validates claims, detects gaps, and advises researchers on what to read and investigate next.

Do not build a generic AI writing assistant first.

## Phase 0: Stabilize the repo

Goal: remove hackathon ambiguity and make the project coherent for Codex and contributors.

Tasks:

- Replace hackathon README with product README.
- Rename project metadata from `ic-hack-26` to `erla`.
- Add source-of-truth docs.
- Define target architecture.
- Define data model.
- Define validation rules.
- Define UI direction.
- Define agent rules.
- Add `.env.example` later.
- Add development setup instructions.

Exit criteria:

- A new contributor or Codex can understand the product goal.
- The repo clearly distinguishes current prototype from target architecture.
- The next implementation steps are unambiguous.

## Phase 1: Product API skeleton

Goal: introduce an API boundary without breaking the current research core.

Build:

- FastAPI product API under `apps/api` or `src/api`.
- Project endpoints.
- Session endpoints.
- Branch endpoints.
- Event endpoints.
- Paper endpoints.
- Run-control endpoints.

Do not run long research jobs synchronously in API handlers.

Exit criteria:

- API can create a project.
- API can create a session.
- API can return session/branch/paper state from a durable or temporary repository abstraction.
- API shape matches `ARCHITECTURE.md`.

## Phase 2: Durable state

Goal: replace prototype-only in-memory session state for product workflows.

Build:

- Postgres schema.
- Database migrations.
- Repository layer.
- Project/session/branch/paper persistence.
- Event persistence.
- Summary persistence.

Exit criteria:

- A session can be reconstructed after restart.
- Failed jobs and partial results are preserved.
- Dashboard does not depend on process memory.

## Phase 3: Background jobs

Goal: make research sessions reliable and cancellable.

Build:

- Job queue.
- Worker process.
- Job status table.
- Retry handling.
- Timeouts.
- Failure events.
- Pause/resume/cancel behavior.

Exit criteria:

- Long jobs do not block API requests.
- Job failures create visible events.
- Partial results are preserved.

## Phase 4: Web dashboard MVP

Goal: remove CLI-first interaction.

Build:

- Next.js frontend.
- Projects page.
- Project detail page.
- Session dashboard.
- Session creation.
- Run controls.
- Branch tree visualization.
- Paper list.
- Paper inspector.
- Event log.

Exit criteria:

- User can start a research session online.
- User can see branches and papers appear.
- User can click papers and branches.
- User does not need CLI.

## Phase 5: Claim-level validation

Goal: turn ERLA into a trustworthy evidence engine.

Build:

- Atomic claim extraction.
- Claim evidence retrieval.
- Claim verification.
- Claim statuses.
- Claim ledger UI.
- Claim inspector.
- Evidence passage viewer.
- Validation trace panel.

Exit criteria:

- Summaries are decomposed into claims.
- Claims have evidence status.
- Users can inspect supporting passages.
- Unsupported claims are not promoted silently.

## Phase 6: Research maps

Goal: make the dashboard useful for real research navigation.

Build:

- Citation graph view.
- Timeline view.
- Cluster labels.
- Foundational/recent paper distinction.
- Related paper recommendations.
- Branch-level synthesis.
- Field overview.

Exit criteria:

- User can visually understand the literature landscape.
- User can identify foundational papers.
- User can identify recent papers.
- User can follow citation/reference paths.

## Phase 7: Gap and contradiction analysis

Goal: help researchers find promising directions.

Build:

- Contradiction detection.
- Gap detection.
- Weak-evidence detection.
- Open-problem extraction.
- Research advisor panel.
- Hypothesis generation improvements.
- Hypothesis inspector.

Exit criteria:

- ERLA surfaces disagreements.
- ERLA surfaces weakly covered areas.
- ERLA recommends research directions with evidence.
- Hypotheses are clearly marked as speculative.

## Phase 8: Exports

Goal: produce useful research artifacts.

Build:

- BibTeX export.
- RIS export.
- Markdown research report.
- LaTeX literature review outline.
- Annotated bibliography.
- Claim ledger CSV/JSON.
- Research map JSON.

Exit criteria:

- User can leave ERLA with useful artifacts.
- Exports preserve validation status.
- Unsupported claims are labeled.

## Immediate priority order

1. Upload this corrected root-level doc bundle.
2. Replace README and pyproject metadata.
3. Add API skeleton.
4. Add database schema and migrations.
5. Add frontend dashboard shell.
6. Wire session creation to existing research loop.
7. Add event streaming.
8. Add paper and branch inspectors.
9. Add claim extraction.
10. Add claim validation.

## Do not prioritize yet

- Full academic writing editor.
- Payment system.
- Mobile app.
- Browser extension.
- Complex collaboration.
- Fancy 3D visualizations.
- Overly broad model-provider abstraction.
- Premature enterprise features.
