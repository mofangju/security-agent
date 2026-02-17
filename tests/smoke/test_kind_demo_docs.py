from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_kind_demo_walkthrough_includes_cli_exec_flow():
    walkthrough = REPO_ROOT / "docs" / "kind-demo-walkthrough.md"
    assert walkthrough.exists()
    text = walkthrough.read_text(encoding="utf-8")

    assert "bash scripts/demo_dependencies_up.sh" in text
    assert "bash scripts/kind_demo_up.sh" in text
    assert "bash scripts/kind_demo_deploy.sh" in text
    assert "python -m security_agent.assistant" in text
    assert "curl -s http://localhost:8081/metrics" in text
    assert "kubectl --context kind-security-agent-demo apply -f k8s/observability/otel-collector.yaml" in text
