# Agent 03: Connection Pool Specialist

## YOUR MISSION

Optimize database performance with proper connection pooling, query optimization, and caching strategies for 10,000 concurrent users.

## NO SILENT FALLBACKS PRINCIPLE

### Connection Pool Configuration Requirements

**NEVER use default connection limits without capacity planning:**

```python
# ❌ FORBIDDEN: Magic number connection limits
pool = await asyncpg.create_pool(
    dsn,
    min_size=10,     # Arbitrary default
    max_size=20      # No capacity planning
)

# ✅ REQUIRED: Explicit capacity-based configuration
pool_config = PoolConfig(
    min_connections=calculate_min_connections(expected_rps=1000),
    max_connections=calculate_max_connections(
        db_max_connections=100,
        app_instances=5,
        safety_margin=0.8
    ),
    connection_timeout=30,  # Explicit timeout
    command_timeout=60      # Explicit query timeout
)

if pool_config.max_connections > db_max_connections * 0.8:
    raise ValueError(f"Pool size {pool_config.max_connections} exceeds safe DB limit")
```

**NEVER implement silent connection recovery without configuration:**

```python
# ❌ FORBIDDEN: Silent reconnection attempts
class Database:
    async def execute(self, query):
        try:
            return await self._pool.execute(query)
        except Exception:
            # Silent reconnect attempt
            await self._reconnect()
            return await self._pool.execute(query)

# ✅ REQUIRED: Explicit reconnection policy
class Database:
    def __init__(self, recovery_config: RecoveryConfig):
        if not recovery_config:
            raise ValueError("Recovery configuration required")
        self._recovery = recovery_config

    async def execute(self, query) -> Result[Any, str]:
        try:
            return Ok(await self._pool.execute(query))
        except ConnectionError as e:
            if self._recovery.auto_recover:
                recover_result = await self._attempt_recovery()
                if recover_result.is_err():
                    return Err(f"Connection failed and recovery failed: {e}")
                return await self.execute(query)
            return Err(f"Connection failed: {e}")
```

**NEVER skip pool health validation:**

```python
# ❌ FORBIDDEN: Assume pool is healthy
class PoolManager:
    async def get_connection(self):
        return await self._pool.acquire()  # No health check

# ✅ REQUIRED: Explicit pool health monitoring
class PoolManager:
    async def get_connection(self) -> Result[Connection, str]:
        # Check pool health first
        health = await self.check_pool_health()
        if health.is_err():
            return health

        if self._pool.get_free_size() == 0:
            return Err("Connection pool exhausted")

        try:
            conn = await self._pool.acquire(timeout=self._config.acquire_timeout)
            return Ok(conn)
        except asyncio.TimeoutError:
            return Err("Connection acquisition timeout")
```

### Fail Fast Validation

If ANY connection pool parameter is unconfigured, you MUST:

1. **Calculate explicit limits** based on system capacity
2. **Validate pool size** against database connection limits
3. **Never use framework defaults** without justification
4. **Test connection acquisition** under load during startup

### Explicit Error Remediation

**When connection pool fails:**

- Never retry with silent backoff
- Expose pool metrics (active, idle, failed connections)
- Log exact pool configuration that caused failure
- Provide specific remediation (increase pool size, tune timeouts)

**Required validation for connection management:**

- Pool size calculation based on expected concurrent load
- Connection timeout configuration based on query complexity
- Health check intervals appropriate for failure detection
- Connection leak detection and automatic cleanup
- Database connection limit coordination across app instances

## MANDATORY PRE-WORK

1. Read ALL documents listed in AGENT_TEMPLATE.md FIRST
2. Specifically study:
   - `src/pd_prime_demo/core/database.py` for current implementation
   - `src/pd_prime_demo/core/config.py` for pool settings
   - `.sage/source_documents/DEMO_OVERALL_ARCHITECTURE.md` for performance requirements

## SPECIFIC TASKS

### 1. Enhance Database Connection Pool (`src/pd_prime_demo/core/database.py`)

Current implementation needs optimization:

