"""CVE lookup tool — searches a mock CVE database for threat intelligence."""

from __future__ import annotations

import json


# Mock CVE database mapping attack patterns to known vulnerabilities
CVE_DATABASE = {
    "sqli": [
        {
            "cve_id": "CWE-89",
            "name": "SQL Injection",
            "owasp": "A03:2021 - Injection",
            "severity": "Critical",
            "description": "Improper Neutralization of Special Elements used in an SQL Command",
            "remediation": "Use parameterized queries / prepared statements. Never concatenate user input into SQL strings.",
            "references": [
                "https://owasp.org/Top10/A03_2021-Injection/",
                "https://cwe.mitre.org/data/definitions/89.html",
            ],
        },
    ],
    "xss": [
        {
            "cve_id": "CWE-79",
            "name": "Cross-Site Scripting (XSS)",
            "owasp": "A07:2021 - Cross-Site Scripting",
            "severity": "High",
            "description": "Improper Neutralization of Input During Web Page Generation",
            "remediation": "Escape all user-supplied data before rendering. Use Content Security Policy (CSP) headers. Use frameworks that auto-escape (React, Angular).",
            "references": [
                "https://owasp.org/Top10/A07_2021-Cross-Site_Scripting/",
                "https://cwe.mitre.org/data/definitions/79.html",
            ],
        },
    ],
    "traversal": [
        {
            "cve_id": "CWE-22",
            "name": "Path Traversal",
            "owasp": "A01:2021 - Broken Access Control",
            "severity": "High",
            "description": "Improper Limitation of a Pathname to a Restricted Directory",
            "remediation": "Validate file paths against an allowed directory. Use os.path.realpath() and check the prefix. Never use user input directly in file paths.",
            "references": [
                "https://owasp.org/Top10/A01_2021-Broken_Access_Control/",
                "https://cwe.mitre.org/data/definitions/22.html",
            ],
        },
    ],
    "cmdi": [
        {
            "cve_id": "CWE-78",
            "name": "OS Command Injection",
            "owasp": "A03:2021 - Injection",
            "severity": "Critical",
            "description": "Improper Neutralization of Special Elements used in an OS Command",
            "remediation": "Never pass user input to shell commands. Use subprocess with shell=False and a list of arguments. Use shlex.quote() if shell is unavoidable.",
            "references": [
                "https://owasp.org/Top10/A03_2021-Injection/",
                "https://cwe.mitre.org/data/definitions/78.html",
            ],
        },
    ],
    "ssrf": [
        {
            "cve_id": "CWE-918",
            "name": "Server-Side Request Forgery (SSRF)",
            "owasp": "A10:2021 - Server-Side Request Forgery",
            "severity": "High",
            "description": "Server-side code fetches a URL provided by the attacker",
            "remediation": "Validate and sanitize all URLs. Deny internal/private IP ranges. Use allowlists for permitted destinations.",
            "references": [
                "https://owasp.org/Top10/A10_2021-Server-Side_Request_Forgery/",
                "https://cwe.mitre.org/data/definitions/918.html",
            ],
        },
    ],
}


def tool_cve_lookup(attack_category: str) -> str:
    """Look up CVE/CWE information for an attack category.

    Args:
        attack_category: Attack type — one of: sqli, xss, traversal, cmdi, ssrf

    Returns:
        JSON string with CVE/CWE details, OWASP mapping, and remediation
    """
    category = attack_category.lower().strip()
    if category in CVE_DATABASE:
        return json.dumps(CVE_DATABASE[category], indent=2)
    else:
        return json.dumps({
            "error": f"Unknown category: {category}",
            "available": list(CVE_DATABASE.keys()),
        })
