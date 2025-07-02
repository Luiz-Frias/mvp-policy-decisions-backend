# WAVE 1 IMPLEMENTATION CONTEXT

## Overview

This document provides the complete context for Wave 1 implementation of the MVP Policy Decision Backend. Following SAGE principles, Wave 1 aims to create a working skeleton of the entire system (80% build) with maximum parallelization using 5-10 agents.

## Pre-Wave 1 Setup Requirements

### Manual Railway Setup Required

Since Railway CLI doesn't support non-interactive project creation with services, please complete these steps via the Railway web UI:

1. **Create New Project**
   - Go to https://railway.app/dashboard
   - Click "New Project"
   - Name it: `mvp-policy-decision-backend`

2. **Add PostgreSQL Service**
   - Click "+ New" → "Database" → "Add PostgreSQL"
   - Railway will automatically provision PostgreSQL 15
   - Note the connection string from the Variables tab

3. **Add Redis Service**
   - Click "+ New" → "Database" → "Add Redis"
   - Railway will automatically provision Redis 7
   - Note the connection URL from the Variables tab

4. **Link Local Project**

   ```bash
   railway link
   # Select the mvp-policy-decision-backend project
   ```

5. **Copy Environment Variables**
   ```bash
   railway variables > .env.railway
   ```

## Wave 1 Objectives

### Foundation Components (80% Build)

The Wave 1 implementation creates the complete system skeleton with these components:

1. **Project Structure**

   ```
   src/
   ├── pd_prime_demo/
   │   ├── __init__.py
   │   ├── main.py              # FastAPI application entry
   │   ├── core/
   │   │   ├── __init__.py
   │   │   ├── config.py        # Pydantic settings
   │   │   ├── database.py      # Database connections
   │   │   ├── security.py      # Security utilities
   │   │   └── cache.py         # Redis caching
   │   ├── models/
   │   │   ├── __init__.py
   │   │   ├── base.py          # Base Pydantic models
   │   │   ├── policy.py        # Policy domain models
   │   │   ├── customer.py      # Customer models
   │   │   └── claim.py         # Claim models
   │   ├── api/
   │   │   ├── __init__.py
   │   │   ├── v1/
   │   │   │   ├── __init__.py
   │   │   │   ├── policies.py  # Policy endpoints
   │   │   │   ├── customers.py # Customer endpoints
   │   │   │   ├── claims.py    # Claim endpoints
   │   │   │   └── health.py    # Health checks
   │   │   └── dependencies.py  # FastAPI dependencies
   │   ├── services/
   │   │   ├── __init__.py
   │   │   ├── policy_service.py
   │   │   ├── customer_service.py
   │   │   └── claim_service.py
   │   └── schemas/
   │       ├── __init__.py
   │       ├── policy.py        # API schemas
   │       ├── customer.py
   │       └── claim.py
   tests/
   ├── __init__.py
   ├── conftest.py             # Pytest configuration
   ├── unit/
   │   ├── __init__.py
   │   ├── test_models.py
   │   └── test_services.py
   └── integration/
       ├── __init__.py
       └── test_api.py
   ```

2. **Database Schema**

   ```sql
   -- Core tables with JSONB for flexibility
   CREATE TABLE customers (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       data JSONB NOT NULL,
       created_at TIMESTAMPTZ DEFAULT NOW(),
       updated_at TIMESTAMPTZ DEFAULT NOW()
   );

   CREATE TABLE policies (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       customer_id UUID REFERENCES customers(id),
       data JSONB NOT NULL,
       status VARCHAR(50) NOT NULL,
       created_at TIMESTAMPTZ DEFAULT NOW(),
       updated_at TIMESTAMPTZ DEFAULT NOW()
   );

   CREATE TABLE claims (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       policy_id UUID REFERENCES policies(id),
       data JSONB NOT NULL,
       status VARCHAR(50) NOT NULL,
       created_at TIMESTAMPTZ DEFAULT NOW(),
       updated_at TIMESTAMPTZ DEFAULT NOW()
   );

   -- Indexes for performance
   CREATE INDEX idx_policies_customer ON policies(customer_id);
   CREATE INDEX idx_claims_policy ON claims(policy_id);
   CREATE INDEX idx_policies_data ON policies USING gin(data);
   ```

3. **Core API Endpoints**
   - `GET /health` - Health check
   - `GET /api/v1/policies` - List policies
   - `POST /api/v1/policies` - Create policy
   - `GET /api/v1/policies/{id}` - Get policy
   - `PUT /api/v1/policies/{id}` - Update policy
   - `DELETE /api/v1/policies/{id}` - Delete policy
   - Similar CRUD for customers and claims

