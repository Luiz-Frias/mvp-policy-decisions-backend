# DEPLOYMENT_PLAN.md

## Executive Summary

This deployment plan outlines the systematic approach for deploying the MVP Policy Decision Backend following the SAGE (Supervisor Agent-Generated Engineering) system principles. The plan ensures enterprise-grade deployment with peak excellence standards, defensive programming patterns, and comprehensive monitoring.

## Current Status

### CLI Tools Availability

- ✅ Railway CLI: v4.5.4 (requires authentication)
- ✅ Doppler CLI: v3.75.1
- ✅ Snyk CLI: v1.1297.3
- ✅ GitHub CLI: v2.74.2
- ✅ Vercel CLI: v44.2.7

### Required Actions Before Wave 1

1. Railway authentication: `railway login`
2. GitHub authentication verification: `gh auth status`
3. Vercel authentication: `vercel login`
4. Doppler setup: `doppler login`

## Infrastructure Architecture

### Primary Components

```
┌─────────────────────────────────────────────────────────────┐
│                        Production Stack                      │
├─────────────────────────────────────────────────────────────┤
│  Frontend (Vercel)          │  Backend (Railway)            │
│  - Next.js 14               │  - FastAPI + Python 3.11.7    │
│  - React Server Components  │  - PostgreSQL 15              │
│  - Tailwind CSS             │  - Redis 7                    │
│  - shadcn/ui                │  - Asyncpg connection pool    │
└─────────────────────────────────────────────────────────────┘
```

### Database Architecture

- **PostgreSQL 15** (Railway managed)
  - JSONB for flexible demo schemas
  - Extensions: uuid-ossp, pg_trgm, btree_gin
  - Connection pooling: 5-20 connections
  - Automated backups

- **Redis 7** (Railway managed)
  - API response caching
  - Session storage
  - Real-time metrics
  - WebSocket pub/sub

## Deployment Phases

### Phase 1: Infrastructure Provisioning (Pre-Wave 1)

1. **Railway Backend Infrastructure**
   - Create Railway project
   - Provision PostgreSQL database
   - Provision Redis cache
   - Configure environment variables
   - Set up custom domain (optional)

2. **Vercel Frontend Infrastructure**
   - Create Vercel project
   - Configure build settings
   - Set environment variables
   - Configure preview deployments

3. **Security & Monitoring Setup**
   - Configure Doppler for secrets management
   - Set up Snyk for vulnerability scanning
   - Configure Sentry for error tracking
   - Set up GitHub Actions workflows

### Phase 2: Wave 1 Implementation (Foundation - 80% Build)

**Objective**: Create working skeleton of entire system

**Components to Deploy**:

1. Database schema initialization
2. Core API routes structure
3. Basic UI components
4. Authentication scaffolding
5. CI/CD pipeline setup

**Deployment Commands**:

```bash
# Database migrations
railway run alembic upgrade head

# Deploy backend
railway up

# Deploy frontend
vercel --prod
```

### Phase 3: Wave 2 Implementation (Features - 90% Build)

**Objective**: Implement business logic and workflows

**Components**:

1. Policy calculation engine
2. Business rule implementations
3. API integrations
4. Complex UI interactions
5. Real-time features via WebSocket

### Phase 4: Wave 3 Implementation (Polish - 100% Build)

**Objective**: Production hardening and optimization

**Components**:

1. Performance optimization
2. Security hardening
3. Monitoring dashboards
4. Load testing results
5. Documentation completion

## CI/CD Pipeline Configuration

### GitHub Actions Workflow

```yaml
name: Deploy

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11.7"
      - name: Install dependencies
        run: |
          pip install uv
          uv sync --dev
      - name: Run tests
        run: |
          uv run pytest --cov
          uv run mypy src --strict
      - name: Security scan
        run: |
          uv run bandit -r src
          uv run safety check
          uv run pip-audit

  deploy-backend:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Railway
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
        run: |
          npm install -g @railway/cli
          railway up

  deploy-frontend:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Vercel
        env:
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
        run: |
          npm install -g vercel
          vercel --prod --token=$VERCEL_TOKEN
```

## Environment Variables Management

### Required Variables (via Doppler)

```bash
# Backend (Railway)
DATABASE_URL          # PostgreSQL connection string
REDIS_URL            # Redis connection string
SECRET_KEY           # Application secret
JWT_SECRET           # JWT signing secret
OPENAI_API_KEY       # OpenAI API key
SENTRY_DSN           # Error tracking
API_CORS_ORIGINS     # Allowed CORS origins

# Frontend (Vercel)
NEXT_PUBLIC_API_URL  # Backend API URL
NEXT_PUBLIC_WS_URL   # WebSocket URL
NEXT_PUBLIC_SENTRY_DSN # Client-side error tracking
```

