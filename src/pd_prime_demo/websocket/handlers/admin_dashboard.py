"""Admin dashboard WebSocket handler for real-time monitoring."""

import asyncio
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

from pd_prime_demo.core.result_types import Err, Ok, Result

from ...core.cache import Cache
from ...core.database import Database
from ..manager import ConnectionManager, MessageType, WebSocketMessage
from pd_prime_demo.models.base import BaseModelConfig
from ..message_models import create_websocket_message_data


@beartype
class CacheData(BaseModelConfig):
    """Cache data model."""

    hit_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    total_hits: int = Field(default=0, ge=0)
    total_misses: int = Field(default=0, ge=0)
    memory_usage_mb: float = Field(default=0.0, ge=0.0)
    evictions: int = Field(default=0, ge=0)


@beartype
class CacheStatsData(BaseModelConfig):
    """Cache statistics data."""

    hit_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    total_requests: int = Field(default=0, ge=0)
    memory_usage_mb: float = Field(default=0.0, ge=0.0)
    avg_response_time_ms: float = Field(default=0.0, ge=0.0)


@beartype
class ErrorRatesMetrics(BaseModelConfig):
    """Error rates metrics by endpoint."""

    login: float = Field(default=0.0, ge=0.0, le=1.0)
    quote_generation: float = Field(default=0.0, ge=0.0, le=1.0)
    policy_creation: float = Field(default=0.0, ge=0.0, le=1.0)
    claim_submission: float = Field(default=0.0, ge=0.0, le=1.0)
    overall: float = Field(default=0.0, ge=0.0, le=1.0)


@beartype
class ErrorCountsMap(BaseModelConfig):
    """Error counts by circuit breaker."""

    system_monitoring: int = Field(default=0, ge=0)
    user_activity: int = Field(default=0, ge=0)
    performance: int = Field(default=0, ge=0)
    last_reset: datetime = Field(default_factory=datetime.now)


@beartype
class FiltersData(BaseModelConfig):
    """Activity filter configuration."""

    user_ids: list[UUID] | None = Field(default=None)
    action_types: list[str] | None = Field(default=None)
    resource_types: list[str] | None = Field(default=None)
    start_date: datetime | None = Field(default=None)
    end_date: datetime | None = Field(default=None)
    status_filter: list[str] | None = Field(default=None)


@beartype
class ConfigData(BaseModelConfig):
    """Configuration data."""

    update_interval: int = Field(default=5, ge=1, le=60)
    metrics_enabled: list[str] = Field(default_factory=list)
    alert_thresholds: dict[str, float] = Field(default_factory=dict)  # metric_name -> threshold_value
    retention_days: int = Field(default=30, ge=1)


@beartype
class DataPayload(BaseModelConfig):
    """Generic data payload."""

    content: str | None = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.now)
    source: str | None = Field(default=None)


@beartype
class WsStatsData(BaseModelConfig):
    """WebSocket statistics data."""

    active_connections: int = Field(default=0, ge=0)
    total_messages_sent: int = Field(default=0, ge=0)
    total_messages_received: int = Field(default=0, ge=0)
    avg_latency_ms: float = Field(default=0.0, ge=0.0)
    connection_errors: int = Field(default=0, ge=0)


@beartype
class DatabaseData(BaseModelConfig):
    """Database metrics data."""

    active_connections: int = Field(default=0, ge=0)
    idle_connections: int = Field(default=0, ge=0)
    total_connections: int = Field(default=0, ge=0)
    avg_query_time_ms: float = Field(default=0.0, ge=0.0)
    slow_queries: int = Field(default=0, ge=0)


@beartype
class ApiResponseTimesMetrics(BaseModelConfig):
    """API response time metrics by endpoint."""

    quotes: float = Field(default=0.0, ge=0.0)
    policies: float = Field(default=0.0, ge=0.0)
    claims: float = Field(default=0.0, ge=0.0)
    customers: float = Field(default=0.0, ge=0.0)
    overall_p50: float = Field(default=0.0, ge=0.0)
    overall_p95: float = Field(default=0.0, ge=0.0)
    overall_p99: float = Field(default=0.0, ge=0.0)


