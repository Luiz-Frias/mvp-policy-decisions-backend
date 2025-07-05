# Agent 02: Service Integration Specialist

## YOUR MISSION

Fix all Wave 1 TODOs and make database queries actually work. Every service must persist and retrieve real data.

## NO SILENT FALLBACKS PRINCIPLE

### Service Configuration Requirements

**NEVER use default service endpoints without explicit configuration:**

```python
# ❌ FORBIDDEN: Implicit service discovery
class PolicyService:
    def __init__(self):
        self.db_url = "postgresql://localhost:5432/db"  # Hard-coded default
        self.cache_url = "redis://localhost:6379"      # Implicit fallback

# ✅ REQUIRED: Explicit service configuration validation
class PolicyService:
    def __init__(self, db: Database, cache: Cache):
        if not db or not db.is_connected():
            raise ValueError("Database connection required and must be active")
        if not cache or not cache.is_available():
            raise ValueError("Cache connection required and must be available")
        self._db = db
        self._cache = cache
```

**NEVER implement silent retry logic without explicit configuration:**

```python
# ❌ FORBIDDEN: Silent retry with default backoff
async def create_customer(self, data):
    for attempt in range(3):  # Magic number
        try:
            return await self._db.execute(query)
        except Exception:
            await asyncio.sleep(1)  # Silent backoff
    return None  # Silent failure

# ✅ REQUIRED: Explicit retry configuration
async def create_customer(self, data, retry_config: RetryConfig):
    if not retry_config:
        raise ValueError("Retry configuration required")

    for attempt in range(retry_config.max_attempts):
        try:
            return Ok(await self._db.execute(query))
        except Exception as e:
            if attempt == retry_config.max_attempts - 1:
                return Err(f"Failed after {retry_config.max_attempts} attempts: {e}")
            await asyncio.sleep(retry_config.backoff_seconds)
```

**NEVER skip dependency validation:**

```python
# ❌ FORBIDDEN: Assume dependencies are available
class ServiceIntegrator:
    async def integrate_services(self):
        # Assumes all services work
        return await some_service.call()

# ✅ REQUIRED: Explicit dependency validation
class ServiceIntegrator:
    async def validate_dependencies(self) -> Result[bool, str]:
        checks = [
            ("database", self._check_database),
            ("cache", self._check_cache),
            ("external_api", self._check_external_api)
        ]

        for name, check in checks:
            result = await check()
            if not result:
                return Err(f"Dependency check failed: {name}")
        return Ok(True)
```

### Fail Fast Validation

If ANY service dependency is unconfigured, you MUST:

1. **Immediately throw explicit error** with dependency name
2. **Document required configuration** in error message
3. **Never proceed** with default/fallback behavior
4. **Validate ALL dependencies** at service startup

### Explicit Error Remediation

**When service integration fails:**

- Never catch and ignore exceptions silently
- Always return Result[T, E] with explicit error details
- Log exact dependency that failed with configuration needed
- Provide actionable remediation steps in error messages

**Required validation for each service:**

- Database connection pool health check
- Cache connectivity and key space validation
- External API authentication and rate limit verification
- Message queue connectivity and subscription verification
- File system permissions and disk space checks

## MANDATORY PRE-WORK

1. Read ALL documents listed in AGENT_TEMPLATE.md FIRST
2. Specifically study:
   - Search for all TODO comments: `grep -r "TODO" src/`
   - Review service pattern in `src/pd_prime_demo/services/`
   - Understand Result[T, E] pattern usage

## SPECIFIC TASKS

### 1. Fix PolicyService (`src/pd_prime_demo/services/policy_service.py`)

Current issues to fix:

- `_row_to_policy` method has incorrect field mappings
- Premium/coverage amounts are nested incorrectly in JSON
- Missing proper error handling for database failures

Required fixes:

```python
@beartype
def _row_to_policy(self, row: asyncpg.Record) -> Policy:
    """Convert database row to Policy model."""
    data = dict(row["data"])

    # Fix the JSON structure to match what we're storing
    return Policy(
        id=row["id"],
        customer_id=row["customer_id"],
        policy_number=row["policy_number"],
        policy_type=PolicyType(data.get("type", "AUTO")),
        status=PolicyStatus(row["status"]),
        premium_amount=Decimal(str(data.get("premium", "0"))),
        coverage_amount=Decimal(str(data.get("coverage_amount", "0"))),
        deductible=Decimal(str(data.get("deductible", "0"))),
        effective_date=row["effective_date"],
        expiration_date=row["expiration_date"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        notes=data.get("notes"),
        cancelled_at=None,  # TODO: Implement cancellation tracking
    )
```

### 2. Fix CustomerService (`src/pd_prime_demo/services/customer_service.py`)

Current issues:

