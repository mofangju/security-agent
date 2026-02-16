from __future__ import annotations

import time

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


def test_config_change_executes_after_confirm_with_nonce(monkeypatch):
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

    first = {
        "messages": [HumanMessage(content="Switch WAF to block mode")],
        "next_node": "config_manager",
        "context": {"confirmed": False},
    }
    prompt = config_manager_node(first)
    nonce = prompt["context"]["pending_action"]["nonce"]

    second = {
        "messages": [HumanMessage(content=f"confirm {nonce}")],
        "next_node": "config_manager",
        "context": prompt["context"],
    }
    out = config_manager_node(second)

    assert called["set_mode"] == "block"
    assert "executed" in out["messages"][-1].content.lower()


def test_confirm_rejected_when_nonce_does_not_match(monkeypatch):
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
        "messages": [HumanMessage(content="confirm 999999")],
        "next_node": "config_manager",
        "context": {
            "pending_action": {
                "action": "set_mode",
                "mode": "block",
                "ip": None,
                "comment": "",
                "nonce": "123456",
                "expires_at": int(time.time()) + 120,
            },
            "confirmed": False,
        },
    }
    out = config_manager_node(state)

    assert called["set_mode"] is False
    assert "invalid confirmation token" in out["messages"][-1].content.lower()


def test_confirm_rejected_when_pending_action_expired(monkeypatch):
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
        "messages": [HumanMessage(content="confirm 123456")],
        "next_node": "config_manager",
        "context": {
            "pending_action": {
                "action": "set_mode",
                "mode": "block",
                "ip": None,
                "comment": "",
                "nonce": "123456",
                "expires_at": 0,
            },
            "confirmed": False,
        },
    }
    out = config_manager_node(state)

    assert called["set_mode"] is False
    assert "expired" in out["messages"][-1].content.lower()


def test_config_manager_does_not_claim_success_on_tool_error(monkeypatch):
    monkeypatch.setattr(
        "security_agent.assistant.graph.get_llm",
        lambda temperature=0.0: _LLMStub("ok"),
    )
    monkeypatch.setattr("security_agent.assistant.graph.tool_get_system_info", lambda: "{}")
    monkeypatch.setattr(
        "security_agent.assistant.graph.tool_set_protection_mode",
        lambda _mode: '{"error":"api timeout"}',
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
                "expires_at": int(time.time()) + 120,
            },
            "confirmed": False,
        },
    }
    out = config_manager_node(state)

    text = out["messages"][-1].content.lower()
    assert "executed" not in text
    assert "failed" in text


def test_blacklist_action_rejected_for_invalid_ip(monkeypatch):
    monkeypatch.setattr(
        "security_agent.assistant.graph.get_llm",
        lambda temperature=0.0: _LLMStub("ok"),
    )
    monkeypatch.setattr("security_agent.assistant.graph.tool_get_system_info", lambda: "{}")

    state = {
        "messages": [HumanMessage(content="blacklist ip 999.999.999.999 now")],
        "next_node": "config_manager",
        "context": {"confirmed": False},
    }
    out = config_manager_node(state)

    assert "invalid ip" in out["messages"][-1].content.lower()
