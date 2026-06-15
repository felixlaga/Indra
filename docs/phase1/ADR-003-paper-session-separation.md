# ADR-003: Paper And SessionPaper Separation

Status: Accepted

## Context

The API modeled papers as session-scoped records, while SQL already had global
`papers` and contextual `session_papers`. This made global deduplication and
multi-session paper reuse ambiguous.

## Decision

`Paper` is global and must not contain `session_id` or `branch_id`.
`SessionPaper` stores session ID, optional branch ID, global paper ID, discovery
method, selection reason, selected flag, iteration number, and timestamp.
`SessionPaperView` combines both for API reads.

Canonical key precedence:

1. Normalized DOI.
2. Normalized arXiv ID.
3. Semantic Scholar ID.
4. OpenAlex ID.
5. Normalized title plus year.

## Alternatives Considered

- Keep session-scoped API Paper and normalize later. Rejected because it keeps
Phase 2 ambiguous.
- Use fuzzy title matching as canonical identity. Rejected because fuzzy matches
are heuristics, not durable identity.

## Consequences

- One global paper can appear in multiple sessions and branches.
- Session paper listing returns metadata plus contextual discovery fields.
- Provider-to-domain conversion is explicit.

## Compatibility And Migration Notes

The in-memory repository keeps separate `_papers` and `_session_papers` maps but
does not yet populate them from workers. Automated discovery persistence remains
Phase 2.
