# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Performance monitoring middleware and utilities for Wave 2.5 implementation."""

import asyncio
import time
import tracemalloc
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any

from attrs import field, frozen
from beartype import beartype
from fastapi import Request, Response
from pydantic import Field
from starlette.middleware.base import BaseHTTPMiddleware

from pd_prime_demo.models.base import BaseModelConfig

from .result_types import Err, Ok, Result

# Auto-generated models


@beartype
class ErrorCountsCounts(BaseModelConfig):
    """Structured model replacing dict[str, int] usage."""

    total: int = Field(default=0, ge=0, description="Total count")


@beartype
class CountersCounts(BaseModelConfig):
    """Structured model replacing dict[str, int] usage."""

    total: int = Field(default=0, ge=0, description="Total count")


@frozen
class PerformanceMetrics:
    """Immutable performance metrics snapshot."""

    operation: str = field()
    total_requests: int = field()
    total_duration_ms: float = field()
    avg_duration_ms: float = field()
    min_duration_ms: float = field()
    max_duration_ms: float = field()
    p50_duration_ms: float = field()
    p95_duration_ms: float = field()
    p99_duration_ms: float = field()
    memory_usage_mb: float = field()
    error_rate: float = field()
    success_rate: float = field()
    requests_per_second: float = field()


@frozen
class RequestMetrics:
    """Individual request performance metrics."""

    method: str = field()
    endpoint: str = field()
    status_code: int = field()
    duration_ms: float = field()
    memory_allocated_mb: float = field()
    memory_peak_mb: float = field()
    timestamp: float = field()
    user_agent: str = field(default="")
    client_ip: str = field(default="")