```python
"""Enhanced database connection with advanced pooling."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

import asyncpg
from beartype import beartype

from .config import Settings


class Database:
    """Enhanced database connection manager with monitoring."""

    def __init__(self, settings: Settings) -> None:
        """Initialize with settings."""
        self._settings = settings
        self._pool: Optional[asyncpg.Pool] = None
        self._read_pool: Optional[asyncpg.Pool] = None  # For read replicas
        self._metrics = {
            "connections_active": 0,
            "connections_idle": 0,
            "queries_total": 0,
            "queries_slow": 0,
            "pool_exhausted_count": 0,
        }

    @beartype
    async def connect(self) -> None:
        """Create connection pools with optimized settings."""
        # Main write pool
        self._pool = await asyncpg.create_pool(
            self._settings.database_url,
            min_size=self._settings.database_pool_min,
            max_size=self._settings.database_pool_max,
            max_inactive_connection_lifetime=600,  # 10 minutes
            command_timeout=30,

            # Performance optimizations
            server_settings={
                'jit': 'off',  # Disable JIT for consistent performance
                'random_page_cost': '1.1',  # SSD optimized
                'effective_cache_size': '4GB',
                'shared_buffers': '256MB',
            },

            # Connection initialization
            init=self._init_connection,
        )

        # Read replica pool (if configured)
        if hasattr(self._settings, 'database_read_url'):
            self._read_pool = await asyncpg.create_pool(
                self._settings.database_read_url,
                min_size=self._settings.database_pool_min * 2,  # More connections for reads
                max_size=self._settings.database_pool_max * 2,
                max_inactive_connection_lifetime=600,
                command_timeout=30,
                init=self._init_read_connection,
            )

    @beartype
    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """Initialize each connection with prepared statements."""
        # Register custom types
        await conn.set_type_codec(
            'jsonb',
            encoder=lambda v: json.dumps(v),
            decoder=lambda v: json.loads(v),
            schema='pg_catalog'
        )

        # Prepare common statements for performance
        await conn.execute("""
            PREPARE get_quote_by_id AS
            SELECT * FROM quotes WHERE id = $1;
        """)

        await conn.execute("""
            PREPARE get_customer_policies AS
            SELECT * FROM policies WHERE customer_id = $1
            ORDER BY created_at DESC LIMIT $2 OFFSET $3;
        """)

    @beartype
    async def _init_read_connection(self, conn: asyncpg.Connection) -> None:
        """Initialize read-only connections."""
        await self._init_connection(conn)
        await conn.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")

    @beartype
    @asynccontextmanager
    async def acquire(self, *, timeout: float = 10.0) -> AsyncGenerator[asyncpg.Connection, None]:
        """Acquire a connection with timeout and monitoring."""
        if not self._pool:
            raise RuntimeError("Database not connected")

        start_time = asyncio.get_event_loop().time()

        try:
            async with self._pool.acquire(timeout=timeout) as conn:
                self._metrics["connections_active"] += 1
                self._metrics["queries_total"] += 1

                yield conn

                # Track slow queries
                duration = asyncio.get_event_loop().time() - start_time
                if duration > 1.0:  # 1 second threshold
                    self._metrics["queries_slow"] += 1

        except asyncpg.PoolTimeout:
            self._metrics["pool_exhausted_count"] += 1
            raise
        finally:
            self._metrics["connections_active"] -= 1

    @beartype
    @asynccontextmanager
    async def acquire_read(self, *, timeout: float = 10.0) -> AsyncGenerator[asyncpg.Connection, None]:
        """Acquire a read-only connection from replica pool."""
        pool = self._read_pool or self._pool
        if not pool:
            raise RuntimeError("Database not connected")

        async with pool.acquire(timeout=timeout) as conn:
            yield conn

    @beartype
    async def execute_many(self, query: str, args: list[tuple]) -> None:
        """Execute many statements efficiently."""
        async with self.acquire() as conn:
            await conn.executemany(query, args)

    @beartype
    async def fetch_one_cached(self, query: str, *args: Any, cache_key: str) -> Optional[asyncpg.Record]:
        """Fetch one row with caching support."""
        # This will be integrated with Redis cache
        # For now, just pass through
        async with self.acquire_read() as conn:
            return await conn.fetchrow(query, *args)

    @beartype
    async def get_pool_stats(self) -> dict[str, Any]:
        """Get connection pool statistics."""
        if not self._pool:
            return {}

        return {
            "size": self._pool.get_size(),
            "free_size": self._pool.get_free_size(),
            "min_size": self._pool.get_min_size(),
            "max_size": self._pool.get_max_size(),
            **self._metrics,
        }
```

### 2. Implement Query Optimization Helper (`src/pd_prime_demo/core/query_optimizer.py`)

