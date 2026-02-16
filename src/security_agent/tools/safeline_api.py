"""SafeLine WAF REST API wrapper — tools for the Security agent."""

from __future__ import annotations

import json

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from security_agent.config import config
from security_agent.tools.validators import normalize_mode, sanitize_comment, validate_ip_or_cidr


class SafeLineAPI:
    """Wrapper for SafeLine WAF REST API."""

    def __init__(self):
        self.base_url = config.safeline.url.rstrip("/")
        self.headers = config.safeline.headers
        self.timeout = config.safeline.timeout
        self.retries = config.safeline.retries
        self.verify_tls = config.safeline.verify_tls
        self.ca_bundle = config.safeline.ca_bundle.strip()

        self.session = requests.Session()
        retry = Retry(
            total=self.retries,
            connect=self.retries,
            read=self.retries,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET", "POST", "PUT"]),
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # For local demo setups using self-signed certs.
        if not self.verify_tls:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    @property
    def verify(self) -> bool | str:
        """Return requests-compatible TLS verify value."""
        if self.verify_tls and self.ca_bundle:
            return self.ca_bundle
        return self.verify_tls

    def _get(self, path: str, params: dict | None = None) -> dict:
        """Make a GET request to SafeLine API."""
        url = f"{self.base_url}{path}"
        resp = self.session.get(
            url,
            headers=self.headers,
            params=params,
            verify=self.verify,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: dict | None = None) -> dict:
        """Make a POST request to SafeLine API."""
        url = f"{self.base_url}{path}"
        resp = self.session.post(
            url,
            headers=self.headers,
            json=data,
            verify=self.verify,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, data: dict | None = None) -> dict:
        """Make a PUT request to SafeLine API."""
        url = f"{self.base_url}{path}"
        resp = self.session.put(
            url,
            headers=self.headers,
            json=data,
            verify=self.verify,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    # ─── System ───

    def get_system_info(self) -> dict:
        """Get SafeLine version and system information."""
        return self._get("/api/open/system")

    # ─── Events and Logs ───

    def get_attack_events(self, page: int = 1, page_size: int = 20) -> dict:
        """Get paginated attack events."""
        return self._get("/api/open/events", params={"page": page, "page_size": page_size})

    def get_acl_records(self, page: int = 1, page_size: int = 20) -> dict:
        """Get ACL block records."""
        return self._get("/api/open/records/acl", params={"page": page, "page_size": page_size})

    def get_challenge_records(self, page: int = 1, page_size: int = 20) -> dict:
        """Get bot detection challenge records."""
        return self._get(
            "/api/open/records/challenge", params={"page": page, "page_size": page_size}
        )

    # ─── Statistics ───

    def get_qps(self) -> dict:
        """Get real-time queries per second."""
        return self._get("/api/stat/qps")

    # ─── Protection Configuration ───

    def get_protection_mode(self) -> dict:
        """Get current protection mode."""
        return self._get("/api/open/global/mode")

    def set_protection_mode(self, mode_data: dict) -> dict:
        """Set protection mode (block/detect/off)."""
        return self._put("/api/open/global/mode", data=mode_data)

    # ─── Policy Rules ───

    def get_policies(self, page: int = 1, page_size: int = 20) -> dict:
        """Get custom policy rules."""
        return self._get(
            "/api/open/policy",
            params={"page": page, "page_size": page_size, "action": -1},
        )

    def create_policy(self, policy_data: dict) -> dict:
        """Create a new custom policy rule."""
        return self._post("/api/open/policy", data=policy_data)


    # ─── IP Groups ───

    def get_ip_groups(self, top: int = 20) -> dict:
        """Get IP groups (blacklist/whitelist)."""
        return self._get("/api/open/ipgroup", params={"top": top})

    def add_ip_group(self, group_data: dict) -> dict:
        """Add an IP group entry."""
        return self._post("/api/open/ipgroup", data=group_data)

    # ─── Sites ───

    def add_site(self, site_data: dict) -> dict:
        """Add a new protected site."""
        return self._post("/api/open/site", data=site_data)

    # ─── Enhanced Rules ───

    def get_enhanced_rules(self) -> dict:
        """Get enhanced detection rules (Skynet)."""
        return self._get("/api/open/skynet/rule")

    def add_enhanced_rule(self, rule_data: dict) -> dict:
        """Add an enhanced detection rule."""
        return self._post("/api/open/skynet/rule", data=rule_data)


# ─── LangChain Tool Functions ───
# These are standalone functions used as LangGraph tools


def tool_get_attack_events(page: int = 1, page_size: int = 20) -> str:
    """Get recent attack events from SafeLine WAF.

    Args:
        page: Page number (default: 1)
        page_size: Number of events per page (default: 20)

    Returns:
        JSON string of attack events
    """
    api = SafeLineAPI()
    try:
        result = api.get_attack_events(page=page, page_size=page_size)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_get_traffic_stats() -> str:
    """Get real-time traffic statistics from SafeLine WAF.

    Returns QPS data and recent attack event counts.
    """
    api = SafeLineAPI()
    stats = {}
    try:
        stats["qps"] = api.get_qps()
    except Exception as e:
        stats["qps"] = {"error": str(e)}
    try:
        events = api.get_attack_events(page=1, page_size=1)
        stats["total_attacks"] = events.get("data", {}).get("total", 0)
    except Exception as e:
        stats["total_attacks"] = {"error": str(e)}
    return json.dumps(stats, indent=2)


def tool_set_protection_mode(mode: str) -> str:
    """Set SafeLine WAF protection mode for all detection categories.

    SafeLine v9.3.2 uses per-category semantic detection modes.
    This tool sets ALL categories to the same mode.

    Args:
        mode: Protection mode — "block" (actively block attacks),
              "default" (detect and log only), or "disable" (turn off detection)

    Returns:
        JSON string with result
    """
    normalized_mode = normalize_mode(mode)
    if normalized_mode is None:
        return json.dumps({"error": f"Invalid mode: {mode}"})

    # Map normalized names to SafeLine API values.
    mode_map = {
        "block": "block",
        "detect": "default",
        "off": "disable",
    }
    api_mode = mode_map[normalized_mode]

    # All semantic detection categories in SafeLine v9.3.2
    categories = [
        "m_sqli", "m_xss", "m_cmd_injection", "m_file_include",
        "m_file_upload", "m_ssrf", "m_ssti", "m_csrf",
        "m_java", "m_java_unserialize", "m_php_code_injection",
        "m_php_unserialize", "m_asp_code_injection", "m_http",
        "m_scanner", "m_response", "m_rule",
    ]
    semantics = {cat: api_mode for cat in categories}

    api = SafeLineAPI()
    try:
        result = api.set_protection_mode({"semantics": semantics})
        return json.dumps(
            {
                "status": "ok",
                "mode": normalized_mode,
                "api_mode": api_mode,
                "result": result,
            }
        )
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_manage_ip_blacklist(action: str, ip: str, comment: str = "") -> str:
    """Add or list IP blacklist entries in SafeLine WAF.

    Args:
        action: "add" to add IP, "list" to list current entries
        ip: IP address to add (only for action="add")
        comment: Optional comment for the entry

    Returns:
        JSON string with result
    """
    api = SafeLineAPI()
    try:
        normalized_action = (action or "").strip().lower()
        if normalized_action == "list":
            result = api.get_ip_groups(top=50)
            return json.dumps(result, indent=2)
        elif normalized_action == "add":
            valid_ip = validate_ip_or_cidr(ip)
            if valid_ip is None:
                return json.dumps({"error": f"Invalid IP/CIDR: {ip}"})

            safe_comment = sanitize_comment(comment or "Blocked by Security agent")
            if not safe_comment:
                safe_comment = "Blocked by Security agent"

            result = api.add_ip_group({
                "ips": [valid_ip],
                "action": "deny",
                "comment": safe_comment,
            })
            return json.dumps({"status": "ok", "ip": valid_ip, "result": result})
        else:
            return json.dumps({"error": f"Unknown action: {action}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_get_system_info() -> str:
    """Get SafeLine WAF system information and version."""
    api = SafeLineAPI()
    try:
        result = api.get_system_info()
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})
