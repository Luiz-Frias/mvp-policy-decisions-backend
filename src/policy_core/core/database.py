# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Enhanced database connection management with advanced pooling and monitoring."""

import asyncio
import contextlib
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

import asyncpg
import asyncpg.exceptions  # type: ignore[import-untyped]
from attrs import field, frozen
from beartype import beartype
from pydantic import Field

from policy_core.models.base import BaseModelConfig

from .config import get_settings
from .redis_connection_manager import RedisConnectionManager
from .result_types import Err, Ok, Result

logger = logging.getLogger(__name__)

# Auto-generated models


@beartype
class ServerSettingsMapping(BaseModelConfig):
    """Structured model replacing dict[str, str] usage."""

    key: str = Field(..., min_length=1, description="Mapping key")
    value: str = Field(..., min_length=1, description="Mapping value")


@beartype
class PreparedStatementsMapping(BaseModelConfig):
    """Structured model replacing dict[str, str] usage."""

    key: str = Field(..., min_length=1, description="Mapping key")
    value: str = Field(..., min_length=1, description="Mapping value")


@beartype
class MetricsData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@frozen
class DatabaseConfig:
    """Backward compatibility database configuration."""

    url: str = field()
    min_size: int = field(default=5)
    max_size: int = field(default=20)
    command_timeout: float = field(default=30.0)
    statement_cache_size: int = field(default=100)


@frozen
class PoolConfig:
    """Immutable pool configuration with capacity planning."""

    min_connections: int = field()
    max_connections: int = field()
    connection_timeout: float = field(default=30.0)
    command_timeout: float = field(default=60.0)
    max_inactive_connection_lifetime: float = field(default=600.0)
    server_settings: ServerSettingsMapping = field(factory=dict)


@frozen
class PoolMetrics:
    """Immutable pool metrics snapshot."""

    size: int = field()
    free_size: int = field()
    min_size: int = field()
    max_size: int = field()
    connections_active: int = field()
    connections_idle: int = field()
    queries_total: int = field()
    queries_slow: int = field()
    pool_exhausted_count: int = field()
    average_query_time_ms: float = field()


@frozen
class RecoveryConfig:
    """Connection recovery configuration."""

    auto_recover: bool = field(default=True)
    max_retry_attempts: int = field(default=3)
    retry_delay_seconds: float = field(default=1.0)
    exponential_backoff: bool = field(default=True)


