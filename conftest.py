"""Keep the test suite hermetic from a developer's local model credentials."""

import os

import pytest

# Modules call load_dotenv(), which searches parent directories for a .env file.
MODEL_ENV_VARS = ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OPENROUTER_BASE_URL")


@pytest.fixture(autouse=True)
def _no_live_model_credentials(monkeypatch):
    """Tests use fixture models; a real key must never make paid or quota-limited calls."""

    if os.getenv("INDRA_RUN_LIVE_TESTS") == "true":
        return
    for name in MODEL_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
