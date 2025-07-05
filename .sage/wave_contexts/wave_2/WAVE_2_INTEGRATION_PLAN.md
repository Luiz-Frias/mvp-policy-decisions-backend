# Wave 2 Integration Plan - Following Existing Structure

## Overview

This plan details how Wave 2 features will integrate with the existing `src/pd_prime_demo` codebase, respecting current patterns and conventions while adding FULL PRODUCTION features.

## Integration Architecture

### 1. **Quote System Integration**

Following the existing pattern, we'll add:

```
src/pd_prime_demo/
├── models/
│   └── quote.py                 # Quote domain models
├── schemas/
│   └── quote.py                 # Quote API schemas
├── services/
│   ├── quote_service.py         # Quote business logic
│   └── rating_engine.py         # Full rating implementation
├── api/v1/
│   └── quotes.py                # Quote REST endpoints
```

#### models/quote.py

```python
"""Quote domain models following existing patterns."""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from pydantic import Field, field_validator

from .base import BaseModelConfig, TimestampedModel, IdentifiableModel


class QuoteStatus(str, Enum):
    """Quote lifecycle statuses."""
    DRAFT = "draft"
    CALCULATING = "calculating"
    QUOTED = "quoted"
    EXPIRED = "expired"
    BOUND = "bound"
    DECLINED = "declined"


class VehicleInfo(BaseModelConfig):
    """Vehicle information for auto quotes."""

    vin: str = Field(..., min_length=17, max_length=17)
    year: int = Field(..., ge=1900, le=datetime.now().year + 1)
    make: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=50)
    trim: Optional[str] = Field(None, max_length=50)
    annual_mileage: int = Field(..., ge=0, le=200000)
    garage_zip: str = Field(..., pattern=r'^\d{5}(-\d{4})?$')

    @field_validator('vin')
    @classmethod
    def validate_vin(cls, v: str) -> str:
        """Validate VIN format."""
        # Add VIN validation logic
        return v.upper()


class DriverInfo(BaseModelConfig):
    """Driver information for quotes."""

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: date
    license_number: str = Field(..., min_length=5, max_length=20)
    license_state: str = Field(..., pattern=r'^[A-Z]{2}$')
    years_licensed: int = Field(..., ge=0, le=100)
    accidents_3_years: int = Field(0, ge=0, le=10)
    violations_3_years: int = Field(0, ge=0, le=10)

    @field_validator('date_of_birth')
    @classmethod
    def validate_age(cls, v: date) -> date:
        """Ensure driver is at least 16 years old."""
        age = (datetime.now().date() - v).days / 365.25
        if age < 16:
            raise ValueError("Driver must be at least 16 years old")
        if age > 100:
            raise ValueError("Driver age must be reasonable")
        return v


class QuoteBase(BaseModelConfig):
    """Base quote information."""

    customer_id: UUID
    product_type: str = Field(..., pattern=r'^(auto|home|commercial)$')
    state: str = Field(..., pattern=r'^[A-Z]{2}$')
    effective_date: date

    # Coverage details
    coverage_type: str = Field(..., pattern=r'^(basic|standard|premium|comprehensive)$')
    coverage_amount: Decimal = Field(..., ge=Decimal('15000'), le=Decimal('1000000'))
    deductible: Decimal = Field(..., ge=Decimal('0'), le=Decimal('10000'))

    # Product-specific data
    vehicle_info: Optional[VehicleInfo] = None
    drivers: List[DriverInfo] = Field(default_factory=list)

    @field_validator('effective_date')
    @classmethod
    def validate_effective_date(cls, v: date) -> date:
        """Ensure effective date is not in the past."""
        if v < datetime.now().date():
            raise ValueError("Effective date cannot be in the past")
        return v


class Quote(QuoteBase, IdentifiableModel):
    """Full quote model with calculated fields."""

    quote_number: str = Field(..., pattern=r'^Q-\d{8}-\d{6}$')
    status: QuoteStatus = Field(default=QuoteStatus.DRAFT)

    # Calculated fields
    base_premium: Optional[Decimal] = None
    total_premium: Optional[Decimal] = None
    monthly_premium: Optional[Decimal] = None

    # Rating details
    rating_factors: dict = Field(default_factory=dict)
    discounts_applied: List[dict] = Field(default_factory=list)
    surcharges_applied: List[dict] = Field(default_factory=list)

    # AI risk assessment
    ai_risk_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    ai_risk_factors: List[str] = Field(default_factory=list)

    # Expiration
    expires_at: datetime

    # Conversion tracking
    converted_to_policy_id: Optional[UUID] = None

    class Config:
        """Additional configuration."""
        json_schema_extra = {
            "example": {
                "quote_number": "Q-20240105-000001",
                "customer_id": "123e4567-e89b-12d3-a456-426614174000",
                "product_type": "auto",
                "state": "CA",
                "status": "quoted",
                "total_premium": "1200.00"
            }
        }


class QuoteCreate(QuoteBase):
    """Quote creation model."""
    pass


class QuoteUpdate(BaseModelConfig):
    """Quote update model."""

    coverage_amount: Optional[Decimal] = Field(None, ge=Decimal('15000'))
    deductible: Optional[Decimal] = Field(None, ge=Decimal('0'))
    vehicle_info: Optional[VehicleInfo] = None
    drivers: Optional[List[DriverInfo]] = None
```