class Database:
    """Enhanced database connection manager with monitoring and optimization.

    ``Database`` now **optionally** wraps an existing :class:`asyncpg.Connection`.
    This is purely for backward-compatibility with helper code that used to do

    >>> db_conn = await get_db_connection()
    >>> database = Database(db_conn)

    When a direct connection is supplied we bypass the internal pool-acquire
    logic inside convenience helpers like :py:meth:`fetch` and route queries
    straight to that connection.  Pool-based usage continues to work
    unchanged.
    """

    def __init__(
        self, connection: asyncpg.Connection | None = None
    ) -> None:  # noqa: D401
        """Create the manager.

        Args:
            connection: Optional existing connection obtained elsewhere
                (e.g., FastAPI dependency injection).  If ``None`` the caller
                must invoke :py:meth:`connect` to create a pool before issuing
                queries.
        """

        # Direct connection takes precedence over pools.
        self._direct_conn: asyncpg.Connection | None = connection

        self._pool: asyncpg.Pool | None = None
        self._read_pool: asyncpg.Pool | None = None
        self._admin_pool: asyncpg.Pool | None = None
        self._settings = get_settings()
        self._recovery_config = RecoveryConfig()
        self._main_config: PoolConfig | None = None
        self._conn_manager: RedisConnectionManager | None = None

        # Performance metrics
        self._metrics: MetricsData = {
            "connections_active": 0,
            "connections_idle": 0,
            "queries_total": 0,
            "queries_slow": 0,
            "pool_exhausted_count": 0,
            "query_times_ms": [],
            "connection_errors": 0,
            "pool_wait_times_ms": [],
            "connection_acquisitions": 0,
            "connection_releases": 0,
            "warmup_time_ms": 0,
        }

        # Prepared statement cache
        self._prepared_statements: PreparedStatementsMapping = {}

    @beartype
    def calculate_min_connections(self, expected_rps: int) -> int:
        """Calculate minimum connections based on expected requests per second."""
        # Rule: 1 connection per 50 RPS with minimum of 5
        return max(5, expected_rps // 50)

    @beartype
    def calculate_max_connections(
        self,
        db_max_connections: int,
        app_instances: int,
        safety_margin: float = 0.8,
    ) -> int:
        """Calculate maximum connections with safety margin."""
        # Reserve connections: 80% for app, 20% for admin/maintenance
        available_for_app = int(db_max_connections * safety_margin)
        per_instance = available_for_app // app_instances

        # Ensure we don't exceed safe limits
        return min(per_instance, 100)  # Cap at 100 per instance

    @beartype
    def _get_pool_config(self, pool_type: str = "main") -> PoolConfig:
        """Get pool configuration based on capacity planning and performance optimization."""
        # CRITICAL: Drastically reduced pool sizes to prevent connection exhaustion
        # Database likely has max_connections=100, and we need to share with other services
        
        if pool_type == "admin":
            # Admin pool - minimal connections for occasional queries
            return PoolConfig(
                min_connections=1,  # Reduced from 10
                max_connections=2,  # Reduced from 20
                connection_timeout=5.0,
                command_timeout=10.0,
                server_settings={
                    "application_name": "policy_core_admin",
                    "timezone": "UTC",
                },
            )

        # Main pool configuration - Railway optimized
        # Railway PostgreSQL typically has max_connections=100
        # We want to be conservative: 3 pools × max_conn should be < 30
        if pool_type == "main":
            min_conn = 2
            max_conn = 8  # Main pool gets more connections
        elif pool_type == "read":
            min_conn = 1
            max_conn = 5  # Read pool moderate
        else:
            # Default conservative settings
            min_conn = 1
            max_conn = 3

        # Connection-level settings only (no server-level parameters)
        server_settings = {
            "application_name": "policy_core",
            "timezone": "UTC",
        }

        if pool_type == "read":
            # Read replicas with conservative connections
            min_conn = max(min_conn, 5)  # Reduced from 30 to 5
            max_conn = min(max_conn * 1.5, 30)  # Reduced from 80 to 30 max
            # Ensure min_conn is not greater than max_conn for read pool
            if min_conn > max_conn:
                min_conn = min(min_conn, max_conn)
            server_settings.update(
                {
                    "application_name": "policy_core_read",
                    "default_transaction_read_only": "on",
                }
            )

        return PoolConfig(
            min_connections=min_conn,
            max_connections=max_conn,
            connection_timeout=5.0,  # Reduced from 30.0 for faster failure detection
            command_timeout=10.0,  # Reduced from 60.0 for testing
            max_inactive_connection_lifetime=self._settings.database_max_inactive_connection_lifetime,
            server_settings=server_settings,
        )

    @beartype
    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """Initialize each connection with optimizations."""
        logger.info("🚨 NEW CODE RUNNING - _init_connection WITH TRY/CATCH - BUILD 20250715")
        
        # Register custom types
        await conn.set_type_codec(  # type: ignore[attr-defined]
            "jsonb",
            encoder=lambda v: json.dumps(v),
            decoder=lambda v: json.loads(v),
            schema="pg_catalog",
        )

        # Prepare common statements for performance
        self._prepared_statements = {
            "get_quote_by_id": """
                SELECT * FROM quotes WHERE id = $1
            """,
            "get_customer_policies": """
                SELECT * FROM policies
                WHERE customer_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
            """,
            "get_policy_by_number": """
                SELECT * FROM policies WHERE policy_number = $1
            """,
            "check_quote_exists": """
                SELECT EXISTS(SELECT 1 FROM quotes WHERE quote_number = $1)
            """,
        }

        # Try to prepare statements, but don't fail if tables don't exist yet
        # This handles the case where migrations haven't run yet
        for name, query in self._prepared_statements.items():
            try:
                await conn.execute(f"PREPARE {name} AS {query}")
            except asyncpg.exceptions.UndefinedTableError:
                # Tables don't exist yet - migrations probably haven't run
                logger.warning(f"Cannot prepare statement '{name}' - table doesn't exist yet. This is normal during initial setup.")
            except Exception as e:
                # Log other errors but don't fail initialization
                logger.error(f"Failed to prepare statement '{name}': {e}")

    @beartype
    async def _init_read_connection(self, conn: asyncpg.Connection) -> None:
        """Initialize read-only connections."""
        await self._init_connection(conn)
        await conn.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")

    @beartype
    async def _setup_connection(self, conn: asyncpg.Connection) -> None:
        """Setup connection with optimizations."""
        # Enable TCP keepalive for better connection health detection
        # Note: This would typically be done at the socket level
        # For asyncpg, we ensure proper connection state
        await conn.execute("SELECT 1")  # Simple health check

        # Set connection-level optimizations
        await conn.execute(
            """
            SET statement_timeout = '30s';
            SET lock_timeout = '10s';
            SET idle_in_transaction_session_timeout = '60s';
        """
        )

    @beartype
    async def _warm_connection_pool(self) -> None:
        """Pre-warm connection pool to avoid cold start penalties."""
        if not self._pool:
            return

        import time

        warmup_start = time.perf_counter()

        # Acquire and immediately release connections to warm the pool
        connections = []
        successful_warmups = 0

        try:
            # Based on Agent 03 audit: warm more connections to reduce initial timeout rates
            assert self._pool is not None  # Help MyPy understand the control flow
            # Target 80% of max_size for aggressive pre-warming
            # Note: asyncpg Pool doesn't expose direct size getters in newer versions
            # Use the config values we set during pool creation
            target_warmup = (
                int(self._main_config.max_connections * 0.8)
                if self._main_config
                else 20
            )

            # Parallel connection establishment for faster warming
            batch_size = 10  # Increased from 5

            async def warm_single_connection() -> bool:
                """Warm a single connection."""
                try:
                    if self._pool is None:
                        return False
                    conn: Any = await self._pool.acquire().__aenter__()
                    connections.append(conn)

                    # Perform initialization queries to fully warm the connection
                    await asyncio.gather(
                        conn.fetchval("SELECT 1"),
                        conn.fetchval("SELECT version()"),
                        conn.fetchval("SELECT current_timestamp"),
                        conn.fetchval("SELECT pg_backend_pid()"),
                    )
                    return True
                except Exception:
                    return False

            # Warm connections in parallel batches
            for batch_start in range(0, target_warmup, batch_size):
                batch_end = min(batch_start + batch_size, target_warmup)
                batch_tasks = []

                for i in range(batch_start, batch_end):
                    batch_tasks.append(warm_single_connection())

                # Execute batch in parallel
                results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                successful_warmups += sum(1 for r in results if r is True)

                # No delay between batches - we want fast warming

            warmup_duration = (time.perf_counter() - warmup_start) * 1000
            self._metrics["warmup_time_ms"] = warmup_duration

            print(
                f"🔥 Pool warmed: {successful_warmups}/{target_warmup} connections in {warmup_duration:.1f}ms"
            )

        except Exception as e:
            # Pool warming is best-effort, don't fail startup
            print(f"⚠️ Pool warming partially failed: {str(e)}")
        finally:
            # Release all warmed connections back to pool
            release_tasks: list[Any] = []
            for conn in connections:
                # asyncpg pool connections are managed by context managers
                # We don't need to manually release them
                pass

            # Release all connections in parallel
            if release_tasks:
                await asyncio.gather(*release_tasks, return_exceptions=True)

    @beartype
    async def connect(self) -> None:
        """Create connection pools with optimized settings."""
        if self._pool is not None:
            return

        # Initialize Redis connection manager if enabled
        if self._settings.redis_url:
            try:
                self._conn_manager = RedisConnectionManager()
                await self._conn_manager.initialize()
                logger.info("✅ Redis connection manager initialized")
            except Exception as e:
                logger.warning(f"Redis connection manager init failed: {e}")
                self._conn_manager = None

        # Main write pool configuration
        main_config = self._get_pool_config("main")
        self._main_config = main_config  # Save for later use

        # asyncpg expects postgresql:// URLs, not postgresql+driver:// format
        # Remove any driver specification from the URL
        db_url = self._settings.effective_database_url
        if db_url.startswith("postgresql+"):
            # Remove the +driver part (e.g., postgresql+asyncpg:// -> postgresql://)
            db_url = "postgresql://" + db_url.split("://", 1)[1]
        
        # Log the database we're connecting to (sanitized)
        import urllib.parse
        parsed = urllib.parse.urlparse(db_url)
        logger.info(f"🔗 Connecting to database: {parsed.hostname}:{parsed.port}/{parsed.path.lstrip('/')}")
        
        self._pool = await asyncpg.create_pool(
            db_url,
            min_size=main_config.min_connections,
            max_size=main_config.max_connections,
            max_inactive_connection_lifetime=main_config.max_inactive_connection_lifetime,
            command_timeout=main_config.command_timeout,
            server_settings=main_config.server_settings,
            init=self._init_connection,
            # Advanced connection pool optimizations
            setup=self._setup_connection,
            max_queries=50000,  # Rotate connections after 50k queries
        )

        # Pre-warm the connection pool for better initial performance
        await self._warm_connection_pool()

        # Read replica pool (if configured)
        if self._settings.database_read_url:
            read_config = self._get_pool_config("read")
            self._read_pool = await asyncpg.create_pool(
                self._settings.database_read_url,
                min_size=read_config.min_connections,
                max_size=read_config.max_connections,
                max_inactive_connection_lifetime=read_config.max_inactive_connection_lifetime,
                command_timeout=read_config.command_timeout,
                server_settings=read_config.server_settings,
                init=self._init_read_connection,
            )

        # Admin pool for complex queries
        if self._settings.database_admin_pool_enabled:
            admin_config = self._get_pool_config("admin")
            self._admin_pool = await asyncpg.create_pool(
                self._settings.effective_database_url,
                min_size=admin_config.min_connections,
                max_size=admin_config.max_connections,
                max_inactive_connection_lifetime=admin_config.max_inactive_connection_lifetime,
                command_timeout=admin_config.command_timeout,
                server_settings=admin_config.server_settings,
                init=self._init_connection,
            )

    @beartype
    async def disconnect(self) -> None:
        """Close all connection pools."""
        pools = [self._pool, self._read_pool, self._admin_pool]
        for pool in pools:
            if pool is not None:
                try:
                    # Add timeout to prevent hanging
                    await asyncio.wait_for(pool.close(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(
                        "Pool close timed out after 5 seconds - forcing termination"
                    )
                    # Force terminate all connections
                    pool.terminate()

        self._pool = None
        self._read_pool = None
        self._admin_pool = None

    @beartype
    async def check_pool_health(self) -> Result[str, str]:
        """Check pool health before operations."""
        if self._pool is None:
            return Err("Database pool not initialized")

        # asyncpg Pool doesn't expose size methods in newer versions
        # We'll use the _holders attribute if available, otherwise estimate
        pool_size = (
            len(getattr(self._pool, "_holders", []))
            if hasattr(self._pool, "_holders")
            else (self._main_config.max_connections if self._main_config else 20)
        )
        free_size = (
            len([h for h in getattr(self._pool, "_holders", []) if h._con is None])
            if hasattr(self._pool, "_holders")
            else 0
        )

        # Check if pool is exhausted
        if free_size == 0:
            self._metrics["pool_exhausted_count"] += 1
            return Err(f"Connection pool exhausted: {pool_size} connections in use")

        # Check if pool is near capacity
        utilization = (pool_size - free_size) / pool_size
        if utilization > 0.9:
            return Ok(f"Warning: Pool at {utilization:.0%} capacity")

        return Ok("Pool healthy")

    @contextlib.asynccontextmanager
    @beartype
    async def acquire(
        self, *, timeout: float | None = None
    ) -> AsyncIterator[asyncpg.Connection]:
        """Acquire a connection with monitoring and health checks."""
        if self._pool is None:
            raise RuntimeError("Database not connected")

        # Check pool health first
        health = await self.check_pool_health()
        if health.is_err():
            err_msg = health.err_value
            if err_msg and isinstance(err_msg, str) and "exhausted" in err_msg:
                # Use TimeoutError for pool timeout
                raise TimeoutError("Pool exhausted")

        timeout = timeout or self._settings.database_pool_timeout
        start_time = time.perf_counter()
        acquisition_start = start_time

        try:
            async with asyncio.timeout(timeout), self._pool.acquire() as conn:
                acquisition_time_ms = (time.perf_counter() - acquisition_start) * 1000
                self._metrics["pool_wait_times_ms"].append(acquisition_time_ms)
                self._metrics["connection_acquisitions"] += 1
                self._metrics["connections_active"] += 1
                # Estimate idle connections based on pool internals
                self._metrics["connections_idle"] = (
                    len(
                        [
                            h
                            for h in getattr(self._pool, "_holders", [])
                            if h._con is None
                        ]
                    )
                    if hasattr(self._pool, "_holders")
                    else 0
                )
                self._metrics["queries_total"] += 1

                # Keep only last 1000 wait time measurements
                if len(self._metrics["pool_wait_times_ms"]) > 1000:
                    self._metrics["pool_wait_times_ms"] = self._metrics[
                        "pool_wait_times_ms"
                    ][-1000:]

                yield conn

                # Track query performance
                duration_ms = (time.perf_counter() - start_time) * 1000
                self._metrics["query_times_ms"].append(duration_ms)

                # Keep only last 1000 measurements
                if len(self._metrics["query_times_ms"]) > 1000:
                    self._metrics["query_times_ms"] = self._metrics["query_times_ms"][
                        -1000:
                    ]

                # Track slow queries
                if duration_ms > 1000:  # 1 second threshold
                    self._metrics["queries_slow"] += 1

                self._metrics["connection_releases"] += 1

        except TimeoutError:
            self._metrics["pool_exhausted_count"] += 1
            raise
        except Exception:
            self._metrics["connection_errors"] += 1
            raise
        finally:
            self._metrics["connections_active"] = max(
                0, self._metrics["connections_active"] - 1
            )

    @contextlib.asynccontextmanager
    @beartype
    async def acquire_read(
        self, *, timeout: float | None = None
    ) -> AsyncIterator[asyncpg.Connection]:
        """Acquire a read-only connection from replica pool."""
        pool = self._read_pool or self._pool
        if pool is None:
            raise RuntimeError("Database not connected")

        timeout = timeout or self._settings.database_pool_timeout
        async with asyncio.timeout(timeout), pool.acquire() as conn:
            yield conn

    @contextlib.asynccontextmanager
    @beartype
    async def acquire_admin(
        self, *, timeout: float | None = None
    ) -> AsyncIterator[asyncpg.Connection]:
        """Acquire an admin connection for complex queries."""
        pool = self._admin_pool or self._pool
        if pool is None:
            raise RuntimeError("Database not connected")

        # Admin queries may take longer
        timeout = timeout or 60.0
        async with asyncio.timeout(timeout), pool.acquire() as conn:
            yield conn

    @beartype
    async def execute_with_retry(
        self,
        query: str,
        *args: Any,
        max_attempts: int = 3,
    ) -> Any:
        """Execute query with automatic retry on connection errors."""
        last_error = None

        for attempt in range(max_attempts):
            try:
                async with self.acquire() as conn:
                    result = await conn.execute(query, *args)
                    return Ok(result)
            except (
                asyncpg.exceptions.PostgresConnectionError,
                asyncpg.PostgresError,
            ) as e:
                last_error = e
                if attempt < max_attempts - 1:
                    # Exponential backoff
                    delay = self._recovery_config.retry_delay_seconds * (2**attempt)
                    await asyncio.sleep(delay)
                    continue
            except Exception as e:
                return Err(f"Query execution failed: {str(e)}")

        return Err(
            f"Connection failed after {max_attempts} attempts: {str(last_error)}"
        )

    @beartype
    async def execute_many(self, query: str, args: list[tuple[Any, ...]]) -> None:
        """Execute many statements efficiently in a batch."""
        async with self.acquire() as conn:
            # Use execute in a loop instead of executemany
            for arg_tuple in args:
                await conn.execute(query, *arg_tuple)

    @beartype
    async def get_pool_stats(self) -> PoolMetrics:
        """Get comprehensive pool statistics."""
        if self._pool is None:
            return PoolMetrics(
                size=0,
                free_size=0,
                min_size=0,
                max_size=0,
                connections_active=0,
                connections_idle=0,
                queries_total=0,
                queries_slow=0,
                pool_exhausted_count=0,
                average_query_time_ms=0.0,
            )

        # Calculate average query time
        avg_query_time = 0.0
        if self._metrics["query_times_ms"]:
            avg_query_time = sum(self._metrics["query_times_ms"]) / len(
                self._metrics["query_times_ms"]
            )

        return PoolMetrics(
            # Use pool config values and estimates since newer asyncpg doesn't expose these methods
            size=(
                len(getattr(self._pool, "_holders", []))
                if hasattr(self._pool, "_holders")
                else 0
            ),
            free_size=(
                len([h for h in getattr(self._pool, "_holders", []) if h._con is None])
                if hasattr(self._pool, "_holders")
                else 0
            ),
            min_size=self._main_config.min_connections if self._main_config else 5,
            max_size=self._main_config.max_connections if self._main_config else 20,
            connections_active=self._metrics["connections_active"],
            connections_idle=self._metrics["connections_idle"],
            queries_total=self._metrics["queries_total"],
            queries_slow=self._metrics["queries_slow"],
            pool_exhausted_count=self._metrics["pool_exhausted_count"],
            average_query_time_ms=avg_query_time,
        )

    @beartype
    async def get_detailed_pool_metrics(self) -> dict[str, Any]:  # SYSTEM_BOUNDARY: Performance monitoring needs flexible dict structure
        """Get detailed pool metrics for advanced monitoring."""
        basic_stats = await self.get_pool_stats()

        # Calculate additional metrics
        avg_wait_time = 0.0
        p95_wait_time = 0.0
        if self._metrics["pool_wait_times_ms"]:
            wait_times = self._metrics["pool_wait_times_ms"]
            avg_wait_time = sum(wait_times) / len(wait_times)
            if len(wait_times) >= 20:
                sorted_times = sorted(wait_times)
                p95_index = int(len(sorted_times) * 0.95)
                p95_wait_time = sorted_times[p95_index]

        # Connection efficiency metrics
        total_acquisitions = self._metrics["connection_acquisitions"]
        acquisition_error_rate = 0.0
        if total_acquisitions > 0:
            acquisition_error_rate = (
                self._metrics["connection_errors"] / total_acquisitions
            )

        return {
            "basic_stats": {
                "size": basic_stats.size,
                "free_size": basic_stats.free_size,
                "min_size": basic_stats.min_size,
                "max_size": basic_stats.max_size,
                "utilization_percent": (
                    (basic_stats.size - basic_stats.free_size) / basic_stats.size * 100
                    if basic_stats.size > 0
                    else 0
                ),
            },
            "performance_metrics": {
                "queries_total": basic_stats.queries_total,
                "queries_slow": basic_stats.queries_slow,
                "average_query_time_ms": basic_stats.average_query_time_ms,
                "slow_query_rate": (
                    basic_stats.queries_slow / basic_stats.queries_total
                    if basic_stats.queries_total > 0
                    else 0
                ),
            },
            "connection_metrics": {
                "total_acquisitions": total_acquisitions,
                "total_releases": self._metrics["connection_releases"],
                "connection_errors": self._metrics["connection_errors"],
                "acquisition_error_rate": acquisition_error_rate,
                "pool_exhausted_count": basic_stats.pool_exhausted_count,
                "average_wait_time_ms": avg_wait_time,
                "p95_wait_time_ms": p95_wait_time,
            },
            "health_indicators": {
                "is_healthy": basic_stats.pool_exhausted_count == 0
                and acquisition_error_rate < 0.01,
                "warning_signs": self._get_warning_signs(
                    basic_stats, acquisition_error_rate
                ),
            },
        }

    @beartype
    def _get_warning_signs(self, stats: PoolMetrics, error_rate: float) -> list[str]:
        """Identify potential issues with the connection pool."""
        warnings = []

        # High utilization
        utilization = (
            (stats.size - stats.free_size) / stats.size if stats.size > 0 else 0
        )
        if utilization > 0.9:
            warnings.append(f"High pool utilization: {utilization:.1%}")

        # Frequent exhaustion
        if stats.pool_exhausted_count > 0:
            warnings.append(f"Pool exhausted {stats.pool_exhausted_count} times")

        # High error rate
        if error_rate > 0.01:
            warnings.append(f"High connection error rate: {error_rate:.1%}")

        # High query times
        if stats.average_query_time_ms > 100:
            warnings.append(
                f"High average query time: {stats.average_query_time_ms:.1f}ms"
            )

        # Many slow queries
        if stats.queries_total > 0:
            slow_rate = stats.queries_slow / stats.queries_total
            if slow_rate > 0.05:
                warnings.append(f"High slow query rate: {slow_rate:.1%}")

        return warnings

    @beartype
    async def health_check(self) -> Result[str, str]:
        """Perform comprehensive health check."""
        try:
            # Check main pool
            async with self.acquire(timeout=5.0) as conn:
                result = await conn.fetchval("SELECT 1")
                if result != 1:
                    return Err("Health check query failed")

            # Check read pool if available
            if self._read_pool:
                async with self.acquire_read(timeout=5.0) as conn:
                    result = await conn.fetchval("SELECT 1")
                    if result != 1:
                        return Err("Read pool health check failed")

            # Check pool utilization
            stats = await self.get_pool_stats()
            if stats.free_size == 0:
                return Err("Connection pool exhausted")

            utilization = (
                (stats.size - stats.free_size) / stats.size if stats.size > 0 else 0
            )
            if utilization > 0.9:
                return Ok(
                    f"Warning: Pool at {utilization:.0%} capacity"
                )  # Unhealthy but operational

            return Ok("Healthy")

        except Exception as e:
            return Err(f"Health check failed: {str(e)}")

    # Backward compatibility methods
    @beartype
    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query without returning results."""
        # Shortcut when wrapping a direct connection – no retries.
        if self._direct_conn is not None:
            return await self._direct_conn.execute(query, *args)

        result = await self.execute_with_retry(query, *args)
        if result.is_err():
            raise RuntimeError(result.err_value)
        return str(result.ok_value)

    @beartype
    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        """Execute a query and fetch all results."""
        # If wrapping a direct connection, use it.
        if self._direct_conn is not None:
            return await self._direct_conn.fetch(query, *args)

        async with self.acquire_read() as conn:
            return await conn.fetch(query, *args)

    @beartype
    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        """Execute a query and fetch a single row."""
        if self._direct_conn is not None:
            return await self._direct_conn.fetchrow(query, *args)

        async with self.acquire_read() as conn:
            return await conn.fetchrow(query, *args)

    @beartype
    async def fetchval(self, query: str, *args: Any) -> Any:
        """Execute a query and fetch a single value."""
        if self._direct_conn is not None:
            return await self._direct_conn.fetchval(query, *args)

        async with self.acquire_read() as conn:
            return await conn.fetchval(query, *args)

    @contextlib.asynccontextmanager
    @beartype
    async def transaction(self) -> AsyncIterator[asyncpg.Connection]:
        """Create a database transaction context."""
        if self._direct_conn is not None:
            # Transaction handling on a single connection; delegate directly.
            async with self._direct_conn.transaction():
                yield self._direct_conn
            return

        async with self.acquire() as conn:
            async with conn.transaction():
                yield conn

    @property
    @beartype
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._pool is not None


# Global database instance
_database: Database | None = None


@beartype
def get_database() -> Database:
    """Get global database instance."""
    global _database
    if _database is None:
        _database = Database()
    return _database


@beartype
async def init_db_pool() -> None:
    """Initialize the database connection pool."""
    db = get_database()
    await db.connect()


@beartype
async def close_db_pool() -> None:
    """Close the database connection pool."""
    db = get_database()
    await db.disconnect()


@contextlib.asynccontextmanager
@beartype
async def get_db_session() -> AsyncIterator[asyncpg.Connection]:
    """Get a database connection for dependency injection."""
    db = get_database()
    async with db.acquire() as conn:
        yield conn
# SYSTEM_BOUNDARY: Database layer performance monitoring requires flexible dict structures
