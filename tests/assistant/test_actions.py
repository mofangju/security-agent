from __future__ import annotations

from langchain_core.messages import HumanMessage

from security_agent.assistant.graph import config_manager_node


class _LLMStub:
    def __init__(self, content: str):
        self._content = content

    def invoke(self, _messages):
        return type("Resp", (), {"content": self._content})()


def test_no_config_change_without_explicit_confirm(monkeypatch):
    called = {"set_mode": False}

    monkeypatch.setattr(
        "security_agent.assistant.graph.get_llm",
        lambda temperature=0.0: _LLMStub("set mode to block"),
    )
    monkeypatch.setattr("security_agent.assistant.graph.tool_get_system_info", lambda: "{}")

    def _fake_set_mode(mode: str) -> str:
        called["set_mode"] = True
        return f'{{"mode":"{mode}"}}'

    monkeypatch.setattr("security_agent.assistant.graph.tool_set_protection_mode", _fake_set_mode)

    state = {
        "messages": [HumanMessage(content="Switch WAF to block mode")],
        "next_node": "config_manager",
        "context": {"confirmed": False},
    }
    out = config_manager_node(state)

    assert called["set_mode"] is False
    assert "confirm" in out["messages"][-1].content.lower()
    assert out["context"].get("pending_action")


def test_config_change_executes_after_confirm(monkeypatch):
    called = {"set_mode": None}

    monkeypatch.setattr(
        "security_agent.assistant.graph.get_llm",
        lambda temperature=0.0: _LLMStub("ok"),
    )
    monkeypatch.setattr("security_agent.assistant.graph.tool_get_system_info", lambda: "{}")

    def _fake_set_mode(mode: str) -> str:
        called["set_mode"] = mode
        return f'{{"mode":"{mode}"}}'

    monkeypatch.setattr("security_agent.assistant.graph.tool_set_protection_mode", _fake_set_mode)

    state = {
        "messages": [HumanMessage(content="Switch WAF to block mode")],
        "next_node": "config_manager",
        "context": {"confirmed": True},
    }
    out = config_manager_node(state)

    assert called["set_mode"] == "block"
    assert "executed" in out["messages"][-1].content.lower()
