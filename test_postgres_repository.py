"""Tests for the Phase 2 Postgres repository boundary."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.api.models import (
    BranchStatus,
    EvidenceSourceType,
    JobStatus,
    JobType,
    SessionStatus,
)
from src.api.postgres_repository import (
    PostgresRepository,
    _branch_from_row,
    _claim_evidence_from_row,
    _event_from_row,
    _job_from_row,
    _paper_from_row,
    _project_from_row,
    _runtime_loop_binding_from_row,
    _session_from_row,
    _session_paper_view_from_row,
)
from src.api.repository_factory import (
    DATABASE_URL_ENV,
    RepositoryConfigurationError,
    create_repository,
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def test_postgres_repository_instantiates_without_connecting() -> None:
    repository = PostgresRepository("postgresql://example")

    assert isinstance(repository, PostgresRepository)


def test_factory_selects_postgres_backend(monkeypatch) -> None:
    monkeypatch.setenv(DATABASE_URL_ENV, "postgresql://example")

    repository = create_repository("postgres")

    assert isinstance(repository, PostgresRepository)


def test_factory_requires_database_url(monkeypatch) -> None:
    monkeypatch.delenv(DATABASE_URL_ENV, raising=False)

    with pytest.raises(RepositoryConfigurationError):
        create_repository("postgres")


def test_core_row_mappers_preserve_uuid_strings_and_statuses() -> None:
    timestamp = now()
    project_id = uuid4()
    session_id = uuid4()
    branch_id = uuid4()
    paper_id = uuid4()

    project = _project_from_row(
        {
            "id": project_id,
            "title": "Project",
            "description": None,
            "field": "AI",
            "settings": {"a": 1},
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    )
    assert project.id == str(project_id)

    session = _session_from_row(
        {
            "id": session_id,
            "project_id": project_id,
            "initial_query": "query",
            "source_providers": ["semantic_scholar"],
            "filters": {},
            "parameters": {},
            "status": "running",
            "failure_reason": None,
            "started_at": timestamp,
            "completed_at": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    )
    assert session.status == SessionStatus.RUNNING
    assert session.project_id == str(project_id)

    branch = _branch_from_row(
        {
            "id": branch_id,
            "session_id": session_id,
            "parent_branch_id": None,
            "query": "query",
            "label": "Root",
            "rationale": "Initial",
            "mode": "search_summarize",
            "status": "failed",
            "prune_reason": None,
            "failure_reason": "provider timeout",
            "depth": 0,
            "context_tokens_used": 5,
            "max_context_tokens": 100,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    )
    assert branch.status == BranchStatus.FAILED
    assert branch.failure_reason == "provider timeout"

    binding = _runtime_loop_binding_from_row(
        {
            "session_id": session_id,
            "loop_id": "loop_abc",
            "loop_number": 1,
            "root_branch_id": branch_id,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
    )
    assert binding.root_branch_id == str(branch_id)

    job = _job_from_row(
        {
            "id": uuid4(),
            "session_id": session_id,
            "branch_id": branch_id,
            "job_type": "research_session",
            "status": "running",
            "payload": {"initial_query": "query"},
            "result": {},
            "priority": 0,
            "attempts": 1,
            "max_attempts": 3,
            "timeout_seconds": 1800,
            "run_at": timestamp,
            "locked_by": "worker-1",
            "locked_at": timestamp,
            "last_error": None,
            "created_at": timestamp,
            "updated_at": timestamp,
            "completed_at": None,
        }
    )
    assert job.job_type == JobType.RESEARCH_SESSION
    assert job.status == JobStatus.RUNNING
    assert job.locked_by == "worker-1"

    paper_row = {
        "id": paper_id,
        "canonical_key": "doi:10/test",
        "semantic_scholar_id": "S2",
        "arxiv_id": None,
        "doi": "10/test",
        "openalex_id": None,
        "title": "Paper",
        "abstract": "Abstract",
        "year": 2024,
        "venue": "Venue",
        "citation_count": 1,
        "reference_count": 2,
        "influential_citation_count": 3,
        "url": "https://example.test",
        "pdf_url": None,
        "open_access_pdf_url": None,
        "metadata": {"provider": "test"},
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    paper = _paper_from_row(paper_row)
    assert paper.id == str(paper_id)
    assert paper.doi == "10/test"

    view = _session_paper_view_from_row(
        {
            **paper_row,
            "session_paper_id": uuid4(),
            "session_id": session_id,
            "branch_id": branch_id,
            "paper_id": paper_id,
            "discovery_method": "query_search",
            "selection_reason": "relevant",
            "selected": True,
            "iteration_number": 1,
            "session_paper_created_at": timestamp,
        }
    )
    assert view.paper.id == str(paper_id)
    assert view.session_id == str(session_id)


def test_evidence_and_event_row_mappers() -> None:
    timestamp = now()
    claim_id = uuid4()
    session_id = uuid4()
    evidence = _claim_evidence_from_row(
        {
            "id": uuid4(),
            "claim_id": claim_id,
            "session_id": session_id,
            "source_type": "manual",
            "paper_id": None,
            "chunk_id": None,
            "metadata_field": None,
            "upload_id": None,
            "document_id": None,
            "external_uri": None,
            "source_id": None,
            "reviewer_id": "api_user",
            "evidence_text": "Reviewed by user.",
            "relation": "supports",
            "score": 0.9,
            "page_start": None,
            "page_end": None,
            "section_title": None,
            "created_at": timestamp,
        }
    )
    assert evidence.source_type == EvidenceSourceType.MANUAL
    assert evidence.reviewer_id == "api_user"

    event = _event_from_row(
        {
            "id": uuid4(),
            "session_id": session_id,
            "branch_id": None,
            "paper_id": None,
            "event_type": "session_created",
            "payload": {"ok": True},
            "severity": "info",
            "created_at": timestamp,
        }
    )
    assert event.payload == {"ok": True}
