"""Evidence provenance and validation records."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from .base import DomainModel
from .enums import (
    EvidenceRelation,
    EvidenceSourceType,
    ValidationStatus,
    ValidationTargetType,
    ValidatorType,
)
from .provenance import GenerationProvenance, utc_now


class EvidenceLocator(DomainModel):
    """Resolvable locator for evidence supporting or challenging a claim."""

    source_type: EvidenceSourceType
    paper_id: UUID | None = None
    chunk_id: UUID | None = None
    metadata_field: str | None = None
    upload_id: str | None = None
    document_id: str | None = None
    external_uri: str | None = None
    source_id: str | None = None
    reviewer_id: str | None = None
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    section_title: str | None = None

    @model_validator(mode="after")
    def validate_locator(self) -> "EvidenceLocator":
        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_end < self.page_start
        ):
            raise ValueError("page_end cannot precede page_start")

        if self.source_type == EvidenceSourceType.PAPER_CHUNK:
            if self.paper_id is None or self.chunk_id is None:
                raise ValueError("paper_chunk evidence requires paper_id and chunk_id")
        elif self.source_type == EvidenceSourceType.PAPER_ABSTRACT:
            if self.paper_id is None:
                raise ValueError("paper_abstract evidence requires paper_id")
        elif self.source_type == EvidenceSourceType.PAPER_METADATA:
            if self.paper_id is None or not self.metadata_field:
                raise ValueError("paper_metadata evidence requires paper_id and metadata_field")
        elif self.source_type == EvidenceSourceType.USER_UPLOAD:
            if not (self.upload_id or self.document_id):
                raise ValueError("user_upload evidence requires upload_id or document_id")
        elif self.source_type == EvidenceSourceType.EXTERNAL_SOURCE:
            if not (self.external_uri or self.source_id):
                raise ValueError("external_source evidence requires external_uri or source_id")
        elif self.source_type == EvidenceSourceType.MANUAL:
            if not self.reviewer_id:
                raise ValueError("manual evidence requires reviewer_id")
        return self


class ClaimEvidence(DomainModel):
    """Evidence passage attached to a claim with provenance."""

    id: UUID
    claim_id: UUID
    session_id: UUID
    evidence_text: str
    relation: EvidenceRelation
    locator: EvidenceLocator
    score: float | None = Field(default=None, ge=0, le=1)
    created_at: datetime = Field(default_factory=utc_now)


class ValidationRecord(DomainModel):
    """Automatic or manual validation record for a target artifact."""

    id: UUID
    target_type: ValidationTargetType
    target_id: UUID
    validator_type: ValidatorType
    status: ValidationStatus
    score: float | None = Field(default=None, ge=0, le=1)
    raw_result: dict = Field(default_factory=dict)
    generation_provenance: GenerationProvenance | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ManualClaimReview(DomainModel):
    """Human review that preserves the original automatic validation state."""

    id: UUID
    claim_id: UUID
    reviewer_id: str
    manual_status: ValidationStatus
    notes: str | None = None
    automatic_validation_id: UUID | None = None
    created_at: datetime = Field(default_factory=utc_now)
