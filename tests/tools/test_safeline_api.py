from __future__ import annotations

from security_agent.tools.safeline_api import SafeLineAPI


def test_verify_tls_default_true():
    api = SafeLineAPI()
    assert api.verify_tls is True
