from __future__ import annotations

import json

from security_agent.assistant.telemetry import AgentTelemetry


def test_route_and_tool_metrics_render_with_labels():
    telemetry = AgentTelemetry(namespace="security_agent")
    telemetry.inc_route("monitor")
    telemetry.observe_tool_call("config_manager", "tool_set_protection_mode", "ok", 0.12)
    text = telemetry.render_prometheus()

    assert 'security_agent_agent_route_total{selected_agent="monitor"} 1' in text
    assert (
        'security_agent_agent_tool_calls_total{agent="config_manager",'
        'tool="tool_set_protection_mode",status="ok"} 1'
    ) in text


def test_trace_event_is_written_with_correlation_ids(tmp_path):
    path = tmp_path / "agent-traces.jsonl"
    telemetry = AgentTelemetry(
        namespace="security_agent",
        trace_jsonl_path=path,
        enabled=True,
    )

    telemetry.emit_event(
        "route.selected",
        trace_id="tr1",
        session_id="s1",
        turn_id="u1",
        metadata={"selected_agent": "monitor"},
    )

    row = path.read_text(encoding="utf-8").strip()
    payload = json.loads(row)
    assert payload["trace_id"] == "tr1"
    assert payload["event"] == "route.selected"