class PerformanceCollector:
    """Thread-safe performance metrics collector with bounded memory usage."""

    def __init__(self, max_samples: int = 10000) -> None:
        """Initialize collector with maximum sample size."""
        self.max_samples = max_samples
        self._metrics: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=max_samples)
        )
        self._counters: CountersCounts = defaultdict(int)
        self._error_counts: ErrorCountsCounts = defaultdict(int)
        self._lock = asyncio.Lock()

    @beartype
    async def record_request(self, metrics: RequestMetrics) -> None:
        """Record request metrics with thread safety."""
        async with self._lock:
            endpoint_key = f"{metrics.method} {metrics.endpoint}"

            # Store detailed metrics
            self._metrics[endpoint_key].append(
                {
                    "duration_ms": metrics.duration_ms,
                    "memory_allocated_mb": metrics.memory_allocated_mb,
                    "memory_peak_mb": metrics.memory_peak_mb,
                    "timestamp": metrics.timestamp,
                    "status_code": metrics.status_code,
                }
            )

            # Update counters
            self._counters[endpoint_key] += 1
            if metrics.status_code >= 400:
                self._error_counts[endpoint_key] += 1

    @beartype
    async def get_metrics(self, operation: str) -> Result[PerformanceMetrics, str]:
        """Get aggregated metrics for an operation."""
        async with self._lock:
            if operation not in self._metrics:
                return Err(f"No metrics found for operation: {operation}")

            samples = list(self._metrics[operation])
            if not samples:
                return Err(f"No samples found for operation: {operation}")

            # Calculate statistics
            durations = [s["duration_ms"] for s in samples]
            memory_usage = [s["memory_peak_mb"] for s in samples]

            durations.sort()
            total_requests = len(durations)

            # Percentile calculations
            p50_idx = int(0.50 * total_requests)
            p95_idx = int(0.95 * total_requests)
            p99_idx = int(0.99 * total_requests)

            error_count = self._error_counts.get(operation, 0)
            success_count = total_requests - error_count

            # Calculate RPS over last minute
            current_time = time.time()
            recent_samples = [s for s in samples if current_time - s["timestamp"] <= 60]
            requests_per_second = len(recent_samples) / 60.0 if recent_samples else 0.0

            return Ok(
                PerformanceMetrics(
                    operation=operation,
                    total_requests=total_requests,
                    total_duration_ms=sum(durations),
                    avg_duration_ms=sum(durations) / total_requests,
                    min_duration_ms=min(durations),
                    max_duration_ms=max(durations),
                    p50_duration_ms=(
                        durations[p50_idx] if p50_idx < total_requests else 0.0
                    ),
                    p95_duration_ms=(
                        durations[p95_idx] if p95_idx < total_requests else 0.0
                    ),
                    p99_duration_ms=(
                        durations[p99_idx] if p99_idx < total_requests else 0.0
                    ),
                    memory_usage_mb=(
                        sum(memory_usage) / len(memory_usage) if memory_usage else 0.0
                    ),
                    error_rate=(
                        error_count / total_requests if total_requests > 0 else 0.0
                    ),
                    success_rate=(
                        success_count / total_requests if total_requests > 0 else 0.0
                    ),
                    requests_per_second=requests_per_second,
                )
            )

    @beartype
    async def get_all_metrics(self) -> dict[str, PerformanceMetrics]:
        """Get metrics for all tracked operations."""
        async with self._lock:
            results = {}
            for operation in self._metrics.keys():
                metrics_result = await self.get_metrics(operation)
                if metrics_result.is_ok():
                    results[operation] = metrics_result.unwrap()
            return results  # SYSTEM_BOUNDARY - Aggregated system data

    @beartype
    async def check_performance_alerts(self) -> list[str]:
        """Check for performance issues and return alerts."""
        alerts = []
        all_metrics = await self.get_all_metrics()

        for operation, metrics in all_metrics.items():
            # Alert on high P99 latency (>100ms requirement)
            if metrics.p99_duration_ms > 100:
                alerts.append(
                    f"HIGH LATENCY: {operation} P99 {metrics.p99_duration_ms:.1f}ms (>100ms threshold)"
                )

            # Alert on high error rate (>1%)
            if metrics.error_rate > 0.01:
                alerts.append(
                    f"HIGH ERROR RATE: {operation} {metrics.error_rate:.1%} (>1% threshold)"
                )

            # Alert on low RPS (possible performance issue)
            if metrics.requests_per_second > 0 and metrics.avg_duration_ms > 50:
                alerts.append(
                    f"SLOW RESPONSES: {operation} avg {metrics.avg_duration_ms:.1f}ms (>50ms target)"
                )

            # Alert on high memory usage (>10MB per request)
            if metrics.memory_usage_mb > 10:
                alerts.append(
                    f"HIGH MEMORY: {operation} avg {metrics.memory_usage_mb:.1f}MB (>10MB threshold)"
                )

        return alerts

    @beartype
    async def reset_metrics(self) -> None:
        """Reset all collected metrics."""
        async with self._lock:
            self._metrics.clear()
            self._counters.clear()
            self._error_counts.clear()


# Global performance collector
_performance_collector: PerformanceCollector | None = None


