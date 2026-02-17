from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_kind_values_sets_demo_safe_defaults():
    values = REPO_ROOT / "kind" / "security-agent-values-kind.yaml"
    assert values.exists()
    text = values.read_text(encoding="utf-8")

    assert "replicaCount: 1" in text
    assert "autoscaling:" in text
    assert "enabled: false" in text
    assert "SAFELINE_URL: https://host.docker.internal:9443" in text
    assert 'SAFELINE_VERIFY_TLS: "false"' in text
