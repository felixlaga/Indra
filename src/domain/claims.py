"""Canonical claim contract."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from .base import DomainModel
from .enums import ClaimStatus, ClaimType
from .provenance import utc_now


class Claim(DomainModel):
    """Atomic claim extracted from generated research text."""

    id: UUID
    session_id: UUID
    claim_text: str
    claim_type: ClaimType
    status: ClaimStatus = ClaimStatus.NEEDS_REVIEW
    branch_id: UUID | None = None
    paper_id: UUID | None = None
    summary_id: UUID | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    created_by: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
