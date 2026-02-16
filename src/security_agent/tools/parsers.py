"""Parsing helpers for SafeLine API payloads."""

from __future__ import annotations

import json
from datetime import datetime, timezone


def _to_dict(payload: str | dict) -> dict:
    if isinstance(payload, dict):
        return payload
    try:
        return json.loads(payload)
    except Exception:
        return {}


def _node_qps_value(node: dict) -> float:
    for key in ("qps", "value", "requests"):
        val = node.get(key)
        if isinstance(val, (int, float)):
            return float(val)

    numeric_values = []
    for key, val in node.items():
        if key.lower() in {"time", "ts", "timestamp"}:
            continue
        if isinstance(val, (int, float)):
            numeric_values.append(float(val))
    if not numeric_values:
        return 0.0
    return numeric_values[-1]


def parse_qps(payload: str | dict) -> dict:
    """Extract normalized QPS summary from SafeLine stats payload."""
    data = _to_dict(payload)
    nodes = data.get("qps", {}).get("data", {}).get("nodes", [])

    active = []
    latest = 0.0
    for node in nodes:
        qps = _node_qps_value(node)
        latest = qps
        if qps > 0:
            active.append((node.get("time", "?"), qps))

    return {
        "current_qps": latest,
        "total_attacks": data.get("total_attacks", 0),
        "active_qps": active,
    }


def parse_events(payload: str | dict) -> dict:
    """Normalize event payload into display-friendly records."""
    data = _to_dict(payload)
    raw_nodes = data.get("data", {}).get("nodes", [])
    total = data.get("data", {}).get("total", 0)

    normalized = []
    for node in raw_nodes:
        deny = int(node.get("deny_count", 0) or 0)
        passed = int(node.get("pass_count", 0) or 0)
        status = "BLOCKED" if deny > 0 and passed == 0 else "PARTIAL"
        if deny == 0:
            status = "PASSED"

        ts = node.get("start_at", 0)
        if ts and ts > 0:
            time_str = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )
        else:
            time_str = "unknown"

        normalized.append(
            {
                "id": node.get("id", "?"),
                "ip": node.get("ip", "?"),
                "host": node.get("host", "?"),
                "dst_port": node.get("dst_port", "?"),
                "deny_count": deny,
                "pass_count": passed,
                "status": status,
                "time": time_str,
                "country": node.get("country", ""),
                "finished": node.get("finished", True),
            }
        )

    return {"total": total, "events": normalized}