### Doppler Setup

```bash
# Install and authenticate
doppler login

# Setup project
doppler setup

# Import existing .env
doppler secrets upload .env.local

# Sync with Railway
doppler run -- railway up
```

## Performance Monitoring

### Key Metrics to Track

1. **API Response Times**
   - Target: <100ms for critical paths
   - Monitor: p50, p95, p99 percentiles

2. **Database Performance**
   - Query execution time
   - Connection pool utilization
   - Slow query log analysis

3. **Memory Usage**
   - Backend: <500MB baseline
   - Function allocations: <1MB
   - No memory leaks >1MB/1000 iterations

4. **Error Rates**
   - Target: <0.1% error rate
   - Alert thresholds configured

## Security Hardening

### Pre-Deployment Checklist

- [ ] All secrets in Doppler/environment variables
- [ ] HTTPS/SSL certificates configured
- [ ] CORS properly configured
- [ ] Rate limiting implemented
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention verified
- [ ] XSS protection enabled
- [ ] CSRF tokens implemented
- [ ] Security headers configured

### Security Scanning

```bash
# Backend security scan
snyk test
bandit -r src
safety check
pip-audit

# Frontend security scan
cd frontend && snyk test
```

## Rollback Strategy

### Automated Rollback Triggers

- Failed health checks (3 consecutive failures)
- Error rate >5%
- Response time >500ms (p95)
- Memory usage >1GB

### Manual Rollback Commands

```bash
# Railway rollback
railway rollback

# Vercel rollback
vercel rollback
```

## Post-Deployment Validation

### Health Checks

```bash
# Backend health
curl https://api.yourdomain.com/health

# Database connectivity
railway run python scripts/check_db.py

# Redis connectivity
railway run python scripts/check_redis.py
```

### Performance Validation

```bash
# Run load tests
uv run locust -f tests/load/locustfile.py

# Check memory usage
railway logs --filter="memory"

# Verify benchmarks
uv run pytest --benchmark-only
```

## Demo-Specific Features

### Quick Reset Capability

```bash
# Reset demo data
railway run python scripts/reset_demo_data.py

# Clear cache
railway run python scripts/clear_cache.py
```

### Demo Optimizations

1. Pre-warmed cache for instant responses
2. Mock fallbacks for external services
3. Simplified authentication for demos
4. Sample data generators

## Troubleshooting Guide

### Common Issues and Solutions

1. **Railway Authentication Failed**

   ```bash
   railway login
   railway link
   ```

2. **Database Connection Issues**

   ```bash
   # Check DATABASE_URL
   railway variables

   # Test connection
   railway run python -c "import asyncpg; print('Connected')"
   ```

3. **Deployment Failures**

   ```bash
   # Check logs
   railway logs

   # Check build logs
   railway logs --build
   ```

4. **Performance Issues**
   - Check connection pool exhaustion
   - Review slow query logs
   - Verify Redis cache hit rates
   - Check for memory leaks

## Evolution Path

### Phase 1 (Current): MVP Demo

- Python/TypeScript stack
- Railway/Vercel hosting
- Basic monitoring

### Phase 2: Production Readiness

- Add Rust modules for performance
- Implement advanced caching
- Enhanced security measures
- Multi-region deployment

### Phase 3: Enterprise Scale

- Kubernetes deployment
- AWS/GCP migration
- Advanced observability
- Compliance certifications

## Next Steps

1. **Immediate Actions Required**:
   - Authenticate Railway CLI: `railway login`
   - Verify GitHub CLI auth: `gh auth status`
   - Set up Doppler: `doppler login && doppler setup`

2. **Pre-Wave 1 Setup**:
   - Create Railway project and services
   - Configure all environment variables
   - Set up CI/CD secrets
   - Initialize database schema

3. **Wave 1 Readiness**:
   - All infrastructure provisioned
   - Environment variables configured
   - CI/CD pipeline ready
   - Monitoring configured

## Conclusion

This deployment plan provides a comprehensive roadmap for deploying the MVP Policy Decision Backend with enterprise-grade standards. Following this plan ensures:

- ✅ Systematic, reproducible deployments
- ✅ Security-first approach
- ✅ Performance monitoring from day one
- ✅ Clear evolution path to production
- ✅ Compliance with SAGE principles
- ✅ Adherence to master ruleset standards

The deployment architecture is designed to start simple for the demo while providing a clear path to enterprise-scale production deployment.
