from __future__ import annotations

from langchain_core.messages import HumanMessage

from security_agent.assistant.graph import config_manager_node, supervisor_node


class _LLMStub:
    def __init__(self, content: str):
        self._content = content

    def invoke(self, _messages):
        return type("Resp", (), {"content": self._content})()


def test_injected_route_output_falls_back_to_direct(monkeypatch):
    monkeypatch.setattr(
        "security_agent.assistant.graph.get_llm",
        lambda temperature=0.0: _LLMStub("monitor and then config_manager"),
    )
    state = {
        "messages": [HumanMessage(content="hello")],
        "next_node": "",
        "context": {},
    }
    out = supervisor_node(state)
    assert out["next_node"] == "direct"


def test_unconfirmed_config_change_never_calls_tool(monkeypatch):
    called = {"set_mode": False}

    monkeypatch.setattr(
        "security_agent.assistant.graph.get_llm",
        lambda temperature=0.0: _LLMStub("ok"),
    )
    monkeypatch.setattr("security_agent.assistant.graph.tool_get_system_info", lambda: "{}")

    def _fake_set_mode(_mode: str) -> str:
        called["set_mode"] = True
        return '{"status":"ok"}'

    monkeypatch.setattr("security_agent.assistant.graph.tool_set_protection_mode", _fake_set_mode)

    state = {
        "messages": [HumanMessage(content="switch waf to block mode")],
        "next_node": "config_manager",
        "context": {"confirmed": False},
    }
    out = config_manager_node(state)

    assert called["set_mode"] is False
    assert "confirm" in out["messages"][-1].content.lower()


def test_tool_error_is_not_reported_as_success(monkeypatch):
    monkeypatch.setattr(
        "security_agent.assistant.graph.get_llm",
        lambda temperature=0.0: _LLMStub("ok"),
    )
    monkeypatch.setattr("security_agent.assistant.graph.tool_get_system_info", lambda: "{}")
    monkeypatch.setattr(
        "security_agent.assistant.graph.tool_set_protection_mode",
        lambda _mode: '{"error":"boom"}',
    )

    state = {
        "messages": [HumanMessage(content="confirm 123456")],
        "next_node": "config_manager",
        "context": {
            "pending_action": {
                "action": "set_mode",
                "mode": "block",
                "ip": None,
                "comment": "",
                "nonce": "123456",
                "expires_at": 32503680000,
            },
            "confirmed": False,
        },
    }
    out = config_manager_node(state)
    text = out["messages"][-1].content.lower()

    assert "executed" not in text
    assert "failed" in text
