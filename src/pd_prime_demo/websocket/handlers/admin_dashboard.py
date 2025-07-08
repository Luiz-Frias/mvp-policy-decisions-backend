"""Admin dashboard WebSocket handler for real-time monitoring."""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List
from uuid import UUID

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

from ...core.cache import Cache
from ...core.database import Database
from ...services.result import Err, Ok
from ..manager import ConnectionManager, WebSocketMessage


class SystemMetrics(BaseModel):
    """System health metrics."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    database: dict[str, Any] = Field(default_factory=dict)
    websockets: dict[str, Any] = Field(default_factory=dict)
    cache: dict[str, Any] = Field(default_factory=dict)
    errors: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class UserActivity(BaseModel):
    """User activity event."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    admin_user_id: UUID = Field(...)
    action: str = Field(..., min_length=1, max_length=100)
    resource_type: str = Field(..., min_length=1, max_length=50)
    resource_id: str | None = Field(default=None)
    status: str = Field(..., pattern="^(success|failure|error)$")
    ip_address: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)


class PerformanceMetrics(BaseModel):
    """Performance monitoring data."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    api_response_times: dict[str, float] = Field(default_factory=dict)
    quote_calculation_times: dict[str, float] = Field(default_factory=dict)
    active_sessions: int = Field(default=0, ge=0)
    error_rates: dict[str, float] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class AdminDashboardHandler:
    """Handle admin dashboard real-time updates with strict validation."""

    def __init__(self, manager: ConnectionManager, db: Database, cache: Cache) -> None:
        """Initialize admin dashboard handler."""
        self._manager = manager
        self._db = db
        self._cache = cache
        self._active_streams: dict[str, asyncio.Task[None]] = {}

        # Circuit breakers for system protection
        self._error_counts: dict[str, int] = {}
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_reset_time = 300  # 5 minutes

    @beartype
    async def start_system_monitoring(
        self,
        connection_id: str,
        admin_user_id: UUID,
        dashboard_config: dict[str, Any],
    ):
        """Start real-time system monitoring for admin with explicit permission check."""
        # Verify admin permissions
        permission_result = await self._check_admin_permissions(
            admin_user_id, "analytics:read"
        )
        if permission_result.is_err():
            await self._send_permission_error(connection_id, "analytics:read")
            return permission_result

        # Validate monitoring config
        update_interval = dashboard_config.get("update_interval", 5)
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
                type="admin_monitoring_started",
                data={
                    "initial_metrics": initial_metrics.unwrap(),
                    "config": dashboard_config,
                    "admin_user_id": str(admin_user_id),
                },
            )
            await self._manager.send_personal_message(connection_id, welcome_msg)

        return Ok(None)

    @beartype
    async def start_user_activity_monitoring(
        self,
        connection_id: str,
        admin_user_id: UUID,
        filters: dict[str, Any],
    ):
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
    ):
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
        config: dict[str, Any],
    ) -> None:
        """Stream system health metrics with circuit breaker protection."""
        update_interval = config.get("update_interval", 5)
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
                            type="monitoring_error",
                            data={
                                "error": "Failed to collect system metrics",
                                "consecutive_errors": error_count,
                            },
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
                    type="system_metrics",
                    data=metrics,
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
        filters: dict[str, Any],
    ) -> None:
        """Stream user activity events with filtering."""
        try:
            # Send initial batch of recent activities
            recent_activities = await self._get_recent_user_activity(filters)
            if recent_activities.is_ok():
                initial_msg = WebSocketMessage(
                    type="user_activity_batch",
                    data={
                        "activities": recent_activities.unwrap(),
                        "is_initial": True,
                    },
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
                        type="user_activity",
                        data={
                            "activities": new_activities.unwrap(),
                            "is_incremental": True,
                        },
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
                        type="performance_metrics",
                        data=perf_data.unwrap(),
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
    async def _collect_system_metrics(self) -> dict:
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

            return Ok(
                {
                    "database": db_stats,
                    "websockets": ws_stats,
                    "cache": cache_stats,
                    "errors": error_stats,
                    "timestamp": datetime.now().isoformat(),
                    "health_status": self._calculate_health_status(
                        db_stats, ws_stats, cache_stats, error_stats
                    ),
                }
            )
        except Exception as e:
            return Err(f"Failed to collect system metrics: {str(e)}")

    @beartype
    async def _get_database_stats(self) -> dict:
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

            return Ok(
                {
                    "pool": dict(pool_stats) if pool_stats else {},
                    "performance": dict(query_stats) if query_stats else {},
                    "status": (
                        "healthy"
                        if pool_stats and pool_stats["active_connections"] < 100
                        else "warning"
                    ),
                }
            )
        except Exception as e:
            return Err(f"Database stats error: {str(e)}")

    @beartype
    async def _get_cache_stats(self) -> dict:
        """Get Redis cache statistics."""
        try:
            # Get Redis info
            redis_client = self._cache._redis
            if not redis_client:
                return Err("Redis not connected")

            info = await redis_client.info()
            memory_info = await redis_client.info("memory")

            return Ok(
                {
                    "connected_clients": info.get("connected_clients", 0),
                    "used_memory_mb": memory_info.get("used_memory", 0) / (1024 * 1024),
                    "hit_rate": info.get("keyspace_hits", 0)
                    / max(
                        info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1
                    ),
                    "total_keys": await redis_client.dbsize(),
                    "status": "healthy",
                }
            )
        except Exception as e:
            return Err(f"Cache stats error: {str(e)}")

    @beartype
    async def _get_error_statistics(self) -> dict:
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

            return Ok(
                {
                    "by_type": [dict(row) for row in error_counts],
                    "trend": dict(error_trend) if error_trend else {},
                    "circuit_breakers": {
                        name: "open"
                        for name, count in self._error_counts.items()
                        if count >= self._circuit_breaker_threshold
                    },
                }
            )
        except Exception as e:
            return Err(f"Error stats error: {str(e)}")

    @beartype
    async def _get_recent_user_activity(self, filters: dict[str, Any]) -> dict:
        """Get recent user activity events."""
        try:
            # Build query with filters
            where_clauses = ["aal.created_at > NOW() - INTERVAL '30 minutes'"]
            params = []

            if "action" in filters:
                params.append(filters["action"])
                where_clauses.append(f"aal.action = ${len(params)}")

            if "resource_type" in filters:
                params.append(filters["resource_type"])
                where_clauses.append(f"aal.resource_type = ${len(params)}")

            query = f"""
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
                WHERE {' AND '.join(where_clauses)}
                ORDER BY aal.created_at DESC
                LIMIT 50
            """

            rows = await self._db.fetch(query, *params)
            return Ok([dict(row) for row in rows])
        except Exception as e:
            return Err(f"Failed to get user activity: {str(e)}")

    @beartype
    async def _get_user_activity_since(
        self, since: datetime, filters: dict[str, Any]
    ) -> dict:
        """Get user activity since a specific time."""
        try:
            where_clauses = ["aal.created_at > $1"]
            params = [since]

            if "action" in filters:
                params.append(filters["action"])
                where_clauses.append(f"aal.action = ${len(params)}")

            if "resource_type" in filters:
                params.append(filters["resource_type"])
                where_clauses.append(f"aal.resource_type = ${len(params)}")

            query = f"""
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
                WHERE {' AND '.join(where_clauses)}
                ORDER BY aal.created_at ASC
                LIMIT 20
            """

            rows = await self._db.fetch(query, *params)
            return Ok([dict(row) for row in rows])
        except Exception as e:
            return Err(f"Failed to get activity updates: {str(e)}")

    @beartype
    async def _collect_performance_metrics(self, metrics: list[str]) -> dict:
        """Collect requested performance metrics."""
        try:
            data = {}

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
                data["api_response_times"] = dict(api_times) if api_times else {}

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
                data["quote_calculation_times"] = dict(calc_times) if calc_times else {}

            if "active_sessions" in metrics:
                # Get active user sessions
                sessions = await self._db.fetchval(
                    """
                    SELECT COUNT(DISTINCT user_id)
                    FROM user_sessions
                    WHERE last_activity > NOW() - INTERVAL '15 minutes'
                    """
                )
                data["active_sessions"] = sessions or 0

            if "error_rates" in metrics:
                # Calculate error rates
                error_rates = await self._db.fetchrow(
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
                data["error_rates"] = dict(error_rates) if error_rates else {}

            data["timestamp"] = datetime.now().isoformat()
            return Ok(data)
        except Exception as e:
            return Err(f"Failed to collect performance metrics: {str(e)}")

    @beartype
    async def broadcast_admin_alert(
        self,
        alert_type: str,
        message: str,
        severity: str,
        data: dict[str, Any] | None = None,
    ):
        """Broadcast alert to all admin users with proper severity validation."""
        if severity not in ["low", "medium", "high", "critical"]:
            return Err(
                f"Invalid alert severity: {severity}. "
                "Must be one of: low, medium, high, critical"
            )

        alert = WebSocketMessage(
            type="admin_alert",
            data={
                "alert_type": alert_type,
                "message": message,
                "severity": severity,
                "data": data or {},
                "timestamp": datetime.now().isoformat(),
                "requires_action": severity in ["high", "critical"],
            },
        )

        # Send to all admin monitoring rooms
        pattern = "admin:system_monitoring:*"
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
    ):
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
        db_stats: dict[str, Any],
        ws_stats: dict[str, Any],
        cache_stats: dict[str, Any],
        error_stats: dict[str, Any],
    ) -> str:
        """Calculate overall system health status."""
        # Simple health calculation
        issues = 0

        # Check database
        if db_stats.get("status") != "healthy":
            issues += 2

        # Check WebSocket utilization
        if ws_stats.get("utilization", 0) > 0.8:
            issues += 1

        # Check error rates
        if error_stats.get("trend", {}).get("last_5min", 0) > 100:
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
            type="permission_error",
            data={
                "error": "Insufficient permissions",
                "required_permission": required_permission,
                "message": f"You need '{required_permission}' permission to access this feature",
            },
        )
        await self._manager.send_personal_message(connection_id, error_msg)

    @beartype
    async def _send_circuit_breaker_alert(
        self, connection_id: str, service: str
    ) -> None:
        """Send circuit breaker alert."""
        alert_msg = WebSocketMessage(
            type="circuit_breaker_alert",
            data={
                "service": service,
                "status": "open",
                "message": f"Circuit breaker open for {service}. Too many errors detected.",
                "reset_time": datetime.now()
                + timedelta(seconds=self._circuit_breaker_reset_time),
            },
        )
        await self._manager.send_personal_message(connection_id, alert_msg)

    @beartype
    async def _send_stream_error(
        self, connection_id: str, stream_type: str, error: str
    ) -> None:
        """Send streaming error message."""
        error_msg = WebSocketMessage(
            type="stream_error",
            data={
                "stream_type": stream_type,
                "error": error,
                "fatal": True,
                "message": f"Streaming failed for {stream_type}: {error}",
            },
        )
        await self._manager.send_personal_message(connection_id, error_msg)
