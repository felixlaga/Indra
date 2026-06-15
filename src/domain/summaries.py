"""Canonical summary models and validation-state policy."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from .base import DomainModel
from .enums import SummaryType, SummaryValidationStatus
from .provenance import GenerationProvenance, utc_now


class Summary(DomainModel):
    """Generated summary with explicit validation state."""

    id: UUID
    session_id: UUID
    summary_type: SummaryType
    text: str
    branch_id: UUID | None = None
    paper_id: UUID | None = None
    groundedness_score: float | None = Field(default=None, ge=0, le=1)
    validation_status: SummaryValidationStatus = SummaryValidationStatus.NOT_VALIDATED
    validation_details: dict = Field(default_factory=dict)
    generation_provenance: GenerationProvenance | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @property
    def accepted_for_downstream_use(self) -> bool:
        """Default downstream eligibility policy for hypotheses and synthesis."""

        return self.validation_status == SummaryValidationStatus.VALIDATED


class SummaryGenerationResult(DomainModel):
    """Runtime result that preserves generated text for all validation outcomes."""

    summary_text: str | None
    validation_status: SummaryValidationStatus
    groundedness_score: float | None = Field(default=None, ge=0, le=1)
    validation_details: dict = Field(default_factory=dict)
    attempts: int = Field(default=0, ge=0)
    accepted_for_downstream_use: bool = False
    error: str | None = None
    generation_provenance: GenerationProvenance | None = None


def classify_summary_validation(
    groundedness_score: float | None,
    threshold: float,
    nli_contradictions: int = 0,
    validation_error: str | None = None,
    validation_attempted: bool = True,
) -> SummaryValidationStatus:
    """Classify summary validation according to the canonical policy."""

    if not validation_attempted:
        return SummaryValidationStatus.NOT_VALIDATED
    if validation_error:
        return SummaryValidationStatus.FAILED_VALIDATION
    if groundedness_score is None:
        return SummaryValidationStatus.FAILED_VALIDATION
    if nli_contradictions > 0:
        return SummaryValidationStatus.FAILED_VALIDATION
    if groundedness_score >= threshold:
        return SummaryValidationStatus.VALIDATED
    return SummaryValidationStatus.PARTIALLY_VALIDATED
