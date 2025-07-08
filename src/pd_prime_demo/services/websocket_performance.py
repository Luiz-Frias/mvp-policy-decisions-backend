"""WebSocket performance monitoring and optimization service."""

import asyncio
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

from ..core.cache import Cache
from ..core.database import Database


class ConnectionMetrics(BaseModel):
    """WebSocket connection performance metrics."""

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
    message_count: int = Field(default=0, ge=0)
    bytes_sent: int = Field(default=0, ge=0)
    bytes_received: int = Field(default=0, ge=0)
    avg_response_time_ms: float = Field(default=0.0, ge=0)
    error_count: int = Field(default=0, ge=0)
    reconnection_count: int = Field(default=0, ge=0)


class RoomMetrics(BaseModel):
    """WebSocket room performance metrics."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    room_id: str = Field(...)
    subscriber_count: int = Field(default=0, ge=0)
    message_count: int = Field(default=0, ge=0)
    bytes_transferred: int = Field(default=0, ge=0)
    avg_message_size: float = Field(default=0.0, ge=0)
    peak_subscribers: int = Field(default=0, ge=0)
    created_at: datetime = Field(...)
    last_activity: datetime = Field(...)


class PerformanceAlert(BaseModel):
    """Performance alert definition."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    alert_type: str = Field(...)
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    threshold_value: float = Field(...)
    current_value: float = Field(...)
    metric_name: str = Field(...)
    description: str = Field(...)
    recommended_action: str = Field(...)


