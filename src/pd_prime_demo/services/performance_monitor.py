"""Performance monitoring decorator for critical quote operations."""

import asyncio
import json
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from beartype import beartype

P = ParamSpec("P")
T = TypeVar("T")


@beartype
def performance_monitor(
    operation_name: str,
    max_duration_ms: int = 2000,
    memory_threshold_mb: int = 100,
    log_slow_operations: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator to monitor performance of critical quote operations.

    This decorator follows the master ruleset requirement that functions >10 lines
    must have performance benchmarks and tracks:
    - Execution time with alerting for slow operations
    - Memory usage patterns
    - Operation success/failure rates

    Args:
        operation_name: Name of the operation for monitoring
        max_duration_ms: Alert threshold in milliseconds
        memory_threshold_mb: Memory usage alert threshold in MB
        log_slow_operations: Whether to log slow operations
    """

    @beartype
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start_time = time.perf_counter()
            operation_id = f"{operation_name}_{int(start_time * 1000)}"

            # Get initial memory state (simplified - in production use tracemalloc)
            try:
                import tracemalloc

                tracemalloc.start()
                snapshot_start = tracemalloc.take_snapshot()
            except Exception:
                snapshot_start = None

            try:
                # Execute the function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                # Calculate metrics
                duration_ms = (time.perf_counter() - start_time) * 1000

                # Memory tracking
                memory_usage_mb = 0.0
                if snapshot_start:
                    try:
                        snapshot_end = tracemalloc.take_snapshot()
                        top_stats = snapshot_end.compare_to(snapshot_start, "lineno")
                        if top_stats:
                            memory_usage_mb = float(
                                sum(stat.size_diff for stat in top_stats[:10])
                                / 1024
                                / 1024
                            )
                    except Exception:
                        pass

                # Log performance metrics
                await _log_performance_metrics(
                    operation_id=operation_id,
                    operation_name=operation_name,
                    duration_ms=duration_ms,
                    memory_usage_mb=memory_usage_mb,
                    success=True,
                    max_duration_ms=max_duration_ms,
                    memory_threshold_mb=memory_threshold_mb,
                    log_slow_operations=log_slow_operations,
                )

                return result  # type: ignore[no-any-return]

            except Exception as e:
                # Log failed operation
                duration_ms = (time.perf_counter() - start_time) * 1000

                await _log_performance_metrics(
                    operation_id=operation_id,
                    operation_name=operation_name,
                    duration_ms=duration_ms,
                    memory_usage_mb=0,
                    success=False,
                    error=str(e),
                    max_duration_ms=max_duration_ms,
                    memory_threshold_mb=memory_threshold_mb,
                    log_slow_operations=log_slow_operations,
                )

                raise

            finally:
                if snapshot_start:
                    try:
                        tracemalloc.stop()
                    except Exception:
                        pass

        @wraps(func)
        @beartype
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # For synchronous functions, use simplified monitoring
            start_time = time.perf_counter()

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000

                # Simple logging for sync functions
                if log_slow_operations and duration_ms > max_duration_ms:
                    print(
                        f"PERFORMANCE WARNING: {operation_name} took {duration_ms:.2f}ms (threshold: {max_duration_ms}ms)"
                    )

                return result

            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                print(
                    f"PERFORMANCE ERROR: {operation_name} failed after {duration_ms:.2f}ms: {str(e)}"
                )
                raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        else:
            return sync_wrapper

    return decorator


@beartype
async def _log_performance_metrics(
    operation_id: str,
    operation_name: str,
    duration_ms: float,
    memory_usage_mb: float,
    success: bool,
    max_duration_ms: int,
    memory_threshold_mb: int,
    log_slow_operations: bool,
    error: str | None = None,
) -> None:
    """Log performance metrics for monitoring and alerting."""

    # Create performance metrics
    metrics = {
        "operation_id": operation_id,
        "operation_name": operation_name,
        "duration_ms": round(duration_ms, 2),
        "memory_usage_mb": round(memory_usage_mb, 2),
        "success": success,
        "timestamp": time.time(),
        "error": error,
    }

    # Check for performance violations
    violations = []

    if duration_ms > max_duration_ms:
        violations.append(
            f"Slow operation: {duration_ms:.2f}ms > {max_duration_ms}ms threshold"
        )

    if memory_usage_mb > memory_threshold_mb:
        violations.append(
            f"High memory usage: {memory_usage_mb:.2f}MB > {memory_threshold_mb}MB threshold"
        )

    # Log warnings for violations
    if violations and log_slow_operations:
        print(f"PERFORMANCE WARNING [{operation_name}]: {', '.join(violations)}")
        print(f"Metrics: {json.dumps(metrics, indent=2)}")

    # In production, this would send to monitoring system (DataDog, New Relic, etc.)
    # For now, we'll store in a simple format that could be picked up by monitoring
    try:
        # This could write to a monitoring file, send to logging service, etc.
        # await send_to_monitoring_system(metrics)
        pass
    except Exception:
        # Never fail the operation due to monitoring issues
        pass


@beartype
class PerformanceTracker:
    """Class-based performance tracking for quote service operations."""

    def __init__(self) -> None:
        """Initialize performance tracker."""
        self._operation_stats: dict[str, dict[str, Any]] = {}

    @beartype
    def track_operation(
        self, operation_name: str, duration_ms: float, success: bool
    ) -> None:
        """Track an operation's performance."""
        if operation_name not in self._operation_stats:
            self._operation_stats[operation_name] = {
                "count": 0,
                "total_duration_ms": 0,
                "success_count": 0,
                "failure_count": 0,
                "avg_duration_ms": 0,
                "max_duration_ms": 0,
                "min_duration_ms": float("inf"),
            }

        stats = self._operation_stats[operation_name]
        stats["count"] += 1
        stats["total_duration_ms"] += duration_ms

        if success:
            stats["success_count"] += 1
        else:
            stats["failure_count"] += 1

        stats["avg_duration_ms"] = stats["total_duration_ms"] / stats["count"]
        stats["max_duration_ms"] = max(stats["max_duration_ms"], duration_ms)
        stats["min_duration_ms"] = min(stats["min_duration_ms"], duration_ms)

    @beartype
    def get_operation_stats(self, operation_name: str) -> dict[str, Any] | None:
        """Get performance stats for an operation."""
        return self._operation_stats.get(operation_name)

    @beartype
    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get all operation statistics."""
        return self._operation_stats.copy()

    @beartype
    def reset_stats(self) -> None:
        """Reset all performance statistics."""
        self._operation_stats.clear()


# Global performance tracker instance
performance_tracker = PerformanceTracker()
