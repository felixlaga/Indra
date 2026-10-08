"""Keep the test suite hermetic from a developer's local .env settings."""

import os

import pytest

# Modules call load_dotenv(), which searches parent directories for a .env file.
MODEL_ENV_VARS = (
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
    "OPENROUTER_BASE_URL",
    # A configured embedding model would be loaded (and downloaded) by API tests.
    "INDRA_EMBEDDING_MODEL",
    # A local dashboard port changes which browser origins the API allows.
    "INDRA_CORS_ORIGINS",
)


@pytest.fixture(autouse=True)
def _no_live_model_credentials(monkeypatch):
    """Tests use fixture models; real keys or local models must never be used."""

    if os.getenv("INDRA_RUN_LIVE_TESTS") == "true":
        return
    for name in MODEL_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
