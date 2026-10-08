# Phase 9: large sessions, measured

The remaining scale items were database pagination, graph virtualization, asynchronous exports and cache eviction or versioning. Rather than build all four, this phase measured the largest session the research limits allow and fixed what the numbers showed.

## The fixture

A synthetic session in Postgres at the maximum the limits allow: 260 papers (20 root plus 12 branches × 20), 1,300 passages, 2,600 claims and 7,800 evidence links. It is clearly labelled as a performance fixture, not research.

## Measurements before changes (local Postgres, M-series Mac)

| What | Result |
| --- | --- |
| `GET /sessions/{id}/state` | 0.23 s, **9.9 MB** (7.65 MB of it evidence passages) |
| `/claims`, `/papers`, `/events` | 37 ms, 17 ms, 7 ms |
| BibTeX, claim-ledger CSV, Markdown report exports | 0.19 s, 0.20 s, 0.43 s |
| Map and advisor build in the view worker | 0.6 s; cached reads ~25 ms |
| Session page ready in the browser | ~0.5 s |
| Citation graph with 260 papers | 127 ms to render, ~4,500 DOM nodes |

Rendering, exports and views are fast. The problem is transfer size: the dashboard downloaded 9.9 MB on every load and, while research ran, reloaded it after nearly every event (at most every 500 ms). The snapshot was not compressed and the dashboard never reads the passage text in it.

## Changes

- **Compact snapshots.** `GET /sessions/{id}/state?compact=true` keeps only the evidence fields the hub counts (`id`, `claim_id`, `paper_id`, `relation`, `source_type`); passages are still fetched per claim when one is opened. The dashboard uses it.
- **Compression.** The API gzips responses over 2 KB (event streams excluded), and the dashboard's proxy gzips JSON and text for browsers that accept it, since Next.js does not compress route-handler responses.
- **Adaptive reloads.** During a run the session page waits four times its last load time before reloading (between 0.5 and 10 seconds), so large sessions are not reloaded continuously.
- **Versioned view cache.** Cached maps and advisor results now record the builder version that produced them. A result from an older version is rebuilt on its next request instead of being served. This also fixes a real upgrade problem: advice cached before Phase 5 would otherwise have stayed without model hypotheses until the session changed again.

## Result

| What | Before | After |
| --- | --- | --- |
| Snapshot sent to the browser | 9.9 MB | **616 KB** (4.1 MB uncompressed) |
| Snapshot over a 20 Mbit/s link | ~4 s | ~0.25 s |

## Not built, and why

- **Database pagination for papers and claims**: the full lists serve in under 40 ms and the ledger already pages and filters 2,600 rows in the browser.
- **Graph virtualization**: 260 nodes render in 127 ms.
- **Asynchronous export jobs**: the slowest export takes 0.43 s.
- **Cache eviction**: each session has one cached row, replaced on rebuild, so the cache cannot grow beyond the number of sessions.

Revisit these if the research limits are raised well beyond 20 papers per branch and 12 branches.

## Verification — October 8, 2026

- 217 backend tests including compact snapshot fields, gzip negotiation, and versioned rebuilds on memory and real Postgres; 27 frontend tests (compact snapshot request), typecheck and build.
- Browser on the fixture: 616 KB transferred, all 2,600 claims checked, ledger counts intact, live updates connected through the compressing proxy.
