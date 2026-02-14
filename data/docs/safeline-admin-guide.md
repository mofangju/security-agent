# SafeLine WAF Administration Guide

## Overview

SafeLine is an open-source Web Application Firewall developed by Chaitin Tech. It uses semantic analysis to detect and block web attacks including SQL injection, XSS, path traversal, and command injection.

SafeLine operates as a reverse proxy, sitting between clients and your web application. All HTTP/HTTPS traffic flows through SafeLine for inspection before reaching your backend.

## Architecture

SafeLine runs as 7 Docker containers:
- **safeline-tengine**: Nginx-based reverse proxy for traffic inspection
- **safeline-detector**: AI semantic analysis engine for attack detection
- **safeline-mgt**: Web management UI (default port 9443)
- **safeline-pg**: PostgreSQL database for logs and configuration
- **safeline-luigi**: Data processing pipeline
- **safeline-fvm**: Analytics engine
- **safeline-chaos**: Supplementary services

## Protection Modes

SafeLine supports three protection modes:
1. **Block Mode**: Actively blocks detected attacks with 403 responses
2. **Detect Mode**: Logs attacks but allows all traffic through (monitoring only)
3. **Off Mode**: No protection, all traffic passes through

To change the protection mode:
- Via UI: Go to Protection → General Settings → Protection Mode
- Via API: PUT /api/open/global/mode with the desired mode value

## Adding Protected Sites

To protect a web application with SafeLine:
1. Go to Applications → Add Application
2. Enter the domain name (or IP) of your application
3. Set the port SafeLine should listen on (e.g., 80 or 443)
4. Enter the upstream (real) address of your application
5. For HTTPS, enable SSL and upload certificates

Via API: POST /api/open/site with port, server_names, and upstreams.

## Custom Rules and Policies

### Creating Custom Rules
- Go to Protection → Custom Rules
- Via API: POST /api/open/policy

Custom rules support:
- URL pattern matching (exact, prefix, regex)
- Header inspection
- Request body analysis
- IP-based filtering

### Rate Limiting
- Configure at Protection → Rate Limiting
- Via API: POST /api/open/global/acl
- Set thresholds per IP per time window
- Action on exceed: block for N seconds

### IP Groups (Blacklist/Whitelist)
- Manage at Protection → IP Groups
- Via API: GET/POST /api/open/ipgroup
- Add individual IPs or CIDR ranges
- Whitelist trusted IPs (skip WAF inspection)
- Blacklist known malicious IPs

## Attack Detection

SafeLine uses semantic analysis rather than simple regex pattern matching. This means it can detect:
- Zero-day attack patterns
- Obfuscated payloads
- Multi-vector attacks
- Context-aware attack detection

### Attack Categories Detected
- SQL Injection (CWE-89)
- Cross-Site Scripting / XSS (CWE-79)
- Path Traversal (CWE-22)
- Command Injection (CWE-78)
- XXE / XML External Entity (CWE-611)
- CRLF Injection (CWE-93)
- Server-Side Request Forgery / SSRF (CWE-918)

## Monitoring and Logs

### Viewing Attack Logs
- Go to Events → Attack List
- Via API: GET /api/open/events?page=1&page_size=20

Each event includes:
- Timestamp
- Source IP
- Target URL
- Attack type
- Request details
- Matched rule

### Dashboard Statistics
- Daily request count: GET /api/dashboard/requests
- Block statistics: GET /api/dashboard/intercepts
- Real-time QPS: GET /api/stat/qps
- Error rates (4xx/5xx): GET /api/dashboard/counts

## API Authentication

SafeLine REST API uses token-based authentication:
1. Go to System Management → API Token
2. Generate a new API token
3. Include in requests: `X-SLCE-API-TOKEN: <your-token>`

All API endpoints are served on the management port (default 9443) over HTTPS.

## Troubleshooting

### False Positives
If legitimate requests are being blocked:
1. Check the attack log for the blocked request details
2. Create a whitelist rule for the specific URL pattern
3. Or add the client IP to the whitelist IP group
4. Consider adjusting protection sensitivity

### Performance Issues
- Check QPS via /api/stat/qps
- Monitor CPU and memory of safeline-detector container
- Consider scaling upstream servers if throughput is limited

### Log Rotation
SafeLine stores logs in PostgreSQL. To manage storage:
- Configure log retention in System Management
- Export old logs before purging
