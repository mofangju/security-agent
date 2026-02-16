"""Structured action parsing for configuration changes."""

from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass
from typing import Literal

from security_agent.tools.validators import sanitize_comment

_IP_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})")
_CONFIRM_RE = re.compile(r"\b(yes|y|confirm|confirmed|proceed|apply|go ahead|do it)\b")
_CONFIRM_NONCE_RE = re.compile(r"\bconfirm\s+(\d{6})\b")
PENDING_ACTION_TTL_SECONDS = 300


@dataclass(frozen=True)
class ConfigAction:
    """Normalized representation of a configuration action."""

    action: Literal["set_mode", "blacklist_ip", "none"]
    mode: str | None = None
    ip: str | None = None
    comment: str | None = None


def infer_config_action(text: str) -> ConfigAction:
    """Infer configuration intent from user text."""
    norm = " ".join(text.lower().split())

    ip_match = _IP_RE.search(norm)
    if ip_match and any(k in norm for k in ("block", "ban", "blacklist", "deny")):
        return ConfigAction(
            action="blacklist_ip",
            ip=ip_match.group(1),
            comment="Blocked by Security agent",
        )

    if any(k in norm for k in ("mode", "protection", "waf")):
        if any(k in norm for k in ("block mode", "blocking mode", "set block", "enable block")):
            return ConfigAction(action="set_mode", mode="block")
        if any(
            k in norm
            for k in ("detect mode", "detection mode", "monitor mode", "default mode")
        ):
            return ConfigAction(action="set_mode", mode="detect")
        if any(k in norm for k in ("off mode", "disable mode", "turn off", "disable waf")):
            return ConfigAction(action="set_mode", mode="off")

    return ConfigAction(action="none")


def is_confirmation_message(text: str) -> bool:
    """Return True when the message is an explicit confirmation."""
    return bool(_CONFIRM_RE.search(text.lower()))


def extract_confirmation_nonce(text: str) -> str | None:
    """Return the explicit confirmation nonce from user text."""
    match = _CONFIRM_NONCE_RE.search(text.lower())
    if not match:
        return None
    return match.group(1)


def build_pending_action(
    action: ConfigAction,
    *,
    now_ts: int | None = None,
    ttl_seconds: int = PENDING_ACTION_TTL_SECONDS,
) -> dict:
    """Build a bounded pending-action payload with nonce + expiry."""
    now = int(now_ts if now_ts is not None else time.time())
    return {
        "action": action.action,
        "mode": action.mode,
        "ip": action.ip,
        "comment": sanitize_comment(action.comment),
        "nonce": f"{secrets.randbelow(1_000_000):06d}",
        "expires_at": now + ttl_seconds,
    }


def is_pending_action_valid(raw: dict | None, *, now_ts: int | None = None) -> tuple[bool, str]:
    """Validate pending action envelope."""
    if not isinstance(raw, dict):
        return False, "missing"

    action = str(raw.get("action", ""))
    nonce = str(raw.get("nonce", ""))
    expires_at = raw.get("expires_at")
    if action not in {"set_mode", "blacklist_ip"}:
        return False, "invalid_action"
    if not re.fullmatch(r"\d{6}", nonce):
        return False, "invalid_nonce"
    if not isinstance(expires_at, int):
        return False, "invalid_expiry"

    now = int(now_ts if now_ts is not None else time.time())
    if now > expires_at:
        return False, "expired"
    return True, "ok"


def action_from_pending(raw: dict | None) -> ConfigAction:
    """Build a ConfigAction from pending action state."""
    if not isinstance(raw, dict):
        return ConfigAction(action="none")

    action = str(raw.get("action", "none"))
    if action not in {"set_mode", "blacklist_ip"}:
        return ConfigAction(action="none")

    return ConfigAction(
        action=action,
        mode=raw.get("mode"),
        ip=raw.get("ip"),
        comment=raw.get("comment"),
    )


def action_preview(action: ConfigAction) -> str:
    """Human-readable action description."""
    if action.action == "set_mode":
        return f"set SafeLine protection mode to {action.mode}"
    if action.action == "blacklist_ip":
        return f"add IP {action.ip} to SafeLine blacklist"
    return "no action"
