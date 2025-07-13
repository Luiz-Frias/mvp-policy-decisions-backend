# Reusable Components Guide

## Overview

This guide documents the reusable components created during Wave 2 implementation that can be leveraged in future waves or projects. These components follow the master ruleset and implement best practices for enterprise software development.

## Core Infrastructure Components

### 1. Base Pydantic Models

**Location**: `src/pd_prime_demo/models/base.py`

**Description**: Foundation classes for all domain models with strict validation and immutability.

```python
@beartype
class BaseModelConfig(BaseModel):
    """Base model with strict configuration for all domain entities."""
    model_config = ConfigDict(
        frozen=True,                    # Immutable by default
        extra="forbid",                # No extra fields allowed
        validate_assignment=True,       # Validate on assignment
        str_strip_whitespace=True,     # Clean string inputs
        validate_default=True,         # Validate default values
        use_enum_values=True,          # Use enum values in serialization
        arbitrary_types_allowed=False, # Strict type enforcement
    )
```

**Usage Pattern**:

```python
# Inherit from BaseModelConfig for all domain models
class YourModel(BaseModelConfig):
    field1: str = Field(..., min_length=1, max_length=100)
    field2: int = Field(..., ge=0, le=1000)
```

**Reusability**: ⭐⭐⭐⭐⭐ (Universal - use for all domain models)

**Customization Points**:

- Validation rules per field
- Serialization configuration
- Computed fields
- Custom validators

### 2. Result Type System

**Location**: `src/pd_prime_demo/services/result.py`

**Description**: Rust-inspired Result types for explicit error handling without exceptions.

```python
# Core Result types
Result = Union[Ok[T], Err[E]]

@beartype
async def your_service_method(data: InputData) -> Result[OutputData, str]:
    try:
        # Business logic
        result = process_data(data)
        return Ok(result)
    except ValidationError as e:
        return Err(f"Validation failed: {e}")
```

**Usage Pattern**:

```python
# Service layer
result = await service.create_item(data)
if isinstance(result, Err):
    return {"error": result.unwrap_err()}
return {"success": result.unwrap()}

# Chaining operations
return (await validate_input(data)
    .and_then(lambda x: process_data(x))
    .and_then(lambda x: save_to_db(x)))
```

**Reusability**: ⭐⭐⭐⭐⭐ (Universal - use in all services)

**Benefits**:

- No exceptions for control flow
- Explicit error handling
- Composable operations
- Type-safe error propagation

### 3. Performance Monitoring

**Location**: `src/pd_prime_demo/services/performance_monitor.py`

**Description**: Decorator for monitoring function performance with configurable thresholds.

```python
@beartype
@performance_monitor(
    operation_name="quote_creation",
    max_duration_ms=2000,
    memory_threshold_mb=100
)
async def create_quote(data: QuoteCreate) -> Result[Quote, str]:
    # Implementation must complete within thresholds
    pass
```

**Usage Pattern**:

```python
# Apply to all functions >10 lines (master ruleset requirement)
@performance_monitor("operation_name", max_duration_ms=1000)
def your_function():
    # Function implementation
    pass
```

**Reusability**: ⭐⭐⭐⭐⭐ (Universal - use on all critical functions)

**Features**:

- Execution time monitoring
- Memory usage tracking
- Performance regression detection
- Automatic alerting for slow operations

## Database Infrastructure

### 1. Enhanced Connection Pool

**Location**: `src/pd_prime_demo/core/database_enhanced.py`

**Description**: Intelligent connection pool management with workload-specific optimizations.

```python
class DatabaseEnhanced:
    """Enhanced database with intelligent connection pooling."""

    def __init__(self, config: DatabaseConfig):
        # Capacity-based pool sizing
        # Read replica support
        # Admin pool for complex queries
        # Health monitoring
        pass
```

**Features**:

