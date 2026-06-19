"""API contracts for automated claim evidence retrieval and inspection."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .models import Claim, ClaimEvidence, Paper


class ClaimAutoValidationRequest(BaseModel):
    """Controls for deterministic evidence retrieval against session papers."""

    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=0.15, ge=0, le=1)
    include_session_papers: bool = True


class ClaimValidationTrace(BaseModel):
    """Durable validation trace reconstructed from claim-validation events."""

    id: str
    status: str
    confidence: float | None = None
    validator_type: str
    notes: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class ClaimInspection(BaseModel):
    """Read model for the claim inspector and evidence passage viewer."""

    claim: Claim
    evidence: list[ClaimEvidence] = Field(default_factory=list)
    validations: list[ClaimValidationTrace] = Field(default_factory=list)
    paper: Paper | None = None


class ClaimAutoValidationResult(BaseModel):
    """Result of retrieval, relation classification, and stored validation."""

    inspection: ClaimInspection
    candidates_considered: int
    evidence_retrieved: int
