from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_runbook_mentions_agent_specific_metrics_and_queries():
    runbook = REPO_ROOT / "docs" / "agent-observability-runbook.md"
    assert runbook.exists()
    text = runbook.read_text(encoding="utf-8")

    assert "security_agent_agent_handoff_total" in text
    assert "security_agent_agent_tool_calls_total" in text
    assert "security_agent_agent_selfrag_decision_total" in text
    assert "security_agent_agent_guardrail_total" in text
    assert "trace_id" in text
    assert "session_id" in text
    assert "sum(rate(security_agent_agent_tool_calls_total" in text
