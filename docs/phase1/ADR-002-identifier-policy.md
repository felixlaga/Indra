# ADR-002: Identifier Policy

Status: Accepted

## Context

Runtime branches used truncated UUID strings and API entities used prefixed
short strings. SQL used `uuid`. Provider IDs such as DOI, arXiv, Semantic
Scholar, and OpenAlex were sometimes treated like internal IDs.

## Decision

Durable ERLA entities use UUID semantics. API responses serialize these UUIDs as
standard lowercase UUID strings. Provider IDs remain strings in explicit
external ID fields.

## Alternatives Considered

- Continue prefixed API IDs. Rejected because SQL and Phase 2 storage would need
translation rules.
- Hash legacy strings into UUIDs. Rejected because it creates silent identity
claims.
- Typed wrapper classes for every ID. Deferred; direct `uuid.UUID` plus helpers
is sufficient for Phase 1.

## Consequences

- New in-memory product IDs are UUID strings.
- Runtime branch creation uses full UUID strings.
- Mappers reject malformed internal IDs instead of coercing them.

## Compatibility And Migration Notes

`LoopState.loop_id` may still use the legacy `loop_*` runtime identifier because
it is not a durable product entity. Provider identifiers are represented by
`PaperExternalIds` and `ProviderId`.
