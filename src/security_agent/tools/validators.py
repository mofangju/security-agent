"""Input validation helpers for tool guardrails."""

from __future__ import annotations

import ipaddress
import re

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")

_MODE_ALIASES = {
    "block": "block",
    "detect": "detect",
    "default": "detect",
    "off": "off",
    "disable": "off",
}


def normalize_mode(mode: str | None) -> str | None:
    """Normalize mode to block/detect/off, returning None when invalid."""
    if mode is None:
        return None
    return _MODE_ALIASES.get(mode.strip().lower())


def validate_ip_or_cidr(raw: str | None) -> str | None:
    """Validate IPv4/IPv6 address or CIDR and return normalized value."""
    if not raw:
        return None

    value = raw.strip()
    try:
        if "/" in value:
            return str(ipaddress.ip_network(value, strict=False))
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def sanitize_comment(comment: str | None, max_len: int = 128) -> str:
    """Strip control chars and bound comment length."""
    clean = _CONTROL_CHARS_RE.sub("", (comment or ""))
    clean = " ".join(clean.split())
    if len(clean) > max_len:
        clean = clean[:max_len].rstrip()
    return clean