- Returns mock data instead of database queries
- Missing cache implementation
- No proper transaction handling

Required implementation:

```python
@beartype
async def create(self, customer_data: CustomerCreate) -> Result[Customer, str]:
    """Create a new customer with proper validation."""
    # Start transaction
    async with self._db.transaction():
        try:
            # Check for duplicate email
            existing = await self._db.fetchrow(
                "SELECT id FROM customers WHERE email = $1",
                customer_data.email
            )
            if existing:
                return Err(f"Customer with email {customer_data.email} already exists")

            # Insert customer
            query = """
                INSERT INTO customers (first_name, last_name, email, phone,
                                     date_of_birth, address)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, first_name, last_name, email, phone,
                         date_of_birth, address, created_at, updated_at
            """

            row = await self._db.fetchrow(
                query,
                customer_data.first_name,
                customer_data.last_name,
                customer_data.email,
                customer_data.phone,
                customer_data.date_of_birth,
                customer_data.address.model_dump() if customer_data.address else None,
            )

            if not row:
                return Err("Failed to create customer")

            customer = Customer(
                id=row["id"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                email=row["email"],
                phone=row["phone"],
                date_of_birth=row["date_of_birth"],
                address=Address(**row["address"]) if row["address"] else None,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

            # Invalidate cache
            await self._cache.delete(f"customer:email:{customer.email}")

            return Ok(customer)

        except Exception as e:
            # Transaction will rollback automatically
            return Err(f"Database error: {str(e)}")
```

### 3. Fix ClaimService (`src/pd_prime_demo/services/claim_service.py`)

Current issues:

- All methods return mock data
- No status transition validation
- Missing claim number generation

Required features:

- Generate claim numbers: `CLM-YYYY-NNNNNN`
- Validate status transitions
- Track status history
- Calculate claim metrics

### 4. Implement Caching Properly

Create cache patterns for all services:

```python
class CacheKeys:
    """Centralized cache key management."""

    @staticmethod
    def customer_by_id(customer_id: UUID) -> str:
        return f"customer:id:{customer_id}"

    @staticmethod
    def customer_by_email(email: str) -> str:
        return f"customer:email:{email}"

    @staticmethod
    def policy_by_id(policy_id: UUID) -> str:
        return f"policy:id:{policy_id}"

    @staticmethod
    def policies_by_customer(customer_id: UUID) -> str:
        return f"customer:{customer_id}:policies"
```

### 5. Add Database Health Checks

Implement in `src/pd_prime_demo/api/v1/health.py`:

```python
@beartype
async def check_database_health(db: Database) -> Result[dict, str]:
    """Check database connectivity and performance."""
    try:
        start = time.time()
        result = await db.fetchval("SELECT 1")
        latency = (time.time() - start) * 1000

        if result != 1:
            return Err("Database returned unexpected result")

        if latency > 10:  # 10ms threshold
            return Err(f"Database latency too high: {latency:.2f}ms")

        return Ok({
            "status": "healthy",
            "latency_ms": round(latency, 2)
        })
    except Exception as e:
        return Err(f"Database connection failed: {str(e)}")
```

### 6. Implement Proper Transaction Patterns

Create a transaction helper:

```python
@beartype
async def with_transaction[T](
    db: Database,
    operation: Callable[[], Awaitable[Result[T, str]]]
) -> Result[T, str]:
    """Execute operation within a transaction with automatic rollback."""
    async with db.transaction():
        try:
            result = await operation()
            if isinstance(result, Err):
                # Transaction will rollback
                return result
            return result
        except Exception as e:
            # Transaction will rollback
            return Err(f"Transaction failed: {str(e)}")
```

## SEARCH TRIGGERS (30-second timeout)

If confidence < 95% on:

- Transaction patterns → Search: "asyncpg transaction best practices"
- Cache invalidation → Search: "redis cache invalidation patterns"
- Error handling → Search: "python result type error handling"

## DELIVERABLES

1. **Fixed Services**: All services with working database queries
2. **Cache Implementation**: Proper caching with invalidation
3. **Transaction Safety**: All writes use transactions
4. **Health Checks**: Database health monitoring
5. **Error Handling**: Comprehensive Result[T, E] usage

## SUCCESS CRITERIA

1. NO mock data returns anywhere
2. All CRUD operations persist to database
3. Cache hit rate > 80% for reads
4. Transaction rollback on errors
5. Health checks return <10ms latency

## PARALLEL COORDINATION

- Coordinate with Agent 01 (Database) for schema
- Agent 03 (Connection Pool) will optimize your queries
- Agent 04 (Quote Model) needs your patterns

Document all fixed TODOs in your completion report!

## ADDITIONAL REQUIREMENT: Admin Services