@beartype
class RecentError(BaseModelConfig):
    """Recent error detail."""
    
    type: str
    count: int = Field(ge=0)
    last_occurrence: str | None = None


@beartype
class ErrorsData(BaseModelConfig):
    """Error statistics data."""

    total_errors: int = Field(default=0, ge=0)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    errors_by_type: dict[str, int] = Field(default_factory=dict)
    recent_errors: list[RecentError] = Field(default_factory=list)


@beartype
class DbStatsData(BaseModelConfig):
    """Database statistics data."""

    connection_pool_size: int = Field(default=0, ge=0)
    active_queries: int = Field(default=0, ge=0)
    transaction_rate: float = Field(default=0.0, ge=0.0)
    replication_lag_seconds: float = Field(default=0.0, ge=0.0)


@beartype
class WebsocketsData(BaseModelConfig):
    """WebSocket connection data."""

    total_connections: int = Field(default=0, ge=0)
    active_connections: int = Field(default=0, ge=0)
    rooms: dict[str, int] = Field(default_factory=dict)  # room_name -> connection_count
    message_queue_size: int = Field(default=0, ge=0)


@beartype
class DashboardConfigData(BaseModelConfig):
    """Dashboard configuration data."""

    update_interval: int = Field(default=5, ge=1, le=60)
    theme: str = Field(default="light", pattern="^(light|dark)$")
    widgets: list[str] = Field(default_factory=list)
    refresh_on_focus: bool = Field(default=True)


@beartype
class QuoteCalculationTimesMetrics(BaseModelConfig):
    """Quote calculation time metrics."""

    average_ms: float = Field(default=0.0, ge=0.0)
    min_ms: float = Field(default=0.0, ge=0.0)
    max_ms: float = Field(default=0.0, ge=0.0)
    p50_ms: float = Field(default=0.0, ge=0.0)
    p95_ms: float = Field(default=0.0, ge=0.0)
    p99_ms: float = Field(default=0.0, ge=0.0)


@beartype
class ActiveStreamsMap(BaseModelConfig):
    """Active streams tracking map."""

    streams: dict[str, str] = Field(default_factory=dict)  # stream_key -> task_id


