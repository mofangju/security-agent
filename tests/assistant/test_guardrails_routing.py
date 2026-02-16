from __future__ import annotations

from security_agent.assistant.guardrails import parse_supervisor_route


def test_route_accepts_only_exact_allowed_token():
    assert parse_supervisor_route("monitor") == "monitor"
    assert parse_supervisor_route(" MONITOR ") == "monitor"


def test_route_rejects_embedded_or_multi_route_output():
    assert parse_supervisor_route("route=monitor") == "direct"
    assert parse_supervisor_route("monitor and then config_manager") == "direct"
    assert parse_supervisor_route("unknown") == "direct"
