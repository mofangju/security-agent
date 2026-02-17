from __future__ import annotations

from security_agent.assistant.api import create_app


class _GraphStub:
    pass


def _turn_runner(*, graph, messages, context, user_input):
    assert isinstance(graph, _GraphStub)
    reply = f"echo:{user_input}"
    result = {"messages": [type("Msg", (), {"content": reply})()]}
    next_messages = [
        *messages,
        {"role": "user", "content": user_input},
        {"role": "ai", "content": reply},
    ]
    return result, next_messages[-20:], context


def test_health_and_ready_endpoints():
    app = create_app(graph_factory=lambda: _GraphStub(), turn_runner=_turn_runner)
    client = app.test_client()

    health = client.get("/healthz")
    ready = client.get("/readyz")

    assert health.status_code == 200
    assert ready.status_code == 200
    assert health.get_json()["status"] == "ok"
    assert ready.get_json()["status"] == "ready"


def test_chat_endpoint_persists_session_state():
    app = create_app(graph_factory=lambda: _GraphStub(), turn_runner=_turn_runner)
    client = app.test_client()

    first = client.post("/v1/chat", json={"message": "hello"})
    assert first.status_code == 200
    first_body = first.get_json()
    assert first_body["reply"] == "echo:hello"
    session_id = first_body["session_id"]

    second = client.post("/v1/chat", json={"session_id": session_id, "message": "again"})
    assert second.status_code == 200
    second_body = second.get_json()
    assert second_body["session_id"] == session_id
    assert second_body["reply"] == "echo:again"
    assert second_body["message_count"] >= 4


def test_chat_endpoint_rejects_empty_message():
    app = create_app(graph_factory=lambda: _GraphStub(), turn_runner=_turn_runner)
    client = app.test_client()

    resp = client.post("/v1/chat", json={"message": "   "})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "message_required"
