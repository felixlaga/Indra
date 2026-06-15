# ADR-005: Evidence Source Model

Status: Accepted

## Context

Claim evidence needed to support paper chunks, abstracts, metadata, user
uploads, manual review, and external sources. The API allowed `paper_id=None`
while SQL required `paper_id`, which solved neither provenance nor manual review.

## Decision

Evidence has an explicit source type and source-specific locator:

- `paper_chunk`: requires `paper_id` and `chunk_id`.
- `paper_abstract`: requires `paper_id`.
- `paper_metadata`: requires `paper_id` and `metadata_field`.
- `user_upload`: requires `upload_id` or `document_id`.
- `external_source`: requires `external_uri` or `source_id`.
- `manual`: requires `reviewer_id`.

Manual claim review is separate from automatic validation and must not erase the
automatic validation record.

## Alternatives Considered

- Make SQL `paper_id` nullable without replacement. Rejected because evidence
would become unresolvable.
- Encode every source in freeform JSON only. Rejected because constraints would
be untestable.
- Treat manual review as evidence from a paper. Rejected because human review is
a decision, not source evidence.

## Consequences

- API evidence payloads validate locator requirements.
- SQL has source-type constraints.
- Deterministic claim verification keeps contradiction priority and does not
promote mention-only evidence.

## Compatibility And Migration Notes

For API compatibility, supplied evidence without a source type defaults to
`manual` with reviewer provenance `api_user`. Production auth-backed reviewer
identity is deferred.
