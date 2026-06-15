"""Model and prompt provenance for generated artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import Field, model_validator

from .base import DomainModel
from .enums import CostSource


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class TokenUsage(DomainModel):
    """Token usage reported or estimated for a model call."""

    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class GenerationCost(DomainModel):
    """Cost metadata for a model call."""

    amount: float = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    source: CostSource = CostSource.ESTIMATED


class GenerationProvenance(DomainModel):
    """Provider/model/prompt metadata for generated artifacts."""

    provider: str
    model: str
    prompt_name: str
    prompt_version: str
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1)
    token_usage: TokenUsage | None = None
    cost: GenerationCost | None = None
    provider_request_id: str | None = None
    generated_at: datetime = Field(default_factory=utc_now)
    generation_parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def forbid_secret_material(self) -> "GenerationProvenance":
        """Reject obvious secret-bearing fields in generation parameters."""

        secret_keys = {"api_key", "authorization", "headers", "token", "secret"}
        lower_keys = {key.lower() for key in self.generation_parameters}
        if secret_keys & lower_keys:
            raise ValueError("Generation provenance must not store secret material")
        return self


class LLMCompletion(DomainModel):
    """Structured completion result with compatibility text access."""

    text: str
    provenance: GenerationProvenance | None = None
