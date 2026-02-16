from __future__ import annotations

from security_agent.tools.parsers import parse_qps


def test_extracts_latest_qps_metric_not_timestamp():
    payload = {
        "qps": {
            "data": {
                "nodes": [
                    {"time": "10:00:00", "value": 0},
                    {"time": "10:00:05", "value": 12},
                ]
            }
        },
        "total_attacks": 4,
    }

    parsed = parse_qps(payload)
    assert parsed["current_qps"] == 12
    assert parsed["total_attacks"] == 4
