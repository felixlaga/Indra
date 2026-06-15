"""Shared Pydantic base configuration for domain models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    """Base model for canonical domain values."""

    model_config = ConfigDict(
        use_enum_values=False,
        arbitrary_types_allowed=False,
    )
