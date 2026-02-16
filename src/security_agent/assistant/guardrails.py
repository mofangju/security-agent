"""Deterministic guardrails for assistant routing and tool-result handling."""

from __future__ import annotations

import json

ALLOWED_ROUTES = {
    "monitor",
    "log_analyst",
    "config_manager",
    "threat_intel",
    "tuner",
    "reporter",
    "rag_agent",
    "direct",
}


def parse_supervisor_route(raw: str) -> str:
    """Return an allowed route token, defaulting to direct."""
    token = (raw or "").strip().lower()
    if token in ALLOWED_ROUTES:
        return token
    return "direct"


def parse_tool_result(raw: str | dict) -> tuple[bool, str]:
    """Return (success, reason) based on tool JSON payload."""
    payload: object = raw
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except Exception:
            return False, "tool response was not valid JSON"

    if not isinstance(payload, dict):
        return False, "tool response was not an object"

    if payload.get("error"):
        return False, str(payload["error"])

    status = str(payload.get("status", "")).strip().lower()
    if status and status not in {"ok", "success"}:
        return False, f"unexpected status: {status}"

    return True, ""
