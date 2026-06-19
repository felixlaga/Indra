"""Export catalog and artifact contracts."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExportDescriptor(BaseModel):
    """One downloadable session artifact."""

    format: str
    label: str
    filename: str
    media_type: str
    description: str
    preserves_validation_status: bool = True


class ExportCatalog(BaseModel):
    """Available artifacts for a research session."""

    session_id: str
    artifacts: list[ExportDescriptor] = Field(default_factory=list)


class ExportArtifact(BaseModel):
    """Generated text artifact returned by the export service."""

    format: str
    filename: str
    media_type: str
    content: str