```python
"""Query optimization utilities."""

from typing import Any, Optional
import asyncpg
from beartype import beartype

from .database import Database


class QueryOptimizer:
    """Analyze and optimize database queries."""

    def __init__(self, db: Database) -> None:
        """Initialize with database connection."""
        self._db = db

    @beartype
    async def explain_analyze(self, query: str, *args: Any) -> dict[str, Any]:
        """Run EXPLAIN ANALYZE on a query."""
        explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"

        async with self._db.acquire() as conn:
            result = await conn.fetchval(explain_query, *args)
            return result[0]

    @beartype
    async def suggest_indexes(self, table_name: str) -> list[str]:
        """Suggest missing indexes based on query patterns."""
        query = """
            SELECT schemaname, tablename, attname, n_distinct, correlation
            FROM pg_stats
            WHERE tablename = $1
            AND n_distinct > 100
            AND correlation < 0.1
            ORDER BY n_distinct DESC
        """

        async with self._db.acquire_read() as conn:
            stats = await conn.fetch(query, table_name)

        suggestions = []
        for stat in stats:
            suggestions.append(
                f"CREATE INDEX idx_{table_name}_{stat['attname']} "
                f"ON {stat['schemaname']}.{stat['tablename']}({stat['attname']})"
            )

        return suggestions

    @beartype
    async def analyze_slow_queries(self) -> list[dict[str, Any]]:
        """Find slow queries from pg_stat_statements."""
        query = """
            SELECT
                query,
                calls,
                total_exec_time,
                mean_exec_time,
                stddev_exec_time,
                rows
            FROM pg_stat_statements
            WHERE mean_exec_time > 100  -- 100ms threshold
            ORDER BY mean_exec_time DESC
            LIMIT 20
        """

        async with self._db.acquire_read() as conn:
            # Enable pg_stat_statements if needed
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
            return await conn.fetch(query)
```

### 3. Add Connection Pool Monitoring (`src/pd_prime_demo/api/v1/monitoring.py`)

```python
"""Database monitoring endpoints."""

from fastapi import APIRouter, Depends
from beartype import beartype

from ...core.database import Database
from ..dependencies import get_db


router = APIRouter()


@router.get("/pool-stats")
@beartype
async def get_pool_stats(db: Database = Depends(get_db)) -> dict:
    """Get connection pool statistics."""
    return await db.get_pool_stats()


@router.get("/slow-queries")
@beartype
async def get_slow_queries(db: Database = Depends(get_db)) -> list[dict]:
    """Get slow query analysis."""
    optimizer = QueryOptimizer(db)
    return await optimizer.analyze_slow_queries()
```

### 4. Configure pgBouncer (`config/pgbouncer.ini`)

```ini
[databases]
# Main database with transaction pooling
pd_prime_demo = host=localhost port=5432 dbname=pd_prime_demo

# Read replica with session pooling
pd_prime_demo_read = host=read-replica.example.com port=5432 dbname=pd_prime_demo

[pgbouncer]
# Connection limits
pool_mode = transaction
max_client_conn = 10000
default_pool_size = 25
min_pool_size = 10
reserve_pool_size = 5
reserve_pool_timeout = 3

# Performance tuning
server_lifetime = 3600
server_idle_timeout = 600
query_timeout = 30
query_wait_timeout = 10

# Logging
log_connections = 0
log_disconnections = 0
log_pooler_errors = 1
stats_period = 60

# Authentication
auth_type = md5
auth_file = /etc/pgbouncer/userlist.txt
```

### 5. Add Database Health Monitoring Script (`scripts/monitor_db_health.py`)

Create a monitoring script that tracks:

- Connection pool utilization
- Query performance metrics
- Cache hit rates
- Replication lag
- Index usage statistics

## SEARCH TRIGGERS (30-second timeout)

If confidence < 95% on:

- Connection pooling → Search: "asyncpg connection pool best practices"
- pgBouncer config → Search: "pgbouncer configuration high traffic"
- Query optimization → Search: "postgresql query optimization techniques"

## DELIVERABLES

1. **Enhanced Database Class**: With pool monitoring and read replicas
2. **Query Optimizer**: Automated query analysis
3. **pgBouncer Config**: Production-ready configuration
4. **Monitoring Endpoints**: Pool and query statistics
5. **Health Check Script**: Proactive monitoring

## SUCCESS CRITERIA

1. Connection pool never exhausted under load
2. 99% of queries complete in <100ms
3. Read queries use replica pool
4. Automatic slow query detection
5. Zero connection leaks

## PARALLEL COORDINATION

- Agent 01 creates tables you'll optimize
- Agent 02 uses your connection methods
- Agent 05-10 depend on your performance

Document all optimization techniques in your completion report!

## ADDITIONAL REQUIREMENT: Admin Query Optimization

**IMPORTANT**: You must ALSO read `.sage/wave_contexts/wave_2/AGENT_DEPLOYMENT_SUMMARY.md` to understand the full system context.

### 6. Optimize Admin Queries

Admin dashboards and reports require special optimization due to their complex aggregation queries:

#### Create Admin Query Optimizer (`src/pd_prime_demo/core/admin_query_optimizer.py`)