class SystemMetrics(BaseModel):
    """System health metrics."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    database: DatabaseData
    websockets: WebsocketsData
    cache: CacheData
    errors: ErrorsData
    timestamp: datetime = Field(default_factory=datetime.now)


# UserActivity is imported from admin_models


# PerformanceMetrics is imported from admin_models


class AdminDashboardHandler:
    """Handle admin dashboard real-time updates with strict validation."""

    def __init__(self, manager: ConnectionManager, db: Database, cache: Cache) -> None:
        """Initialize admin dashboard handler."""
        self._manager = manager
        self._db = db
        self._cache = cache
        self._active_streams: dict[str, asyncio.Task[None]] = {}

        # Circuit breakers for system protection
        self._error_counts: ErrorCountsMap = ErrorCountsMap()
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_reset_time = 300  # 5 minutes

    @beartype
    async def start_system_monitoring(
        self,
        connection_id: str,
        admin_user_id: UUID,
        dashboard_config: DashboardConfigData,
    ) -> Result[None, str]:
        """Start real-time system monitoring for admin with explicit permission check."""
        # Verify admin permissions
        permission_result = await self._check_admin_permissions(
            admin_user_id, "analytics:read"
        )
        if permission_result.is_err():
            await self._send_permission_error(connection_id, "analytics:read")
            return permission_result

        # Validate monitoring config
        update_interval = dashboard_config.update_interval
        if not 1 <= update_interval <= 60:
            return Err(
                f"Invalid update interval: {update_interval}. "
                "Must be between 1 and 60 seconds."
            )

        # Subscribe to admin monitoring room
        room_id = f"admin:system_monitoring:{admin_user_id}"
        subscribe_result = await self._manager.subscribe_to_room(connection_id, room_id)
        if subscribe_result.is_err():
            return subscribe_result

        # Cancel any existing stream
        stream_key = f"admin_monitor_{connection_id}"
        if stream_key in self._active_streams:
            await self._cancel_stream(stream_key)

        # Start monitoring stream
        self._active_streams[stream_key] = asyncio.create_task(
            self._system_monitoring_stream(connection_id, dashboard_config)
        )

        # Send initial system state
        initial_metrics = await self._collect_system_metrics()
        if initial_metrics.is_ok():
            welcome_msg = WebSocketMessage(
                type=MessageType.SYSTEM_ALERT,
                data=create_websocket_message_data(
                    user_id=admin_user_id,
                    payload={
                        "initial_metrics": initial_metrics.unwrap(),
                        "config": dashboard_config,
                        "admin_user_id": str(admin_user_id),
                    },
                ).model_dump(),
            )
            await self._manager.send_personal_message(connection_id, welcome_msg)

        return Ok(None)

    @beartype
    async def start_user_activity_monitoring(
        self,
        connection_id: str,
        admin_user_id: UUID,
        filters: FiltersData,
    ) -> Result[None, str]:
        """Start real-time user activity monitoring with audit permissions."""
        # Verify audit permissions
        permission_result = await self._check_admin_permissions(
            admin_user_id, "audit:read"
        )
        if permission_result.is_err():
            await self._send_permission_error(connection_id, "audit:read")
            return permission_result

        # Subscribe to activity room
        room_id = f"admin:user_activity:{admin_user_id}"
        subscribe_result = await self._manager.subscribe_to_room(connection_id, room_id)
        if subscribe_result.is_err():
            return subscribe_result

        # Start activity stream
        stream_key = f"user_activity_{connection_id}"
        if stream_key in self._active_streams:
            await self._cancel_stream(stream_key)

        self._active_streams[stream_key] = asyncio.create_task(
            self._user_activity_stream(connection_id, filters)
        )

        return Ok(None)

    @beartype
    async def start_performance_monitoring(
        self,
        connection_id: str,
        admin_user_id: UUID,
        metrics: list[str],
    ) -> Result[None, str]:
        """Start real-time performance monitoring."""
        # Verify performance monitoring permissions
        permission_result = await self._check_admin_permissions(
            admin_user_id, "performance:read"
        )
        if permission_result.is_err():
            await self._send_permission_error(connection_id, "performance:read")
            return permission_result

        # Validate requested metrics
        valid_metrics = {
            "api_response_times",
            "quote_calculation_times",
            "active_sessions",
            "error_rates",
            "database_performance",
            "cache_performance",
        }

        invalid_metrics = [m for m in metrics if m not in valid_metrics]
        if invalid_metrics:
            return Err(
                f"Invalid metrics requested: {invalid_metrics}. "
                f"Valid metrics are: {sorted(valid_metrics)}"
            )

        # Subscribe to performance room
        room_id = f"admin:performance:{admin_user_id}"
        subscribe_result = await self._manager.subscribe_to_room(connection_id, room_id)
        if subscribe_result.is_err():
            return subscribe_result

        # Start performance stream
        stream_key = f"performance_{connection_id}"
        if stream_key in self._active_streams:
            await self._cancel_stream(stream_key)

        self._active_streams[stream_key] = asyncio.create_task(
            self._performance_monitoring_stream(connection_id, metrics)
        )

        return Ok(None)

    async def _system_monitoring_stream(
        self,
        connection_id: str,
        config: ConfigData,
    ) -> None:
        """Stream system health metrics with circuit breaker protection."""
        update_interval = config.update_interval
        error_count = 0

        try:
            while True:
                # Check circuit breaker
                if self._is_circuit_open("system_monitoring"):
                    await self._send_circuit_breaker_alert(
                        connection_id, "system_monitoring"
                    )
                    await asyncio.sleep(30)  # Wait longer when circuit is open
                    continue

                # Collect metrics
                metrics_result = await self._collect_system_metrics()

                if metrics_result.is_err():
                    error_count += 1
                    self._record_error("system_monitoring")

                    if error_count > 3:
                        error_msg = WebSocketMessage(
                            type=MessageType.ERROR,
                            data=create_websocket_message_data(
                                error="Failed to collect system metrics",
                                payload={"consecutive_errors": error_count},
                            ).model_dump(),
                        )
                        await self._manager.send_personal_message(
                            connection_id, error_msg
                        )

                    await asyncio.sleep(update_interval * 2)  # Back off on errors
                    continue

                error_count = 0  # Reset on success
                metrics = metrics_result.unwrap()

                # Send update
                update_msg = WebSocketMessage(
                    type=MessageType.SYSTEM_ALERT,
                    data=create_websocket_message_data(
                        payload=metrics,
                    ).model_dump(),
                )

                send_result = await self._manager.send_personal_message(
                    connection_id, update_msg
                )
                if send_result.is_err():
                    break  # Connection lost

                # Wait for next update
                await asyncio.sleep(update_interval)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self._send_stream_error(connection_id, "system_monitoring", str(e))

    async def _user_activity_stream(
        self,
        connection_id: str,
        filters: FiltersData,
    ) -> None:
        """Stream user activity events with filtering."""
        try:
            # Send initial batch of recent activities
            recent_activities = await self._get_recent_user_activity(filters)
            if recent_activities.is_ok():
                initial_msg = WebSocketMessage(
                    type=MessageType.SYSTEM_ALERT,
                    data=create_websocket_message_data(
                        payload={
                            "activities": recent_activities.unwrap(),
                            "is_initial": True,
                        },
                    ).model_dump(),
                )
                await self._manager.send_personal_message(connection_id, initial_msg)

            # Stream new activities
            last_check = datetime.now()

            while True:
                await asyncio.sleep(2)  # Check every 2 seconds

                # Get activities since last check
                new_activities = await self._get_user_activity_since(
                    last_check, filters
                )
                if new_activities.is_ok() and new_activities.unwrap():
                    activity_msg = WebSocketMessage(
                        type=MessageType.SYSTEM_ALERT,
                        data=create_websocket_message_data(
                            payload={
                                "activities": new_activities.unwrap(),
                                "is_incremental": True,
                            },
                        ).model_dump(),
                    )

                    send_result = await self._manager.send_personal_message(
                        connection_id, activity_msg
                    )
                    if send_result.is_err():
                        break

                last_check = datetime.now()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self._send_stream_error(connection_id, "user_activity", str(e))

    async def _performance_monitoring_stream(
        self,
        connection_id: str,
        metrics: list[str],
    ) -> None:
        """Stream performance metrics with high frequency updates."""
        try:
            while True:
                # Collect requested metrics
                perf_data = await self._collect_performance_metrics(metrics)

                if perf_data.is_ok():
                    perf_msg = WebSocketMessage(
                        type=MessageType.SYSTEM_ALERT,
                        data=create_websocket_message_data(
                            payload=perf_data.unwrap(),
                        ).model_dump(),
                    )

                    send_result = await self._manager.send_personal_message(
                        connection_id, perf_msg
                    )
                    if send_result.is_err():
                        break

                await asyncio.sleep(1)  # 1-second updates for performance

        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self._send_stream_error(connection_id, "performance", str(e))

    @beartype
    async def _collect_system_metrics(self) -> Result[SystemMetrics, str]:
        """Collect current system health metrics."""
        try:
            # Database connection stats
            db_stats_result = await self._get_database_stats()
            db_stats = db_stats_result.unwrap() if db_stats_result.is_ok() else {}

            # WebSocket connection stats
            ws_stats = await self._manager.get_connection_stats()

            # Cache stats
            cache_stats_result = await self._get_cache_stats()
            cache_stats = (
                cache_stats_result.unwrap() if cache_stats_result.is_ok() else {}
            )

            # Recent error stats
            error_stats_result = await self._get_error_statistics()
            error_stats = (
                error_stats_result.unwrap() if error_stats_result.is_ok() else {}
            )

            # Convert stats to appropriate models
            # Handle database stats
            if isinstance(db_stats, DatabaseData):
                db_model = db_stats
            else:
                db_model = DatabaseData()
            
            # Handle websocket stats - convert dict to model
            if isinstance(ws_stats, dict):
                ws_model = WebsocketsData(**ws_stats)
            elif isinstance(ws_stats, WebsocketsData):
                ws_model = ws_stats
            else:
                ws_model = WebsocketsData()
            
            # Handle cache stats
            if isinstance(cache_stats, CacheData):
                cache_model = cache_stats
            else:
                cache_model = CacheData()
            
            # Handle error stats
            if isinstance(error_stats, ErrorsData):
                errors_model = error_stats
            else:
                errors_model = ErrorsData()
            
            return Ok(
                SystemMetrics(
                    database=db_model,
                    websockets=ws_model,
                    cache=cache_model,
                    errors=errors_model,
                    timestamp=datetime.now(),
                )
            )
        except Exception as e:
            return Err(f"Failed to collect system metrics: {str(e)}")

    @beartype
    async def _get_database_stats(self) -> Result[DatabaseData, str]:
        """Get database connection pool statistics."""
        try:
            # Get connection pool stats
            pool_stats = await self._db.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE state = 'active') as active_connections,
                    COUNT(*) FILTER (WHERE state = 'idle') as idle_connections,
                    COUNT(*) as total_connections,
                    MAX(EXTRACT(EPOCH FROM (NOW() - backend_start))) as longest_connection_seconds
                FROM pg_stat_activity
                WHERE datname = current_database()
                """
            )

            # Get query performance stats
            query_stats = await self._db.fetchrow(
                """
                SELECT
                    AVG(mean_exec_time) as avg_query_time_ms,
                    MAX(mean_exec_time) as max_query_time_ms,
                    SUM(calls) as total_queries
                FROM pg_stat_statements
                WHERE query NOT LIKE '%pg_stat%'
                LIMIT 1
                """
            )

            # Extract data from query results
            active_conn = pool_stats["active_connections"] if pool_stats else 0
            idle_conn = pool_stats["idle_connections"] if pool_stats else 0
            total_conn = pool_stats["total_connections"] if pool_stats else 0
            avg_query_time = query_stats["avg_query_time_ms"] if query_stats else 0.0
            
            # Count slow queries based on threshold (e.g., > 100ms)
            slow_queries = 0
            if query_stats and query_stats["max_query_time_ms"]:
                if query_stats["max_query_time_ms"] > 100:
                    slow_queries = 1  # At least one slow query
            
            return Ok(
                DatabaseData(
                    active_connections=active_conn,
                    idle_connections=idle_conn,
                    total_connections=total_conn,
                    avg_query_time_ms=avg_query_time,
                    slow_queries=slow_queries,
                )
            )
        except Exception as e:
            return Err(f"Database stats error: {str(e)}")

    @beartype
    async def _get_cache_stats(self) -> Result[CacheData, str]:
        """Get Redis cache statistics."""
        try:
            # Get Redis info
            redis_client = self._cache._redis
            if not redis_client:
                return Err("Redis not connected")

            info = await redis_client.info()
            memory_info = await redis_client.info("memory")

            hits = float(info.get("keyspace_hits", 0))
            misses = float(info.get("keyspace_misses", 0))
            total_requests = hits + misses
            hit_rate = hits / max(total_requests, 1)
            
            memory_usage_mb = float(memory_info.get("used_memory", 0)) / (1024 * 1024)
            
            # Note: evictions not directly available in standard Redis info
            # Would need to track separately or use specific Redis commands
            evictions = 0
            
            return Ok(
                CacheData(
                    hit_rate=hit_rate,
                    total_hits=int(hits),
                    total_misses=int(misses),
                    memory_usage_mb=memory_usage_mb,
                    evictions=evictions,
                )
            )
        except Exception as e:
            return Err(f"Cache stats error: {str(e)}")

    @beartype
    async def _get_error_statistics(self) -> Result[ErrorsData, str]:
        """Get recent error statistics."""
        try:
            # Get error counts by type (last hour)
            error_counts = await self._db.fetch(
                """
                SELECT
                    error_type,
                    COUNT(*) as count,
                    MAX(created_at) as last_occurrence
                FROM error_logs
                WHERE created_at > NOW() - INTERVAL '1 hour'
                GROUP BY error_type
                ORDER BY count DESC
                LIMIT 10
                """
            )

            # Get error rate trend
            error_trend = await self._db.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '5 minutes') as last_5min,
                    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as last_hour,
                    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as last_24h
                FROM error_logs
                """
            )

            # Calculate total errors and error rate
            total_errors = 0
            errors_by_type = {}
            recent_errors = []
            
            for row in error_counts:
                error_type = row["error_type"]
                count = row["count"]
                total_errors += count
                errors_by_type[error_type] = count
                recent_errors.append(RecentError(
                    type=error_type,
                    count=count,
                    last_occurrence=row["last_occurrence"].isoformat() if row["last_occurrence"] else None
                ))
            
            # Assume we have a way to get total requests for error rate calculation
            # For now, use a simple calculation based on errors in last hour
            error_rate = min(total_errors / 1000.0, 1.0)  # Assuming ~1000 requests/hour baseline
            
            return Ok(
                ErrorsData(
                    total_errors=total_errors,
                    error_rate=error_rate,
                    errors_by_type=errors_by_type,
                    recent_errors=recent_errors[:10],  # Limit to 10 most recent
                )
            )
        except Exception as e:
            return Err(f"Error stats error: {str(e)}")

    @beartype
    async def _get_recent_user_activity(
        self, filters: FiltersData
    ) -> Result[list[UserActivity], str]:
        """Get recent user activity events."""
        try:
            # Build query with filters
            where_clauses = ["aal.created_at > NOW() - INTERVAL '30 minutes'"]
            params = []

            if filters.action_types:
                for action in filters.action_types:
                    params.append(action)
                    where_clauses.append(f"aal.action = ${len(params)}")

            if filters.resource_types:
                for resource_type in filters.resource_types:
                    params.append(resource_type)
                    where_clauses.append(f"aal.resource_type = ${len(params)}")

            # Safe query construction - where_clauses are built from parameterized conditions
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            query = (
                """
                SELECT
                    aal.id,
                    aal.admin_user_id,
                    au.email,
                    aal.action,
                    aal.resource_type,
                    aal.resource_id,
                    aal.status,
                    aal.created_at,
                    aal.ip_address
                FROM admin_activity_logs aal
                JOIN admin_users au ON aal.admin_user_id = au.id
                WHERE """
                + where_clause
                + """
                ORDER BY aal.created_at DESC
                LIMIT 50
            """
            )

            rows = await self._db.fetch(query, *params)
            return Ok([UserActivity(**dict(row)) for row in rows])
        except Exception as e:
            return Err(f"Failed to get user activity: {str(e)}")

    @beartype
    async def _get_user_activity_since(
        self, since: datetime, filters: FiltersData
    ) -> Result[list[UserActivity], str]:
        """Get user activity since a specific time."""
        try:
            where_clauses = ["aal.created_at > $1"]
            params = [since]

            if filters.action_types:
                for action in filters.action_types:
                    params.append(action)
                    where_clauses.append(f"aal.action = ${len(params)}")

            if filters.resource_types:
                for resource_type in filters.resource_types:
                    params.append(resource_type)
                    where_clauses.append(f"aal.resource_type = ${len(params)}")

            # Safe query construction - where_clauses are built from parameterized conditions
            where_clause = " AND ".join(where_clauses) if where_clauses else "1=1"
            query = (
                """
                SELECT
                    aal.id,
                    aal.admin_user_id,
                    au.email,
                    aal.action,
                    aal.resource_type,
                    aal.resource_id,
                    aal.status,
                    aal.created_at,
                    aal.ip_address
                FROM admin_activity_logs aal
                JOIN admin_users au ON aal.admin_user_id = au.id
                WHERE """
                + where_clause
                + """
                ORDER BY aal.created_at ASC
                LIMIT 20
            """
            )

            rows = await self._db.fetch(query, *params)
            return Ok([UserActivity(**dict(row)) for row in rows])
        except Exception as e:
            return Err(f"Failed to get activity updates: {str(e)}")

    @beartype
    async def _collect_performance_metrics(
        self, metrics: list[str]
    ) -> Result[PerformanceMetrics, str]:
        """Collect requested performance metrics."""
        try:
            # Initialize with default values
            api_response_times = None
            quote_calculation_times = None
            active_sessions = None
            error_rates = None

            if "api_response_times" in metrics:
                # Get from recent request logs
                api_times = await self._db.fetchrow(
                    """
                    SELECT
                        AVG(response_time_ms) as avg,
                        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY response_time_ms) as p50,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) as p95,
                        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY response_time_ms) as p99
                    FROM api_request_logs
                    WHERE created_at > NOW() - INTERVAL '5 minutes'
                    """
                )
                if api_times:
                    api_response_times = ApiResponseTimes(**dict(api_times))

            if "quote_calculation_times" in metrics:
                # Get quote calculation performance
                calc_times = await self._db.fetchrow(
                    """
                    SELECT
                        AVG(calculation_time_ms) as avg,
                        MIN(calculation_time_ms) as min,
                        MAX(calculation_time_ms) as max,
                        COUNT(*) as total
                    FROM quote_calculations
                    WHERE created_at > NOW() - INTERVAL '5 minutes'
                    """
                )
                if calc_times:
                    quote_calculation_times = QuoteCalculationTimes(**dict(calc_times))

            if "active_sessions" in metrics:
                # Get active user sessions
                sessions = await self._db.fetchval(
                    """
                    SELECT COUNT(DISTINCT user_id)
                    FROM user_sessions
                    WHERE last_activity > NOW() - INTERVAL '15 minutes'
                    """
                )
                active_sessions = int(sessions) if sessions is not None else 0

            if "error_rates" in metrics:
                # Calculate error rates
                error_rates_data = await self._db.fetchrow(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE status >= 400) as errors,
                        COUNT(*) as total,
                        CASE
                            WHEN COUNT(*) > 0
                            THEN COUNT(*) FILTER (WHERE status >= 400)::float / COUNT(*)::float
                            ELSE 0
                        END as error_rate
                    FROM api_request_logs
                    WHERE created_at > NOW() - INTERVAL '5 minutes'
                    """
                )
                if error_rates_data:
                    error_rates = ErrorRates(**dict(error_rates_data))

            return Ok(
                PerformanceMetrics(
                    api_response_times=api_response_times,
                    quote_calculation_times=quote_calculation_times,
                    active_sessions=active_sessions,
                    error_rates=error_rates,
                    timestamp=datetime.now()
                )
            )
        except Exception as e:
            return Err(f"Failed to collect performance metrics: {str(e)}")

    @beartype
    async def broadcast_admin_alert(
        self,
        alert_type: str,
        message: str,
        severity: str,
        data: DataData | None = None,
    ) -> Result[None, str]:
        """Broadcast alert to all admin users with proper severity validation."""
        if severity not in ["low", "medium", "high", "critical"]:
            return Err(
                f"Invalid alert severity: {severity}. "
                "Must be one of: low, medium, high, critical"
            )

        WebSocketMessage(
            type=MessageType.SYSTEM_ALERT,
            data=create_websocket_message_data(
                alert_type=alert_type,
                severity=severity,
                payload={
                    "message": message,
                    "data": data or {},
                    "timestamp": datetime.now().isoformat(),
                    "requires_action": severity in ["high", "critical"],
                },
            ).model_dump(),
        )

        # Send to all admin monitoring rooms
        # Note: In production, implement pattern-based room sending
        # For now, track admin rooms separately

        return Ok(None)

    @beartype
    async def handle_admin_disconnect(self, connection_id: str) -> None:
        """Clean up when admin disconnects."""
        # Cancel all active streams for this connection
        streams_to_cancel = [
            key for key in self._active_streams.keys() if connection_id in key
        ]

        for stream_key in streams_to_cancel:
            await self._cancel_stream(stream_key)

    @beartype
    async def _check_admin_permissions(
        self, admin_user_id: UUID, required_permission: str
    ) -> Result[None, str]:
        """Check if admin user has required permission."""
        # In production, query actual permissions from database
        # For now, simplified check
        try:
            admin_user = await self._db.fetchrow(
                """
                SELECT id, role, is_active
                FROM admin_users
                WHERE id = $1
                """,
                admin_user_id,
            )

            if not admin_user:
                return Err("Admin user not found")

            if not admin_user["is_active"]:
                return Err("Admin account is disabled")

            # Check role-based permissions
            role = admin_user["role"]
            permission_map = {
                "super_admin": [
                    "analytics:read",
                    "audit:read",
                    "performance:read",
                    "system:manage",
                ],
                "admin": ["analytics:read", "audit:read", "performance:read"],
                "analyst": ["analytics:read", "performance:read"],
                "auditor": ["audit:read"],
            }

            allowed_permissions = permission_map.get(role, [])
            if required_permission not in allowed_permissions:
                return Err(
                    f"Permission denied. Role '{role}' does not have '{required_permission}' permission. "
                    f"Required role: {[r for r, perms in permission_map.items() if required_permission in perms]}"
                )

            return Ok(None)
        except Exception as e:
            return Err(f"Permission check failed: {str(e)}")

    @beartype
    def _calculate_health_status(
        self,
        db_stats: DatabaseData,
        ws_stats: WebsocketsData,
        cache_stats: CacheData,
        error_stats: ErrorsData,
    ) -> str:
        """Calculate overall system health status."""
        # Simple health calculation
        issues = 0

        # Check database - high connection count or slow queries
        if db_stats.active_connections > 100 or db_stats.slow_queries > 10:
            issues += 2

        # Check WebSocket utilization (based on active vs total connections)
        if ws_stats.total_connections > 0:
            utilization = ws_stats.active_connections / ws_stats.total_connections
            if utilization > 0.8:
                issues += 1

        # Check error rates
        if error_stats.error_rate > 0.05:  # More than 5% error rate
            issues += 2

        # Determine health status
        if issues == 0:
            return "healthy"
        elif issues <= 2:
            return "degraded"
        else:
            return "critical"

    @beartype
    def _is_circuit_open(self, service: str) -> bool:
        """Check if circuit breaker is open for a service."""
        return self._error_counts.get(service, 0) >= self._circuit_breaker_threshold

    @beartype
    def _record_error(self, service: str) -> None:
        """Record an error for circuit breaker tracking."""
        if service not in self._error_counts:
            self._error_counts[service] = 0
        self._error_counts[service] += 1

        # Schedule reset after timeout
        asyncio.create_task(self._reset_circuit_breaker(service))

    async def _reset_circuit_breaker(self, service: str) -> None:
        """Reset circuit breaker after timeout."""
        await asyncio.sleep(self._circuit_breaker_reset_time)
        if service in self._error_counts:
            self._error_counts[service] = 0

    @beartype
    async def _cancel_stream(self, stream_key: str) -> None:
        """Cancel a streaming task safely."""
        if stream_key in self._active_streams:
            task = self._active_streams.pop(stream_key)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @beartype
    async def _send_permission_error(
        self, connection_id: str, required_permission: str
    ) -> None:
        """Send permission error message."""
        error_msg = WebSocketMessage(
            type=MessageType.ERROR,
            data=create_websocket_message_data(
                error="Insufficient permissions",
                payload={
                    "required_permission": required_permission,
                    "message": f"You need '{required_permission}' permission to access this feature",
                },
            ).model_dump(),
        )
        await self._manager.send_personal_message(connection_id, error_msg)

    @beartype
    async def _send_circuit_breaker_alert(
        self, connection_id: str, service: str
    ) -> None:
        """Send circuit breaker alert."""
        alert_msg = WebSocketMessage(
            type=MessageType.SYSTEM_ALERT,
            data=create_websocket_message_data(
                status="open",
                payload={
                    "service": service,
                    "message": f"Circuit breaker open for {service}. Too many errors detected.",
                    "reset_time": datetime.now()
                    + timedelta(seconds=self._circuit_breaker_reset_time),
                },
            ).model_dump(),
        )
        await self._manager.send_personal_message(connection_id, alert_msg)

    @beartype
    async def _send_stream_error(
        self, connection_id: str, stream_type: str, error: str
    ) -> None:
        """Send streaming error message."""
        error_msg = WebSocketMessage(
            type=MessageType.ERROR,
            data=create_websocket_message_data(
                error=error,
                payload={
                    "stream_type": stream_type,
                    "fatal": True,
                    "message": f"Streaming failed for {stream_type}: {error}",
                },
            ).model_dump(),
        )
        await self._manager.send_personal_message(connection_id, error_msg)
