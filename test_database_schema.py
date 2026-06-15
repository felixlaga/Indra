"""Static checks for the initial ERLA database migration."""

import re
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).parent / "migrations" / "0001_initial_product_schema.sql"
)
MIGRATION_SQL = MIGRATION_PATH.read_text()


def test_initial_migration_defines_required_tables():
    required_tables = {
        "users",
        "projects",
        "research_sessions",
        "branches",
        "papers",
        "paper_authors",
        "session_papers",
        "paper_edges",
        "paper_documents",
        "paper_chunks",
        "summaries",
        "claims",
        "claim_evidence",
        "validations",
        "hypotheses",
        "hypothesis_support",
        "agent_decisions",
        "events",
        "exports",
    }

    tables = set(re.findall(r"CREATE TABLE ([a-z_]+)", MIGRATION_SQL))

    assert required_tables <= tables


def test_initial_migration_defines_required_indexes():
    required_indexes = {
        "idx_research_sessions_project_id",
        "idx_branches_session_id",
        "idx_branches_parent_branch_id",
        "idx_papers_canonical_key",
        "idx_papers_doi",
        "idx_papers_arxiv_id",
        "idx_papers_semantic_scholar_id",
        "idx_session_papers_session_id",
        "idx_session_papers_branch_id",
        "idx_session_papers_paper_id",
        "idx_paper_edges_source_paper_id",
        "idx_paper_edges_target_paper_id",
        "idx_paper_chunks_paper_id",
        "idx_claims_session_id",
        "idx_claims_branch_id",
        "idx_claims_paper_id",
        "idx_claims_status",
        "idx_claim_evidence_claim_id",
        "idx_hypotheses_session_id",
        "idx_agent_decisions_session_id",
        "idx_events_session_created_at",
    }

    indexes = set(
        re.findall(r"CREATE (?:UNIQUE )?INDEX ([a-z_]+)", MIGRATION_SQL)
    )

    assert required_indexes <= indexes


def test_initial_migration_preserves_core_status_values():
    for status in ("pending", "running", "paused", "completed", "cancelled", "failed"):
        assert f"'{status}'" in MIGRATION_SQL

    for status in (
        "supported",
        "weakly_supported",
        "contradicted",
        "not_found",
        "speculative",
        "needs_review",
    ):
        assert f"'{status}'" in MIGRATION_SQL

    for severity in ("debug", "info", "warning", "error", "critical"):
        assert f"'{severity}'" in MIGRATION_SQL


def test_initial_migration_has_uuid_and_vector_foundations():
    assert "CREATE EXTENSION IF NOT EXISTS pgcrypto;" in MIGRATION_SQL
    assert "CREATE EXTENSION IF NOT EXISTS vector;" in MIGRATION_SQL
    assert "id uuid PRIMARY KEY DEFAULT gen_random_uuid()" in MIGRATION_SQL
    assert "embedding vector" in MIGRATION_SQL
