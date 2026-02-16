"""Register Pet Shop as a protected site in SafeLine WAF.

This script uses SafeLine's REST API to add Pet Shop as a
reverse-proxied application.

Usage:
    python -m security_agent.setup_site
"""

from __future__ import annotations

import json
import sys
from typing import Sequence

import requests
import urllib3

from security_agent.config import config

# Suppress InsecureRequestWarning for self-signed certs in local demo mode.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def discover_petshop_container(candidates: Sequence[str] | None = None) -> str | None:
    """Resolve a running petshop container name from Docker Compose labels."""
    import subprocess

    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "label=com.docker.compose.service=petshop",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if names:
            return names[0]
    except Exception:
        pass

    for name in candidates or ("security-agent-petshop-1",):
        if name:
            return name
    return None


def discover_petshop_ip(container_name: str | None) -> str | None:
    """Resolve container IP from Docker inspect."""
    import subprocess

    if not container_name:
        return None

    try:
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                container_name,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        ip = result.stdout.strip()
        if ip:
            return ip
    except Exception:
        pass
    return None


def build_site_payload(petshop_ip: str, petshop_port: int, listen_port: str = "8888") -> dict:
    """Build SafeLine site registration payload."""
    upstream = f"http://{petshop_ip}:{petshop_port}"
    return {
        "ports": [listen_port],
        "server_names": ["localhost", "petshop.local"],
        "upstreams": [upstream],
        "load_balance": {
            "balance_type": 1,  # Round-robin
        },
        "comment": "Pet Shop — Vulnerable Demo Application",
    }


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

    petshop_ip = "127.0.0.1"
    petshop_port = config.petshop.port
    container_name = discover_petshop_container()
    discovered_ip = discover_petshop_ip(container_name)
    if discovered_ip:
        petshop_ip = discovered_ip

    upstream = f"http://{petshop_ip}:{petshop_port}"
    site_payload = build_site_payload(petshop_ip=petshop_ip, petshop_port=petshop_port)

    print("\n📝 Registering Pet Shop in SafeLine...")
    print("   Domains: localhost, petshop.local")
    print(f"   Upstream: {upstream}")
    print("   SafeLine listen port: 8888")

    try:
        resp = requests.post(
            f"{base_url}/api/open/site",
            headers=headers,
            json=site_payload,
            verify=False,
            timeout=30,
        )
        if resp.status_code == 200:
            print("✅ Pet Shop registered successfully!")
            print("\n   Access Pet Shop via SafeLine: http://localhost:8888")
            print("   Access Pet Shop directly (no WAF): http://localhost:8080")
        elif resp.status_code in (400, 409) and "exist" in resp.text.lower():
            print("✅ Pet Shop appears to be already registered (idempotent success).")
            print(f"   Existing upstream target: {upstream}")
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
