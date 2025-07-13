# OAuth2 Developer Guide

## Overview

This guide provides comprehensive documentation for integrating with the MVP Policy Decision Backend OAuth2 authorization server. Our implementation follows RFC 6749 with additional security enhancements and support for modern OAuth2 flows.

## Quick Start

### 1. Register Your Application

First, register your application with an administrator to get your client credentials:

```bash
# Example client registration request
curl -X POST https://api.example.com/api/v1/admin/oauth2/clients \
  -H "Authorization: Bearer ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "My Insurance App",
    "client_type": "confidential",
    "allowed_grant_types": ["authorization_code", "refresh_token"],
    "allowed_scopes": ["quote:read", "quote:write", "policy:read"],
    "redirect_uris": ["https://myapp.com/auth/callback"],
    "description": "Insurance application for customer quotes"
  }'
```

### 2. Authorization Code Flow (Recommended)

For web applications, use the authorization code flow with PKCE:

```javascript
// Step 1: Generate PKCE challenge
const codeVerifier = generateRandomString(128);
const codeChallenge = await sha256(codeVerifier);

// Step 2: Redirect user to authorization endpoint
const authUrl = new URL("https://api.example.com/api/v1/oauth2/authorize");
authUrl.searchParams.append("response_type", "code");
authUrl.searchParams.append("client_id", "YOUR_CLIENT_ID");
authUrl.searchParams.append("redirect_uri", "https://myapp.com/auth/callback");
authUrl.searchParams.append("scope", "quote:read quote:write");
authUrl.searchParams.append("state", "random_state_value");
authUrl.searchParams.append("code_challenge", codeChallenge);
authUrl.searchParams.append("code_challenge_method", "S256");

window.location.href = authUrl.toString();

// Step 3: Exchange authorization code for tokens
const tokenResponse = await fetch("https://api.example.com/api/v1/oauth2/token", {
  method: "POST",
  headers: {
    "Content-Type": "application/x-www-form-urlencoded",
  },
  body: new URLSearchParams({
    grant_type: "authorization_code",
    client_id: "YOUR_CLIENT_ID",
    client_secret: "YOUR_CLIENT_SECRET",
    code: "AUTHORIZATION_CODE",
    redirect_uri: "https://myapp.com/auth/callback",
    code_verifier: codeVerifier,
  }),
});

const tokens = await tokenResponse.json();
```

### 3. Client Credentials Flow

For server-to-server communication:

```python
import requests

def get_client_credentials_token():
    """Get access token using client credentials flow."""
    response = requests.post(
        'https://api.example.com/api/v1/oauth2/token',
        data={
            'grant_type': 'client_credentials',
            'client_id': 'YOUR_CLIENT_ID',
            'client_secret': 'YOUR_CLIENT_SECRET',
            'scope': 'analytics:read'
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )

    if response.status_code == 200:
        return response.json()['access_token']
    else:
        raise Exception(f"Token request failed: {response.text}")
```

## Authentication Methods

### Bearer Token Authentication

Include the access token in the Authorization header:

```bash
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  https://api.example.com/api/v1/quotes
```

### API Key Authentication

For simplified integration, use API keys:

```bash
curl -H "Authorization: Bearer pd_YOUR_API_KEY" \
  https://api.example.com/api/v1/quotes
```

## Scopes and Permissions

### Available Scopes

| Scope              | Description                     | Use Case                     |
| ------------------ | ------------------------------- | ---------------------------- |
| `user:read`        | Read user profile information   | User account displays        |
| `user:write`       | Update user profile information | Account management           |
| `quote:read`       | Read quote information          | Quote viewing and listing    |
| `quote:write`      | Create and update quotes        | Quote generation and editing |
| `quote:calculate`  | Calculate quote pricing         | Real-time pricing updates    |
| `quote:convert`    | Convert quotes to policies      | Policy binding               |
| `policy:read`      | Read policy information         | Policy viewing               |
| `policy:write`     | Create and update policies      | Policy management            |
| `policy:cancel`    | Cancel policies                 | Policy cancellation          |
| `claim:read`       | Read claim information          | Claim viewing                |
| `claim:write`      | Create and update claims        | Claim filing                 |
| `claim:approve`    | Approve or deny claims          | Claims processing            |
| `analytics:read`   | Read analytics data             | Reporting and dashboards     |
| `analytics:export` | Export analytics data           | Data export                  |
| `admin:users`      | Manage users                    | User administration          |
| `admin:clients`    | Manage OAuth2 clients           | Developer tools              |
| `admin:system`     | System administration           | Full system access           |

### Scope Hierarchies

Some scopes automatically include others:

- `user:write` includes `user:read`
- `quote:write` includes `quote:read`
- `quote:convert` includes `quote:read` and `policy:write`
- `admin:system` includes `admin:users` and `admin:clients`

## Security Best Practices

### PKCE (Proof Key for Code Exchange)

Always use PKCE for public clients and single-page applications:

```javascript
// Generate code verifier
function generateCodeVerifier() {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return btoa(String.fromCharCode.apply(null, array))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=/g, "");
}

// Generate code challenge
async function generateCodeChallenge(verifier) {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return btoa(String.fromCharCode.apply(null, new Uint8Array(digest)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=/g, "");
}
```

### Token Storage

**Web Applications:**

- Store tokens in secure, HttpOnly cookies
- Use short-lived access tokens (1 hour)
- Implement proper CSRF protection

**Mobile Applications:**

- Use platform keychain/keystore
- Implement biometric protection when available
- Use refresh token rotation

**Single-Page Applications:**

- Store tokens in memory only
- Use short-lived tokens (15 minutes)
- Implement automatic token renewal

### Error Handling

Handle OAuth2 errors gracefully:

```javascript
function handleOAuth2Error(error) {
  switch (error.error) {
    case "invalid_client":
      // Redirect to registration or contact admin
      break;
    case "invalid_scope":
      // Request fewer scopes or show scope explanation
      break;
    case "rate_limit_exceeded":
      // Implement exponential backoff
      break;
    case "access_denied":
      // User declined authorization
      break;
    default:
      // Log error and show user-friendly message
      console.error("OAuth2 error:", error);
  }
}
```

## API Integration Examples

### Creating a Quote

```python
import requests

class InsuranceAPIClient:
    def __init__(self, access_token):
        self.access_token = access_token
        self.base_url = 'https://api.example.com/api/v1'

    def create_quote(self, quote_data):
        """Create a new insurance quote."""
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

        response = requests.post(
            f'{self.base_url}/quotes',
            json=quote_data,
            headers=headers
        )

        if response.status_code == 401:
            # Token expired, refresh it
            self.refresh_token()
            headers['Authorization'] = f'Bearer {self.access_token}'
            response = requests.post(
                f'{self.base_url}/quotes',
                json=quote_data,
                headers=headers
            )

        return response.json()
```

### Real-time Quote Updates

```javascript
// WebSocket connection for real-time updates
const ws = new WebSocket(`wss://api.example.com/ws/quotes?token=${accessToken}`);

ws.onmessage = function (event) {
  const update = JSON.parse(event.data);
  if (update.type === "quote_updated") {
    updateQuoteDisplay(update.data);
  }
};

// Update quote with real-time pricing
async function updateQuoteCoverage(quoteId, coverage) {
  const response = await fetch(`/api/v1/quotes/${quoteId}/calculate`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ coverage }),
  });

  // Real-time update will come via WebSocket
  return response.json();
}
```

## Rate Limiting

### Default Limits

| Operation              | Limit      | Window     |
| ---------------------- | ---------- | ---------- |
| Token requests         | 300/minute | Per client |
| Authorization requests | 100/minute | Per client |
| Token introspection    | 600/minute | Per client |
| API calls              | 1000/hour  | Per client |

### Handling Rate Limits

```python
import time
import random

def api_call_with_retry(func, max_retries=3):
    """Make API call with exponential backoff on rate limit."""
    for attempt in range(max_retries):
        try:
            return func()
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise

            # Exponential backoff with jitter
            delay = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(delay)

    raise Exception("Max retries exceeded")
```

## Testing and Development

### Development Environment

Use the demo mode for testing:

```bash
# Set demo mode
export DEMO_MODE=true

# Test endpoints without authentication
curl https://api.example.com/api/v1/quotes
```

### Testing OAuth2 Flows

Test the complete OAuth2 flow:

```bash
# Get server metadata
curl https://api.example.com/api/v1/oauth2/.well-known/oauth-authorization-server

# Test client credentials flow
curl -X POST https://api.example.com/api/v1/oauth2/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=test_client&client_secret=test_secret&scope=quote:read"

# Test token introspection
curl -X POST https://api.example.com/api/v1/oauth2/introspect \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "token=YOUR_ACCESS_TOKEN"
```

### Postman Collection

Import our Postman collection for easy testing:

```json
{
  "info": {
    "name": "MVP Policy Decision Backend OAuth2",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "auth": {
    "type": "oauth2",
    "oauth2": [
      {
        "key": "tokenUrl",
        "value": "https://api.example.com/api/v1/oauth2/token"
      },
      {
        "key": "authUrl",
        "value": "https://api.example.com/api/v1/oauth2/authorize"
      }
    ]
  }
}
```

## Troubleshooting

### Common Issues

**Invalid Client Error:**

```
{
  "error": "invalid_client",
  "error_description": "Client authentication failed"
}
```

Solution: Verify client_id and client_secret are correct.

**Invalid Scope Error:**

```
{
  "error": "invalid_scope",
  "error_description": "Scopes not allowed: admin:system"
}
```

Solution: Request only scopes your client is authorized for.

**Rate Limit Exceeded:**

```
{
  "error": "rate_limit_exceeded",
  "error_description": "Rate limit exceeded for token_request: 301/300 per minute"
}
```

Solution: Implement exponential backoff and respect rate limits.

### Debug Mode

Enable debug logging for troubleshooting:

```python
import logging

# Enable OAuth2 debug logging
logging.getLogger('oauth2').setLevel(logging.DEBUG)

# Or set environment variable
import os
os.environ['OAUTH2_DEBUG'] = 'true'
```

### Health Checks

Monitor OAuth2 server health:

```bash
curl https://api.example.com/api/v1/oauth2/health
```

Expected response:

```json
{
  "status": "healthy",
  "active_tokens": 1234,
  "active_clients": 56,
  "tokens_issued_last_hour": 89,
  "server_time": "2025-07-05T12:00:00Z"
}
```

## Support and Resources

### Documentation

- [OAuth2 RFC 6749](https://tools.ietf.org/html/rfc6749)
- [PKCE RFC 7636](https://tools.ietf.org/html/rfc7636)
- [Token Introspection RFC 7662](https://tools.ietf.org/html/rfc7662)

### Code Examples

- [GitHub Repository](https://github.com/example/oauth2-examples)
- [Sample Applications](https://github.com/example/sample-apps)

### Getting Help

- Email: developers@example.com
- Slack: #oauth2-support
- Documentation: https://docs.example.com/oauth2

---

_This documentation is automatically updated with each release. Last updated: 2025-07-05_
