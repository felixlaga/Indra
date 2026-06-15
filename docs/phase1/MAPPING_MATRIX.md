# Phase 1 Mapping Matrix

Mappings are explicit and side-effect free. Read mappings must not create random
IDs. Creation mappings receive an existing ID or an explicit ID factory.

| Source | Target | Function | Required IDs | Notes |
|---|---|---|---|---|
| Provider paper | Domain `Paper` | `src/domain/mappings.py::paper_from_provider` | `paper_id` or `id_factory` | Preserves provider IDs, title, abstract, authors, counts, URLs |
| Runtime branch | Domain `Branch` | `runtime_branch_to_domain` | Runtime branch UUID and session UUID | Rejects malformed internal IDs |
| Runtime summary result | Domain `Summary` | `summary_from_runtime_result` | Summary/session UUIDs | Preserves validation status and provenance |
| Runtime hypothesis | Domain `Hypothesis` | `runtime_hypothesis_to_domain` | Hypothesis/session UUIDs | Provider paper IDs need explicit lookup |
| Domain `Paper` | API `Paper` | `src/api/mappings.py::paper_to_api` | Existing domain ID | Does not add session or branch fields |
| Domain `SessionPaperView` | API `SessionPaperView` | `session_paper_view_to_api` | Existing domain IDs | Combines global metadata and discovery context |
| Domain `Branch` | API `Branch` | `branch_to_api` | Existing domain ID | Preserves failure/prune reasons |
| Domain `Summary` | API `Summary` | `summary_to_api` | Existing domain ID | Serializes provenance as JSON |
| Domain `Claim` | API `Claim` | `claim_to_api` | Existing domain ID | Preserves status, type, confidence |
| Domain `ClaimEvidence` | API `ClaimEvidence` | `claim_evidence_to_api` | Existing domain ID | Preserves source locator fields |
| Domain `Event` | API `Event` | `event_to_api` | Existing domain ID | Preserves severity enum |

## Deferred Mappings

- Full database row mappings are deferred until the Postgres repository.
- Convex mappings remain projection-oriented and may intentionally drop
production-only fields.
