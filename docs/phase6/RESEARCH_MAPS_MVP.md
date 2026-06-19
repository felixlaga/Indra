# Phase 6: Research maps MVP

## Scope

This implementation constructs a session-level literature landscape from durable ERLA state and exposes it through:

```http
GET /sessions/{session_id}/map
```

The web route is:

```text
/sessions/{session_id}/map
```

## Delivered views

- Citation/reference graph from resolvable provider metadata.
- Explicitly separate inferred related-paper edges.
- Publication timeline.
- Explainable branch/thematic clusters.
- Session-relative foundational candidates.
- Recent-paper distinction relative to the newest retrieved paper.
- Related-paper recommendations with shared-term reasons.
- Branch synthesis from persisted branch summaries or grounded claims.
- Deterministic field overview and caveats.

## Epistemic rules

- A citation edge is created only when persisted metadata names another paper that is already present in the same session.
- Lexical similarity is labelled `related`, marked `observed=false`, and never represented as a citation.
- `foundational_candidate` is a session-relative navigation heuristic using age and citation signals. It is not a quality judgement or a field-wide claim of foundational status.
- Branch synthesis prefers persisted branch summaries. If none exist, it uses only supported or weakly supported claims. Otherwise it emits a structural fallback that states counts and the absence of a grounded synthesis.
- Citation count is used only as one navigation signal and never as proof of quality or correctness.

## Current metadata support

The map builder resolves common provider metadata shapes including:

- `references`, `reference_ids`, `referencePapers`, `citedPapers`;
- `citations`, `citation_ids`, `citingPapers`;
- `related`, `related_papers`, `relatedPapers`;
- identifiers in strings or objects such as `paperId`, DOI, arXiv ID, Semantic Scholar ID, OpenAlex ID, title, and title/year.

Only session-local matches become graph edges.

## Verification

```bash
python -m pytest -q test_research_map.py test_api.py test_api_cors.py test_claim_evidence_retrieval.py

cd apps/web
npm run typecheck
npm test
npm run build
```

## Known limits

- The map uses citation/reference metadata already persisted with papers. It does not make live provider calls in the request handler.
- Provider metadata may not contain full citation lists, so a sparse graph can reflect incomplete persisted metadata rather than an absence of literature relations.
- The lexical cluster and recommendation system is deterministic and inspectable, but it is not embedding-based semantic clustering.
- Foundational-candidate scoring is relative to the current session corpus.
- Large-session graph virtualization and server-side cached map materialization remain later hardening work.
