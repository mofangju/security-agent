from __future__ import annotations

from security_agent.tools.validators import normalize_mode, sanitize_comment, validate_ip_or_cidr


def test_validate_ip_or_cidr_rejects_invalid_ipv4():
    assert validate_ip_or_cidr("999.999.999.999") is None
    assert validate_ip_or_cidr("192.168.1.7") == "192.168.1.7"


def test_normalize_mode_rejects_unknown_mode():
    assert normalize_mode("block") == "block"
    assert normalize_mode("DROP TABLE") is None


def test_sanitize_comment_strips_control_chars_and_caps_length():
    dirty = "blocked\x00\x01 reason\n\nline2"
    clean = sanitize_comment(dirty, max_len=12)
    assert "\x00" not in clean
    assert "\x01" not in clean
    assert len(clean) <= 12
