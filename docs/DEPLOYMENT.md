# Deployment Guide

## Overview

This guide covers deployment strategies for the MVP Policy Decision Backend, including containerization, cloud deployment options, and production configurations.

## Deployment Architecture

```mermaid
graph TB
    LB[Load Balancer]
    API1[API Server 1]
    API2[API Server 2]
    API3[API Server N]
    DB[(PostgreSQL Primary)]
    DBR[(PostgreSQL Replica)]
    REDIS[(Redis Cluster)]
    S3[Object Storage]

    LB --> API1
    LB --> API2
    LB --> API3

    API1 --> DB
    API1 --> REDIS
    API1 --> S3

    API2 --> DB
    API2 --> REDIS
    API2 --> S3

    API3 --> DBR
    API3 --> REDIS
    API3 --> S3

    DB -.-> DBR
```

## Container Strategy

### Production Dockerfile

```dockerfile
# Multi-stage build for optimal size and security
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 appuser

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src:$PYTHONPATH"
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "src.pd_prime_demo.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose for Production

```yaml
version: "3.8"

services:
  api:
    build:
      context: .
      dockerfile: docker/Dockerfile
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:${DB_PASSWORD}@db:5432/policy_db
      - REDIS_URL=redis://redis:6379/0
      - APP_ENV=production
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: "1"
          memory: 1G
        reservations:
          cpus: "0.5"
          memory: 512M
    restart: unless-stopped

  db:
    image: postgres:14-alpine
    environment:
      - POSTGRES_DB=policy_db
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - api

volumes:
  postgres_data:
  redis_data:
```

## Cloud Deployment Options

### Railway Deployment

Railway provides simple deployment with automatic SSL and scaling.

#### Setup

1. **Install Railway CLI**

   ```bash
   npm install -g @railway/cli
   ```

2. **Login to Railway**

   ```bash
   railway login
   ```

3. **Initialize Project**

   ```bash
   railway init
   ```

4. **Configure Environment**

   ```bash
   railway variables set DATABASE_URL="postgresql://..."
   railway variables set REDIS_URL="redis://..."
   railway variables set SECRET_KEY="..."
   ```

5. **Deploy**
   ```bash
   railway up
   ```

#### Railway Configuration

`railway.toml`:

```toml
[build]
builder = "dockerfile"
dockerfilePath = "docker/Dockerfile"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "always"

[[services]]
name = "api"
port = 8000

[services.scaling]
minInstances = 2
maxInstances = 10
```

### AWS Deployment

#### ECS with Fargate

1. **Build and Push Image**

   ```bash
   # Build image
   docker build -t mvp-policy-backend .

   # Tag for ECR
   docker tag mvp-policy-backend:latest $AWS_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/mvp-policy-backend:latest

   # Push to ECR
   aws ecr get-login-password | docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
   docker push $AWS_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/mvp-policy-backend:latest
   ```

2. **Task Definition**
   ```json
   {
     "family": "mvp-policy-backend",
     "networkMode": "awsvpc",
     "requiresCompatibilities": ["FARGATE"],
     "cpu": "1024",
     "memory": "2048",
     "containerDefinitions": [
       {
         "name": "api",
         "image": "${AWS_ACCOUNT}.dkr.ecr.us-east-1.amazonaws.com/mvp-policy-backend:latest",
         "portMappings": [
           {
             "containerPort": 8000,
             "protocol": "tcp"
           }
         ],
         "environment": [
           {
             "name": "APP_ENV",
             "value": "production"
           }
         ],
         "secrets": [
           {
             "name": "DATABASE_URL",
             "valueFrom": "arn:aws:secretsmanager:us-east-1:${AWS_ACCOUNT}:secret:database-url"
           }
         ],
         "healthCheck": {
           "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
           "interval": 30,
           "timeout": 5,
           "retries": 3
         },
         "logConfiguration": {
           "logDriver": "awslogs",
           "options": {
             "awslogs-group": "/ecs/mvp-policy-backend",
             "awslogs-region": "us-east-1",
             "awslogs-stream-prefix": "ecs"
           }
         }
       }
     ]
   }
   ```

#### Elastic Beanstalk

1. **Create `.ebextensions/python.config`**

   ```yaml
   option_settings:
     aws:elasticbeanstalk:container:python:
       WSGIPath: src.pd_prime_demo.main:app
     aws:elasticbeanstalk:application:environment:
       PYTHONPATH: "/var/app/current/src:$PYTHONPATH"
   ```

2. **Deploy**
   ```bash
   eb init -p python-3.11 mvp-policy-backend
   eb create production
   eb deploy
   ```

### Google Cloud Run

1. **Build for Cloud Run**

   ```bash
   gcloud builds submit --tag gcr.io/$PROJECT_ID/mvp-policy-backend
   ```

2. **Deploy**
   ```bash
   gcloud run deploy mvp-policy-backend \
     --image gcr.io/$PROJECT_ID/mvp-policy-backend \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars "APP_ENV=production" \
     --set-secrets "DATABASE_URL=database-url:latest" \
     --min-instances 1 \
     --max-instances 10 \
     --memory 1Gi \
     --cpu 1
   ```

### Kubernetes Deployment

#### Deployment Manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mvp-policy-backend
  labels:
    app: mvp-policy-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mvp-policy-backend
  template:
    metadata:
      labels:
        app: mvp-policy-backend
    spec:
      containers:
        - name: api
          image: mvp-policy-backend:latest
          ports:
            - containerPort: 8000
          env:
            - name: APP_ENV
              value: "production"
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: mvp-policy-secrets
                  key: database-url
          resources:
            requests:
              memory: "512Mi"
              cpu: "500m"
            limits:
              memory: "1Gi"
              cpu: "1000m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: mvp-policy-backend-service
spec:
  selector:
    app: mvp-policy-backend
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: LoadBalancer
```

