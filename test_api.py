"""Tests for the ERLA product API skeleton."""

from queue import Empty

from fastapi.testclient import TestClient

from src.api import create_app
from src.api.event_stream import format_sse_comment, format_sse_event
from src.api.repository import InMemoryRepository


def make_client() -> TestClient:
    """Create an isolated API client for each test."""

    return TestClient(create_app(InMemoryRepository()))


def test_project_and_session_creation_creates_root_branch():
    client = make_client()

    project_response = client.post(
        "/projects",
        json={
            "title": "Wave Optics Lensing",
            "description": "Research workspace",
            "field": "gravitational waves",
        },
    )
    assert project_response.status_code == 201
    project = project_response.json()
    assert project["title"] == "Wave Optics Lensing"

    session_response = client.post(
        "/sessions",
        json={
            "project_id": project["id"],
            "initial_query": "wave optics gravitational wave lensing",
        },
    )
    assert session_response.status_code == 201
    session = session_response.json()
    assert session["project_id"] == project["id"]
    assert session["status"] == "pending"

    loop_response = client.get(f"/sessions/{session['id']}/loop")
    assert loop_response.status_code == 200
    loop = loop_response.json()
    assert loop["session_id"] == session["id"]
    assert loop["loop_id"].startswith("loop_")
    assert loop["loop_number"] == 1

    branches_response = client.get(f"/sessions/{session['id']}/branches")
    assert branches_response.status_code == 200
    branches = branches_response.json()
    assert len(branches) == 1
    assert branches[0]["id"] == loop["root_branch_id"]
    assert branches[0]["query"] == session["initial_query"]
    assert branches[0]["label"] == "Root"
    assert branches[0]["mode"] == "search_summarize"

    state_response = client.get(f"/sessions/{session['id']}/state")
    assert state_response.status_code == 200
    state = state_response.json()
    assert state["session"]["id"] == session["id"]
    assert state["runtime_loop"]["loop_id"] == loop["loop_id"]
    assert state["runtime_loop"]["root_branch_id"] == loop["root_branch_id"]
    assert len(state["branches"]) == 1
    assert state["papers"] == []
    assert [event["event_type"] for event in state["events"]] == [
        "session_created",
        "research_loop_created",
        "branch_created",
    ]
    assert state["events"][1]["payload"]["root_branch_id"] == loop["root_branch_id"]


