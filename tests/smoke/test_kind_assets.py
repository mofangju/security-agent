from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_kind_config_exists_and_has_control_plane():
    cfg = REPO_ROOT / "kind" / "kind-config.yaml"
    assert cfg.exists()
    text = cfg.read_text(encoding="utf-8")
    assert "kind: Cluster" in text
    assert "control-plane" in text


def test_kind_scripts_are_present():
    up = REPO_ROOT / "scripts" / "kind_demo_up.sh"
    down = REPO_ROOT / "scripts" / "kind_demo_down.sh"
    assert up.exists()
    assert down.exists()

    up_text = up.read_text(encoding="utf-8")
    down_text = down.read_text(encoding="utf-8")
    assert "kind create cluster" in up_text
    assert "kind delete cluster" in down_text
