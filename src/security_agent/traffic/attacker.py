"""Attacker traffic generator.

Executes attack payloads against Pet Shop (directly or via SafeLine).
Reports results showing which attacks succeeded vs were blocked.
"""

from __future__ import annotations

import time

import requests

from security_agent.traffic.payloads import ALL_PAYLOADS, Payload


def execute_payload(payload: Payload, base_url: str, timeout: int = 10) -> dict:
    """Execute a single attack payload and record the result."""
    url = f"{base_url}{payload.path}"

    try:
        if payload.method == "GET":
            resp = requests.get(url, params=payload.params, timeout=timeout)
        else:
            resp = requests.post(url, data=payload.data, timeout=timeout)

        # Determine if the attack was blocked (403) or succeeded
        blocked = resp.status_code == 403
        success = resp.status_code == 200

        return {
            "payload": payload.name,
            "category": payload.category,
            "method": payload.method,
            "path": payload.path,
            "status_code": resp.status_code,
            "blocked": blocked,
            "success": success,
            "response_length": len(resp.text),
            "description": payload.description,
        }

    except requests.RequestException as e:
        return {
            "payload": payload.name,
            "category": payload.category,
            "method": payload.method,
            "path": payload.path,
            "status_code": 0,
            "blocked": False,
            "success": False,
            "error": str(e),
            "description": payload.description,
        }


def generate_attacker_traffic(
    base_url: str = "http://localhost:8080",
    delay: float = 0.5,
    categories: list[str] | None = None,
) -> list[dict]:
    """Execute all attack payloads and report results.

    Args:
        base_url: Target URL (Pet Shop directly or via SafeLine)
        delay: Delay between attacks (seconds)
        categories: Filter by category (sqli, xss, traversal, cmdi). None = all.

    Returns:
        List of attack result records
    """
    payloads = ALL_PAYLOADS
    if categories:
        payloads = [p for p in payloads if p.category in categories]

    results = []
    blocked_count = 0
    success_count = 0

    print(f"\n💀 Launching {len(payloads)} attack payloads against {base_url}")
    print(f"{'─' * 70}")

    for payload in payloads:
        result = execute_payload(payload, base_url)
        results.append(result)

        if result.get("blocked"):
            icon = "🛡️ BLOCKED"
            blocked_count += 1
        elif result.get("success"):
            icon = "💥 SUCCESS"
            success_count += 1
        else:
            icon = "❓ UNKNOWN"

        print(
            f"  [{payload.category.upper():10s}] {icon} — {payload.name}"
            f" → HTTP {result['status_code']}"
        )

        time.sleep(delay)

    # Summary
    total = len(results)
    print(f"\n{'═' * 70}")
    print(f"  Attack Summary")
    print(f"{'─' * 70}")
    print(f"  Total payloads:  {total}")
    print(f"  💥 Successful:   {success_count}")
    print(f"  🛡️ Blocked:      {blocked_count}")
    print(f"  ❓ Other:        {total - success_count - blocked_count}")
    print(f"{'═' * 70}")

    if blocked_count == total:
        print("  ✅ ALL attacks were blocked! WAF is working.")
    elif success_count > 0:
        print(f"  ⚠️  {success_count} attacks SUCCEEDED! Application is vulnerable.")

    return results


if __name__ == "__main__":
    generate_attacker_traffic()