def test_run_controls_update_session_and_branch_state():
    client = make_client()
    session = client.post(
        "/sessions",
        json={"initial_query": "LLM reasoning evaluation"},
    ).json()

    start_response = client.post(f"/sessions/{session['id']}/start")
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "running"

    branches = client.get(f"/sessions/{session['id']}/branches").json()
    assert branches[0]["status"] == "running"

    pause_response = client.post(f"/sessions/{session['id']}/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "paused"

    resume_response = client.post(f"/sessions/{session['id']}/resume")
    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == "running"

    cancel_response = client.post(f"/sessions/{session['id']}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    invalid_pause_response = client.post(f"/sessions/{session['id']}/pause")
    assert invalid_pause_response.status_code == 409

    events = client.get(f"/sessions/{session['id']}/events").json()
    event_types = [event["event_type"] for event in events]
    assert event_types[-4:] == [
        "session_started",
        "session_paused",
        "session_resumed",
        "session_cancelled",
    ]
    loop = client.get(f"/sessions/{session['id']}/loop").json()
    started_event = next(
        event for event in events if event["event_type"] == "session_started"
    )
    assert started_event["payload"]["loop_id"] == loop["loop_id"]
    assert started_event["payload"]["root_branch_id"] == loop["root_branch_id"]


def test_event_stream_subscription_replays_and_publishes_events():
    repository = InMemoryRepository()
    client = TestClient(create_app(repository))
    session = client.post(
        "/sessions",
        json={"initial_query": "live research event stream"},
    ).json()

    subscription = repository.subscribe_events(session["id"])
    try:
        assert [event.event_type for event in subscription.replay_events] == [
            "session_created",
            "research_loop_created",
            "branch_created",
        ]

        start_response = client.post(f"/sessions/{session['id']}/start")
        assert start_response.status_code == 200

        published_event = subscription.queue.get_nowait()
        assert published_event.event_type == "session_started"

        frame = format_sse_event(published_event)
        assert f"id: {published_event.id}" in frame
        assert "event: session_started" in frame
        assert '"event_type":"session_started"' in frame
        assert frame.endswith("\n\n")
        assert format_sse_comment("keep-alive") == ": keep-alive\n\n"
    finally:
        repository.unsubscribe_events(subscription)

    client.post(f"/sessions/{session['id']}/pause")
    try:
        subscription.queue.get_nowait()
    except Empty:
        pass
    else:
        raise AssertionError("Unsubscribed event stream received an event")


def test_claim_extraction_creates_review_ready_claims():
    client = make_client()
    session = client.post(
        "/sessions",
        json={"initial_query": "claim extraction for research summaries"},
    ).json()
    root_branch = client.get(f"/sessions/{session['id']}/branches").json()[0]

    response = client.post(
        f"/sessions/{session['id']}/claims/extract",
        json={
            "branch_id": root_branch["id"],
            "source_text": (
                "The paper introduces a retrieval method, evaluates the method "
                "on several datasets, outperforms baseline systems, and "
                "discusses limitations."
            ),
        },
    )

    assert response.status_code == 201
    claims = response.json()
    assert [claim["claim_text"] for claim in claims] == [
        "The paper introduces a retrieval method.",
        "The paper evaluates the method on several datasets.",
        "The paper outperforms baseline systems.",
        "The paper discusses limitations.",
    ]
    assert [claim["claim_type"] for claim in claims] == [
        "methodological",
        "empirical_result",
        "comparison",
        "limitation",
    ]
    assert {claim["status"] for claim in claims} == {"needs_review"}
    assert {claim["branch_id"] for claim in claims} == {root_branch["id"]}

    claims_response = client.get(f"/sessions/{session['id']}/claims")
    assert claims_response.status_code == 200
    assert [claim["id"] for claim in claims_response.json()] == [
        claim["id"] for claim in claims
    ]

    claim_response = client.get(f"/claims/{claims[0]['id']}")
    assert claim_response.status_code == 200
    assert claim_response.json()["claim_text"] == claims[0]["claim_text"]

    state = client.get(f"/sessions/{session['id']}/state").json()
    assert len(state["claims"]) == 4

    events = client.get(f"/sessions/{session['id']}/events").json()
    event_types = [event["event_type"] for event in events]
    assert "claims_extracted" in event_types
    assert "claim_validated" not in event_types
    claims_event = next(
        event for event in events if event["event_type"] == "claims_extracted"
    )
    assert claims_event["payload"]["claim_count"] == 4


def test_claim_validation_stores_evidence_and_updates_status():
    client = make_client()
    session = client.post(
        "/sessions",
        json={"initial_query": "claim validation for evidence ledger"},
    ).json()

    claims = client.post(
        f"/sessions/{session['id']}/claims/extract",
        json={"source_text": "The paper introduces a retrieval method."},
    ).json()
    claim = claims[0]

    validation_response = client.post(
        f"/claims/{claim['id']}/validate",
        json={
            "evidence": [
                {
                    "evidence_text": (
                        "We introduce a retrieval method for evidence-grounded "
                        "literature navigation."
                    ),
                    "relation": "supports",
                    "score": 0.93,
                    "section_title": "Abstract",
                }
            ]
        },
    )

    assert validation_response.status_code == 200
    result = validation_response.json()
    assert result["claim"]["status"] == "supported"
    assert result["claim"]["confidence"] == 0.93
    assert result["evidence"][0]["relation"] == "supports"
    assert result["evidence"][0]["claim_id"] == claim["id"]

    claim_response = client.get(f"/claims/{claim['id']}")
    assert claim_response.status_code == 200
    assert claim_response.json()["status"] == "supported"

    evidence_response = client.get(f"/claims/{claim['id']}/evidence")
    assert evidence_response.status_code == 200
    assert evidence_response.json()[0]["section_title"] == "Abstract"

    state = client.get(f"/sessions/{session['id']}/state").json()
    assert state["claims"][0]["status"] == "supported"
    assert len(state["claim_evidence"]) == 1

    events = client.get(f"/sessions/{session['id']}/events").json()
    claim_validated = next(
        event for event in events if event["event_type"] == "claim_validated"
    )
    assert claim_validated["payload"]["status"] == "supported"
    assert claim_validated["payload"]["evidence_ids"] == [
        result["evidence"][0]["id"]
    ]


def test_branch_split_patch_and_prune():
    client = make_client()
    session = client.post(
        "/sessions",
        json={"initial_query": "retrieval augmented generation evaluation"},
    ).json()
    root_branch = client.get(f"/sessions/{session['id']}/branches").json()[0]

    split_response = client.post(
        f"/branches/{root_branch['id']}/split",
        json={
            "branches": [
                {
                    "query": "RAG benchmark datasets",
                    "label": "Benchmarks",
                    "rationale": "Separate evaluation datasets from methods.",
                },
                {
                    "query": "RAG hallucination mitigation",
                    "label": "Mitigation",
                },
            ]
        },
    )
    assert split_response.status_code == 200
    children = split_response.json()
    assert len(children) == 2
    assert {child["parent_branch_id"] for child in children} == {root_branch["id"]}
    assert {child["depth"] for child in children} == {1}

    patch_response = client.patch(
        f"/branches/{children[0]['id']}",
        json={"label": "Evaluation benchmarks"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["label"] == "Evaluation benchmarks"

    prune_response = client.post(f"/branches/{children[1]['id']}/prune")
    assert prune_response.status_code == 200
    assert prune_response.json()["status"] == "pruned"

    continue_pruned_response = client.post(f"/branches/{children[1]['id']}/continue")
    assert continue_pruned_response.status_code == 409


def test_paper_and_not_found_endpoints_are_wired():
    client = make_client()
    session = client.post(
        "/sessions",
        json={"initial_query": "citation graph exploration"},
    ).json()

    papers_response = client.get(f"/sessions/{session['id']}/papers")
    assert papers_response.status_code == 200
    assert papers_response.json() == []

    missing_session_response = client.get("/sessions/missing")
    assert missing_session_response.status_code == 404

    missing_loop_response = client.get("/sessions/missing/loop")
    assert missing_loop_response.status_code == 404

    missing_event_stream_response = client.get("/sessions/missing/events/stream")
    assert missing_event_stream_response.status_code == 404

    missing_paper_response = client.get("/papers/missing")
    assert missing_paper_response.status_code == 404

    missing_claims_response = client.get("/sessions/missing/claims")
    assert missing_claims_response.status_code == 404

    missing_claim_response = client.get("/claims/missing")
    assert missing_claim_response.status_code == 404

    missing_evidence_response = client.get("/claims/missing/evidence")
    assert missing_evidence_response.status_code == 404

    missing_validation_response = client.post(
        "/claims/missing/validate",
        json={"evidence": []},
    )
    assert missing_validation_response.status_code == 404


def test_split_requires_at_least_one_child_branch():
    client = make_client()
    session = client.post(
        "/sessions",
        json={"initial_query": "agentic literature review"},
    ).json()
    root_branch = client.get(f"/sessions/{session['id']}/branches").json()[0]

    response = client.post(
        f"/branches/{root_branch['id']}/split",
        json={"branches": []},
    )
    assert response.status_code == 400
