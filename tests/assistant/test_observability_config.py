from __future__ import annotations

from security_agent.config import AppConfig


def test_observability_defaults():
    cfg = AppConfig()
    assert cfg.observability.enabled is True
    assert cfg.observability.trace_jsonl_path.endswith("agent-traces.jsonl")
    assert cfg.observability.metrics_namespace == "security_agent"
