"""WebSocket reconnection strategies and client-side connection management."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class ReconnectionStrategy(str, Enum):
    """Reconnection strategy types."""

    IMMEDIATE = "immediate"
    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    CUSTOM = "custom"


class ConnectionState(str, Enum):
    """Connection state for reconnection logic."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    ABANDONED = "abandoned"


@dataclass
class ReconnectionAttempt:
    """Details of a reconnection attempt."""

    attempt_number: int
    timestamp: datetime
    delay_seconds: float
    reason: str
    success: bool
    error: str | None = None


class ReconnectionConfig(BaseModel):
    """Configuration for reconnection behavior."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    strategy: ReconnectionStrategy = Field(
        default=ReconnectionStrategy.EXPONENTIAL_BACKOFF
    )
    max_attempts: int = Field(default=10, ge=1, le=100)
    initial_delay_seconds: float = Field(default=1.0, ge=0.1, le=60.0)
    max_delay_seconds: float = Field(default=30.0, ge=1.0, le=300.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    jitter_enabled: bool = Field(default=True)
    jitter_max_seconds: float = Field(default=1.0, ge=0.0, le=10.0)

    # Connection health checks
    ping_interval_seconds: float = Field(default=30.0, ge=5.0, le=300.0)
    ping_timeout_seconds: float = Field(default=10.0, ge=1.0, le=60.0)

    # Failure detection
    consecutive_failures_threshold: int = Field(default=3, ge=1, le=10)
    failure_window_seconds: int = Field(default=300, ge=60, le=3600)  # 5 minutes

    # Circuit breaker
    circuit_breaker_enabled: bool = Field(default=True)
    circuit_breaker_failure_threshold: int = Field(default=5, ge=1, le=20)
    circuit_breaker_timeout_seconds: int = Field(default=60, ge=10, le=600)


class ConnectionMetrics(BaseModel):
    """Metrics for connection health and performance."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    total_connections: int = Field(default=0, ge=0)
    successful_connections: int = Field(default=0, ge=0)
    failed_connections: int = Field(default=0, ge=0)
    total_reconnections: int = Field(default=0, ge=0)
    current_uptime_seconds: float = Field(default=0.0, ge=0.0)
    average_connection_duration_seconds: float = Field(default=0.0, ge=0.0)
    last_connection_timestamp: datetime | None = Field(default=None)
    last_disconnection_timestamp: datetime | None = Field(default=None)
    last_error: str | None = Field(default=None)

    @property
    def success_rate(self) -> float:
        """Calculate connection success rate."""
        if self.total_connections == 0:
            return 0.0
        return self.successful_connections / self.total_connections

    @property
    def is_healthy(self) -> bool:
        """Check if connection is healthy based on metrics."""
        return (
            self.success_rate >= 0.9  # 90% success rate
            and self.current_uptime_seconds >= 60.0  # At least 1 minute uptime
        )


