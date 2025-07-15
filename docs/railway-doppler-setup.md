# Railway + Doppler Integration Setup

## Overview

Railway has native Doppler integration, which means we don't need to install Doppler CLI in our containers or use `doppler run` commands. Instead, Doppler automatically syncs secrets to Railway environment variables.

## Setup Steps

### 1. Prerequisites

- Railway account with a project created
- Doppler account with secrets configured
- Railway Priority Boarding beta access (for API access)

### 2. Create Railway API Token

1. Go to [Railway Token Creation](https://railway.app/account/tokens)
2. Join Priority Boarding beta if not already enrolled
3. Create a new token (NOT a project-specific token)

### 3. Configure Doppler Integration

1. In Doppler, go to Integrations
2. Select Railway
3. Authenticate with your Railway API token
4. Select:
   - Railway Project: `mvp-policy-decision-backend`
   - Environment: `production` 
   - Service: `policy-core-api` or "Shared across all services"
   - Doppler Config: `prd`
   - Auto-redeploy: Enable for automatic updates

### 4. Import Behavior

Choose how to handle existing Railway variables:
- **Prefer Doppler**: Use Doppler values for any conflicts
- **Prefer Railway**: Keep existing Railway values
- **Import from Railway**: Import Railway vars to Doppler first

## Environment Variables

Since Doppler syncs directly to Railway, our app can use standard environment variables:

```python
# No need for doppler run - just use env vars directly
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL")
JWT_SECRET = os.getenv("JWT_SECRET")
```

## Deployment Configuration

### railway.json
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3,
    "healthcheckPath": "/api/v1/health/live",
    "healthcheckTimeout": 10
  }
}
```

### Required Environment Variables

These should be configured in Doppler and will sync to Railway:

```env
# Database (Railway PostgreSQL)
DATABASE_URL=postgresql://...
DATABASE_HOST=...
DATABASE_PORT=5432
DATABASE_NAME=...
DATABASE_USER=...
DATABASE_PASSWORD=...

# Redis (Railway Redis)
REDIS_URL=redis://...

# Application
API_HOST=0.0.0.0
API_PORT=${{PORT}}  # Railway provides PORT
API_ENV=production
LOG_LEVEL=info

# Secrets (from Doppler)
JWT_SECRET=...
ENCRYPTION_KEY=...
SESSION_SECRET=...

# Feature Flags
DEMO_MODE=true
UVLOOP_ENABLED=true
```

## PgBouncer on Railway

Since Railway runs containers, we can include PgBouncer in our deployment:

1. Use a multi-process supervisor (like supervisord)
2. Or run PgBouncer as a sidecar service
3. Or use Railway's database proxy features

## Benefits

- No Doppler CLI needed in production containers
- Automatic secret rotation
- Git-style secret versioning
- Compliance audit trails
- Zero-downtime secret updates