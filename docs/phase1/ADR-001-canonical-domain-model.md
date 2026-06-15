# ADR-001: Canonical Domain Model

Status: Accepted

## Context

ERLA represented core entities in runtime dataclasses, FastAPI models, SQL,
Convex projection records, and frontend mock data. These shapes drifted in IDs,
statuses, paper scoping, validation states, and evidence provenance.

## Decision

Canonical product contracts live in `src/domain`. Domain modules must not import
FastAPI, Convex, database clients, model clients, or ML services. API schemas,
runtime dataclasses, provider models, and SQL map explicitly to and from domain
contracts.

## Alternatives Considered

- Keep API models as canonical. Rejected because FastAPI should not define the
database and runtime contract.
- Keep SQL as canonical. Rejected because Python needs importable, tested
contracts before the Postgres adapter exists.
- Rewrite runtime models wholesale. Rejected as too broad for Phase 1.

## Consequences

- `src/domain` is the stable vocabulary for Phase 2.
- Mapping code is named and testable.
- Legacy runtime shapes continue where rewriting would be risky.

## Compatibility And Migration Notes

`src/__init__.py` and `src/api/__init__.py` now use lazy exports to keep domain
and mapping imports lightweight. Existing convenience imports still resolve.
