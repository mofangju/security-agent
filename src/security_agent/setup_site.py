"""Register Pet Shop as a protected site in SafeLine WAF.

This script uses SafeLine's REST API to add Pet Shop as a
reverse-proxied application.

Usage:
    python -m security_agent.setup_site
"""

from __future__ import annotations

import json
import sys
import urllib3

import requests

from security_agent.config import config

# Suppress InsecureRequestWarning for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def setup_site() -> None:
    """Register Pet Shop in SafeLine WAF."""
    base_url = config.safeline.url.rstrip("/")
    headers = config.safeline.headers

    if not config.safeline.api_token:
        print("❌ SAFELINE_API_TOKEN not set in .env")
        print("   1. Open SafeLine UI: https://localhost:9443")
        print("   2. Go to System Management → API Token")
        print("   3. Generate a token and add it to .env")
        sys.exit(1)

    # Check if SafeLine is reachable
    try:
        resp = requests.get(
            f"{base_url}/api/open/system",
            headers=headers,
            verify=False,
            timeout=10,
        )
        resp.raise_for_status()
        version = resp.json()
        print(f"✅ SafeLine is reachable. Version: {json.dumps(version, indent=2)}")
    except requests.RequestException as e:
        print(f"❌ Cannot reach SafeLine at {base_url}: {e}")
        sys.exit(1)

    # Register Pet Shop as a protected site
    site_payload = {
        "ports": ["80"],
        "server_names": ["petshop.local"],
        "upstreams": ["http://petshop:8080"],
        "load_balance": {
            "balance_type": 1,  # Round-robin
        },
        "comment": "Pet Shop — Vulnerable Demo Application",
    }

    print(f"\n📝 Registering Pet Shop in SafeLine...")
    print(f"   Domain: petshop.local")
    print(f"   Upstream: http://petshop:8080")
    print(f"   SafeLine listen port: 80")

    try:
        resp = requests.post(
            f"{base_url}/api/open/site",
            headers=headers,
            json=site_payload,
            verify=False,
            timeout=10,
        )
        if resp.status_code == 200:
            print(f"✅ Pet Shop registered successfully!")
            print(f"\n   Access Pet Shop via SafeLine: http://localhost:80")
            print(f"   Access Pet Shop directly (no WAF): http://localhost:8080")
        else:
            print(f"⚠️  Response ({resp.status_code}): {resp.text}")
            print("   Site may already be registered, or payload format may differ.")
            print("   You can also register manually via SafeLine UI.")
    except requests.RequestException as e:
        print(f"❌ Failed to register site: {e}")
        print("   You can register manually via SafeLine UI → Applications → Add Application")


def check_protection_mode() -> None:
    """Check and display current SafeLine protection mode."""
    base_url = config.safeline.url.rstrip("/")
    headers = config.safeline.headers

    try:
        resp = requests.get(
            f"{base_url}/api/open/global/mode",
            headers=headers,
            verify=False,
            timeout=10,
        )
        if resp.status_code == 200:
            mode_data = resp.json()
            print(f"\n🛡️  Current protection mode: {json.dumps(mode_data, indent=2)}")
        else:
            print(f"⚠️  Could not fetch protection mode: {resp.status_code}")
    except requests.RequestException:
        pass


if __name__ == "__main__":
    setup_site()
    check_protection_mode()
