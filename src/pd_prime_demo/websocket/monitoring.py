"""WebSocket Performance Monitoring and Observability.

Provides comprehensive monitoring capabilities for the WebSocket infrastructure:
- Real-time performance metrics
- Connection health monitoring
- Message throughput tracking
- Error rate analysis
- Memory usage optimization
"""

import asyncio
import json
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

from ..core.cache import Cache
from ..core.database import Database


class ConnectionMetrics(BaseModel):
    """Metrics for a single connection."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    connection_id: str = Field(...)
    user_id: UUID | None = Field(default=None)
    connected_at: datetime = Field(...)
    last_activity: datetime = Field(...)
    messages_sent: int = Field(default=0, ge=0)
    messages_received: int = Field(default=0, ge=0)
    bytes_sent: int = Field(default=0, ge=0)
    bytes_received: int = Field(default=0, ge=0)
    rooms_subscribed: int = Field(default=0, ge=0)
    errors_count: int = Field(default=0, ge=0)


class SystemMetrics(BaseModel):
    """System-wide WebSocket metrics."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    timestamp: datetime = Field(default_factory=datetime.now)
    total_connections: int = Field(default=0, ge=0)
    active_connections: int = Field(default=0, ge=0)
    peak_connections: int = Field(default=0, ge=0)
    messages_per_second: float = Field(default=0.0, ge=0)
    avg_message_latency_ms: float = Field(default=0.0, ge=0)
    p95_message_latency_ms: float = Field(default=0.0, ge=0)
    error_rate: float = Field(default=0.0, ge=0, le=1.0)
    memory_usage_mb: float = Field(default=0.0, ge=0)
    cpu_usage_percent: float = Field(default=0.0, ge=0, le=100)


