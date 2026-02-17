from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_demo_dependencies_script_mentions_safeline_and_petshop_steps():
    up = REPO_ROOT / "scripts" / "demo_dependencies_up.sh"
    down = REPO_ROOT / "scripts" / "demo_dependencies_down.sh"
    assert up.exists()
    assert down.exists()

    up_text = up.read_text(encoding="utf-8")
    down_text = down.read_text(encoding="utf-8")

    assert "scripts/safeline.sh up" in up_text
    assert "docker compose up -d petshop" in up_text
    assert "python -m security_agent.setup_site" in up_text
    assert "docker compose down" in down_text
