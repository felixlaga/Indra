"""Browser-boundary tests for the Phase 4 web dashboard."""

from fastapi.testclient import TestClient

from src.api import create_app
from src.api.repository import InMemoryRepository


def test_dashboard_origin_is_allowed_by_default():
    client = TestClient(create_app(InMemoryRepository()))

    response = client.options(
        "/projects",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "GET" in response.headers["access-control-allow-methods"]


def test_unconfigured_origin_is_not_allowed():
    client = TestClient(create_app(InMemoryRepository()))

    response = client.options(
        "/projects",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers
