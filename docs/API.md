# API Documentation

## Overview

The MVP Policy Decision Backend provides a RESTful API for policy management, quote generation, and underwriting operations in the P&C insurance domain. Built with FastAPI, it offers automatic OpenAPI documentation, type safety, and high performance.

## Base URL

```
Development: http://localhost:8000
Production: https://api.mvp-policy-backend.com
```

## Authentication

All API endpoints require authentication using JWT tokens.

```http
Authorization: Bearer <jwt-token>
```

### Obtaining a Token

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "secure-password"
}
```

Response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

## API Versioning

The API uses URL-based versioning. Current version: `v1`

```
/api/v1/...
```

## Common Response Formats

### Success Response

```json
{
  "status": "success",
  "data": {
    // Response data
  },
  "meta": {
    "timestamp": "2024-12-27T10:00:00Z",
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### Error Response

```json
{
  "status": "error",
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [
      {
        "field": "premium",
        "message": "Premium must be greater than 0"
      }
    ]
  },
  "meta": {
    "timestamp": "2024-12-27T10:00:00Z",
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

## Endpoints

### Policies

#### Create Policy

```http
POST /api/v1/policies
Content-Type: application/json

{
  "policy_type": "auto",
  "effective_date": "2024-01-01",
  "coverage": {
    "liability": 500000,
    "collision": 50000,
    "comprehensive": 50000
  },
  "insured": {
    "first_name": "John",
    "last_name": "Doe",
    "date_of_birth": "1980-01-01",
    "drivers_license": "D123456789"
  },
  "vehicle": {
    "make": "Toyota",
    "model": "Camry",
    "year": 2022,
    "vin": "1HGBH41JXMN109186"
  }
}
```

Response:

```json
{
  "status": "success",
  "data": {
    "policy_id": "550e8400-e29b-41d4-a716-446655440000",
    "policy_number": "AUTO-2024-000001",
    "status": "active",
    "premium": 1200.0,
    "effective_date": "2024-01-01",
    "expiration_date": "2025-01-01"
  }
}
```

#### Get Policy

```http
GET /api/v1/policies/{policy_id}
```

Response:

```json
{
  "status": "success",
  "data": {
    "policy_id": "550e8400-e29b-41d4-a716-446655440000",
    "policy_number": "AUTO-2024-000001",
    "status": "active",
    "policy_type": "auto",
    "premium": 1200.0,
    "effective_date": "2024-01-01",
    "expiration_date": "2025-01-01",
    "coverage": {
      "liability": 500000,
      "collision": 50000,
      "comprehensive": 50000
    },
    "insured": {
      "first_name": "John",
      "last_name": "Doe",
      "date_of_birth": "1980-01-01"
    }
  }
}
```

#### List Policies

```http
GET /api/v1/policies?page=1&limit=20&status=active
```

Query Parameters:

- `page` (integer): Page number (default: 1)
- `limit` (integer): Items per page (default: 20, max: 100)
- `status` (string): Filter by status (active, expired, cancelled)
- `policy_type` (string): Filter by type (auto, home, umbrella)

Response:

```json
{
  "status": "success",
  "data": {
    "policies": [
      {
        "policy_id": "550e8400-e29b-41d4-a716-446655440000",
        "policy_number": "AUTO-2024-000001",
        "status": "active",
        "premium": 1200.0
      }
    ],
    "pagination": {
      "page": 1,
      "limit": 20,
      "total": 150,
      "pages": 8
    }
  }
}
```

#### Update Policy

```http
PUT /api/v1/policies/{policy_id}
Content-Type: application/json

{
  "coverage": {
    "liability": 1000000,
    "collision": 50000,
    "comprehensive": 50000
  }
}
```

#### Cancel Policy

```http
POST /api/v1/policies/{policy_id}/cancel
Content-Type: application/json

{
  "reason": "non_payment",
  "effective_date": "2024-12-31"
}
```

### Quotes

#### Generate Quote

```http
POST /api/v1/quotes
Content-Type: application/json

{
  "policy_type": "auto",
  "state": "CA",
  "coverage_requested": {
    "liability": 500000,
    "collision": 50000,
    "comprehensive": 50000
  },
  "driver_info": {
    "age": 35,
    "driving_experience": 15,
    "violations": 0,
    "claims": 0
  },
  "vehicle_info": {
    "make": "Toyota",
    "model": "Camry",
    "year": 2022,
    "safety_features": ["abs", "airbags", "backup_camera"]
  }
}
```

Response:

```json
{
  "status": "success",
  "data": {
    "quote_id": "650e8400-e29b-41d4-a716-446655440000",
    "quote_number": "Q-2024-000001",
    "premium": {
      "annual": 1200.0,
      "monthly": 100.0
    },
    "coverage": {
      "liability": 500000,
      "collision": 50000,
      "comprehensive": 50000
    },
    "discounts_applied": [
      {
        "type": "safe_driver",
        "amount": 120.0
      },
      {
        "type": "safety_features",
        "amount": 80.0
      }
    ],
    "valid_until": "2024-01-15T00:00:00Z"
  }
}
```

#### Get Quote

```http
GET /api/v1/quotes/{quote_id}
```

#### Convert Quote to Policy

```http
POST /api/v1/quotes/{quote_id}/bind
Content-Type: application/json

{
  "payment_method": "credit_card",
  "payment_schedule": "monthly",
  "effective_date": "2024-01-01"
}
```

### Rates

#### Get Rate Tables

```http
GET /api/v1/rates?state=CA&policy_type=auto&effective_date=2024-01-01
```

Response:

```json
{
  "status": "success",
  "data": {
    "rate_table_id": "750e8400-e29b-41d4-a716-446655440000",
    "state": "CA",
    "policy_type": "auto",
    "effective_date": "2024-01-01",
    "base_rates": {
      "liability": {
        "per_100k": 120.0
      },
      "collision": {
        "per_10k": 80.0
      },
      "comprehensive": {
        "per_10k": 60.0
      }
    },
    "factors": {
      "age": {
        "16-25": 1.5,
        "26-35": 1.1,
        "36-55": 1.0,
        "56+": 1.2
      },
      "driving_experience": {
        "0-2": 1.3,
        "3-5": 1.1,
        "6+": 1.0
      }
    }
  }
}
```

#### Calculate Premium

```http
POST /api/v1/rates/calculate
Content-Type: application/json

{
  "state": "CA",
  "policy_type": "auto",
  "coverage": {
    "liability": 500000,
    "collision": 50000,
    "comprehensive": 50000
  },
  "risk_factors": {
    "driver_age": 35,
    "driving_experience": 15,
    "credit_score": 750,
    "claims_history": 0
  }
}
```

### Underwriting

#### Risk Assessment

```http
POST /api/v1/underwriting/assess
Content-Type: application/json

{
  "applicant": {
    "age": 35,
    "occupation": "software_engineer",
    "credit_score": 750,
    "claims_history": []
  },
  "property": {
    "type": "single_family",
    "age": 10,
    "location": {
      "zip": "90210",
      "flood_zone": false,
      "fire_risk": "low"
    }
  }
}
```

Response:

```json
{
  "status": "success",
  "data": {
    "risk_score": 85,
    "risk_level": "low",
    "ai_confidence": 0.92,
    "factors": [
      {
        "factor": "credit_score",
        "impact": "positive",
        "weight": 0.25
      },
      {
        "factor": "claims_history",
        "impact": "positive",
        "weight": 0.3
      }
    ],
    "recommendations": [
      {
        "action": "approve",
        "conditions": []
      }
    ]
  }
}
```

#### Get Underwriting Guidelines

```http
GET /api/v1/underwriting/guidelines?state=CA&policy_type=auto
```

### Documents

#### Generate Policy Document

```http
POST /api/v1/documents/generate
Content-Type: application/json

{
  "document_type": "policy_declaration",
  "policy_id": "550e8400-e29b-41d4-a716-446655440000",
  "format": "pdf"
}
```

Response:

```json
{
  "status": "success",
  "data": {
    "document_id": "850e8400-e29b-41d4-a716-446655440000",
    "download_url": "/api/v1/documents/850e8400-e29b-41d4-a716-446655440000/download",
    "expires_at": "2024-12-28T10:00:00Z"
  }
}
```

#### Download Document

```http
GET /api/v1/documents/{document_id}/download
```

Response: Binary PDF file

## Webhooks

The API supports webhooks for asynchronous events:

### Policy Events

```json
{
  "event": "policy.created",
  "data": {
    "policy_id": "550e8400-e29b-41d4-a716-446655440000",
    "policy_number": "AUTO-2024-000001"
  },
  "timestamp": "2024-12-27T10:00:00Z"
}
```

### Supported Events

- `policy.created`
- `policy.updated`
- `policy.cancelled`
- `quote.generated`
- `quote.expired`
- `claim.filed`
- `payment.processed`
- `document.generated`

## Rate Limiting

API endpoints are rate-limited to ensure fair usage:

- **Anonymous**: 10 requests/minute
- **Authenticated**: 100 requests/minute
- **Premium**: 1000 requests/minute

Rate limit headers:

```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1703674800
```

## Error Codes

| Code                      | Description                       |
| ------------------------- | --------------------------------- |
| `VALIDATION_ERROR`        | Invalid input data                |
| `AUTHENTICATION_REQUIRED` | Missing or invalid authentication |
| `PERMISSION_DENIED`       | Insufficient permissions          |
| `RESOURCE_NOT_FOUND`      | Requested resource not found      |
| `DUPLICATE_RESOURCE`      | Resource already exists           |
| `RATE_LIMIT_EXCEEDED`     | Too many requests                 |
| `INTERNAL_ERROR`          | Internal server error             |
| `SERVICE_UNAVAILABLE`     | Service temporarily unavailable   |

## SDK Examples

### Python

```python
from pd_prime_sdk import PolicyClient

client = PolicyClient(
    base_url="https://api.mvp-policy-backend.com",
    api_key="your-api-key"
)

# Create a policy
policy = client.policies.create(
    policy_type="auto",
    effective_date="2024-01-01",
    coverage={
        "liability": 500000,
        "collision": 50000
    }
)

print(f"Policy created: {policy.policy_number}")
```

### JavaScript/TypeScript

```typescript
import { PolicyClient } from "@mvp-policy/sdk";

const client = new PolicyClient({
  baseUrl: "https://api.mvp-policy-backend.com",
  apiKey: "your-api-key",
});

// Generate a quote
const quote = await client.quotes.generate({
  policyType: "auto",
  state: "CA",
  coverageRequested: {
    liability: 500000,
    collision: 50000,
  },
});

console.log(`Premium: $${quote.premium.annual}`);
```

## Testing

### Sandbox Environment

```
https://sandbox.api.mvp-policy-backend.com
```

Test credentials:

- Username: `test@example.com`
- Password: `test123`

### Postman Collection

Download our [Postman collection](https://api.mvp-policy-backend.com/postman/collection.json) for easy API testing.

## OpenAPI Specification

The complete OpenAPI 3.0 specification is available at:

```
https://api.mvp-policy-backend.com/openapi.json
```

Interactive documentation:

```
https://api.mvp-policy-backend.com/docs
```
