from __future__ import annotations

from security_agent.setup_site import build_site_payload


def test_setup_site_uses_discovered_container_or_fallback():
    payload = build_site_payload(petshop_ip="172.18.0.5", petshop_port=8080)
    assert payload["upstreams"] == ["http://172.18.0.5:8080"]
    assert payload["ports"] == ["8888"]