4. **Pydantic Models (with frozen=True)**

   ```python
   from pydantic import BaseModel, Field, ConfigDict
   from decimal import Decimal
   from datetime import datetime
   from typing import Optional
   import uuid

   class PolicyBase(BaseModel):
       model_config = ConfigDict(
           frozen=True,
           extra="forbid",
           validate_assignment=True,
           str_strip_whitespace=True
       )

       premium: Decimal = Field(..., ge=0, decimal_places=2)
       coverage_amount: Decimal = Field(..., ge=0, decimal_places=2)
       policy_type: str = Field(..., min_length=1, max_length=50)
   ```

5. **Configuration Management**

   ```python
   from pydantic_settings import BaseSettings, SettingsConfigDict

   class Settings(BaseSettings):
       model_config = SettingsConfigDict(
           env_file=".env",
           env_file_encoding="utf-8",
           frozen=True
       )

       # Database
       database_url: str
       redis_url: str

       # API
       api_host: str = "0.0.0.0"
       api_port: int = 8000
       api_env: str = "development"

       # Security
       secret_key: str
       jwt_secret: str

       # OpenAI
       openai_api_key: Optional[str] = None
   ```

## Agent Task Allocation

### Agent 1: Core Infrastructure

- **Files**: `src/pd_prime_demo/core/*.py`
- **Tasks**:
  - Database connection setup with asyncpg
  - Redis cache configuration
  - Security utilities (JWT, hashing)
  - Configuration management

### Agent 2: Domain Models

- **Files**: `src/pd_prime_demo/models/*.py`
- **Tasks**:
  - Base Pydantic model with frozen=True
  - Policy, Customer, Claim models
  - Validation decorators
  - Type hints with beartype

### Agent 3: API Layer

- **Files**: `src/pd_prime_demo/api/v1/*.py`
- **Tasks**:
  - FastAPI routers for all endpoints
  - Request/response schemas
  - Error handling
  - OpenAPI documentation

### Agent 4: Service Layer

- **Files**: `src/pd_prime_demo/services/*.py`
- **Tasks**:
  - Business logic stubs
  - Database query patterns
  - Result type implementation
  - Cache integration

### Agent 5: Database & Migrations

- **Files**: `alembic/`, `scripts/`
- **Tasks**:
  - Alembic configuration
  - Initial migration scripts
  - Database initialization
  - Seed data scripts

### Agent 6: Testing Framework

- **Files**: `tests/`, `conftest.py`
- **Tasks**:
  - Pytest configuration
  - Test fixtures
  - Unit test stubs
  - Integration test setup

### Agent 7: CI/CD Pipeline

- **Files**: `.github/workflows/*.yml`
- **Tasks**:
  - GitHub Actions workflows
  - Pre-commit hooks
  - Quality gates
  - Deployment automation

### Agent 8: Development Tools

- **Files**: `Makefile`, `scripts/`
- **Tasks**:
  - Development scripts
  - Performance benchmarks
  - Memory profiling setup
  - Validation scripts

### Agent 9: Documentation

- **Files**: `README.md`, `docs/`
- **Tasks**:
  - API documentation
  - Development guide
  - Deployment instructions
  - Architecture diagrams

### Agent 10: Frontend Scaffold

- **Files**: `frontend/` (Next.js)
- **Tasks**:
  - Next.js 14 setup
  - TypeScript configuration
  - API client stubs
  - Basic UI components

## Success Criteria

Wave 1 is considered successful when:

1. ✅ All 10 agents complete their tasks
2. ✅ `make test` runs without errors
3. ✅ `make lint` passes all checks
4. ✅ API responds to health checks
5. ✅ Database connections work
6. ✅ Redis cache is operational
7. ✅ All Pydantic models use frozen=True
8. ✅ Type coverage is 100%
9. ✅ CI/CD pipeline is green
10. ✅ Frontend displays "Hello World"

## Quality Gates

Each agent must ensure:

1. **Code Quality**
   - MyPy strict mode passes
   - No `Any` types except boundaries
   - All functions have `@beartype`
   - Pydantic models are frozen

2. **Performance**
   - Functions >10 lines have benchmarks
   - Memory allocation <1MB per function
   - No blocking I/O in async functions

3. **Security**
   - No hardcoded secrets
   - Input validation on all endpoints
   - Proper error handling
   - CORS configured correctly

## Post-Wave 1 State

After Wave 1 completion, the system will have:

- Complete project structure
- Working API skeleton
- Database connectivity
- Caching layer
- Basic frontend
- Full CI/CD pipeline
- Comprehensive test framework
- Performance monitoring
- Security scanning
- Documentation framework

This provides a solid foundation for Wave 2 (business logic) and Wave 3 (optimization).

## Supervisor Instructions

As the supervisor, you will:

1. Deploy all 10 agents simultaneously
2. Monitor their progress via status updates
3. Ensure they follow the master ruleset
4. Validate completion criteria
5. Prepare Wave 2 context based on Wave 1 results

Remember: Agents are temporary workers. They execute tasks and disappear. You maintain all context and orchestrate the entire build process.
