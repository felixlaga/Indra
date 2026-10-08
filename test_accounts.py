"""Accounts: sign-in, per-user ownership on every route, and the service key."""

import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api import create_app
from src.api.auth import hash_password, token_hash, verify_password
from src.api.postgres_repository import PostgresRepository
from src.api.repository import InMemoryRepository
from src.jobs.research_worker import ResearchWorker
from src.research.pipeline import ResearchPipeline
from test_research_scouts import full_text, paper
from test_research_worker import postgres_dsn  # noqa: F401  (shared fixture)

SERVICE_KEY = "service-key-for-tests"


@pytest.fixture(params=["memory", "postgres"])
def repo(request, monkeypatch):
    monkeypatch.setenv("INDRA_AUTH_MODE", "accounts")
    monkeypatch.setenv("INDRA_API_KEY", SERVICE_KEY)
    if request.param == "memory":
        yield InMemoryRepository()
        return
    repository = PostgresRepository(request.getfixturevalue("postgres_dsn"))
    with repository._connect() as conn:
        conn.execute("TRUNCATE users, projects, research_sessions, papers CASCADE")
    yield repository
    with repository._connect() as conn:
        conn.execute("TRUNCATE users, projects, research_sessions, papers CASCADE")


@pytest.fixture
def client(repo):
    with TestClient(create_app(repo, run_memory_views=False)) as test_client:
        yield test_client