@beartype
def get_performance_collector() -> PerformanceCollector:
    """Get global performance collector instance."""
    global _performance_collector
    if _performance_collector is None:
        _performance_collector = PerformanceCollector()
    return _performance_collector


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """Comprehensive performance monitoring middleware for all API endpoints."""

    def __init__(self, app: Any, track_memory: bool = True) -> None:
        """Initialize performance monitoring middleware."""
        super().__init__(app)
        self.track_memory = track_memory
        self.collector = get_performance_collector()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Monitor request performance with memory tracking."""
        start_time = time.perf_counter()
        timestamp = time.time()

        # Start memory tracking if enabled
        memory_start = 0.0
        memory_peak = 0.0

        if self.track_memory:
            tracemalloc.start()
            snapshot_start = tracemalloc.take_snapshot()
            memory_start = (
                sum(stat.size for stat in snapshot_start.statistics("filename"))
                / 1024
                / 1024
            )

        try:
            # Process request
            response = await call_next(request)

            # Calculate performance metrics
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Memory tracking
            memory_allocated = 0.0
            if self.track_memory:
                try:
                    snapshot_end = tracemalloc.take_snapshot()
                    memory_end = (
                        sum(stat.size for stat in snapshot_end.statistics("filename"))
                        / 1024
                        / 1024
                    )
                    memory_allocated = memory_end - memory_start
                    memory_peak = (
                        memory_allocated  # Simplified - could track actual peak
                    )
                    tracemalloc.stop()
                except Exception:
                    # Memory tracking failed, continue without it
                    pass

            # Create metrics record
            metrics = RequestMetrics(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                memory_allocated_mb=memory_allocated,
                memory_peak_mb=memory_peak,
                timestamp=timestamp,
                user_agent=request.headers.get("user-agent", ""),
                client_ip=request.client.host if request.client else "",
            )

            # Record metrics asynchronously
            asyncio.create_task(self.collector.record_request(metrics))

            # Add performance headers
            response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
            response.headers["X-Memory-Usage-MB"] = f"{memory_allocated:.2f}"

            # Performance warnings in headers
            if duration_ms > 100:
                response.headers["X-Performance-Warning"] = "SLOW_RESPONSE"
            if memory_allocated > 10:
                response.headers["X-Performance-Warning"] = "HIGH_MEMORY"

            return response

        except Exception:
            # Record error metrics
            duration_ms = (time.perf_counter() - start_time) * 1000

            error_metrics = RequestMetrics(
                method=request.method,
                endpoint=request.url.path,
                status_code=500,
                duration_ms=duration_ms,
                memory_allocated_mb=0.0,
                memory_peak_mb=0.0,
                timestamp=timestamp,
                user_agent=request.headers.get("user-agent", ""),
                client_ip=request.client.host if request.client else "",
            )

            asyncio.create_task(self.collector.record_request(error_metrics))

            if self.track_memory:
                try:
                    tracemalloc.stop()
                except Exception:
                    pass

            raise


@beartype
def performance_monitor(
    track_memory: bool = True,
    log_slow_queries: bool = True,
    threshold_ms: float = 100,
    memory_threshold_mb: float = 1.0,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for monitoring function performance with memory tracking."""

    @beartype
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            memory_start = 0.0

            if track_memory:
                tracemalloc.start()
                snapshot_start = tracemalloc.take_snapshot()
                memory_start = (
                    sum(stat.size for stat in snapshot_start.statistics("filename"))
                    / 1024
                    / 1024
                )

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # Calculate metrics
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                memory_used = 0.0

                if track_memory:
                    try:
                        snapshot_end = tracemalloc.take_snapshot()
                        memory_end = (
                            sum(
                                stat.size
                                for stat in snapshot_end.statistics("filename")
                            )
                            / 1024
                            / 1024
                        )
                        memory_used = memory_end - memory_start
                        tracemalloc.stop()
                    except Exception:
                        pass

                # Log performance issues
                if log_slow_queries and (
                    elapsed_ms > threshold_ms or memory_used > memory_threshold_mb
                ):
                    import logging

                    logger = logging.getLogger(__name__)

                    warnings = []
                    if elapsed_ms > threshold_ms:
                        warnings.append(f"SLOW: {elapsed_ms:.1f}ms > {threshold_ms}ms")
                    if memory_used > memory_threshold_mb:
                        warnings.append(
                            f"MEMORY: {memory_used:.1f}MB > {memory_threshold_mb}MB"
                        )

                    logger.warning(
                        f"Performance issue in {func.__name__}: {' | '.join(warnings)}"
                    )

                return result

            except Exception:
                if track_memory:
                    try:
                        tracemalloc.stop()
                    except Exception:
                        pass
                raise

        @wraps(func)
        @beartype
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            memory_start = 0.0

            if track_memory:
                tracemalloc.start()
                snapshot_start = tracemalloc.take_snapshot()
                memory_start = (
                    sum(stat.size for stat in snapshot_start.statistics("filename"))
                    / 1024
                    / 1024
                )

            try:
                result = func(*args, **kwargs)

                # Calculate metrics
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                memory_used = 0.0

                if track_memory:
                    try:
                        snapshot_end = tracemalloc.take_snapshot()
                        memory_end = (
                            sum(
                                stat.size
                                for stat in snapshot_end.statistics("filename")
                            )
                            / 1024
                            / 1024
                        )
                        memory_used = memory_end - memory_start
                        tracemalloc.stop()
                    except Exception:
                        pass

                # Log performance issues
                if log_slow_queries and (
                    elapsed_ms > threshold_ms or memory_used > memory_threshold_mb
                ):
                    import logging

                    logger = logging.getLogger(__name__)

                    warnings = []
                    if elapsed_ms > threshold_ms:
                        warnings.append(f"SLOW: {elapsed_ms:.1f}ms > {threshold_ms}ms")
                    if memory_used > memory_threshold_mb:
                        warnings.append(
                            f"MEMORY: {memory_used:.1f}MB > {memory_threshold_mb}MB"
                        )

                    logger.warning(
                        f"Performance issue in {func.__name__}: {' | '.join(warnings)}"
                    )

                return result

            except Exception:
                if track_memory:
                    try:
                        tracemalloc.stop()
                    except Exception:
                        pass
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