class PerformanceAlert(BaseModel):
    """Performance alert definition."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    alert_type: str = Field(..., min_length=1, max_length=50)
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    message: str = Field(..., min_length=1)
    metric_name: str = Field(...)
    threshold_value: float = Field(...)
    current_value: float = Field(...)
    timestamp: datetime = Field(default_factory=datetime.now)


class WebSocketMonitor:
    """Comprehensive WebSocket monitoring system."""

    def __init__(self, cache: Cache, db: Database) -> None:
        """Initialize WebSocket monitor."""
        self._cache = cache
        self._db = db

        # Connection tracking
        self._connection_metrics: dict[str, ConnectionMetrics] = {}
        self._system_metrics_history: deque[SystemMetrics] = deque(maxlen=1000)

        # Performance tracking
        self._message_latencies: deque[float] = deque(
            maxlen=10000
        )  # Keep last 10k latencies
        self._message_timestamps: deque[datetime] = deque(maxlen=10000)
        self._error_counts: dict[str, int] = defaultdict(int)

        # Peak tracking
        self._peak_connections = 0
        self._peak_memory_mb = 0.0

        # Alert thresholds
        self._alert_thresholds = {
            "connection_count": 9000,  # Alert at 90% of 10k limit
            "message_latency_ms": 50,  # Alert if avg latency > 50ms
            "error_rate": 0.05,  # Alert if error rate > 5%
            "memory_usage_mb": 1000,  # Alert if memory > 1GB
        }

        # Monitoring task
        self._monitoring_task: asyncio.Task[None] | None = None
        self._monitoring_interval = 5  # seconds

    async def start_monitoring(self) -> None:
        """Start background monitoring."""
        if self._monitoring_task is None or self._monitoring_task.done():
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring(self) -> None:
        """Stop background monitoring."""
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

    @beartype
    async def record_connection_established(
        self,
        connection_id: str,
        user_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a new connection being established."""
        connection_metrics = ConnectionMetrics(
            connection_id=connection_id,
            user_id=user_id,
            connected_at=datetime.now(),
            last_activity=datetime.now(),
        )

        self._connection_metrics[connection_id] = connection_metrics

        # Update peak connections
        current_connections = len(self._connection_metrics)
        self._peak_connections = max(self._peak_connections, current_connections)

        # Store in database for persistence
        await self._store_connection_event(
            "connected", connection_id, user_id, metadata
        )

    @beartype
    async def record_connection_closed(
        self,
        connection_id: str,
        reason: str = "unknown",
    ) -> None:
        """Record a connection being closed."""
        if connection_id in self._connection_metrics:
            connection = self._connection_metrics[connection_id]
            duration = (datetime.now() - connection.connected_at).total_seconds()

            # Store connection stats in database
            await self._store_connection_stats(connection, duration, reason)

            # Remove from active tracking
            del self._connection_metrics[connection_id]

    @beartype
    async def record_message_sent(
        self,
        connection_id: str,
        message_size_bytes: int,
        latency_ms: float | None = None,
    ) -> None:
        """Record a message being sent."""
        if connection_id in self._connection_metrics:
            connection = self._connection_metrics[connection_id]

            # Update connection metrics
            updated_connection = connection.model_copy(
                update={
                    "messages_sent": connection.messages_sent + 1,
                    "bytes_sent": connection.bytes_sent + message_size_bytes,
                    "last_activity": datetime.now(),
                }
            )

            self._connection_metrics[connection_id] = updated_connection

        # Track latency if provided
        if latency_ms is not None:
            self._message_latencies.append(latency_ms)
            self._message_timestamps.append(datetime.now())

    @beartype
    async def record_message_received(
        self,
        connection_id: str,
        message_size_bytes: int,
    ) -> None:
        """Record a message being received."""
        if connection_id in self._connection_metrics:
            connection = self._connection_metrics[connection_id]

            updated_connection = connection.model_copy(
                update={
                    "messages_received": connection.messages_received + 1,
                    "bytes_received": connection.bytes_received + message_size_bytes,
                    "last_activity": datetime.now(),
                }
            )

            self._connection_metrics[connection_id] = updated_connection

    @beartype
    async def record_room_subscription(
        self,
        connection_id: str,
        room_id: str,
        subscribed: bool,
    ) -> None:
        """Record room subscription changes."""
        if connection_id in self._connection_metrics:
            connection = self._connection_metrics[connection_id]

            rooms_delta = 1 if subscribed else -1
            new_room_count = max(0, connection.rooms_subscribed + rooms_delta)

            updated_connection = connection.model_copy(
                update={
                    "rooms_subscribed": new_room_count,
                    "last_activity": datetime.now(),
                }
            )

            self._connection_metrics[connection_id] = updated_connection

    @beartype
    async def record_error(
        self,
        connection_id: str | None,
        error_type: str,
        error_message: str,
    ) -> None:
        """Record an error occurrence."""
        self._error_counts[error_type] += 1

        if connection_id and connection_id in self._connection_metrics:
            connection = self._connection_metrics[connection_id]

            updated_connection = connection.model_copy(
                update={
                    "errors_count": connection.errors_count + 1,
                    "last_activity": datetime.now(),
                }
            )

            self._connection_metrics[connection_id] = updated_connection

        # Store error in database
        await self._store_error_event(connection_id, error_type, error_message)

    @beartype
    async def get_system_metrics(self) -> SystemMetrics:
        """Get current system-wide metrics."""
        import psutil

        # Calculate message throughput
        now = datetime.now()
        recent_messages = [
            ts
            for ts in self._message_timestamps
            if (now - ts).total_seconds() <= 60  # Last minute
        ]
        messages_per_second = len(recent_messages) / 60.0

        # Calculate latency metrics
        recent_latencies = list(self._message_latencies)[-1000:]  # Last 1000 messages
        avg_latency = (
            sum(recent_latencies) / len(recent_latencies) if recent_latencies else 0
        )
        p95_latency = (
            sorted(recent_latencies)[int(len(recent_latencies) * 0.95)]
            if recent_latencies
            else 0
        )

        # Calculate error rate
        total_errors = sum(self._error_counts.values())
        total_messages = sum(
            conn.messages_sent + conn.messages_received
            for conn in self._connection_metrics.values()
        )
        error_rate = total_errors / max(total_messages, 1)

        # System resource usage
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        cpu_percent = process.cpu_percent()

        self._peak_memory_mb = max(self._peak_memory_mb, memory_mb)

        metrics = SystemMetrics(
            total_connections=len(self._connection_metrics),
            active_connections=len(
                [
                    conn
                    for conn in self._connection_metrics.values()
                    if (now - conn.last_activity).total_seconds()
                    < 300  # Active in last 5 min
                ]
            ),
            peak_connections=self._peak_connections,
            messages_per_second=messages_per_second,
            avg_message_latency_ms=avg_latency,
            p95_message_latency_ms=p95_latency,
            error_rate=error_rate,
            memory_usage_mb=memory_mb,
            cpu_usage_percent=cpu_percent,
        )

        # Store in history
        self._system_metrics_history.append(metrics)

        return metrics

    @beartype
    async def get_connection_metrics(
        self, connection_id: str
    ) -> ConnectionMetrics | None:
        """Get metrics for a specific connection."""
        return self._connection_metrics.get(connection_id)

    @beartype
    async def get_performance_alerts(self) -> list[PerformanceAlert]:
        """Check for performance issues and generate alerts."""
        alerts = []
        current_metrics = await self.get_system_metrics()

        # Check connection count
        if (
            current_metrics.total_connections
            >= self._alert_thresholds["connection_count"]
        ):
            alerts.append(
                PerformanceAlert(
                    alert_type="high_connection_count",
                    severity="high",
                    message=f"Connection count ({current_metrics.total_connections}) approaching limit",
                    metric_name="total_connections",
                    threshold_value=self._alert_thresholds["connection_count"],
                    current_value=current_metrics.total_connections,
                )
            )

        # Check message latency
        if (
            current_metrics.avg_message_latency_ms
            > self._alert_thresholds["message_latency_ms"]
        ):
            alerts.append(
                PerformanceAlert(
                    alert_type="high_message_latency",
                    severity="medium",
                    message=f"Average message latency ({current_metrics.avg_message_latency_ms:.1f}ms) above threshold",
                    metric_name="avg_message_latency_ms",
                    threshold_value=self._alert_thresholds["message_latency_ms"],
                    current_value=current_metrics.avg_message_latency_ms,
                )
            )

        # Check error rate
        if current_metrics.error_rate > self._alert_thresholds["error_rate"]:
            alerts.append(
                PerformanceAlert(
                    alert_type="high_error_rate",
                    severity="high",
                    message=f"Error rate ({current_metrics.error_rate:.2%}) above threshold",
                    metric_name="error_rate",
                    threshold_value=self._alert_thresholds["error_rate"],
                    current_value=current_metrics.error_rate,
                )
            )

        # Check memory usage
        if current_metrics.memory_usage_mb > self._alert_thresholds["memory_usage_mb"]:
            alerts.append(
                PerformanceAlert(
                    alert_type="high_memory_usage",
                    severity="critical",
                    message=f"Memory usage ({current_metrics.memory_usage_mb:.1f}MB) above threshold",
                    metric_name="memory_usage_mb",
                    threshold_value=self._alert_thresholds["memory_usage_mb"],
                    current_value=current_metrics.memory_usage_mb,
                )
            )

        return alerts

    @beartype
    async def get_metrics_summary(self) -> dict[str, Any]:
        """Get comprehensive metrics summary."""
        current_metrics = await self.get_system_metrics()
        alerts = await self.get_performance_alerts()

        # Calculate trends from history
        if len(self._system_metrics_history) >= 2:
            prev_metrics = self._system_metrics_history[-2]
            connection_trend = (
                current_metrics.total_connections - prev_metrics.total_connections
            )
            latency_trend = (
                current_metrics.avg_message_latency_ms
                - prev_metrics.avg_message_latency_ms
            )
        else:
            connection_trend = 0
            latency_trend = 0.0

        # Top error types
        top_errors = sorted(
            self._error_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]

        return {
            "current_metrics": current_metrics.model_dump(),
            "trends": {
                "connection_change": connection_trend,
                "latency_change_ms": latency_trend,
            },
            "peaks": {
                "max_connections": self._peak_connections,
                "max_memory_mb": self._peak_memory_mb,
            },
            "alerts": [alert.model_dump() for alert in alerts],
            "top_errors": [
                {"type": error_type, "count": count} for error_type, count in top_errors
            ],
            "connection_details": {
                "total_tracked": len(self._connection_metrics),
                "avg_rooms_per_connection": (
                    (
                        sum(
                            conn.rooms_subscribed
                            for conn in self._connection_metrics.values()
                        )
                        / len(self._connection_metrics)
                    )
                    if self._connection_metrics
                    else 0
                ),
                "avg_messages_per_connection": (
                    (
                        sum(
                            conn.messages_sent + conn.messages_received
                            for conn in self._connection_metrics.values()
                        )
                        / len(self._connection_metrics)
                    )
                    if self._connection_metrics
                    else 0
                ),
            },
        }

    async def _monitoring_loop(self) -> None:
        """Enhanced background monitoring loop with comprehensive metrics."""
        while True:
            try:
                # Collect current metrics
                current_metrics = await self.get_system_metrics()

                # Store metrics in cache for dashboards
                await self._cache.setex(
                    "websocket:current_metrics",
                    300,  # 5 minutes TTL
                    current_metrics.model_dump_json(),
                )

                # Store detailed metrics by priority
                priority_metrics = await self._get_priority_metrics()
                await self._cache.setex(
                    "websocket:priority_metrics",
                    300,
                    json.dumps(priority_metrics),
                )

                # Check for alerts
                alerts = await self.get_performance_alerts()
                if alerts:
                    for alert in alerts:
                        await self._handle_performance_alert(alert)

                # Store metrics in database every minute
                if datetime.now().minute % 1 == 0:  # Every minute
                    await self._store_system_metrics(current_metrics)
                    await self._store_priority_metrics(priority_metrics)

                # Clean up old data
                await self._cleanup_old_data()

                await asyncio.sleep(self._monitoring_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue monitoring
                await self.record_error(None, "monitoring_error", str(e))
                await asyncio.sleep(self._monitoring_interval)

    @beartype
    async def _store_connection_event(
        self,
        event_type: str,
        connection_id: str,
        user_id: UUID | None,
        metadata: dict[str, Any] | None,
    ) -> None:
        """Store connection event in database."""
        try:
            await self._db.execute(
                """
                INSERT INTO websocket_connection_events
                (event_type, connection_id, user_id, metadata, created_at)
                VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
                """,
                event_type,
                connection_id,
                user_id,
                metadata or {},
            )
        except Exception as e:
            # Non-critical, don't fail - log for debugging
            print(f"Warning: Failed to record connection metrics: {e}")  # nosec B608

    @beartype
    async def _store_connection_stats(
        self,
        connection: ConnectionMetrics,
        duration_seconds: float,
        close_reason: str,
    ) -> None:
        """Store connection statistics."""
        try:
            await self._db.execute(
                """
                INSERT INTO websocket_connection_stats
                (connection_id, user_id, duration_seconds, messages_sent, messages_received,
                 bytes_sent, bytes_received, max_rooms_subscribed, errors_count, close_reason)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                connection.connection_id,
                connection.user_id,
                duration_seconds,
                connection.messages_sent,
                connection.messages_received,
                connection.bytes_sent,
                connection.bytes_received,
                connection.rooms_subscribed,
                connection.errors_count,
                close_reason,
            )
        except Exception as e:
            print(f"Warning: Failed to store metrics: {e}")  # nosec B608

    @beartype
    async def _store_error_event(
        self,
        connection_id: str | None,
        error_type: str,
        error_message: str,
    ) -> None:
        """Store error event."""
        try:
            await self._db.execute(
                """
                INSERT INTO websocket_errors
                (connection_id, error_type, error_message, created_at)
                VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
                """,
                connection_id,
                error_type,
                error_message,
            )
        except Exception as e:
            print(f"Warning: Failed to store metrics: {e}")  # nosec B608

    @beartype
    async def _store_system_metrics(self, metrics: SystemMetrics) -> None:
        """Store system metrics in database."""
        try:
            await self._db.execute(
                """
                INSERT INTO websocket_system_metrics
                (timestamp, total_connections, active_connections, peak_connections,
                 messages_per_second, avg_message_latency_ms, p95_message_latency_ms,
                 error_rate, memory_usage_mb, cpu_usage_percent)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                metrics.timestamp,
                metrics.total_connections,
                metrics.active_connections,
                metrics.peak_connections,
                metrics.messages_per_second,
                metrics.avg_message_latency_ms,
                metrics.p95_message_latency_ms,
                metrics.error_rate,
                metrics.memory_usage_mb,
                metrics.cpu_usage_percent,
            )
        except Exception as e:
            print(f"Warning: Failed to store metrics: {e}")  # nosec B608

    @beartype
    async def _handle_performance_alert(self, alert: PerformanceAlert) -> None:
        """Handle performance alert."""
        # Store alert in cache for admin dashboard
        alert_key = (
            f"websocket:alert:{alert.alert_type}:{int(alert.timestamp.timestamp())}"
        )
        await self._cache.setex(alert_key, 3600, alert.model_dump_json())  # 1 hour TTL

        # Could also send to notification system here
        # await notification_handler.send_admin_alert(alert)

    async def _get_priority_metrics(self) -> dict[str, Any]:
        """Get metrics broken down by message priority."""
        from .manager import MessagePriority

        priority_metrics = {}

        # Count messages by priority (would need to track this in practice)
        for priority in MessagePriority:
            priority_metrics[priority.value] = {
                "total_sent": 0,
                "total_received": 0,
                "avg_latency_ms": 0.0,
                "error_count": 0,
                "queue_depth": 0,
            }

        # In practice, these would be tracked from the connection manager
        # For now, return empty metrics structure
        return priority_metrics

    async def _store_priority_metrics(self, priority_metrics: dict[str, Any]) -> None:
        """Store priority metrics in database."""
        try:
            for priority, metrics in priority_metrics.items():
                await self._db.execute(
                    """
                    INSERT INTO websocket_priority_metrics
                    (timestamp, priority, total_sent, total_received, avg_latency_ms, error_count, queue_depth)
                    VALUES (CURRENT_TIMESTAMP, $1, $2, $3, $4, $5, $6)
                    """,
                    priority,
                    metrics["total_sent"],
                    metrics["total_received"],
                    metrics["avg_latency_ms"],
                    metrics["error_count"],
                    metrics["queue_depth"],
                )
        except Exception:
            # Non-critical, continue
            pass

    async def get_detailed_performance_report(self) -> dict[str, Any]:
        """Get comprehensive performance report."""
        current_metrics = await self.get_system_metrics()
        alerts = await self.get_performance_alerts()

        # Connection distribution by state
        connection_states: dict[str, int] = defaultdict(int)
        for conn in self._connection_metrics.values():
            if (datetime.now() - conn.last_activity).total_seconds() < 60:
                connection_states["active"] += 1
            elif (datetime.now() - conn.last_activity).total_seconds() < 300:
                connection_states["idle"] += 1
            else:
                connection_states["stale"] += 1

        # Top users by activity
        user_activity: dict[str, int] = defaultdict(int)
        for conn in self._connection_metrics.values():
            if conn.user_id:
                user_activity[str(conn.user_id)] += (
                    conn.messages_sent + conn.messages_received
                )

        top_users = sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:10]

        # Room statistics
        room_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"connections": 0, "messages": 0})
        for conn in self._connection_metrics.values():
            room_stats["total"]["connections"] += 1
            room_stats["total"]["messages"] += (
                conn.messages_sent + conn.messages_received
            )

        # Performance trends (last hour)
        hourly_trends = await self._get_hourly_trends()

        return {
            "timestamp": datetime.now().isoformat(),
            "system_metrics": current_metrics.model_dump(),
            "alerts": [alert.model_dump() for alert in alerts],
            "connection_distribution": dict(connection_states),
            "top_users_by_activity": top_users,
            "room_statistics": dict(room_stats),
            "performance_trends": hourly_trends,
            "health_score": self._calculate_health_score(current_metrics),
            "recommendations": self._get_performance_recommendations(current_metrics),
        }

    async def _get_hourly_trends(self) -> dict[str, list[float]]:
        """Get performance trends for the last hour."""
        # In practice, this would query the database for historical metrics
        # For now, return sample data structure
        return {
            "connection_count": [],
            "message_throughput": [],
            "avg_latency": [],
            "error_rate": [],
        }

    def _calculate_health_score(self, metrics: SystemMetrics) -> float:
        """Calculate overall system health score (0-100)."""
        score = 100.0

        # Deduct points for high utilization
        if metrics.total_connections > 0:
            utilization = metrics.total_connections / 10000  # Assuming 10k max
            if utilization > 0.8:
                score -= (utilization - 0.8) * 100

        # Deduct points for high latency
        if metrics.avg_message_latency_ms > 50:
            score -= min((metrics.avg_message_latency_ms - 50) / 10, 20)

        # Deduct points for high error rate
        if metrics.error_rate > 0.01:  # 1%
            score -= min(metrics.error_rate * 1000, 30)

        # Deduct points for high memory usage
        if metrics.memory_usage_mb > 500:
            score -= min((metrics.memory_usage_mb - 500) / 50, 20)

        return max(score, 0.0)

    def _get_performance_recommendations(self, metrics: SystemMetrics) -> list[str]:
        """Get performance improvement recommendations."""
        recommendations = []

        if metrics.total_connections > 8000:
            recommendations.append(
                "Consider scaling horizontally - connection count approaching limit"
            )

        if metrics.avg_message_latency_ms > 100:
            recommendations.append(
                "High message latency detected - check network and processing capacity"
            )

        if metrics.error_rate > 0.05:
            recommendations.append(
                "High error rate - investigate error logs and connection stability"
            )

        if metrics.memory_usage_mb > 1000:
            recommendations.append(
                "High memory usage - consider memory optimization or scaling"
            )

        if metrics.messages_per_second < 1 and metrics.total_connections > 100:
            recommendations.append(
                "Low message throughput - check for connection health issues"
            )

        if not recommendations:
            recommendations.append("System performance is optimal")

        return recommendations

    async def _cleanup_old_data(self) -> None:
        """Clean up old monitoring data."""
        # Clean up old message timestamps
        cutoff = datetime.now() - timedelta(hours=1)
        while self._message_timestamps and self._message_timestamps[0] < cutoff:
            self._message_timestamps.popleft()
            if self._message_latencies:
                self._message_latencies.popleft()

        # Clean up old error counts (keep only last 24 hours)
        if len(self._error_counts) > 1000:
            # Keep only the most recent error types
            sorted_errors = sorted(
                self._error_counts.items(), key=lambda x: x[1], reverse=True
            )
            self._error_counts = dict(sorted_errors[:500])

        # Clean up old connection metrics (keep only active connections)
        inactive_connections = []
        for conn_id, metrics in self._connection_metrics.items():
            if (
                datetime.now() - metrics.last_activity
            ).total_seconds() > 3600:  # 1 hour
                inactive_connections.append(conn_id)

        for conn_id in inactive_connections:
            del self._connection_metrics[conn_id]
