from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_observability_assets_include_agent_specific_signals():
    values = (REPO_ROOT / "charts" / "security-agent" / "values.yaml").read_text(encoding="utf-8")
    collector = (REPO_ROOT / "k8s" / "observability" / "otel-collector.yaml").read_text(
        encoding="utf-8"
    )
    rules_path = REPO_ROOT / "k8s" / "observability" / "prometheus-rules-agent.yaml"
    assert rules_path.exists()
    rules = rules_path.read_text(encoding="utf-8")

    assert "AGENT_OBSERVABILITY_ENABLED" in values
    assert "AGENT_METRICS_NAMESPACE" in values
    assert "AGENT_TRACE_JSONL_PATH" in values

    assert "security-agent-security-agent.security-agent.svc.cluster.local:8081" in collector

    assert "SecurityAgentToolFailureHigh" in rules
    assert "SecurityAgentSelfRagEscalationHigh" in rules
    assert "SecurityAgentGuardrailDenySpike" in rules