def register(client, email=None, password="correct horse battery"):
    response = client.post(
        "/auth/register",
        json={"email": email or f"{uuid4().hex[:8]}@example.org", "password": password},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def owned_session(client, repo, headers):
    """A project and session with a branch, paper, claim and job, owned by `headers`."""

    project = client.post("/projects", json={"title": "Mine"}, headers=headers).json()
    session = client.post(
        "/sessions",
        json={
            "project_id": project["id"],
            "initial_query": "graph neural networks for molecules",
            "parameters": {"research": {"max_papers": 1, "max_claims": 1, "max_depth": 0, "synthesize": False}},
        },
        headers=headers,
    ).json()
    assert client.post(f"/sessions/{session['id']}/start", headers=headers).status_code == 200

    async def search(*_):
        return [paper("a")]

    await ResearchWorker(repo, ResearchPipeline(repo, search=search, full_text=full_text)).run_once()
    snapshot = client.get(f"/sessions/{session['id']}/state", headers=headers).json()
    return {
        "project_id": project["id"],
        "session_id": session["id"],
        "branch_id": snapshot["branches"][0]["id"],
        "claim_id": snapshot["claims"][0]["id"],
        "job_id": snapshot["jobs"][0]["id"],
        "paper_id": snapshot["papers"][0]["paper_id"],
        "format_name": "bibtex",
    }


def test_password_hashes_verify_and_never_store_the_password():
    stored = hash_password("correct horse battery")
    assert stored.startswith("scrypt$") and "correct horse" not in stored
    assert verify_password("correct horse battery", stored)
    assert not verify_password("wrong horse battery", stored)
    assert not verify_password("anything at all", None)


def test_signed_out_requests_are_refused_and_report_signup(client):
    response = client.get("/projects")
    assert response.status_code == 401 and response.json()["mode"] == "accounts"
    me = client.get("/auth/me")
    assert me.status_code == 401 and me.json()["signup_open"] is True
    assert client.get("/health").status_code == 200


def test_first_account_adopts_work_created_before_accounts(client, repo, monkeypatch):
    monkeypatch.setenv("INDRA_AUTH_MODE", "off")
    monkeypatch.delenv("INDRA_API_KEY")
    earlier = client.post("/projects", json={"title": "Before accounts"}).json()
    monkeypatch.setenv("INDRA_AUTH_MODE", "accounts")
    first = register(client)
    assert [p["id"] for p in client.get("/projects", headers=first).json()] == [earlier["id"]]
    second = register(client)
    assert client.get("/projects", headers=second).json() == []


async def test_every_route_hides_another_users_resources(client, repo):
    alice, bob = register(client), register(client)
    ids = await owned_session(client, repo, alice)
    checked = 0
    for route in client.app.routes:
        params = re.findall(r"{(\w+)}", getattr(route, "path", ""))
        if not params or not hasattr(route, "methods"):
            continue
        assert set(params) <= set(ids), f"add an ownership fixture for {route.path}"
        path = route.path.format(**ids)
        for method in route.methods - {"HEAD"}:
            response = client.request(method, path, headers=bob, json={})
            expected = 403 if path.startswith("/jobs/") and method != "GET" else 404
            assert response.status_code == expected, (method, route.path, response.status_code)
            # The owner can reach the same resource.
            if method == "GET" and not path.endswith("/stream"):
                assert client.get(path, headers=alice).status_code in {200, 202}, route.path
            checked += 1
    assert checked >= 30
    assert client.get("/projects", headers=bob).json() == []
    assert client.get("/sessions", headers=bob).json() == []
    stolen = client.post(
        "/sessions", json={"project_id": ids["project_id"], "initial_query": "q"}, headers=bob
    )
    assert stolen.status_code == 404


async def test_service_key_reaches_everything_unless_a_user_is_named(client, repo):
    alice, bob = register(client), register(client)
    ids = await owned_session(client, repo, alice)
    service = {"X-Indra-API-Key": SERVICE_KEY}
    assert client.get(f"/sessions/{ids['session_id']}", headers=service).status_code == 200
    assert client.post("/jobs/lease", json={"worker_id": "w"}, headers=service).status_code == 200
    # A user token outranks the service key, so a proxy sending both cannot widen access.
    assert client.get(f"/sessions/{ids['session_id']}", headers={**service, **bob}).status_code == 404
    assert client.post("/jobs/lease", json={"worker_id": "w"}, headers=alice).status_code == 403
    wrong = client.get("/projects", headers={"X-Indra-API-Key": "nope"})
    assert wrong.status_code == 401
    # The dashboard proxy's key never stands in for a signed-in user.
    assert client.get("/projects", headers={"X-Indra-Proxy-Key": SERVICE_KEY}).status_code == 401


def test_login_logout_and_expired_sessions(client, repo):
    email = f"{uuid4().hex[:8]}@Example.org"
    register(client, email=email)
    assert client.post("/auth/login", json={"email": email, "password": "not the password"}).status_code == 401
    assert client.post("/auth/login", json={"email": "nobody@example.org", "password": "correct horse battery"}).status_code == 401
    login = client.post("/auth/login", json={"email": email.upper(), "password": "correct horse battery"})
    assert login.status_code == 200 and login.json()["user"]["email"] == email.lower()
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    assert client.get("/auth/me", headers=headers).json()["user"]["email"] == email.lower()
    assert client.post("/auth/logout", headers=headers).status_code == 204
    assert client.get("/projects", headers=headers).status_code == 401

    user = repo.get_user_credentials(email.lower())[0]
    repo.create_user_session(user.id, token_hash("old"), datetime.now(timezone.utc) - timedelta(seconds=1))
    assert client.get("/projects", headers={"Authorization": "Bearer old"}).status_code == 401


def test_duplicate_emails_and_closed_signup(client, monkeypatch):
    register(client, email="same@example.org")
    duplicate = client.post("/auth/register", json={"email": "same@example.org", "password": "another long password"})
    assert duplicate.status_code == 409
    monkeypatch.setenv("INDRA_ALLOW_SIGNUP", "false")
    closed = client.post("/auth/register", json={"email": "new@example.org", "password": "another long password"})
    assert closed.status_code == 403
    assert client.post("/auth/register", json={"email": "bad", "password": "another long password"}).status_code == 422
    assert client.post("/auth/register", json={"email": "x@example.org", "password": "short"}).status_code == 422


def test_accounts_off_keeps_single_user_behaviour(monkeypatch):
    monkeypatch.setenv("INDRA_AUTH_MODE", "off")
    monkeypatch.delenv("INDRA_API_KEY", raising=False)
    with TestClient(create_app(InMemoryRepository(), run_memory_views=False)) as client:
        assert client.get("/auth/me").json() == {"mode": "off", "user": None, "signup_open": False}
        assert client.post("/auth/register", json={"email": "a@example.org", "password": "correct horse battery"}).status_code == 409
        assert client.post("/projects", json={"title": "Open"}).status_code == 201


def test_proxy_key_unlocks_a_shared_key_deployment_without_accounts(monkeypatch):
    monkeypatch.setenv("INDRA_AUTH_MODE", "off")
    monkeypatch.setenv("INDRA_API_KEY", SERVICE_KEY)
    with TestClient(create_app(InMemoryRepository(), run_memory_views=False)) as client:
        assert client.get("/projects").status_code == 401
        assert client.get("/projects", headers={"X-Indra-Proxy-Key": SERVICE_KEY}).status_code == 200