- Dynamic pool sizing based on expected load
- Separate pools for read/write/admin operations
- Health monitoring and metrics
- Automatic retry with exponential backoff
- Prepared statement caching

**Usage Pattern**:

```python
# Configuration
DATABASE_POOL_MIN = 5
DATABASE_POOL_MAX = 20
DATABASE_ADMIN_POOL_ENABLED = True

# Usage (drop-in replacement for standard database)
db = DatabaseEnhanced(config)
async with db.transaction():
    result = await db.fetchrow(query, *params)
```

**Reusability**: ⭐⭐⭐⭐⭐ (High - works with any PostgreSQL application)

**Customization Points**:

- Pool sizing algorithms
- Health check strategies
- Retry policies
- Monitoring integration

### 2. Query Optimizer

**Location**: `src/pd_prime_demo/core/query_optimizer.py`

**Description**: Tools for analyzing and optimizing database query performance.

```python
class QueryOptimizer:
    """Query performance analysis and optimization tools."""

    async def analyze_query(self, query: str) -> QueryAnalysis:
        # EXPLAIN ANALYZE integration
        # Index recommendations
        # Performance insights
        pass

    async def get_slow_queries(self, threshold_ms: int = 1000) -> List[SlowQuery]:
        # pg_stat_statements integration
        # Slow query identification
        pass
```

**Features**:

- EXPLAIN ANALYZE automation
- Slow query detection
- Index suggestion engine
- Table bloat analysis
- Performance tuning recommendations

**Reusability**: ⭐⭐⭐⭐ (High - PostgreSQL specific but generalizable)

## Security Infrastructure

### 1. SSO Provider Framework

**Location**: `src/pd_prime_demo/core/auth/providers/`

**Description**: Standardized SSO provider implementations for major identity providers.

**Supported Providers**:

- Google Workspace (`google.py`)
- Microsoft Azure AD (`azure.py`)
- Okta (`okta.py`)
- Auth0 (`auth0.py`)

```python
# Example usage
google_provider = GoogleSSOProvider(
    client_id="your-client-id",
    client_secret="your-client-secret",
    redirect_uri="your-redirect-uri",
    hosted_domain="your-domain.com"  # Optional workspace restriction
)

auth_url = await google_provider.get_authorization_url(state, nonce)
user_info = await google_provider.get_user_info(authorization_code)
```

**Features**:

- OAuth2/OIDC compliance
- Token validation
- User info extraction
- Domain restrictions
- Error handling with Result types

**Reusability**: ⭐⭐⭐⭐⭐ (High - standard OAuth2 patterns)

### 2. Role-Based Access Control (RBAC)

**Location**: `src/pd_prime_demo/models/admin.py`

**Description**: Comprehensive RBAC system with hierarchical permissions.

```python
class AdminRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    SUPPORT = "support"
    VIEWER = "viewer"

class Permission(str, Enum):
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    QUOTE_APPROVE = "quote:approve"
    # ... comprehensive permission set
```

**Features**:

- Hierarchical role system
- Granular permissions
- Resource-based access control
- Audit logging integration
- Default permission sets

**Usage Pattern**:

```python
# Check permissions
@require_permission(Permission.QUOTE_APPROVE)
async def approve_quote(quote_id: str, user: AdminUser):
    # Only users with quote:approve permission can access
    pass

# Role-based checks
if user.has_role(AdminRole.ADMIN):
    # Admin-only functionality
    pass
```

**Reusability**: ⭐⭐⭐⭐⭐ (High - generic permission patterns)

## Real-Time Infrastructure

### 1. WebSocket Manager

**Location**: `src/pd_prime_demo/websocket/manager.py`

**Description**: Scalable WebSocket connection and room management.

```python
class ConnectionManager:
    """Manage WebSocket connections and rooms."""

    async def connect(self, websocket: WebSocket, connection_id: str, user_id: UUID = None):
        # Connection management
        pass

    async def join_room(self, connection_id: str, room_id: str):
        # Room subscription
        pass

    async def broadcast_to_room(self, room_id: str, message: WebSocketMessage):
        # Room broadcasting
        pass
```

