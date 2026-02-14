# Incident Response Playbook

## Overview

This playbook defines the procedures for responding to security incidents detected by SafeLine WAF. It follows the NIST SP 800-61 incident handling framework.

## Severity Levels

| Level | Description | Response Time | Example |
|---|---|---|---|
| Critical | Active data breach or system compromise | Immediate (< 15 min) | Successful SQL injection exfiltrating user data |
| High | Active attack in progress | < 1 hour | Persistent automated attack from single IP |
| Medium | Blocked attacks with suspicious patterns | < 4 hours | Repeated SQLi attempts from multiple IPs |
| Low | Single blocked attack attempt | Next business day | Isolated XSS attempt |

## Incident Response Phases

### Phase 1: Detection and Analysis

1. **Review SafeLine attack events**
   - Check /api/open/events for recent attacks
   - Note: attack type, source IP, target URL, timestamp
   - Determine if attacks were blocked or succeeded

2. **Assess impact**
   - Was the application in BLOCK or DETECT mode?
   - Did any attacks reach the application?
   - Check application logs for anomalies

3. **Classify severity**
   - Use the severity table above
   - Escalate if attacks bypass WAF

### Phase 2: Containment

1. **Immediate actions**
   - Switch SafeLine to BLOCK mode if in DETECT mode
   - Add attacker IPs to SafeLine blacklist via /api/open/ipgroup
   - Enable rate limiting for targeted endpoints

2. **Short-term containment**
   - Create custom WAF rules for specific attack patterns
   - Restrict access to sensitive endpoints
   - Consider geographic IP blocking if attacks originate from specific regions

### Phase 3: Eradication

1. **Root cause analysis**
   - Identify the vulnerability the attacker was targeting
   - Map attacks to CWE/OWASP categories
   - Determine if any data was compromised

2. **Patch vulnerabilities**
   - Fix SQL injection: use parameterized queries
   - Fix XSS: implement output encoding
   - Fix command injection: sanitize input, avoid shell=True
   - Fix path traversal: validate file paths against allowed directories

### Phase 4: Recovery

1. **Verify fixes**
   - Re-run attack payloads against patched application
   - Confirm SafeLine blocks all attack vectors
   - Review application logs for clean traffic

2. **Restore normal operations**
   - Monitor for 24-48 hours after incident
   - Adjust WAF rules if false positives emerge
   - Update IP blacklists as needed

### Phase 5: Post-Incident

1. **Generate incident report**
   - Timeline of events
   - Attack vectors and techniques used
   - Impact assessment
   - Actions taken
   - Recommendations for prevention

2. **Lessons learned**
   - What worked well in detection/response?
   - What could be improved?
   - Update WAF rules and monitoring based on findings

## Report Template

```
SECURITY INCIDENT REPORT
========================
Incident ID: [auto-generated]
Date: [incident date]
Severity: [Critical/High/Medium/Low]
Status: [Active/Contained/Resolved]

TIMELINE
--------
[time] - Attack detected by SafeLine
[time] - Investigation began
[time] - Containment actions taken
[time] - Root cause identified
[time] - Incident resolved

ATTACK DETAILS
--------------
Source IP(s): [attacker IPs]
Attack Types: [SQLi, XSS, etc.]
Target URLs: [affected endpoints]
Total Events: [count]
Blocked: [count]
Succeeded: [count]

IMPACT
------
[Description of impact]

ACTIONS TAKEN
-------------
1. [action 1]
2. [action 2]

RECOMMENDATIONS
---------------
1. [recommendation 1]
2. [recommendation 2]
```
