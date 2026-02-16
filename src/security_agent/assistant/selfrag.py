"""Self-RAG decision and grounding helpers."""

from __future__ import annotations

import json
import re
from typing import Any

ALLOWED_SELF_RAG_DECISIONS = {"FINAL", "RETRY", "CLARIFY", "ESCALATE"}
_CITATION_RE = re.compile(r"\[(\d+)\]")


def parse_selfrag_decision(raw: str) -> tuple[str, str]:
    """Parse critic output into (decision, reason)."""
    text = (raw or "").strip()
    if not text:
        return "ESCALATE", "empty_critic_response"

    head, sep, tail = text.partition(":")
    token = head.strip().upper()
    reason = tail.strip() if sep else ""

    if token not in ALLOWED_SELF_RAG_DECISIONS:
        return "ESCALATE", "invalid_decision_token"
    return token, reason


def parse_evidence_payload(raw: str | dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    """Parse tool_rag_search payload into evidence list."""
    payload: Any = raw
    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except Exception:
            return [], "invalid_json"

    if isinstance(payload, dict) and payload.get("error"):
        return [], f"retrieval_error:{payload.get('error')}"

    if not isinstance(payload, list):
        return [], "invalid_payload_type"

    evidence: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        evidence.append(item)
    return evidence, ""


def extract_numeric_citations(answer: str) -> set[int]:
    """Extract numeric citation markers like [1], [2]."""
    citations: set[int] = set()
    for match in _CITATION_RE.finditer(answer or ""):
        try:
            citations.add(int(match.group(1)))
        except ValueError:
            continue
    return citations


def validate_answer_citations(
    answer: str,
    *,
    evidence_count: int,
    min_citations: int = 1,
) -> tuple[bool, str]:
    """Validate that answer contains in-range citations."""
    citations = extract_numeric_citations(answer)
    if len(citations) < min_citations:
        return False, "missing_citations"

    if evidence_count <= 0:
        return False, "no_evidence"

    for idx in citations:
        if idx < 1 or idx > evidence_count:
            return False, f"citation_out_of_range:{idx}"
    return True, "ok"


def format_evidence_for_prompt(evidence: list[dict[str, Any]]) -> str:
    """Render retrieved evidence into deterministic numbered blocks."""
    lines: list[str] = []
    for i, item in enumerate(evidence, start=1):
        source = str(item.get("source", "unknown"))
        section = str(item.get("section", ""))
        text = str(item.get("text", ""))
        lines.append(f"[{i}] source={source} section={section}\n{text}")
    return "\n\n".join(lines)
