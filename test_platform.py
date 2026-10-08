"""Ordered delivery and cached-view regressions against memory and PostgreSQL."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event as ThreadEvent

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app
from src.api.event_notifications import EventNotifications
from src.api.models import ClaimExtractionRequest, ClaimValidationRequest, SessionCreate
from src.api.postgres_repository import PostgresRepository
from src.api.repository import ConflictError, utc_now
from src.jobs.view_worker import ViewWorker
from test_research_worker import postgres_dsn as postgres_fixture, repo as repo_fixture

postgres_dsn = postgres_fixture
repo = repo_fixture


def session(repo):
    return repo.create_session(SessionCreate(initial_query="Platform regression"))


def emit(repo, session_id, event_type="test_event"):
    if isinstance(repo, PostgresRepository):
        with repo._connect() as conn:
            return repo._insert_event(
                conn, session_id=session_id, event_type=event_type, payload={}
            ).event
    with repo._lock:
        return repo._create_event_unlocked(session_id, event_type, {})


def expire(repo, session_id):
    if isinstance(repo, PostgresRepository):
        with repo._connect() as conn:
            conn.execute(
                "UPDATE session_research_views SET lease_until=now()-interval '1 second' WHERE session_id=%s",
                (session_id,),
            )
    else:
        repo._research_views[session_id]["lease_until"] = utc_now() - timedelta(
            seconds=1
        )


def test_events_page_without_gaps_and_accept_legacy_cursors(repo):
    s = session(repo)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _: emit(repo, s.id), range(20)))
    events = repo.list_events(s.id)
    assert [e.sequence for e in events] == list(range(1, len(events) + 1))
    page = repo.read_events(s.id, after=3, limit=7)
    assert [e.sequence for e in page] == list(range(4, 11))
    assert repo.event_position(s.id, page[-1].id) == 10
    assert repo.event_position(s.id, "10") == 10
    assert [e.sequence for e in repo.read_events(s.id, before=11, limit=3)] == [
        8,
        9,
        10,
    ]
    with pytest.raises(ConflictError):
        repo.event_position(s.id, session(repo).id)
    with pytest.raises(ConflictError):
        repo.event_position(s.id, "99999")


def test_bounded_snapshot_preserves_older_validation_history(repo):
    s = session(repo)
    claim = repo.extract_claims(
        s.id, ClaimExtractionRequest(source_text="The method improves accuracy.")
    )[0]
    repo.validate_claim(claim.id, ClaimValidationRequest(evidence=[]))
    for _ in range(8):
        emit(repo, s.id, "research_progress")
    snapshot = repo.get_session_snapshot(s.id, event_limit=3)
    assert len(snapshot.events) == 3
    assert snapshot.events_has_more
    assert snapshot.validated_claim_ids == [claim.id]
    assert snapshot.event_cursor == repo.event_position(s.id)


def test_views_coalesce_survive_restart_and_invalidate(repo):
    s = session(repo)
    with ThreadPoolExecutor(max_workers=4) as executor:
        rows = list(executor.map(lambda _: repo.request_views(s.id), range(8)))
    assert all(r["status"] == "queued" for r in rows)
    assert ViewWorker(repo).run_once() is not None
    assert ViewWorker(repo).run_once() is None
    reader = (
        PostgresRepository(repo._dsn) if isinstance(repo, PostgresRepository) else repo
    )
    row = reader.request_views(s.id)
    assert row["status"] == "ready"
    assert row["result"]["map"]["nodes"] == []
    emit(repo, s.id, "research_progress")
    assert reader.request_views(s.id)["status"] == "ready"
    claim = repo.extract_claims(
        s.id, ClaimExtractionRequest(source_text="The method improves accuracy.")
    )[0]
    assert reader.request_views(s.id)["status"] == "queued"
    ViewWorker(repo).run_once()
    row = reader.request_views(s.id)
    assert row["status"] == "ready"
    assert row["result"]["analysis"]["weak_evidence"][0]["claim_id"] == claim.id
    if reader is not repo:
        reader.close()


def test_stale_view_worker_cannot_publish_or_overwrite_new_attempt(repo):
    s = session(repo)
    repo.request_views(s.id)
    old = repo.lease_views()
    assert repo.lease_views() is None
    expire(repo, s.id)
    fresh = repo.lease_views()
    assert old["lease_token"] != fresh["lease_token"]
    assert not repo.finish_views(old, {"wrong": True})
    emit(repo, s.id)
    repo.request_views(s.id)
    assert repo.finish_views(fresh, {"outdated": True})
    assert repo.request_views(s.id)["status"] == "queued"
    ViewWorker(repo).run_once()
    assert "outdated" not in repo.request_views(s.id)["result"]


def test_views_fail_visibly_and_support_explicit_retry(repo, monkeypatch):
    from src.maps import ResearchMapBuilder

    s = session(repo)
    repo.request_views(s.id)
    with monkeypatch.context() as scoped:
        scoped.setattr(
            ResearchMapBuilder,
            "build",
            lambda *_: (_ for _ in ()).throw(ValueError("broken")),
        )
        ViewWorker(repo).run_once()
    assert repo.request_views(s.id)["status"] == "failed"
    assert repo.get_session(s.id).status.value == "pending"
    assert repo.request_views(s.id, retry=True)["status"] == "queued"
    ViewWorker(repo).run_once()
    assert repo.request_views(s.id)["status"] == "ready"


def test_view_repeated_worker_death_has_bounded_retries(repo):
    s = session(repo)
    repo.request_views(s.id)
    for _ in range(3):
        assert repo.lease_views() is not None
        expire(repo, s.id)
    assert repo.lease_views() is None
    assert repo.request_views(s.id)["status"] == "failed"


def test_routes_queue_compute_off_request_and_validate_page_bounds(repo, monkeypatch):
    s = session(repo)
    app = create_app(repo, run_memory_views=False)
    with TestClient(app) as client:
        response = client.get(f"/sessions/{s.id}/map")
        assert response.status_code == 202
        assert response.headers["retry-after"] == "1"
        ViewWorker(repo).run_once()
        from src.maps import ResearchMapBuilder

        monkeypatch.setattr(
            ResearchMapBuilder,
            "build",
            lambda *_: pytest.fail("API must not compute maps"),
        )
        assert client.get(f"/sessions/{s.id}/map").status_code == 200
        assert client.get(f"/sessions/{s.id}/analysis").status_code == 200
        assert client.get(f"/sessions/{s.id}/events?limit=501").status_code == 422
        assert (
            client.get(f"/sessions/{s.id}/events/stream?cursor=invalid").status_code
            == 409
        )


def test_session_sequence_follows_commit_order(postgres_dsn):
    repo = PostgresRepository(postgres_dsn)
    s = session(repo)
    inserted, release = ThreadEvent(), ThreadEvent()

    def delayed():
        with repo._connect() as conn:
            event = repo._insert_event(
                conn, session_id=s.id, event_type="delayed", payload={}
            ).event
            inserted.set()
            assert release.wait(5)
            return event

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(delayed)
        assert inserted.wait(5)
        second = pool.submit(emit, repo, s.id)
        try:
            assert repo.event_position(s.id) == 3
            assert not second.done()
        finally:
            release.set()
        assert first.result().sequence == 4
        assert second.result().sequence == 5
    repo.close()


async def test_notifications_only_wake_after_commit_and_not_rollback(postgres_dsn):
    repo = PostgresRepository(postgres_dsn)
    s = session(repo)
    notifications = EventNotifications(postgres_dsn)
    await notifications.start()
    try:
        await asyncio.wait_for(notifications.connected.wait(), 5)
        async with notifications.subscribe(s.id) as wake:
            with pytest.raises(RuntimeError):
                with repo._connect() as conn:
                    repo._insert_event(
                        conn, session_id=s.id, event_type="rollback", payload={}
                    )
                    raise RuntimeError("rollback")
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(wake.wait(), 0.1)
            await asyncio.to_thread(emit, repo, s.id)
            await asyncio.wait_for(wake.wait(), 2)
            assert repo.event_position(s.id) == 4
        assert not notifications.subscribers
    finally:
        await notifications.close()
        repo.close()


async def test_listener_recovers_and_catches_up_after_connection_loss(postgres_dsn):
    repo = PostgresRepository(postgres_dsn)
    s = session(repo)
    notifications = EventNotifications(postgres_dsn)
    await notifications.start()
    try:
        await asyncio.wait_for(notifications.connected.wait(), 5)
        async with notifications.subscribe(s.id) as wake:
            with repo._connect() as conn:
                conn.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=current_database() AND application_name='indra-events'"
                )
            for _ in range(100):
                if not notifications.connected.is_set():
                    break
                await asyncio.sleep(0.01)
            assert not notifications.connected.is_set()
            await asyncio.to_thread(emit, repo, s.id)
            await asyncio.wait_for(notifications.connected.wait(), 5)
            await asyncio.wait_for(wake.wait(), 1)
            assert repo.read_events(s.id, after=3)[0].sequence == 4
    finally:
        await notifications.close()
        repo.close()


def test_global_paper_updates_invalidate_other_sessions(repo):
    from test_research_worker import start, paper
    from src.research.models import PaperResult

    first = start(repo)
    lease = repo.lease_next_job("first")
    repo.save_research_paper(lease, PaperResult(paper=paper()))
    repo.finish_research(lease)
    repo.request_views(first.id)
    ViewWorker(repo).run_once()
    assert repo.request_views(first.id)["status"] == "ready"
    start(repo)
    second_lease = repo.lease_next_job("second")
    changed = paper().model_copy(update={"title": "Updated global metadata"})
    repo.save_research_paper(second_lease, PaperResult(paper=changed))
    assert repo.request_views(first.id)["status"] == "queued"
    ViewWorker(repo).run_once()
    assert (
        repo.request_views(first.id)["result"]["map"]["nodes"][0]["title"]
        == "Updated global metadata"
    )


def test_memory_preview_builds_views_in_background():
    import time
    from src.api.repository import InMemoryRepository

    repo = InMemoryRepository()
    s = session(repo)
    with TestClient(create_app(repo)) as client:
        assert client.get(f"/sessions/{s.id}/map").status_code == 202
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            response = client.get(f"/sessions/{s.id}/map")
            if response.status_code == 200:
                break
            time.sleep(0.05)
        assert response.status_code == 200
