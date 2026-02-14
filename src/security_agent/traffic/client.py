"""Legitimate client traffic generator.

Simulates realistic user behavior: browsing homepage, viewing products,
searching, submitting reviews. Used to establish baseline "normal" traffic.
"""

from __future__ import annotations

import random
import time

import requests


# Simulated user browsing sessions
USER_SESSIONS = [
    {
        "name": "Alice",
        "actions": [
            ("GET", "/", None, None),
            ("GET", "/product/1", None, None),
            ("GET", "/search", {"q": "golden retriever"}, None),
            ("GET", "/product/1", None, None),
            ("POST", "/review", None, {"product_id": "1", "author": "Alice", "content": "Love this puppy!", "rating": "5"}),
        ],
    },
    {
        "name": "Bob",
        "actions": [
            ("GET", "/", None, None),
            ("GET", "/search", {"q": "cat"}, None),
            ("GET", "/product/2", None, None),
            ("GET", "/product/4", None, None),
            ("GET", "/search", {"q": "maine coon"}, None),
            ("GET", "/product/8", None, None),
        ],
    },
    {
        "name": "Charlie",
        "actions": [
            ("GET", "/", None, None),
            ("GET", "/product/5", None, None),
            ("GET", "/search", {"q": "rabbit"}, None),
            ("POST", "/review", None, {"product_id": "5", "author": "Charlie", "content": "Great pet for kids", "rating": "4"}),
        ],
    },
    {
        "name": "Diana",
        "actions": [
            ("GET", "/", None, None),
            ("GET", "/search", {"q": "bird"}, None),
            ("GET", "/product/6", None, None),
            ("GET", "/search", {"q": "cockatiel care tips"}, None),
            ("GET", "/api/products", None, None),
        ],
    },
    {
        "name": "Eve",
        "actions": [
            ("GET", "/", None, None),
            ("GET", "/product/3", None, None),
            ("GET", "/product/7", None, None),
            ("GET", "/search", {"q": "labrador"}, None),
            ("POST", "/review", None, {"product_id": "7", "author": "Eve", "content": "Best family dog ever!", "rating": "5"}),
        ],
    },
]


def generate_client_traffic(
    base_url: str = "http://localhost:8080",
    delay_range: tuple[float, float] = (0.5, 2.0),
    rounds: int = 1,
) -> list[dict]:
    """Generate legitimate client traffic.

    Args:
        base_url: Target URL (Pet Shop or SafeLine proxy)
        delay_range: Min/max delay between requests (seconds)
        rounds: Number of times to cycle through all sessions

    Returns:
        List of request/response records
    """
    records = []

    for round_num in range(rounds):
        # Shuffle user order each round
        sessions = USER_SESSIONS.copy()
        random.shuffle(sessions)

        for session in sessions:
            print(f"  👤 {session['name']} browsing...")

            for method, path, params, data in session["actions"]:
                url = f"{base_url}{path}"

                try:
                    if method == "GET":
                        resp = requests.get(url, params=params, timeout=10)
                    else:
                        resp = requests.post(url, data=data, timeout=10)

                    record = {
                        "user": session["name"],
                        "method": method,
                        "path": path,
                        "params": params,
                        "status": resp.status_code,
                        "type": "legitimate",
                    }
                    records.append(record)

                    status_icon = "✅" if resp.status_code < 400 else "⚠️"
                    print(f"    {status_icon} {method} {path} → {resp.status_code}")

                except requests.RequestException as e:
                    print(f"    ❌ {method} {path} → Error: {e}")

                # Random delay to simulate human browsing
                time.sleep(random.uniform(*delay_range))

    print(f"\n📊 Client traffic complete: {len(records)} requests sent")
    return records


if __name__ == "__main__":
    print("🚦 Starting legitimate client traffic...")
    generate_client_traffic()
