"""Structured audit logging for guardrail decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from security_agent.config import config


@dataclass
class GuardrailAuditLogger:
    """Append-only JSON logger for guardrail decisions."""

    path: Path
    enabled: bool = True

    def log(
        self,
        *,
        gate: str,
        decision: str,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "gate": gate,
            "decision": decision,
            "reason": reason,
            "metadata": metadata or {},
        }
        with self.path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, ensure_ascii=True) + "\n")


@lru_cache(maxsize=1)
def get_guardrail_audit_logger() -> GuardrailAuditLogger:
    """Return singleton audit logger based on runtime config."""
    return GuardrailAuditLogger(
        path=Path(config.guardrails.audit_path),
        enabled=config.guardrails.audit_enabled,
    )