### 2. **Rating Engine Integration**

Create a full production rating engine while maintaining the existing service pattern:

```
src/pd_prime_demo/
├── services/
│   ├── rating/
│   │   ├── __init__.py
│   │   ├── engine.py           # Main rating engine
│   │   ├── factors.py          # Rating factor calculations
│   │   ├── rules.py            # State-specific rules
│   │   └── tables.py           # Rate table management
```

### 3. **WebSocket Integration**

Add WebSocket support alongside existing HTTP endpoints:

```
src/pd_prime_demo/
├── websocket/
│   ├── __init__.py
│   ├── manager.py              # WebSocket connection manager
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── quotes.py           # Quote real-time handlers
│   │   ├── analytics.py        # Dashboard handlers
│   │   └── notifications.py    # Push notification handlers
```

### 4. **Security Enhancements**

Extend existing security module:

```
src/pd_prime_demo/
├── core/
│   ├── security.py             # Extend with SSO, OAuth2
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── sso.py             # SSO providers
│   │   ├── oauth2.py          # OAuth2 server
│   │   ├── mfa.py             # Multi-factor auth
│   │   └── soc2.py            # SOC2 compliance
```

### 5. **Database Migrations**

Add new Alembic migrations:

```
alembic/versions/
├── 002_add_quote_tables.py
├── 003_add_rate_tables.py
├── 004_add_security_tables.py
├── 005_add_audit_tables.py
```

## Integration Points

### 1. **Update API Router** (`api/v1/__init__.py`)

```python
"""API v1 router aggregation."""

from fastapi import APIRouter

from .claims import router as claims_router
from .customers import router as customers_router
from .health import router as health_router
from .policies import router as policies_router
from .quotes import router as quotes_router  # Add this
from .rates import router as rates_router    # Add this

router = APIRouter()

# Include all routers
router.include_router(health_router, tags=["health"])
router.include_router(customers_router, prefix="/customers", tags=["customers"])
router.include_router(policies_router, prefix="/policies", tags=["policies"])
router.include_router(claims_router, prefix="/claims", tags=["claims"])
router.include_router(quotes_router, prefix="/quotes", tags=["quotes"])  # Add this
router.include_router(rates_router, prefix="/rates", tags=["rates"])    # Add this
```

### 2. **Update Dependencies** (`api/dependencies.py`)

```python
"""Add quote service dependencies."""

from ..services.quote_service import QuoteService
from ..services.rating_engine import RatingEngine

async def get_quote_service(
    db: AsyncGenerator[asyncpg.Connection, None] = Depends(get_db),
    redis: Redis = Depends(get_redis),
    rating_engine: RatingEngine = Depends(get_rating_engine),
) -> QuoteService:
    """Get quote service instance."""
    cache = Cache(redis)
    database = Database(db)
    return QuoteService(database, cache, rating_engine)

async def get_rating_engine(
    db: AsyncGenerator[asyncpg.Connection, None] = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> RatingEngine:
    """Get rating engine instance."""
    cache = Cache(redis)
    database = Database(db)
    return RatingEngine(database, cache)
```

### 3. **Update Main Application** (`main.py`)

```python
"""Add WebSocket support and new middleware."""

from .websocket import websocket_app

# Add WebSocket routes
app.mount("/ws", websocket_app)

# Add SOC2 compliance middleware
app.add_middleware(SOC2ComplianceMiddleware)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)
```

## Implementation Timeline

### Days 1-2: Foundation & Database

- Complete existing TODOs
- Add quote and rate tables via migrations
- Test database connectivity

### Days 3-4: Quote Core

- Implement quote models and schemas
- Create quote service with Result pattern
- Add basic quote endpoints

### Days 5-6: Rating Engine

- Implement full rating calculations
- Add state-specific rules
- Create rate management APIs

### Days 7-8: Real-Time & Security

- Add WebSocket infrastructure
- Implement SSO and OAuth2
- Add SOC2 compliance features

### Days 9-10: Integration & Testing

- Connect all components
- Add comprehensive tests
- Deploy to Railway

## Key Integration Principles

1. **Follow Existing Patterns**: Use the same Result type, service pattern, and model structure
2. **Maintain Type Safety**: 100% beartype coverage, no Any types
3. **Defensive Programming**: Validate all inputs, use immutable models
4. **Performance First**: Cache aggressively, optimize queries
5. **Security by Default**: Encrypt PII, audit everything

This integration plan ensures Wave 2 features blend seamlessly with the existing codebase while delivering a full production system.
