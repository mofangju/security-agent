"""Guardrails for handling untrusted retrieved documentation content."""

from __future__ import annotations

import re

_SUSPICIOUS_LINE_PATTERNS = [
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"^\s*(system|developer|assistant|tool)\s*:", re.IGNORECASE),
    re.compile(r"you\s+are\s+chatgpt", re.IGNORECASE),
    re.compile(r"\bact\s+as\b", re.IGNORECASE),
]


def _line_is_suspicious(line: str) -> bool:
    return any(pattern.search(line) for pattern in _SUSPICIOUS_LINE_PATTERNS)


def sanitize_retrieved_text(text: str, max_chars: int = 1500) -> str:
    """Drop suspicious instruction-like lines and bound chunk length."""
    lines = []
    for line in (text or "").splitlines():
        if _line_is_suspicious(line):
            continue
        lines.append(line)
    clean = "\n".join(lines).strip()
    if len(clean) > max_chars:
        clean = clean[:max_chars].rstrip()
    return clean
