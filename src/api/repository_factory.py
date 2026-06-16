"""Repository backend selection for the product API."""

from __future__ import annotations

from os import getenv

from .repository import InMemoryRepository, ProductRepository, RepositoryError

REPOSITORY_BACKEND_ENV = "ERLA_REPOSITORY_BACKEND"
DATABASE_URL_ENV = "ERLA_DATABASE_URL"


class RepositoryConfigurationError(RepositoryError):
    """Raised when repository backend configuration is invalid."""


def create_repository(backend: str | None = None) -> ProductRepository:
    """Create the configured API repository implementation."""

    selected = (backend or getenv(REPOSITORY_BACKEND_ENV, "memory")).strip().lower()
    if selected in {"memory", "in_memory", "in-memory"}:
        return InMemoryRepository()

    if selected in {"postgres", "postgresql"}:
        database_url = getenv(DATABASE_URL_ENV, "").strip()
        if not database_url:
            raise RepositoryConfigurationError(
                f"{DATABASE_URL_ENV} is required when "
                f"{REPOSITORY_BACKEND_ENV}=postgres."
            )
        from .postgres_repository import PostgresRepository

        return PostgresRepository(database_url)

    raise RepositoryConfigurationError(
        f"Unsupported repository backend '{selected}'. Supported backends: "
        "memory, postgres."
    )
