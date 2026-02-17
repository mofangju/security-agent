from __future__ import annotations

import json

from langchain_core.messages import HumanMessage

from security_agent.assistant.graph import config_manager_node, rag_agent_node, supervisor_node


class _LLMSequence:
    def __init__(self, outputs: list[str]):
        self._outputs = list(outputs)

    def invoke(self, _messages):
        if not self._outputs:
            raise AssertionError("LLM stub exhausted")
        return type("Resp", (), {"content": self._outputs.pop(0)})()


class _AuditNoop:
    def log(self, **_kwargs):
        return None


class _TelemetrySpy:
    def __init__(self):
        self.route_calls: list[str] = []
        self.handoff_calls: list[tuple[str, str]] = []
        self.tool_calls: list[tuple[str, str, str, float]] = []
        self.guardrail_calls: list[tuple[str, str, str]] = []
        self.selfrag_calls: list[tuple[str, str]] = []
        self.events: list[tuple[str, str, str, str, dict]] = []

    def inc_route(self, selected_agent: str) -> None:
        self.route_calls.append(selected_agent)

    def inc_handoff(self, from_agent: str, to_agent: str) -> None:
        self.handoff_calls.append((from_agent, to_agent))

    def observe_tool_call(
        self,
        agent: str,
        tool: str,
        status: str,
        duration_seconds: float,
    ) -> None:
        self.tool_calls.append((agent, tool, status, duration_seconds))

    def observe_guardrail(self, gate: str, decision: str, reason: str) -> None:
        self.guardrail_calls.append((gate, decision, reason))

    def observe_selfrag_decision(self, decision: str, reason: str) -> None:
        self.selfrag_calls.append((decision, reason))

    def emit_event(
        self,
        event: str,
        *,
        trace_id: str,
        session_id: str,
        turn_id: str,
        metadata: dict | None = None,
    ) -> None:
        self.events.append((event, trace_id, session_id, turn_id, metadata or {}))


def test_supervisor_emits_route_metric(monkeypatch):
    spy = _TelemetrySpy()
    monkeypatch.setattr(
        "security_agent.assistant.graph.get_llm",
        lambda temperature=0.0: _LLMSequence(["monitor"]),
    )
    monkeypatch.setattr("security_agent.assistant.graph.AUDIT_LOGGER", _AuditNoop())
    monkeypatch.setattr("security_agent.assistant.graph.TELEMETRY", spy)

    state = {
        "messages": [HumanMessage(content="show traffic status")],
        "next_node": "",
        "context": {"session_id": "s1", "turn_id": "1", "trace_id": "t1"},
    }
    out = supervisor_node(state)

    assert out["next_node"] == "monitor"
    assert spy.route_calls == ["monitor"]
    assert any(evt[0] == "route.selected" for evt in spy.events)


def test_config_manager_tool_call_emits_tool_metrics(monkeypatch):
    spy = _TelemetrySpy()
    monkeypatch.setattr("security_agent.assistant.graph.AUDIT_LOGGER", _AuditNoop())
    monkeypatch.setattr("security_agent.assistant.graph.TELEMETRY", spy)
    monkeypatch.setattr(
        "security_agent.assistant.graph.tool_set_protection_mode",
        lambda mode: json.dumps({"status": "ok", "mode": mode}),
    )

    state = {
        "messages": [HumanMessage(content="confirm 123456")],
        "next_node": "config_manager",
        "context": {
            "session_id": "s1",
            "turn_id": "2",
            "trace_id": "t2",
            "pending_action": {
                "action": "set_mode",
                "mode": "block",
                "ip": None,
                "comment": "",
                "nonce": "123456",
                "expires_at": 9999999999,
            },
            "confirmed": False,
        },
    }
    out = config_manager_node(state)

    assert "Executed: Set protection mode to BLOCK" in out["messages"][-1].content
    assert any(
        item[0] == "config_manager" and item[1] == "tool_set_protection_mode" and item[2] == "ok"
        for item in spy.tool_calls
    )


def test_selfrag_emits_decision_metric(monkeypatch):
    spy = _TelemetrySpy()
    monkeypatch.setattr("security_agent.assistant.graph.AUDIT_LOGGER", _AuditNoop())
    monkeypatch.setattr("security_agent.assistant.graph.TELEMETRY", spy)
    monkeypatch.setattr(
        "security_agent.assistant.graph.get_llm",
        lambda temperature=0.0: _LLMSequence(
            [
                "SafeLine supports block mode [1].",
                "FINAL: grounded",
            ]
        ),
    )
    monkeypatch.setattr(
        "security_agent.assistant.graph.tool_rag_search",
        lambda query, n_results=5, where=None: json.dumps(
            [
                {
                    "id": "doc-1",
                    "text": "SafeLine supports block mode.",
                    "source": "safeline-mode.md",
                    "section": "Modes",
                    "chunk_index": 0,
                    "score": 0.9,
                }
            ]
        ),
    )

    state = {
        "messages": [HumanMessage(content="Is block mode supported?")],
        "next_node": "rag_agent",
        "context": {"session_id": "s1", "turn_id": "3", "trace_id": "t3"},
    }
    out = rag_agent_node(state)

    assert out["context"]["selfrag"]["grounded"] is True
    assert any(decision == "FINAL" for decision, _reason in spy.selfrag_calls)