**IMPORTANT**: You must ALSO read `.sage/wave_contexts/wave_2/AGENT_DEPLOYMENT_SUMMARY.md` to understand the full system context.

### 7. Create Admin Services

You must also implement comprehensive admin services:

#### Create Admin User Service (`src/pd_prime_demo/services/admin/admin_user_service.py`)

```python
"""Admin user management service."""

from typing import List, Optional
from uuid import UUID

from beartype import beartype
from passlib.context import CryptContext

from ...core.cache import Cache
from ...core.database import Database
from ...models.admin import AdminUser, AdminUserCreate, AdminRole
from ..result import Result, Ok, Err

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class AdminUserService:
    """Service for admin user management."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize admin user service."""
        self._db = db
        self._cache = cache

    @beartype
    async def create_admin(
        self,
        admin_data: AdminUserCreate,
        created_by: UUID,
    ) -> Result[AdminUser, str]:
        """Create new admin user with role assignment."""
        # Hash password
        password_hash = pwd_context.hash(admin_data.password)

        # Create admin user
        # Check permissions
        # Assign role
        # Log activity
        pass

    @beartype
    async def update_admin_role(
        self,
        admin_id: UUID,
        role_id: UUID,
        updated_by: UUID,
    ) -> Result[AdminUser, str]:
        """Update admin user's role."""
        # Verify permissions
        # Update role
        # Log activity
        pass

    @beartype
    async def check_permission(
        self,
        admin_id: UUID,
        resource: str,
        action: str,
    ) -> Result[bool, str]:
        """Check if admin has specific permission."""
        # Get admin's role
        # Check role permissions
        # Check super admin status
        pass
```

#### Create System Settings Service (`src/pd_prime_demo/services/admin/system_settings_service.py`)

```python
"""System configuration management service."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from beartype import beartype

from ...core.cache import Cache
from ...core.database import Database
from ..result import Result, Ok, Err


class SystemSettingsService:
    """Service for system configuration management."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize settings service."""
        self._db = db
        self._cache = cache
        self._settings_cache_prefix = "system_settings:"

    @beartype
    async def get_setting(
        self,
        category: str,
        key: str,
    ) -> Result[Any, str]:
        """Get system setting value."""
        # Check cache first
        # Load from database
        # Decrypt if sensitive
        # Return typed value
        pass

    @beartype
    async def update_setting(
        self,
        category: str,
        key: str,
        value: Any,
        updated_by: UUID,
    ) -> Result[bool, str]:
        """Update system setting."""
        # Validate value against rules
        # Encrypt if sensitive
        # Update database
        # Invalidate cache
        # Log change
        pass

    @beartype
    async def get_category_settings(
        self,
        category: str,
    ) -> Result[Dict[str, Any], str]:
        """Get all settings in a category."""
        pass
```

#### Create Admin Activity Logger (`src/pd_prime_demo/services/admin/activity_logger.py`)

```python
"""Admin activity logging service."""

from typing import Any, Dict, Optional
from uuid import UUID
from datetime import datetime

from beartype import beartype

from ...core.database import Database


class AdminActivityLogger:
    """Log all admin activities for audit trail."""

    def __init__(self, db: Database) -> None:
        """Initialize activity logger."""
        self._db = db

    @beartype
    async def log_activity(
        self,
        admin_user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: Optional[UUID] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Log admin activity asynchronously."""
        await self._db.execute(
            """
            INSERT INTO admin_activity_logs (
                admin_user_id, action, resource_type, resource_id,
                old_values, new_values, status, error_message,
                ip_address, user_agent, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            admin_user_id, action, resource_type, resource_id,
            old_values, new_values, status, error_message,
            ip_address, user_agent, datetime.utcnow()
        )
```

### 8. Create Admin API Endpoints

Add admin routers in `src/pd_prime_demo/api/v1/admin/`:

- `admin_users.py` - Admin user management endpoints
- `system_settings.py` - System configuration endpoints
- `audit_logs.py` - Audit log viewing endpoints
- `dashboards.py` - Admin dashboard endpoints
- `rate_management.py` - Rate table administration

### 9. Add Admin Middleware

Create admin authentication middleware in `src/pd_prime_demo/api/middleware/admin_auth.py`:

```python
"""Admin authentication and permission middleware."""

from fastapi import Request, HTTPException
from beartype import beartype


class AdminAuthMiddleware:
    """Verify admin authentication and permissions."""

    @beartype
    async def __call__(self, request: Request, call_next):
        """Check admin auth for protected routes."""
        if request.url.path.startswith("/api/v1/admin"):
            # Verify admin token
            # Check permissions
            # Log access
            pass

        response = await call_next(request)
        return response
```

Make sure all admin services follow the same Result[T, E] pattern and include comprehensive audit logging!
