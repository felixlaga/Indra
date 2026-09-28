"""Check the dashboard's authenticated advisor and export boundaries."""

import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.api.models import SessionCreate
from src.api.repository import InMemoryRepository


@pytest.mark.parametrize("suffix", ["analysis", "exports", "exports/bibtex"])
def test_advisor_and_exports_require_and_accept_dashboard_key(monkeypatch, suffix):
    monkeypatch.setenv("INDRA_API_KEY", "local-test-key")
    repository = InMemoryRepository()
    session = repository.create_session(SessionCreate(initial_query="Authentication smoke test"))
    with TestClient(create_app(repository)) as client:
        path = f"/sessions/{session.id}/{suffix}"
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"X-Indra-API-Key": "wrong"}).status_code == 401
        assert client.get(path, headers={"X-Indra-API-Key": "local-test-key"}).status_code == 200
        assert client.get(path, params={"api_key": "local-test-key"}).status_code == 200


def test_key_header_is_allowed_in_browser_preflight(monkeypatch):
    monkeypatch.setenv("INDRA_API_KEY", "local-test-key")
    with TestClient(create_app(InMemoryRepository())) as client:
        response = client.options("/projects", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-indra-api-key",
        })
        assert response.status_code == 200
        assert "x-indra-api-key" in response.headers["access-control-allow-headers"].lower()