```python
"""Specialized query optimization for admin operations."""

from typing import Dict, List, Any
from datetime import datetime, timedelta

from beartype import beartype

from .database import Database
from .cache import Cache


class AdminQueryOptimizer:
    """Optimize complex admin queries and dashboards."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize admin query optimizer."""
        self._db = db
        self._cache = cache
        self._materialized_views = {}

    @beartype
    async def create_admin_materialized_views(self) -> None:
        """Create materialized views for admin dashboards."""
        views = [
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS admin_daily_metrics AS
            SELECT
                date_trunc('day', created_at) as metric_date,
                COUNT(DISTINCT customer_id) as unique_customers,
                COUNT(*) FILTER (WHERE status = 'quoted') as quotes_created,
                COUNT(*) FILTER (WHERE status = 'bound') as quotes_converted,
                AVG(total_premium) as avg_premium,
                SUM(total_premium) FILTER (WHERE status = 'bound') as total_bound_premium
            FROM quotes
            GROUP BY metric_date
            WITH DATA;

            CREATE INDEX idx_admin_daily_metrics_date ON admin_daily_metrics(metric_date);
            """,

            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS admin_user_activity_summary AS
            SELECT
                au.id as admin_user_id,
                au.email,
                COUNT(aal.id) as total_actions,
                COUNT(DISTINCT DATE(aal.created_at)) as active_days,
                MAX(aal.created_at) as last_activity,
                COUNT(*) FILTER (WHERE aal.status = 'failed') as failed_actions
            FROM admin_users au
            LEFT JOIN admin_activity_logs aal ON au.id = aal.admin_user_id
            GROUP BY au.id, au.email
            WITH DATA;
            """,

            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS admin_system_health AS
            SELECT
                COUNT(DISTINCT ws.connection_id) as active_connections,
                AVG(ae.duration_ms) as avg_api_response_ms,
                COUNT(*) FILTER (WHERE ae.duration_ms > 1000) as slow_requests,
                COUNT(DISTINCT ae.user_id) as active_users_today
            FROM websocket_connections ws
            CROSS JOIN LATERAL (
                SELECT duration_ms, user_id
                FROM analytics_events
                WHERE created_at > NOW() - INTERVAL '1 day'
            ) ae
            WITH DATA;
            """
        ]

        for view_sql in views:
            await self._db.execute(view_sql)

    @beartype
    async def refresh_materialized_views(self) -> None:
        """Refresh materialized views for admin dashboards."""
        views_to_refresh = [
            "admin_daily_metrics",
            "admin_user_activity_summary",
            "admin_system_health"
        ]

        for view in views_to_refresh:
            await self._db.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")

    @beartype
    async def get_admin_dashboard_metrics(self) -> Dict[str, Any]:
        """Get optimized admin dashboard metrics."""
        # Use materialized views for complex aggregations
        # Cache results for 5 minutes
        cache_key = "admin:dashboard:metrics"
        cached = await self._cache.get(cache_key)

        if cached:
            return cached

        # Parallel queries using connection pool
        queries = {
            "daily_metrics": """
                SELECT * FROM admin_daily_metrics
                WHERE metric_date >= CURRENT_DATE - INTERVAL '30 days'
                ORDER BY metric_date DESC
            """,
            "user_activity": """
                SELECT * FROM admin_user_activity_summary
                ORDER BY last_activity DESC NULLS LAST
                LIMIT 20
            """,
            "system_health": """
                SELECT * FROM admin_system_health
            """
        }

        results = {}
        for name, query in queries.items():
            results[name] = await self._db.fetch(query)

        await self._cache.set(cache_key, results, 300)  # 5 minute cache
        return results
```

#### Add Admin-Specific Connection Pool

```python
# In your enhanced Database class, add:

async def create_admin_pool(self) -> None:
    """Create dedicated connection pool for admin queries."""
    # Admin queries may be complex and long-running
    # Use separate pool to avoid blocking main app
    self._admin_pool = await asyncpg.create_pool(
        self._settings.database_url,
        min_size=2,
        max_size=10,
        command_timeout=60,  # Allow longer queries

        # Admin-optimized settings
        server_settings={
            'work_mem': '256MB',  # More memory for complex sorts
            'temp_buffers': '32MB',
            'maintenance_work_mem': '256MB',
        }
    )
```

### 7. Create Admin Performance Monitoring

Add monitoring specifically for admin operations:

```python
@beartype
async def monitor_admin_query_performance(self) -> Dict[str, Any]:
    """Monitor admin-specific query performance."""
    metrics = {
        "admin_pool_stats": await self.get_admin_pool_stats(),
        "slowest_admin_queries": await self.get_slowest_admin_queries(),
        "materialized_view_freshness": await self.check_view_freshness(),
        "admin_cache_hit_rate": await self.get_admin_cache_stats(),
    }

    return metrics
```

Make sure admin queries don't impact main application performance!
