from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_kind_deploy_script_contains_required_steps():
    script = REPO_ROOT / "scripts" / "kind_demo_deploy.sh"
    assert script.exists()
    text = script.read_text(encoding="utf-8")

    assert "docker build -t" in text
    assert "kind load docker-image" in text
    assert "create secret generic security-agent-secrets" in text
    assert "helm upgrade --install" in text
    assert "rollout status" in text


def test_kind_status_script_has_cli_demo_command():
    script = REPO_ROOT / "scripts" / "kind_demo_status.sh"
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "python -m security_agent.assistant" in text
    assert "kubectl" in text
