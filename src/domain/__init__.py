"""Canonical ERLA domain contracts.

The domain package is intentionally lightweight: importing it must not create
network clients, FastAPI apps, ML models, database connections, or Convex state.
"""

from .enums import (
    AgentDecisionType,
    BranchMode,
    BranchStatus,
    ClaimStatus,
    ClaimType,
    CostSource,
    EventSeverity,
    EvidenceRelation,
    EvidenceSourceType,
    ExportStatus,
    ExportType,
    HypothesisStatus,
    PaperDiscoveryMethod,
    SummaryType,
    SummaryValidationStatus,
    ValidationStatus,
    ValidationTargetType,
    ValidatorType,
)
from .ids import (
    DURABLE_ENTITY_NAMES,
    ProviderId,
    new_uuid,
    new_uuid_str,
    parse_uuid,
    serialize_uuid,
)

__all__ = [
    "AgentDecisionType",
    "BranchMode",
    "BranchStatus",
    "ClaimStatus",
    "ClaimType",
    "CostSource",
    "DURABLE_ENTITY_NAMES",
    "EventSeverity",
    "EvidenceRelation",
    "EvidenceSourceType",
    "ExportStatus",
    "ExportType",
    "HypothesisStatus",
    "PaperDiscoveryMethod",
    "ProviderId",
    "SummaryType",
    "SummaryValidationStatus",
    "ValidationStatus",
    "ValidationTargetType",
    "ValidatorType",
    "new_uuid",
    "new_uuid_str",
    "parse_uuid",
    "serialize_uuid",
]