@asynccontextmanager
@beartype
async def performance_context(operation_name: str) -> AsyncIterator[dict[str, Any]]:
    """Context manager for measuring operation performance."""
    start_time = time.perf_counter()
    tracemalloc.start()

    try:
        yield {}
    finally:
        duration_ms = (time.perf_counter() - start_time) * 1000

        try:
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            memory_mb = peak / 1024 / 1024
        except Exception:
            memory_mb = 0.0

        # Log performance data
        import logging

        logger = logging.getLogger(__name__)
        logger.info(
            f"Performance: {operation_name} completed in {duration_ms:.2f}ms, "
            f"peak memory: {memory_mb:.2f}MB"
        )


@beartype
async def benchmark_operation(
    operation_name: str,
    operation_func: Callable[[], Any],
    iterations: int = 100,
) -> PerformanceMetrics:
    """Benchmark an operation multiple times and return performance metrics."""
    durations = []
    memory_usage = []
    errors = 0

    for i in range(iterations):
        start_time = time.perf_counter()
        tracemalloc.start()

        try:
            if asyncio.iscoroutinefunction(operation_func):
                await operation_func()
            else:
                operation_func()

            duration_ms = (time.perf_counter() - start_time) * 1000
            durations.append(duration_ms)

            try:
                current, peak = tracemalloc.get_traced_memory()
                memory_usage.append(peak / 1024 / 1024)
            except Exception:
                memory_usage.append(0.0)

        except Exception:
            errors += 1
            durations.append((time.perf_counter() - start_time) * 1000)
            memory_usage.append(0.0)
        finally:
            try:
                tracemalloc.stop()
            except Exception:
                pass

    # Calculate statistics
    durations.sort()
    total_requests = len(durations)

    p50_idx = int(0.50 * total_requests)
    p95_idx = int(0.95 * total_requests)
    p99_idx = int(0.99 * total_requests)

    return PerformanceMetrics(
        operation=operation_name,
        total_requests=total_requests,
        total_duration_ms=sum(durations),
        avg_duration_ms=sum(durations) / total_requests,
        min_duration_ms=min(durations),
        max_duration_ms=max(durations),
        p50_duration_ms=durations[p50_idx],
        p95_duration_ms=durations[p95_idx],
        p99_duration_ms=durations[p99_idx],
        memory_usage_mb=sum(memory_usage) / len(memory_usage),
        error_rate=errors / total_requests,
        success_rate=(total_requests - errors) / total_requests,
        requests_per_second=(
            total_requests / (sum(durations) / 1000) if sum(durations) > 0 else 0.0
        ),
    )
