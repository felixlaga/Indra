"""Identifier primitives for durable Indra entities and provider IDs."""

from __future__ import annotations

from typing import NewType
from uuid import UUID, uuid4


DURABLE_ENTITY_NAMES = frozenset(
    {
        "user",
        "project",
        "research_session",
        "branch",
        "paper",
        "session_paper",
        "paper_document",
        "paper_chunk",
        "summary",
        "claim",
        "claim_evidence",
        "validation",
        "hypothesis",
        "agent_decision",
        "event",
        "export",
        "job",
    }
)

ProviderId = NewType("ProviderId", str)


def new_uuid() -> UUID:
    """Create a UUID4 for a durable Indra entity."""

    return uuid4()


def new_uuid_str() -> str:
    """Create a UUID4 and serialize it as a canonical lowercase string."""

    return str(new_uuid())


def parse_uuid(value: str | UUID) -> UUID:
    """Parse and validate an internal durable UUID.

    Provider identifiers such as DOI, arXiv IDs, Semantic Scholar IDs, and
    OpenAlex IDs must remain strings and should not be passed here.
    """

    if isinstance(value, UUID):
        return value
    if not isinstance(value, str):
        raise ValueError("Durable Indra IDs must be UUID strings")
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValueError(f"Malformed durable Indra UUID: {value!r}") from exc


def serialize_uuid(value: str | UUID) -> str:
    """Serialize a durable UUID as a canonical lowercase string."""

    return str(parse_uuid(value))
