from __future__ import annotations

from pathlib import Path

from security_agent.assistant.audit import GuardrailAuditLogger


def test_audit_logger_writes_json_record(tmp_path: Path):
    path = tmp_path / "guardrails.jsonl"
    logger = GuardrailAuditLogger(path=path, enabled=True)

    logger.log(
        gate="route_parse",
        decision="deny",
        reason="invalid_token",
        metadata={"raw": "monitor and config_manager"},
    )

    content = path.read_text(encoding="utf-8")
    assert '"gate": "route_parse"' in content
    assert '"decision": "deny"' in content
    assert '"reason": "invalid_token"' in content