class ReconnectionManager:
    """Manages WebSocket reconnection strategies and connection health."""

    def __init__(self, config: ReconnectionConfig = None) -> None:
        """Initialize reconnection manager."""
        self.config = config or ReconnectionConfig()

        # State tracking
        self.state = ConnectionState.DISCONNECTED
        self.connection_id: str | None = None
        self.user_id: UUID | None = None

        # Attempt tracking
        self.attempts: list[ReconnectionAttempt] = []
        self.current_attempt = 0
        self.last_successful_connection: datetime | None = None
        self.connection_start_time: datetime | None = None

        # Circuit breaker state
        self.circuit_breaker_state = "closed"  # closed, open, half-open
        self.circuit_breaker_failures = 0
        self.circuit_breaker_last_failure: datetime | None = None

        # Metrics
        self.metrics = ConnectionMetrics()

        # Callbacks
        self.on_connection_established: Callable[[str], None] | None = None
        self.on_connection_lost: Callable[[str], None] | None = None
        self.on_reconnection_attempt: Callable[[int, float], None] | None = None
        self.on_reconnection_failed: Callable[[str], None] | None = None

        # Background tasks
        self._health_check_task: asyncio.Task | None = None
        self._reconnection_task: asyncio.Task | None = None

        # Health check state
        self._last_ping_time: datetime | None = None
        self._ping_response_times: list[float] = []

    async def start(self) -> None:
        """Start the reconnection manager."""
        self._health_check_task = asyncio.create_task(self._health_check_loop())

    async def stop(self) -> None:
        """Stop the reconnection manager."""
        for task in [self._health_check_task, self._reconnection_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    @beartype
    async def handle_connection_established(
        self, connection_id: str, user_id: UUID = None
    ) -> None:
        """Handle successful connection establishment."""
        self.state = ConnectionState.CONNECTED
        self.connection_id = connection_id
        self.user_id = user_id
        self.connection_start_time = datetime.now()
        self.last_successful_connection = datetime.now()

        # Reset circuit breaker
        self.circuit_breaker_state = "closed"
        self.circuit_breaker_failures = 0

        # Update metrics
        self.metrics = self.metrics.model_copy(
            update={
                "total_connections": self.metrics.total_connections + 1,
                "successful_connections": self.metrics.successful_connections + 1,
                "last_connection_timestamp": datetime.now(),
            }
        )

        # Record successful attempt
        if self.attempts:
            self.attempts[-1].success = True

        # Reset attempt counter
        self.current_attempt = 0

        # Callback
        if self.on_connection_established:
            self.on_connection_established(connection_id)

        logger.info(f"Connection established: {connection_id}")

    @beartype
    async def handle_connection_lost(self, reason: str) -> None:
        """Handle connection loss and initiate reconnection."""
        if self.state == ConnectionState.DISCONNECTED:
            return  # Already handled

        self.state = ConnectionState.DISCONNECTED

        # Calculate uptime
        uptime = 0.0
        if self.connection_start_time:
            uptime = (datetime.now() - self.connection_start_time).total_seconds()

        # Update metrics
        self.metrics = self.metrics.model_copy(
            update={
                "current_uptime_seconds": uptime,
                "last_disconnection_timestamp": datetime.now(),
                "last_error": reason,
            }
        )

        # Callback
        if self.on_connection_lost:
            self.on_connection_lost(reason)

        logger.warning(f"Connection lost: {reason}")

        # Start reconnection if not already running
        if not self._reconnection_task or self._reconnection_task.done():
            self._reconnection_task = asyncio.create_task(self._reconnection_loop())

    @beartype
    async def handle_reconnection_failed(self, error: str) -> None:
        """Handle failed reconnection attempt."""
        self.circuit_breaker_failures += 1
        self.circuit_breaker_last_failure = datetime.now()

        # Check circuit breaker
        if (
            self.config.circuit_breaker_enabled
            and self.circuit_breaker_failures
            >= self.config.circuit_breaker_failure_threshold
        ):
            self.circuit_breaker_state = "open"
            logger.error(
                f"Circuit breaker opened after {self.circuit_breaker_failures} failures"
            )

        # Update metrics
        self.metrics = self.metrics.model_copy(
            update={
                "failed_connections": self.metrics.failed_connections + 1,
                "last_error": error,
            }
        )

        # Record failed attempt
        if self.attempts:
            self.attempts[-1].success = False
            self.attempts[-1].error = error

        # Callback
        if self.on_reconnection_failed:
            self.on_reconnection_failed(error)

        logger.error(f"Reconnection failed: {error}")

    @beartype
    def should_attempt_reconnection(self) -> bool:
        """Check if reconnection should be attempted."""
        # Check max attempts
        if self.current_attempt >= self.config.max_attempts:
            return False

        # Check circuit breaker
        if self.circuit_breaker_state == "open":
            # Check if we can try half-open
            if (
                self.circuit_breaker_last_failure
                and (datetime.now() - self.circuit_breaker_last_failure).total_seconds()
                > self.config.circuit_breaker_timeout_seconds
            ):
                self.circuit_breaker_state = "half-open"
                return True
            return False

        return True

    @beartype
    def get_next_delay(self) -> float:
        """Calculate delay for next reconnection attempt."""
        if self.config.strategy == ReconnectionStrategy.IMMEDIATE:
            delay = 0.0
        elif self.config.strategy == ReconnectionStrategy.FIXED_DELAY:
            delay = self.config.initial_delay_seconds
        elif self.config.strategy == ReconnectionStrategy.EXPONENTIAL_BACKOFF:
            delay = min(
                self.config.initial_delay_seconds
                * (self.config.backoff_multiplier**self.current_attempt),
                self.config.max_delay_seconds,
            )
        elif self.config.strategy == ReconnectionStrategy.LINEAR_BACKOFF:
            delay = min(
                self.config.initial_delay_seconds
                + (self.current_attempt * self.config.initial_delay_seconds),
                self.config.max_delay_seconds,
            )
        else:
            delay = self.config.initial_delay_seconds

        # Add jitter if enabled
        if self.config.jitter_enabled:
            import random

            jitter = random.uniform(0, self.config.jitter_max_seconds)
            delay += jitter

        return delay

    @beartype
    async def get_connection_health(self) -> dict[str, Any]:
        """Get current connection health status."""
        return {
            "state": self.state.value,
            "connection_id": self.connection_id,
            "uptime_seconds": self.metrics.current_uptime_seconds,
            "success_rate": self.metrics.success_rate,
            "is_healthy": self.metrics.is_healthy,
            "circuit_breaker_state": self.circuit_breaker_state,
            "current_attempt": self.current_attempt,
            "max_attempts": self.config.max_attempts,
            "last_ping_response_time": (
                self._ping_response_times[-1] if self._ping_response_times else None
            ),
            "avg_ping_response_time": (
                sum(self._ping_response_times) / len(self._ping_response_times)
                if self._ping_response_times
                else None
            ),
        }

    async def _reconnection_loop(self) -> None:
        """Main reconnection loop."""
        while (
            self.state == ConnectionState.DISCONNECTED
            and self.should_attempt_reconnection()
        ):
            try:
                self.state = ConnectionState.RECONNECTING
                self.current_attempt += 1

                # Calculate delay
                delay = self.get_next_delay()

                # Create attempt record
                attempt = ReconnectionAttempt(
                    attempt_number=self.current_attempt,
                    timestamp=datetime.now(),
                    delay_seconds=delay,
                    reason="Connection lost",
                    success=False,
                )
                self.attempts.append(attempt)

                # Callback
                if self.on_reconnection_attempt:
                    self.on_reconnection_attempt(self.current_attempt, delay)

                logger.info(
                    f"Reconnection attempt {self.current_attempt}/{self.config.max_attempts} in {delay:.2f}s"
                )

                # Wait before attempting
                await asyncio.sleep(delay)

                # Attempt reconnection (this would be implemented by the WebSocket client)
                # For now, we just simulate the attempt
                # In a real implementation, this would trigger the WebSocket connection logic

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in reconnection loop: {e}")
                await self.handle_reconnection_failed(str(e))

        # If we've exhausted all attempts, mark as failed
        if self.current_attempt >= self.config.max_attempts:
            self.state = ConnectionState.FAILED
            logger.error(
                f"Reconnection failed after {self.config.max_attempts} attempts"
            )

    async def _health_check_loop(self) -> None:
        """Background health check loop."""
        while True:
            try:
                if self.state == ConnectionState.CONNECTED:
                    await asyncio.sleep(self.config.ping_interval_seconds)

                    # Send ping (this would be implemented by the WebSocket client)
                    ping_start = datetime.now()
                    self._last_ping_time = ping_start

                    # In a real implementation, this would send a ping and wait for pong
                    # For now, we simulate a successful ping
                    await asyncio.sleep(0.1)  # Simulate network latency

                    # Record ping response time
                    response_time = (
                        datetime.now() - ping_start
                    ).total_seconds() * 1000  # ms
                    self._ping_response_times.append(response_time)

                    # Keep only recent ping times
                    if len(self._ping_response_times) > 100:
                        self._ping_response_times = self._ping_response_times[-100:]

                    # Check if ping took too long
                    if response_time > self.config.ping_timeout_seconds * 1000:
                        await self.handle_connection_lost("Ping timeout")
                else:
                    await asyncio.sleep(
                        1
                    )  # Check state every second when not connected

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                if self.state == ConnectionState.CONNECTED:
                    await self.handle_connection_lost(f"Health check error: {e}")

    def get_metrics(self) -> ConnectionMetrics:
        """Get connection metrics."""
        # Update current uptime if connected
        if self.state == ConnectionState.CONNECTED and self.connection_start_time:
            uptime = (datetime.now() - self.connection_start_time).total_seconds()
            self.metrics = self.metrics.model_copy(
                update={"current_uptime_seconds": uptime}
            )

        return self.metrics

    def get_recent_attempts(self, limit: int = 10) -> list[ReconnectionAttempt]:
        """Get recent reconnection attempts."""
        return self.attempts[-limit:] if self.attempts else []
