from __future__ import annotations

import json

from langchain_core.messages import HumanMessage

from security_agent.assistant.graph import rag_agent_node
from security_agent.assistant.selfrag import parse_selfrag_decision, validate_answer_citations
from security_agent.config import config


class _LLMSequence:
    def __init__(self, outputs: list[str]):
        self._outputs = list(outputs)

    def invoke(self, _messages):
        if not self._outputs:
            raise AssertionError("LLM stub exhausted")
        return type("Resp", (), {"content": self._outputs.pop(0)})()


def test_parse_selfrag_decision_accepts_allowed_tokens():
    assert parse_selfrag_decision("FINAL: grounded")[0] == "FINAL"
    assert parse_selfrag_decision("retry: weak evidence")[0] == "RETRY"
    assert parse_selfrag_decision("clarify: ambiguous")[0] == "CLARIFY"


def test_citation_guardrail_rejects_missing_citations():
    ok, reason = validate_answer_citations(
        "This answer has no citations.",
        evidence_count=3,
        min_citations=1,
    )
    assert ok is False
    assert "citation" in reason


def test_rag_agent_retries_then_returns_grounded_answer(monkeypatch):
    monkeypatch.setattr(
        "security_agent.assistant.graph.get_llm",
        lambda temperature=0.0: _LLMSequence(
            [
                "SafeLine has a mode called block.",
                "RETRY: missing citations",
                "SafeLine block mode actively blocks attacks [1].",
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
                    "text": "SafeLine supports block, detect, and off modes.",
                    "source": "safeline-mode.md",
                    "section": "Modes",
                    "chunk_index": 0,
                    "score": 0.91,
                }
            ]
        ),
    )

    state = {
        "messages": [HumanMessage(content="How does block mode work?")],
        "next_node": "rag_agent",
        "context": {},
    }
    out = rag_agent_node(state)

    answer = out["messages"][-1].content
    assert "[1]" in answer
    assert out["context"]["selfrag"]["grounded"] is True
    assert len(out["context"]["selfrag"]["trace"]) == 2


def test_rag_agent_clarifies_when_no_evidence(monkeypatch):
    monkeypatch.setattr(
        "security_agent.assistant.graph.get_llm",
        lambda temperature=0.0: _LLMSequence(["FINAL: grounded"]),
    )
    monkeypatch.setattr(
        "security_agent.assistant.graph.tool_rag_search",
        lambda query, n_results=5, where=None: "[]",
    )

    state = {
        "messages": [HumanMessage(content="How do I configure advanced bot rules?")],
        "next_node": "rag_agent",
        "context": {"doc_scope": {"upload_id": "u-1"}},
    }
    out = rag_agent_node(state)

    msg = out["messages"][-1].content.lower()
    assert "grounded evidence" in msg
    assert out["context"]["selfrag"]["grounded"] is False


def test_rag_agent_rejects_final_without_valid_citations(monkeypatch):
    monkeypatch.setattr(config.rag, "selfrag_max_attempts", 1)
    monkeypatch.setattr(
        "security_agent.assistant.graph.get_llm",
        lambda temperature=0.0: _LLMSequence(
            [
                "Block mode is available.",
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
                    "score": 0.88,
                }
            ]
        ),
    )

    state = {
        "messages": [HumanMessage(content="Is block mode supported?")],
        "next_node": "rag_agent",
        "context": {},
    }
    out = rag_agent_node(state)

    msg = out["messages"][-1].content.lower()
    assert "verifiable grounded answer" in msg
    assert out["context"]["selfrag"]["grounded"] is False
