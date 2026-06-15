"""Phase 1 canonical contract tests."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from src.api.mappings import (
    branch_to_api,
    paper_to_api,
    session_paper_view_to_api,
    summary_to_api,
)
from src.domain.enums import (
    BranchMode,
    BranchStatus,
    ClaimStatus,
    ClaimType,
    EventSeverity,
    EvidenceRelation,
    EvidenceSourceType,
    SessionStatus,
    SummaryType,
    SummaryValidationStatus,
)
from src.domain.evidence import EvidenceLocator, ManualClaimReview
from src.domain.ids import new_uuid_str, parse_uuid, serialize_uuid
from src.domain.mappings import MappingError, paper_from_provider, runtime_branch_to_domain
from src.domain.papers import (
    Paper,
    PaperExternalIds,
    SessionPaper,
    SessionPaperView,
    canonical_paper_key,
    normalize_arxiv_id,
    normalize_doi,
)
from src.domain.provenance import (
    CostSource,
    GenerationCost,
    GenerationProvenance,
    LLMCompletion,
    TokenUsage,
)
from src.domain.sessions import Branch
from src.domain.summaries import Summary
from src.domain.transitions import (
    BRANCH_TRANSITIONS,
    SESSION_TRANSITIONS,
    InvalidTransitionError,
    validate_branch_transition,
    validate_session_transition,
)
from src.orchestration.inner_loop import InnerLoop
from src.orchestration.models import SummaryGenerationResult, ValidatedSummary
from src.semantic_scholar.models import Author, OpenAccessPdf, PaperDetails


def test_uuid_helpers_reject_legacy_ids_and_serialize() -> None:
    durable_id = new_uuid_str()

    assert str(parse_uuid(durable_id)) == durable_id
    assert serialize_uuid(UUID(durable_id)) == durable_id

    with pytest.raises(ValueError):
        parse_uuid("branch_abcd1234")


def test_exact_canonical_enum_values() -> None:
    assert [status.value for status in SessionStatus] == [
        "pending",
        "running",
        "paused",
        "completed",
        "cancelled",
        "failed",
    ]
    assert [status.value for status in BranchStatus] == [
        "pending",
        "running",
        "paused",
        "completed",
        "pruned",
        "failed",
    ]
    assert [mode.value for mode in BranchMode] == [
        "search_summarize",
        "hypothesis",
        "synthesis",
        "gap_analysis",
    ]
    assert [status.value for status in SummaryValidationStatus] == [
        "not_validated",
        "validated",
        "partially_validated",
        "failed_validation",
    ]
    assert [status.value for status in ClaimStatus] == [
        "supported",
        "weakly_supported",
        "contradicted",
        "not_found",
        "speculative",
        "needs_review",
    ]
    assert [relation.value for relation in EvidenceRelation] == [
        "supports",
        "weakly_supports",
        "contradicts",
        "mentions",
        "insufficient",
    ]
    assert [severity.value for severity in EventSeverity] == [
        "debug",
        "info",
        "warning",
        "error",
        "critical",
    ]


def test_paper_canonical_key_precedence_and_normalization() -> None:
    external_ids = PaperExternalIds(
        doi="https://doi.org/10.1000/ABC",
        arxiv_id="arXiv:2301.00001v2",
        semantic_scholar_id="S2",
        openalex_id="W1",
    )

    assert normalize_doi("DOI: 10.1000/ABC") == "10.1000/abc"
    assert normalize_arxiv_id("https://arxiv.org/pdf/2301.00001v3.pdf") == "2301.00001"
    assert canonical_paper_key(external_ids, "Ignored", 2024) == "doi:10.1000/abc"
    assert (
        canonical_paper_key(PaperExternalIds(arxiv_id="2301.00001v1"), "Ignored", 2024)
        == "arxiv:2301.00001"
    )
    assert (
        canonical_paper_key(PaperExternalIds(semantic_scholar_id="S2"), "Ignored", 2024)
        == "semantic_scholar:S2"
    )
    assert (
        canonical_paper_key(PaperExternalIds(openalex_id="W1"), "Ignored", 2024)
        == "openalex:W1"
    )
    assert (
        canonical_paper_key(PaperExternalIds(), "A Study: Of Things", 2024)
        == "title_year:a study of things:2024"
    )


def test_paper_is_global_and_session_paper_is_contextual() -> None:
    paper_id = uuid4()
    session_a = uuid4()
    session_b = uuid4()
    branch_a = uuid4()
    branch_b = uuid4()
    paper = Paper(
        id=paper_id,
        canonical_key="doi:10.1/test",
        external_ids=PaperExternalIds(doi="10.1/test"),
        title="Shared Paper",
    )
    first = SessionPaper(id=uuid4(), session_id=session_a, branch_id=branch_a, paper_id=paper_id)
    second = SessionPaper(id=uuid4(), session_id=session_b, branch_id=branch_b, paper_id=paper_id)

    assert not hasattr(paper, "session_id")
    assert first.paper_id == second.paper_id == paper.id
    assert first.session_id != second.session_id

    view = session_paper_view_to_api(SessionPaperView(paper=paper, session_paper=first))
    assert view.paper.id == str(paper.id)
    assert view.session_id == str(session_a)
    assert view.branch_id == str(branch_a)


def test_validated_summary_cannot_hold_partial_result() -> None:
    with pytest.raises(ValueError):
        ValidatedSummary(
            paper_id="p1",
            paper_title="Paper",
            summary="Partial",
            groundedness=0.72,
            validation_status=SummaryValidationStatus.PARTIALLY_VALIDATED,
        )

    result = SummaryGenerationResult(
        paper_id="p1",
        paper_title="Paper",
        summary="Partial text is preserved.",
        groundedness=0.72,
        validation_status=SummaryValidationStatus.PARTIALLY_VALIDATED,
        attempts=2,
    )
    assert result.summary == "Partial text is preserved."
    assert result.to_validated_summary() is None


@pytest.mark.asyncio
async def test_inner_loop_preserves_partial_failed_and_provenance() -> None:
    provenance = GenerationProvenance(
        provider="test",
        model="fake-model",
        prompt_name="paper_summary",
        prompt_version="v1",
    )

    class FakeSummarizer:
        async def complete_structured(self, **kwargs):
            return LLMCompletion(text="Generated summary.", provenance=provenance)

        async def complete(self, *args, **kwargs):
            return "Generated summary."

    class FakeHaluGate:
        def __init__(self, groundedness: float, contradictions: int = 0):
            self.groundedness = groundedness
            self.contradictions = contradictions

        async def validate(self, **kwargs):
            return SimpleNamespace(nli_contradictions=self.contradictions, spans=[])

        def compute_groundedness(self, result, summary_text):
            return self.groundedness

    paper = PaperDetails(
        paper_id="s2-1",
        title="Paper",
        abstract="Source text",
        authors=[Author(name="Ada")],
    )

    loop = InnerLoop(
        search_provider=SimpleNamespace(),
        summarizer=FakeSummarizer(),
        halugate=FakeHaluGate(0.82),
    )
    partial = await loop._summarize_and_validate_result(paper)
    assert partial.validation_status == SummaryValidationStatus.PARTIALLY_VALIDATED
    assert partial.summary == "Generated summary."
    assert partial.generation_provenance == provenance

    loop.halugate = FakeHaluGate(0.99, contradictions=1)
    failed = await loop._summarize_and_validate_result(paper)
    assert failed.validation_status == SummaryValidationStatus.FAILED_VALIDATION
    assert failed.to_validated_summary() is None


def test_evidence_locator_rules_and_manual_review_separation() -> None:
    paper_id = uuid4()
    chunk_id = uuid4()
    EvidenceLocator(
        source_type=EvidenceSourceType.PAPER_CHUNK,
        paper_id=paper_id,
        chunk_id=chunk_id,
        page_start=1,
        page_end=2,
    )
    EvidenceLocator(source_type=EvidenceSourceType.PAPER_ABSTRACT, paper_id=paper_id)
    EvidenceLocator(
        source_type=EvidenceSourceType.PAPER_METADATA,
        paper_id=paper_id,
        metadata_field="title",
    )
    EvidenceLocator(source_type=EvidenceSourceType.USER_UPLOAD, upload_id="upload-1")
    EvidenceLocator(source_type=EvidenceSourceType.EXTERNAL_SOURCE, external_uri="https://example.test")
    EvidenceLocator(source_type=EvidenceSourceType.MANUAL, reviewer_id="reviewer-1")

    with pytest.raises(ValueError):
        EvidenceLocator(source_type=EvidenceSourceType.PAPER_CHUNK, paper_id=paper_id)
    with pytest.raises(ValueError):
        EvidenceLocator(source_type=EvidenceSourceType.MANUAL)
    with pytest.raises(ValueError):
        EvidenceLocator(
            source_type=EvidenceSourceType.PAPER_ABSTRACT,
            paper_id=paper_id,
            page_start=3,
            page_end=2,
        )

    review = ManualClaimReview(
        id=uuid4(),
        claim_id=uuid4(),
        reviewer_id="reviewer-1",
        manual_status="passed",
        automatic_validation_id=uuid4(),
    )
    assert review.automatic_validation_id is not None


def test_transition_matrices_and_retry_policy() -> None:
    for current, targets in SESSION_TRANSITIONS.items():
        for target in targets:
            validate_session_transition(current, target)

    for current, targets in BRANCH_TRANSITIONS.items():
        for target in targets:
            validate_branch_transition(current, target)

    with pytest.raises(InvalidTransitionError):
        validate_session_transition(SessionStatus.COMPLETED, SessionStatus.RUNNING)
    with pytest.raises(InvalidTransitionError):
        validate_branch_transition(BranchStatus.PRUNED, BranchStatus.RUNNING)

    assert validate_branch_transition(BranchStatus.FAILED, BranchStatus.RUNNING).retry


def test_provider_runtime_domain_and_api_mappings_are_explicit() -> None:
    paper_id = uuid4()
    provider_paper = PaperDetails(
        paper_id="arxiv:2301.00001",
        title="Mapped Paper",
        abstract="Abstract",
        authors=[Author(name="Grace")],
        year=2024,
        venue="arXiv",
        citation_count=4,
        external_ids={"ArXiv": "2301.00001v2", "DOI": "10.2/MAP"},
        open_access_pdf=OpenAccessPdf(url="https://arxiv.org/pdf/2301.00001.pdf"),
    )

    paper = paper_from_provider(provider_paper, paper_id=paper_id)
    assert paper.id == paper_id
    assert paper.canonical_key == "doi:10.2/map"
    assert paper.external_ids.arxiv_id == "2301.00001"
    assert paper_to_api(paper).id == str(paper_id)

    with pytest.raises(MappingError):
        paper_from_provider(provider_paper)

    session_id = uuid4()
    runtime_branch = SimpleNamespace(
        id=str(uuid4()),
        parent_branch_id=None,
        query="mapped query",
        mode=BranchMode.SEARCH_SUMMARIZE,
        status=BranchStatus.FAILED,
        failure_reason="provider failed",
        prune_reason=None,
        context_window_used=12,
        max_context_window=128000,
        created_at=None,
        updated_at=None,
    )
    domain_branch = runtime_branch_to_domain(runtime_branch, session_id=session_id)
    assert domain_branch.status == BranchStatus.FAILED
    assert branch_to_api(domain_branch).failure_reason == "provider failed"


def test_summary_and_provenance_api_serialization() -> None:
    provenance = GenerationProvenance(
        provider="openrouter",
        model="model-a",
        prompt_name="paper_summary",
        prompt_version="v1",
        temperature=0.3,
        token_usage=TokenUsage(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        cost=GenerationCost(amount=0.01, currency="USD", source=CostSource.ESTIMATED),
    )
    summary = Summary(
        id=uuid4(),
        session_id=uuid4(),
        summary_type=SummaryType.PAPER,
        text="Summary",
        validation_status=SummaryValidationStatus.VALIDATED,
        groundedness_score=0.96,
        generation_provenance=provenance,
    )

    api_summary = summary_to_api(summary)
    assert api_summary.validation_status == SummaryValidationStatus.VALIDATED
    assert api_summary.generation_provenance["prompt_version"] == "v1"
    assert api_summary.generation_provenance["token_usage"]["total_tokens"] == 3

    with pytest.raises(ValidationError):
        GenerationProvenance(
            provider="x",
            model="y",
            prompt_name="z",
            prompt_version="v1",
            generation_parameters={"api_key": "secret"},
        )


def test_api_paper_lacks_session_and_branch_fields() -> None:
    paper = Paper(
        id=uuid4(),
        canonical_key="doi:10.3/no-context",
        external_ids=PaperExternalIds(doi="10.3/no-context"),
        title="No Context",
    )
    api_paper = paper_to_api(paper)

    assert not hasattr(api_paper, "session_id")
    assert not hasattr(api_paper, "branch_id")
    assert api_paper.model_dump(mode="json")["canonical_key"] == "doi:10.3/no-context"