## Database Configuration

### PostgreSQL Production Setup

1. **Connection Pooling**

   ```python
   # src/pd_prime_demo/core/database.py
   from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

   engine = create_async_engine(
       settings.DATABASE_URL,
       pool_size=20,
       max_overflow=0,
       pool_pre_ping=True,
       pool_recycle=3600,
       echo=False
   )
   ```

2. **Read Replicas**

   ```python
   # Configure read replica for read-heavy operations
   read_engine = create_async_engine(
       settings.DATABASE_READ_URL,
       pool_size=10,
       max_overflow=5
   )
   ```

3. **Database Migrations**
   ```bash
   # Run migrations before deployment
   alembic upgrade head
   ```

### Redis Configuration

1. **Cluster Mode**

   ```python
   # For production Redis cluster
   from redis.asyncio import RedisCluster

   redis_client = RedisCluster(
       startup_nodes=[
           {"host": "redis-node-1", "port": 6379},
           {"host": "redis-node-2", "port": 6379},
           {"host": "redis-node-3", "port": 6379}
       ],
       decode_responses=True,
       skip_full_coverage_check=True
   )
   ```

2. **Sentinel for HA**

   ```python
   from redis.asyncio.sentinel import Sentinel

   sentinel = Sentinel([
       ('sentinel-1', 26379),
       ('sentinel-2', 26379),
       ('sentinel-3', 26379)
   ])
   redis_client = sentinel.master_for('mymaster', decode_responses=True)
   ```

## Environment Variables

### Production Configuration

```bash
# Application
APP_NAME="MVP Policy Decision Backend"
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_PREFIX=/api/v1
CORS_ORIGINS=["https://app.example.com"]

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@db-primary:5432/policy_db
DATABASE_READ_URL=postgresql+asyncpg://user:pass@db-replica:5432/policy_db
DATABASE_POOL_SIZE=50
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_URL=redis://redis-cluster:6379/0
REDIS_PASSWORD=${REDIS_PASSWORD}
REDIS_SSL=true

# Security
SECRET_KEY=${SECRET_KEY}  # Generate with: openssl rand -hex 32
JWT_ALGORITHM=RS256
JWT_PUBLIC_KEY_PATH=/secrets/jwt-public.pem
JWT_PRIVATE_KEY_PATH=/secrets/jwt-private.pem

# External Services
AI_SERVICE_URL=https://ai-service.internal
AI_SERVICE_API_KEY=${AI_SERVICE_KEY}

# Monitoring
SENTRY_DSN=${SENTRY_DSN}
DATADOG_API_KEY=${DATADOG_API_KEY}

# Performance
ENABLE_PROFILING=false
REQUEST_TIMEOUT_SECONDS=30
MAX_REQUEST_SIZE_MB=10
```

