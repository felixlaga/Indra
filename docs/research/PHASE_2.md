# Phase 2: session hub

This phase follows the September product audit's executable-research phase. The historical `docs/phase2` storage milestone uses a different numbering scheme.

The session is now the primary research workspace:

- Scout Tree shows persisted parent/child branches, rationale, status and discovered papers.
- Citation Graph has pointer pan, keyboard pan, zoom/reset controls, citation-sized nodes, an accessible paper list and inspectable claim-evidence relations. Observed citation paths are distinct from inferred relatedness; inferred links are hidden by default. Supports/contradicts apply to specific claims, not agreement between entire papers.
- Timeline groups unique papers by publication year, with undated papers preserved.
- Claim Map groups claims by evidence status and optional branch/topic. It includes the existing advisor's speculative proposals, with missing evidence and supporting context in the inspector.
- Papers remains a direct, compact literature list.

Paper, branch, claim and hypothesis selection opens the right inspector. On narrow screens the inspector appears above the research view. Selections use `?view=graph&inspect=paper&id=…` URLs and survive reload and browser Back/Forward. Native history integrates with Next's search parameters without a server navigation for every selection. Selecting moves keyboard focus to the inspector; Close/Escape returns to the selection control when it is still present.

The claim ledger has all eight specified columns: claim, status, confidence, source paper, evidence count, contradiction count, branch and creation time. Six filters (status, paper, branch, claim type, confidence, review history), text search, sortable headers and 10/25/50-row pages operate on the durable session snapshot. Unscored confidence sorts last in either direction. Review history means a recorded validation check, including retrieval-only checks; it is explicitly not human approval. There is no new manual-review persistence contract in this phase.

Run controls remain available beside Advisor and Export links. Floating shortcuts are removed. The header shows elapsed wall time, claim-check counts, live connection state and worker progress. Run details retain source providers and research filters. Events, readable validation traces and jobs remain available below the workspace. Replayed events are deduplicated; progress patches the current job locally and data-changing events coalesce snapshot refreshes without resetting ledger filters. Tabs implement roving focus, arrow keys, Home/End and associated panels. Statuses retain text labels as well as distinct colors and shapes.

## Verification

```sh
cd apps/web
npm test
npm run typecheck
npm run build
```

Regression tests cover evidence and contradiction counts, all six filters together, null-confidence sorting, shared-paper deduplication, undated papers, stable graph placement and readable validation rationales.

Browser checks use both the prior real arXiv session and a separate, clearly labeled synthetic session with two branches, four papers, all six claim statuses, citations, conflicting evidence and more than one ledger page. Verify:

1. All views and tab keyboard navigation; timeline keeps undated papers.
2. Combined filters, sorting, paging and source/claim selections.
3. Inspect evidence and summaries, reload a selection URL, use Back/Forward, and open a hypothesis's missing-evidence context.
4. Graph zoom, keyboard/pointer pan and reset; inferred links remain opt-in.
5. At 390px, no page-wide horizontal overflow; the ledger scrolls within its own region.
6. A new persisted claim appears over SSE without reloading or clearing active search/topic filters.

Local verification on September 28, 2026 passed 17 frontend tests, TypeScript checking and the production build. Browser checks covered desktop and 390px layouts, paging, combined filters, branch grouping, URL reload/history, keyboard controls, evidence and hypothesis inspection, and live claim updates with active filters preserved. The synthetic fixture is UI evidence only, not model accuracy or scientific evidence.

## Boundaries

This phase reuses existing authenticated API read models and durable Postgres state. It does not change the research worker or add new branch-generation capabilities. The current advisor's hypotheses remain heuristic planning proposals, explicitly speculative. Graphs cannot show observed citations that providers have not supplied. Live model calibration still needs provider credentials.

Pagination here is client-side over the session snapshot. Database pagination, background map/advisor computation, scalable event delivery, accounts, server-side credential handling, deployment, global settings and theme preferences remain later work. Nothing in this phase pushes, merges or deploys branches.
