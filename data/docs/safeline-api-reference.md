# SafeLine REST API Reference

## Authentication

All API requests require the `X-SLCE-API-TOKEN` header:
```
X-SLCE-API-TOKEN: <your-token>
Content-Type: application/json
```

Base URL: `https://<host>:9443`

## System

### Get System Version
```
GET /api/open/system
```
Returns SafeLine version and system information.

### Get Users
```
GET /api/open/users
```
Returns list of SafeLine admin users.

## Events and Logs

### Get Attack Events
```
GET /api/open/events?page=1&page_size=20
```
Returns paginated list of detected attack events.

Query parameters:
- `page`: Page number (default: 1)
- `page_size`: Results per page (default: 20)

### Get ACL Block Records
```
GET /api/open/records/acl?page=1&page_size=20
```
Returns records of requests blocked by ACL rules.

### Get Challenge Records (Bot Detection)
```
GET /api/open/records/challenge?page=1&page_size=20
```
Returns records of human verification challenges.

### Get Auth Defense Records
```
GET /api/open/records/auth_defense?page=1&page_size=20
```
Returns authentication defense activity logs.

## Statistics

### Real-Time QPS
```
GET /api/stat/qps
```
Returns current queries per second.

### Daily Access Statistics
```
GET /api/dashboard/requests
```
Returns daily request count over time.

### Daily Interception Statistics
```
GET /api/dashboard/intercepts
```
Returns daily blocked/intercepted request counts.

### Same-Day Access Statistics
```
GET /api/stat/basic/access
```
Returns today's access breakdown.

### Error Rate Statistics
```
GET /api/dashboard/counts
```
Returns 4xx and 5xx error counts.

### Geographic Access Map
```
GET /api/dashboard/map/counts
```
Returns access statistics by geographic region.

## Site Management

### Add Protected Site
```
POST /api/open/site
```
Body:
```json
{
    "ports": ["80"],
    "server_names": ["example.com"],
    "upstreams": ["http://backend:8080"],
    "load_balance": {
        "balance_type": 1
    },
    "comment": "My web application"
}
```

## Protection Configuration

### Get/Set Protection Mode
```
GET /api/open/global/mode
PUT /api/open/global/mode
```
Set the global protection mode: block, detect, or off.

### Custom Policy Rules
```
GET /api/open/policy?page=1&page_size=20&action=-1
POST /api/open/policy
```
Manage custom WAF rules and policies.

### Enhanced Rules (Skynet)
```
GET /api/open/skynet/rule
POST /api/open/skynet/rule
```
Manage enhanced detection rules.

### Rate Limiting (ACL)
```
GET /api/open/global/acl
POST /api/open/global/acl
```
Configure rate limiting rules per IP/path/time window.

### IP Groups
```
GET /api/open/ipgroup?top=20
POST /api/open/ipgroup
```
Manage IP blacklists, whitelists, and groups.