class WebSocketPerformanceService:
    """Service for monitoring and optimizing WebSocket performance."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize performance service."""
        self._db = db
        self._cache = cache

        # Performance tracking
        self._connection_metrics: dict[str, ConnectionMetrics] = {}
        self._room_metrics: dict[str, RoomMetrics] = {}

        # Performance thresholds
        self._thresholds = {
            "max_connections": 10000,
            "max_room_size": 1000,
            "max_response_time_ms": 100,
            "max_error_rate": 0.05,
            "max_memory_usage_mb": 1000,
            "max_cpu_usage_percent": 80,
        }

        # Performance optimization settings
        self._optimization_enabled = True
        self._auto_scaling_enabled = True
        self._circuit_breaker_enabled = True

        # Background tasks
        self._monitoring_task: asyncio.Task[None] | None = None
        self._cleanup_task: asyncio.Task[None] | None = None

    async def start_monitoring(self) -> None:
        """Start performance monitoring tasks."""
        if self._monitoring_task is None:
            self._monitoring_task = asyncio.create_task(
                self._performance_monitoring_loop()
            )

        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_monitoring(self) -> None:
        """Stop performance monitoring tasks."""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    @beartype
    async def record_connection_start(
        self, connection_id: str, user_id: UUID | None = None
    ) -> None:
        """Record when a connection starts."""
        now = datetime.now()
        metrics = ConnectionMetrics(
            connection_id=connection_id,
            user_id=user_id,
            connected_at=now,
            last_activity=now,
        )
        self._connection_metrics[connection_id] = metrics

        # Store in cache for distributed tracking
        await self._cache.setex(
            f"ws:connection:{connection_id}",
            3600,  # 1 hour TTL
            metrics.model_dump_json(),
        )

    @beartype
    async def record_connection_end(self, connection_id: str) -> None:
        """Record when a connection ends."""
        if connection_id in self._connection_metrics:
            metrics = self._connection_metrics.pop(connection_id)

            # Store final metrics in database
            await self._store_connection_metrics(metrics)

            # Remove from cache
            await self._cache.delete(f"ws:connection:{connection_id}")

    @beartype
    async def record_message_sent(
        self, connection_id: str, message_size: int, response_time_ms: float
    ) -> None:
        """Record a message being sent."""
        if connection_id in self._connection_metrics:
            current = self._connection_metrics[connection_id]
            updated = current.model_copy(
                update={
                    "message_count": current.message_count + 1,
                    "bytes_sent": current.bytes_sent + message_size,
                    "last_activity": datetime.now(),
                    "avg_response_time_ms": (
                        (
                            current.avg_response_time_ms * current.message_count
                            + response_time_ms
                        )
                        / (current.message_count + 1)
                    ),
                }
            )
            self._connection_metrics[connection_id] = updated

    @beartype
    async def record_message_received(
        self, connection_id: str, message_size: int
    ) -> None:
        """Record a message being received."""
        if connection_id in self._connection_metrics:
            current = self._connection_metrics[connection_id]
            updated = current.model_copy(
                update={
                    "bytes_received": current.bytes_received + message_size,
                    "last_activity": datetime.now(),
                }
            )
            self._connection_metrics[connection_id] = updated

    @beartype
    async def record_connection_error(self, connection_id: str) -> None:
        """Record a connection error."""
        if connection_id in self._connection_metrics:
            current = self._connection_metrics[connection_id]
            updated = current.model_copy(
                update={
                    "error_count": current.error_count + 1,
                    "last_activity": datetime.now(),
                }
            )
            self._connection_metrics[connection_id] = updated

    @beartype
    async def record_room_activity(
        self, room_id: str, subscriber_count: int, message_size: int
    ) -> None:
        """Record room activity."""
        now = datetime.now()

        if room_id in self._room_metrics:
            current = self._room_metrics[room_id]
            updated = current.model_copy(
                update={
                    "subscriber_count": subscriber_count,
                    "message_count": current.message_count + 1,
                    "bytes_transferred": current.bytes_transferred + message_size,
                    "avg_message_size": (
                        (
                            current.avg_message_size * current.message_count
                            + message_size
                        )
                        / (current.message_count + 1)
                    ),
                    "peak_subscribers": max(current.peak_subscribers, subscriber_count),
                    "last_activity": now,
                }
            )
            self._room_metrics[room_id] = updated
        else:
            metrics = RoomMetrics(
                room_id=room_id,
                subscriber_count=subscriber_count,
                message_count=1,
                bytes_transferred=message_size,
                avg_message_size=message_size,
                peak_subscribers=subscriber_count,
                created_at=now,
                last_activity=now,
            )
            self._room_metrics[room_id] = metrics

    @beartype
    async def get_performance_summary(self) -> dict[str, Any]:
        """Get current performance summary."""
        total_connections = len(self._connection_metrics)
        total_rooms = len(self._room_metrics)

        # Calculate aggregate metrics
        if self._connection_metrics:
            avg_response_time = sum(
                m.avg_response_time_ms for m in self._connection_metrics.values()
            ) / len(self._connection_metrics)
            total_errors = sum(m.error_count for m in self._connection_metrics.values())
            error_rate = total_errors / max(
                sum(m.message_count for m in self._connection_metrics.values()), 1
            )
        else:
            avg_response_time = 0.0
            error_rate = 0.0

        # Room statistics
        if self._room_metrics:
            avg_room_size = sum(
                m.subscriber_count for m in self._room_metrics.values()
            ) / len(self._room_metrics)
            largest_room = max(m.subscriber_count for m in self._room_metrics.values())
        else:
            avg_room_size = 0.0
            largest_room = 0

        return {
            "connections": {
                "total": total_connections,
                "utilization": total_connections / self._thresholds["max_connections"],
                "avg_response_time_ms": avg_response_time,
                "error_rate": error_rate,
            },
            "rooms": {
                "total": total_rooms,
                "avg_size": avg_room_size,
                "largest_room": largest_room,
            },
            "thresholds": self._thresholds,
            "optimization_enabled": self._optimization_enabled,
        }

    @beartype
    async def check_performance_alerts(self) -> list[PerformanceAlert]:
        """Check for performance issues and generate alerts."""
        alerts = []
        summary = await self.get_performance_summary()

        # Check connection utilization
        connection_utilization = summary["connections"]["utilization"]
        if connection_utilization > 0.9:
            alerts.append(
                PerformanceAlert(
                    alert_type="high_connection_utilization",
                    severity="critical" if connection_utilization > 0.95 else "high",
                    threshold_value=0.9,
                    current_value=connection_utilization,
                    metric_name="connection_utilization",
                    description=f"WebSocket connection utilization at {connection_utilization:.1%}",
                    recommended_action="Scale WebSocket servers or implement connection limiting",
                )
            )

        # Check response time
        avg_response_time = summary["connections"]["avg_response_time_ms"]
        if avg_response_time > self._thresholds["max_response_time_ms"]:
            alerts.append(
                PerformanceAlert(
                    alert_type="high_response_time",
                    severity="medium" if avg_response_time < 200 else "high",
                    threshold_value=self._thresholds["max_response_time_ms"],
                    current_value=avg_response_time,
                    metric_name="avg_response_time_ms",
                    description=f"Average response time is {avg_response_time:.1f}ms",
                    recommended_action="Optimize message processing or scale infrastructure",
                )
            )

        # Check error rate
        error_rate = summary["connections"]["error_rate"]
        if error_rate > self._thresholds["max_error_rate"]:
            alerts.append(
                PerformanceAlert(
                    alert_type="high_error_rate",
                    severity="critical" if error_rate > 0.1 else "high",
                    threshold_value=self._thresholds["max_error_rate"],
                    current_value=error_rate,
                    metric_name="error_rate",
                    description=f"Error rate is {error_rate:.1%}",
                    recommended_action="Investigate connection stability and error causes",
                )
            )

        # Check room sizes
        largest_room = summary["rooms"]["largest_room"]
        if largest_room > self._thresholds["max_room_size"]:
            alerts.append(
                PerformanceAlert(
                    alert_type="large_room_detected",
                    severity="medium" if largest_room < 2000 else "high",
                    threshold_value=self._thresholds["max_room_size"],
                    current_value=largest_room,
                    metric_name="largest_room_size",
                    description=f"Room with {largest_room} subscribers detected",
                    recommended_action="Consider room partitioning or optimization",
                )
            )

        return alerts

    @beartype
    async def optimize_performance(self) -> list[str]:
        """Apply automatic performance optimizations."""
        if not self._optimization_enabled:
            return ["Performance optimization is disabled"]

        optimizations_applied = []
        alerts = await self.check_performance_alerts()

        for alert in alerts:
            if alert.alert_type == "high_connection_utilization":
                # Implement connection throttling
                await self._enable_connection_throttling()
                optimizations_applied.append("Enabled connection throttling")

            elif alert.alert_type == "high_response_time":
                # Enable message batching
                await self._enable_message_batching()
                optimizations_applied.append("Enabled message batching")

            elif alert.alert_type == "large_room_detected":
                # Implement room partitioning suggestions
                await self._suggest_room_partitioning(alert.current_value)
                optimizations_applied.append("Suggested room partitioning")

        return optimizations_applied or ["No optimizations needed"]

    async def _performance_monitoring_loop(self) -> None:
        """Background loop for performance monitoring."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds

                # Check for alerts
                alerts = await self.check_performance_alerts()

                if alerts:
                    # Store alerts for admin review
                    await self._store_performance_alerts(alerts)

                    # Apply automatic optimizations
                    if self._optimization_enabled:
                        await self.optimize_performance()

                # Update performance metrics in cache
                summary = await self.get_performance_summary()
                await self._cache.setex(
                    "ws:performance:summary", 60, str(summary)  # 1 minute TTL
                )

            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue monitoring
                pass

    async def _cleanup_loop(self) -> None:
        """Background loop for cleaning up old metrics."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour

                # Clean up old connection metrics
                cutoff = datetime.now() - timedelta(hours=24)
                expired_connections = [
                    conn_id
                    for conn_id, metrics in self._connection_metrics.items()
                    if metrics.last_activity < cutoff
                ]

                for conn_id in expired_connections:
                    self._connection_metrics.pop(conn_id, None)

                # Clean up old room metrics
                expired_rooms = [
                    room_id
                    for room_id, metrics in self._room_metrics.items()
                    if metrics.last_activity < cutoff and metrics.subscriber_count == 0
                ]

                for room_id in expired_rooms:
                    self._room_metrics.pop(room_id, None)

            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue cleanup
                pass

    @beartype
    async def _store_connection_metrics(self, metrics: ConnectionMetrics) -> None:
        """Store connection metrics in database."""
        try:
            await self._db.execute(
                """
                INSERT INTO websocket_performance_logs
                (connection_id, user_id, connected_at, disconnected_at,
                 message_count, bytes_sent, bytes_received, avg_response_time_ms,
                 error_count, reconnection_count)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (connection_id) DO UPDATE SET
                    disconnected_at = EXCLUDED.disconnected_at,
                    message_count = EXCLUDED.message_count,
                    bytes_sent = EXCLUDED.bytes_sent,
                    bytes_received = EXCLUDED.bytes_received,
                    avg_response_time_ms = EXCLUDED.avg_response_time_ms,
                    error_count = EXCLUDED.error_count,
                    reconnection_count = EXCLUDED.reconnection_count
                """,
                metrics.connection_id,
                metrics.user_id,
                metrics.connected_at,
                datetime.now(),  # disconnected_at
                metrics.message_count,
                metrics.bytes_sent,
                metrics.bytes_received,
                metrics.avg_response_time_ms,
                metrics.error_count,
                metrics.reconnection_count,
            )
        except Exception:
            # Non-critical operation
            pass

    @beartype
    async def _store_performance_alerts(self, alerts: list[PerformanceAlert]) -> None:
        """Store performance alerts in database."""
        for alert in alerts:
            try:
                await self._db.execute(
                    """
                    INSERT INTO performance_alerts
                    (alert_type, severity, metric_name, threshold_value, current_value,
                     description, recommended_action, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    alert.alert_type,
                    alert.severity,
                    alert.metric_name,
                    alert.threshold_value,
                    alert.current_value,
                    alert.description,
                    alert.recommended_action,
                    datetime.now(),
                )
            except Exception:
                # Non-critical operation
                pass

    async def _enable_connection_throttling(self) -> None:
        """Enable connection throttling to reduce load."""
        # Store throttling configuration in cache
        await self._cache.setex("ws:throttling:enabled", 3600, "true")  # 1 hour

    async def _enable_message_batching(self) -> None:
        """Enable message batching to improve efficiency."""
        # Store batching configuration in cache
        await self._cache.setex("ws:batching:enabled", 3600, "true")  # 1 hour

    async def _suggest_room_partitioning(self, room_size: float) -> None:
        """Suggest room partitioning for large rooms."""
        # Store partitioning suggestion in cache
        await self._cache.setex(
            "ws:room_partitioning:suggested", 3600, f"room_size:{room_size}"  # 1 hour
        )