**Features**:

- Connection pooling and management
- Room-based subscriptions
- Message broadcasting
- Health monitoring
- Connection cleanup
- Rate limiting

**Usage Pattern**:

```python
# Real-time quote updates
await manager.join_room(connection_id, f"quote:{quote_id}")
await manager.broadcast_to_room(
    f"quote:{quote_id}",
    WebSocketMessage(type="quote_updated", data=quote_data)
)
```

**Reusability**: ⭐⭐⭐⭐⭐ (High - generic WebSocket patterns)

### 2. WebSocket Performance Monitor

**Location**: `src/pd_prime_demo/services/websocket_performance.py`

**Description**: Performance monitoring specifically for WebSocket operations.

**Features**:

- Connection metrics
- Message latency tracking
- Throughput monitoring
- Error rate analysis
- Connection health scoring

## Business Logic Components

### 1. Quote Management System

**Location**: `src/pd_prime_demo/services/quote_service.py`

**Description**: Comprehensive quote lifecycle management.

**Features**:

- Multi-step quote wizard
- Version management
- Expiration handling
- Conversion to policies
- Admin overrides
- Audit trails

**Reusability**: ⭐⭐⭐ (Medium - insurance specific but patterns applicable)

### 2. Rating Engine

**Location**: `src/pd_prime_demo/services/rating_engine.py`

**Description**: High-performance insurance rating with sub-50ms calculations.

**Features**:

- Multi-factor rating
- State-specific rules
- Discount calculations
- Surcharge application
- AI risk scoring
- Performance optimization

**Reusability**: ⭐⭐ (Low - insurance specific but architecture patterns useful)

## Utility Components

### 1. Cache Key Management

**Location**: `src/pd_prime_demo/services/cache_keys.py`

**Description**: Centralized cache key management with TTL strategies.

```python
class CacheKeys:
    """Centralized cache key management."""

    @staticmethod
    def quote_key(quote_id: str) -> str:
        return f"quote:{quote_id}"

    @staticmethod
    def rate_table_key(state: str, product: str) -> str:
        return f"rates:{state}:{product}"
```

**Features**:

- Consistent key naming
- TTL management
- Cache invalidation patterns
- Key versioning

**Reusability**: ⭐⭐⭐⭐ (High - useful for any cached application)

### 2. Transaction Helpers

**Location**: `src/pd_prime_demo/services/transaction_helpers.py`

**Description**: Database transaction management utilities.

```python
@beartype
async def with_transaction(
    db: Database,
    operation: Callable[[], Awaitable[Result[T, E]]]
) -> Result[T, E]:
    """Execute operation within a database transaction."""
    async with db.transaction():
        return await operation()
```

**Reusability**: ⭐⭐⭐⭐ (High - useful for any transactional application)

## Integration Patterns

### 1. Service Integration Template

```python
class YourService:
    """Template for service implementation."""

    def __init__(
        self,
        db: Database,
        cache: Cache,
        # Optional dependencies with fallback
        external_service: Optional[ExternalService] = None,
    ):
        self._db = db
        self._cache = cache
        self._external_service = external_service

    @beartype
    @performance_monitor("your_operation", max_duration_ms=1000)
    async def your_method(self, data: InputModel) -> Result[OutputModel, str]:
        # 1. Validate input
        validation = self._validate_input(data)
        if isinstance(validation, Err):
            return validation

        # 2. Check cache
        cached = await self._get_from_cache(data.key)
        if cached:
            return Ok(cached)

        # 3. Business logic
        result = await self._process_data(data)
        if isinstance(result, Err):
            return result

        # 4. Cache result
        await self._cache_result(data.key, result.value)

        # 5. Return success
        return result
```

### 2. API Endpoint Template