## SSL/TLS Configuration

### Nginx SSL Configuration

```nginx
server {
    listen 80;
    server_name api.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    location / {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Monitoring and Logging

### Application Monitoring

1. **Prometheus Metrics**

   ```python
   from prometheus_client import Counter, Histogram, generate_latest

   request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
   request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration')
   ```

2. **Health Checks**

   ```python
   @app.get("/health")
   async def health_check():
       # Check database
       try:
           await db.execute("SELECT 1")
           db_status = "healthy"
       except Exception:
           db_status = "unhealthy"

       # Check Redis
       try:
           await redis.ping()
           redis_status = "healthy"
       except Exception:
           redis_status = "unhealthy"

       return {
           "status": "healthy" if all([db_status == "healthy", redis_status == "healthy"]) else "unhealthy",
           "services": {
               "database": db_status,
               "redis": redis_status
           }
       }
   ```

### Logging Configuration

```python
import logging
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
```

## Backup and Disaster Recovery

### Database Backups

1. **Automated Backups**

   ```bash
   # Daily backup script
   #!/bin/bash
   DATE=$(date +%Y%m%d_%H%M%S)
   pg_dump $DATABASE_URL | gzip > backup_$DATE.sql.gz
   aws s3 cp backup_$DATE.sql.gz s3://backups/postgres/
   ```

2. **Point-in-Time Recovery**
   ```bash
   # Enable WAL archiving
   archive_mode = on
   archive_command = 'aws s3 cp %p s3://backups/wal/%f'
   ```

### Disaster Recovery Plan

1. **RTO/RPO Targets**
   - Recovery Time Objective (RTO): 1 hour
   - Recovery Point Objective (RPO): 15 minutes

2. **Backup Strategy**
   - Full database backup: Daily
   - Incremental backup: Every 15 minutes
   - Cross-region replication: Real-time

3. **Recovery Procedures**
   - Database restoration from backup
   - Application redeployment
   - DNS failover
   - Data validation

## Security Hardening

### Production Security Checklist

- [ ] Disable debug mode
- [ ] Use strong secret keys
- [ ] Enable HTTPS only
- [ ] Implement rate limiting
- [ ] Enable CORS properly
- [ ] Use security headers
- [ ] Implement CSP
- [ ] Regular security updates
- [ ] Vulnerability scanning
- [ ] Penetration testing

### Security Headers

```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["api.example.com"]
)

@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

## Performance Tuning

### Application Optimization

1. **Async Processing**

   ```python
   # Use connection pooling
   async with db_pool.acquire() as conn:
       result = await conn.fetch(query)
   ```

2. **Caching Strategy**

   ```python
   @cache(expire=300)
   async def get_rates(state: str) -> list[Rate]:
       return await db.fetch_rates(state)
   ```

3. **Query Optimization**
   ```python
   # Use select_related for joins
   policies = await db.execute(
       select(Policy).options(
           selectinload(Policy.endorsements),
           selectinload(Policy.claims)
       )
   )
   ```

## Rollback Procedures

### Application Rollback

```bash
# Tag current version
docker tag mvp-policy-backend:latest mvp-policy-backend:rollback

# Deploy new version
kubectl set image deployment/mvp-policy-backend api=mvp-policy-backend:v2

# If issues, rollback
kubectl set image deployment/mvp-policy-backend api=mvp-policy-backend:rollback
```

### Database Rollback

```bash
# Check current version
alembic current

# Rollback to previous version
alembic downgrade -1

# Rollback to specific version
alembic downgrade abc123
```

## Post-Deployment Checklist

- [ ] Verify all services are running
- [ ] Check application logs for errors
- [ ] Validate API endpoints
- [ ] Test critical user flows
- [ ] Monitor performance metrics
- [ ] Verify backup procedures
- [ ] Check security scanning results
- [ ] Update documentation
- [ ] Notify stakeholders
