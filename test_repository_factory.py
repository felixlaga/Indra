"""Tests for product API repository backend selection."""

import pytest

from src.api import create_app
from src.api.repository import InMemoryRepository
from src.api.repository_factory import (
    REPOSITORY_BACKEND_ENV,
    RepositoryConfigurationError,
    create_repository,
)


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


def test_repository_factory_rejects_postgres_until_adapter_exists():
    with pytest.raises(RepositoryConfigurationError) as exc:
        create_repository("postgres")

    assert "Postgres repository is not implemented yet" in str(exc.value)


def test_repository_factory_rejects_unknown_backend():
    with pytest.raises(RepositoryConfigurationError) as exc:
        create_repository("sqlite")

    assert "Unsupported repository backend" in str(exc.value)