```python
@router.post("/your-endpoint", response_model=SuccessResponse[OutputSchema])
async def your_endpoint(
    data: InputSchema,
    service: YourService = Depends(get_your_service),
    current_user: User = Depends(get_current_user),
) -> SuccessResponse[OutputSchema]:
    """API endpoint template with proper error handling."""

    # Convert schema to domain model
    domain_data = InputModel.from_schema(data)

    # Call service
    result = await service.your_method(domain_data)

    # Handle result
    if isinstance(result, Err):
        raise HTTPException(
            status_code=400,
            detail={"error": result.unwrap_err()}
        )

    # Convert to response schema
    response_data = OutputSchema.from_model(result.unwrap())
    return SuccessResponse(data=response_data)
```

## Testing Components

### 1. Test Fixtures

**Location**: `tests/fixtures/`

**Description**: Reusable test fixtures for common testing scenarios.

```python
@pytest.fixture
async def test_database():
    """Provide a test database with cleanup."""
    # Setup test database
    yield db
    # Cleanup

@pytest.fixture
def sample_quote_data():
    """Provide sample quote data for testing."""
    return QuoteCreate(
        customer_id=uuid4(),
        state="CA",
        # ... complete test data
    )
```

### 2. Performance Test Templates

```python
@pytest.mark.benchmark
async def test_quote_creation_performance(benchmark, quote_service, sample_data):
    """Benchmark quote creation performance."""
    result = await benchmark(quote_service.create_quote, sample_data)
    assert isinstance(result, Ok)
    assert benchmark.stats["mean"] < 2.0  # 2 second max
```

## Deployment Components

### 1. Health Check Framework

```python
class HealthChecker:
    """Comprehensive health checking."""

    async def check_database(self) -> HealthStatus:
        # Database connectivity and performance
        pass

    async def check_cache(self) -> HealthStatus:
        # Cache connectivity and performance
        pass

    async def check_external_services(self) -> HealthStatus:
        # External service availability
        pass
```

### 2. Configuration Management

```python
class Settings(BaseSettings):
    """Environment-aware configuration."""

    # Database settings
    database_url: str
    database_pool_min: int = 5
    database_pool_max: int = 20

    # Cache settings
    redis_url: str
    cache_ttl: int = 3600

    # Performance settings
    max_duration_ms: int = 2000
    memory_threshold_mb: int = 100

    class Config:
        env_file = ".env"
        case_sensitive = False
```

## Component Usage Guidelines

### 1. Selection Criteria

**Core Infrastructure**: Use for all projects

- Base models
- Result types
- Performance monitoring
- Database pooling

**Security Infrastructure**: Use for enterprise applications

- SSO providers
- RBAC system
- Audit logging

**Business Logic**: Adapt patterns for domain-specific needs

- Quote management patterns
- Rating engine architecture
- Workflow management

### 2. Customization Approach

1. **Start with base component**
2. **Identify customization points**
3. **Extend or compose rather than modify**
4. **Maintain compatibility with core patterns**
5. **Document customizations**

### 3. Integration Best Practices

1. **Follow dependency injection patterns**
2. **Use Result types for error handling**
3. **Apply performance monitoring**
4. **Implement comprehensive testing**
5. **Add health checks**

## Future Component Development

### 1. Patterns to Follow

- **Immutable by default** (frozen=True)
- **Result types for error handling**
- **Performance monitoring built-in**
- **Comprehensive validation**
- **Clear interfaces and dependencies**

### 2. Documentation Requirements

- **Clear usage examples**
- **Customization points**
- **Performance characteristics**
- **Testing guidelines**
- **Integration patterns**

### 3. Quality Standards

- **100% type coverage**
- **95%+ test coverage**
- **Performance benchmarks**
- **Security validation**
- **Master ruleset compliance**

---

**Document Status**: ✅ Complete
**Last Updated**: 2025-07-05
**Maintainer**: SAGE System
**Next Review**: After Wave 3 completion
