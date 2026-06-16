"""Tests for product API repository backend selection."""

import pytest

from src.api import create_app
from src.api.repository import InMemoryRepository
from src.api.repository_factory import (
    DATABASE_URL_ENV,
    REPOSITORY_BACKEND_ENV,
    RepositoryConfigurationError,
    create_repository,
)
from src.api.postgres_repository import PostgresRepository


def test_repository_factory_defaults_to_memory(monkeypatch):
    monkeypatch.delenv(REPOSITORY_BACKEND_ENV, raising=False)

    repository = create_repository()

    assert isinstance(repository, InMemoryRepository)


def test_repository_factory_uses_memory_env_alias(monkeypatch):
    monkeypatch.setenv(REPOSITORY_BACKEND_ENV, "in-memory")

    repository = create_repository()

    assert isinstance(repository, InMemoryRepository)


def test_create_app_uses_repository_factory(monkeypatch):
    monkeypatch.setenv(REPOSITORY_BACKEND_ENV, "memory")

    app = create_app()

    assert isinstance(app.state.repository, InMemoryRepository)


def test_repository_factory_requires_database_url_for_postgres(monkeypatch):
    monkeypatch.delenv(DATABASE_URL_ENV, raising=False)

    with pytest.raises(RepositoryConfigurationError) as exc:
        create_repository("postgres")

    assert DATABASE_URL_ENV in str(exc.value)


def test_repository_factory_uses_postgres_backend(monkeypatch):
    monkeypatch.setenv(DATABASE_URL_ENV, "postgresql://example")

    repository = create_repository("postgres")

    assert isinstance(repository, PostgresRepository)


def test_repository_factory_rejects_unknown_backend():
    with pytest.raises(RepositoryConfigurationError) as exc:
        create_repository("sqlite")

    assert "Unsupported repository backend" in str(exc.value)
