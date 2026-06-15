"""Canonical ERLA enum values shared across API, runtime, and SQL."""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """String enum with readable string conversion."""

    def __str__(self) -> str:
        return self.value


class SessionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class BranchStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    PRUNED = "pruned"
    FAILED = "failed"


class BranchMode(StrEnum):
    SEARCH_SUMMARIZE = "search_summarize"
    HYPOTHESIS = "hypothesis"
    SYNTHESIS = "synthesis"
    GAP_ANALYSIS = "gap_analysis"


class SummaryType(StrEnum):
    PAPER = "paper"
    BRANCH = "branch"
    SESSION = "session"
    FIELD = "field"
    METHOD = "method"
    CONTRADICTION = "contradiction"
    GAP = "gap"


class SummaryValidationStatus(StrEnum):
    NOT_VALIDATED = "not_validated"
    VALIDATED = "validated"
    PARTIALLY_VALIDATED = "partially_validated"
    FAILED_VALIDATION = "failed_validation"


class ClaimType(StrEnum):
    FACTUAL = "factual"
    METHODOLOGICAL = "methodological"
    EMPIRICAL_RESULT = "empirical_result"
    THEORETICAL_RESULT = "theoretical_result"
    DEFINITION = "definition"
    LIMITATION = "limitation"
    ASSUMPTION = "assumption"
    COMPARISON = "comparison"
    HYPOTHESIS = "hypothesis"
    RECOMMENDATION = "recommendation"


class ClaimStatus(StrEnum):
    SUPPORTED = "supported"
    WEAKLY_SUPPORTED = "weakly_supported"
    CONTRADICTED = "contradicted"
    NOT_FOUND = "not_found"
    SPECULATIVE = "speculative"
    NEEDS_REVIEW = "needs_review"


class EvidenceRelation(StrEnum):
    SUPPORTS = "supports"
    WEAKLY_SUPPORTS = "weakly_supports"
    CONTRADICTS = "contradicts"
    MENTIONS = "mentions"
    INSUFFICIENT = "insufficient"


class EvidenceSourceType(StrEnum):
    PAPER_CHUNK = "paper_chunk"
    PAPER_ABSTRACT = "paper_abstract"
    PAPER_METADATA = "paper_metadata"
    USER_UPLOAD = "user_upload"
    MANUAL = "manual"
    EXTERNAL_SOURCE = "external_source"


class EventSeverity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PaperDiscoveryMethod(StrEnum):
    QUERY_SEARCH = "query_search"
    CITATION = "citation"
    REFERENCE = "reference"
    USER_UPLOAD = "user_upload"
    MANUAL_ADD = "manual_add"
    AGENT_RECOMMENDATION = "agent_recommendation"


class ValidationTargetType(StrEnum):
    SUMMARY = "summary"
    CLAIM = "claim"
    HYPOTHESIS = "hypothesis"
    SYNTHESIS = "synthesis"


class ValidatorType(StrEnum):
    HALUGATE_TOKEN = "halugate_token"
    NLI = "nli"
    CLAIM_EVIDENCE = "claim_evidence"
    MANUAL = "manual"
    DETERMINISTIC_CLAIM_VERIFIER = "deterministic_claim_verifier"


class ValidationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    ERROR = "error"
    NOT_APPLICABLE = "not_applicable"


class CostSource(StrEnum):
    ESTIMATED = "estimated"
    PROVIDER_REPORTED = "provider_reported"


class HypothesisStatus(StrEnum):
    DRAFT = "draft"
    SUPPORTED = "supported"
    WEAK = "weak"
    REJECTED = "rejected"
    SELECTED = "selected"
    ARCHIVED = "archived"


class AgentDecisionType(StrEnum):
    PAPER_SELECTION = "paper_selection"
    QUERY_GENERATION = "query_generation"
    BRANCH_SPLIT = "branch_split"
    BRANCH_PRUNE = "branch_prune"
    BRANCH_CONTINUE = "branch_continue"
    HYPOTHESIS_GENERATION = "hypothesis_generation"
    GAP_DETECTION = "gap_detection"
    READING_PLAN = "reading_plan"
    RESEARCH_DIRECTION = "research_direction"
    EXPORT_SYNTHESIS = "export_synthesis"


class ExportType(StrEnum):
    MARKDOWN_REPORT = "markdown_report"
    LATEX_OUTLINE = "latex_outline"
    BIBTEX = "bibtex"
    RIS = "ris"
    CLAIM_LEDGER_CSV = "claim_ledger_csv"
    CLAIM_LEDGER_JSON = "claim_ledger_json"
    RESEARCH_MAP_JSON = "research_map_json"
    ANNOTATED_BIBLIOGRAPHY = "annotated_bibliography"


class ExportStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
