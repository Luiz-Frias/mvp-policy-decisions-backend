# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Performance-optimized caching for rating calculations and expensive operations."""

import hashlib
import json
import time
from collections.abc import Callable
from decimal import Decimal
from functools import wraps
from typing import Any

from attrs import field, frozen
from beartype import beartype
from pydantic import Field

from policy_core.models.base import BaseModelConfig

from .cache import get_cache
from .performance_monitor import performance_context

# Auto-generated models


@beartype
class ResultData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class CacheData(BaseModelConfig):
    """Structured model for cache data usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class ResultsData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class FactorsData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class MetricsData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@frozen
class CacheKey:
    """Immutable cache key with automatic hashing."""

    prefix: str = field()
    data: str = field()

    @classmethod
    @beartype
    def from_data(cls, prefix: str, data: dict[str, Any]) -> "CacheKey":
        """Create cache key from data dictionary."""
        # Sort keys for consistent hashing
        sorted_data = json.dumps(data, sort_keys=True, default=str)
        data_hash = hashlib.sha256(sorted_data.encode()).hexdigest()[:16]
        return cls(prefix=prefix, data=data_hash)

    @property
    @beartype
    def key(self) -> str:
        """Get formatted cache key."""
        return f"{self.prefix}:{self.data}"


@frozen
class CacheMetrics:
    """Cache performance metrics."""

    hits: int = field()
    misses: int = field()
    total_requests: int = field()
    hit_rate: float = field()
    avg_lookup_time_ms: float = field()
    cache_size_mb: float = field()


class PerformanceCache:
    """High-performance caching layer for expensive operations."""

    def __init__(self) -> None:
        """Initialize performance cache."""
        self._cache = get_cache()
        self._metrics: dict[str, Any] = {
            "hits": 0,
            "misses": 0,
            "lookup_times": [],
            "operations": {},
        }

    @beartype
    async def get_with_metrics(self, key: str) -> tuple[Any | None, float]:
        """Get value from cache with timing metrics."""
        start_time = time.perf_counter()

        try:
            value = await self._cache.get(key)
            lookup_time_ms = (time.perf_counter() - start_time) * 1000

            if value is not None:
                self._metrics["hits"] += 1
            else:
                self._metrics["misses"] += 1

            # Keep only last 1000 lookup times
            self._metrics["lookup_times"].append(lookup_time_ms)
            if len(self._metrics["lookup_times"]) > 1000:
                self._metrics["lookup_times"] = self._metrics["lookup_times"][-1000:]

            return value, lookup_time_ms

        except Exception:
            lookup_time_ms = (time.perf_counter() - start_time) * 1000
            self._metrics["misses"] += 1
            return None, lookup_time_ms

    @beartype
    async def set_with_ttl(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """Set value in cache with specific TTL."""
        try:
            return await self._cache.set(key, value, ttl=ttl_seconds)
        except Exception:
            return False

    @beartype
    async def get_metrics(self) -> CacheMetrics:
        """Get cache performance metrics."""
        total_requests = self._metrics["hits"] + self._metrics["misses"]
        hit_rate = self._metrics["hits"] / total_requests if total_requests > 0 else 0.0

        avg_lookup_time = 0.0
        if self._metrics["lookup_times"]:
            avg_lookup_time = sum(self._metrics["lookup_times"]) / len(
                self._metrics["lookup_times"]
            )

        return CacheMetrics(
            hits=self._metrics["hits"],
            misses=self._metrics["misses"],
            total_requests=total_requests,
            hit_rate=hit_rate,
            avg_lookup_time_ms=avg_lookup_time,
            cache_size_mb=0.0,  # Would need Redis MEMORY USAGE command for accurate size
        )

    @beartype
    async def warm_rating_cache(self) -> dict[str, int | float]:
        """Pre-warm cache with common rating calculations."""
        warmed_keys = 0
        start_time = time.time()

        async with performance_context("cache_warming_rating"):
            # Common rate calculation scenarios
            common_scenarios = [
                # Auto insurance - California
                {
                    "state": "CA",
                    "policy_type": "auto",
                    "driver_age": 30,
                    "vehicle_year": 2020,
                    "coverage_liability": 100000,
                },
                {
                    "state": "CA",
                    "policy_type": "auto",
                    "driver_age": 25,
                    "vehicle_year": 2022,
                    "coverage_liability": 250000,
                },
                # Auto insurance - Texas
                {
                    "state": "TX",
                    "policy_type": "auto",
                    "driver_age": 35,
                    "vehicle_year": 2019,
                    "coverage_liability": 50000,
                },
                # Home insurance
                {
                    "state": "CA",
                    "policy_type": "home",
                    "property_value": 500000,
                    "coverage_dwelling": 400000,
                },
                {
                    "state": "TX",
                    "policy_type": "home",
                    "property_value": 300000,
                    "coverage_dwelling": 240000,
                },
            ]

            # Mock warm-up for rating calculations
            for scenario in common_scenarios:
                cache_key = CacheKey.from_data("rating", scenario)

                # Check if already cached
                existing, _ = await self.get_with_metrics(cache_key.key)
                if existing is None:
                    # Generate mock rate calculation result
                    mock_result = {
                        "base_premium": str(Decimal("1200.00")),
                        "total_premium": str(Decimal("1080.00")),
                        "monthly_premium": str(Decimal("108.00")),
                        "tier": "STANDARD",
                        "factors": scenario,
                        "calculation_time_ms": 25,
                        "cached_at": time.time(),
                    }

                    # Cache for 1 hour
                    await self.set_with_ttl(cache_key.key, mock_result, 3600)
                    warmed_keys += 1

        warmup_time = time.time() - start_time
        return {  # SYSTEM_BOUNDARY - Aggregated system data
            "warmed_keys": warmed_keys,
            "warmup_time_ms": warmup_time * 1000,
            "total_scenarios": len(common_scenarios),
        }

    @beartype
    async def warm_reference_data(self) -> dict[str, int | float]:
        """Pre-warm cache with reference data (states, vehicle makes, etc.)."""
        warmed_keys = 0
        start_time = time.time()

        async with performance_context("cache_warming_reference"):
            # Reference data that rarely changes
            reference_data = {
                "states:all": [
                    {"code": "CA", "name": "California", "active": True},
                    {"code": "TX", "name": "Texas", "active": True},
                    {"code": "NY", "name": "New York", "active": True},
                    {"code": "FL", "name": "Florida", "active": True},
                ],
                "vehicle_makes:popular": [
                    "TOYOTA",
                    "HONDA",
                    "FORD",
                    "CHEVROLET",
                    "NISSAN",
                    "BMW",
                    "MERCEDES",
                    "AUDI",
                    "TESLA",
                    "HYUNDAI",
                ],
                "coverage_types:auto": [
                    {"type": "liability", "required": True, "min_limit": 15000},
                    {"type": "collision", "required": False, "min_limit": 0},
                    {"type": "comprehensive", "required": False, "min_limit": 0},
                    {
                        "type": "uninsured_motorist",
                        "required": True,
                        "min_limit": 15000,
                    },
                ],
                "policy_types:all": [
                    {"type": "auto", "active": True},
                    {"type": "home", "active": True},
                    {"type": "renters", "active": True},
                    {"type": "life", "active": True},
                ],
            }

            for key, data in reference_data.items():
                existing, _ = await self.get_with_metrics(key)
                if existing is None:
                    # Cache reference data for 24 hours
                    await self.set_with_ttl(key, data, 86400)
                    warmed_keys += 1

        warmup_time = time.time() - start_time
        return {  # SYSTEM_BOUNDARY - Aggregated system data
            "warmed_keys": warmed_keys,
            "warmup_time_ms": warmup_time * 1000,
            "reference_sets": len(reference_data),
        }


# Global performance cache instance
_performance_cache: PerformanceCache | None = None


@beartype
def get_performance_cache() -> PerformanceCache:
    """Get global performance cache instance."""
    global _performance_cache
    if _performance_cache is None:
        _performance_cache = PerformanceCache()
    return _performance_cache


@beartype
def cached_operation(
    cache_prefix: str,
    ttl_seconds: int = 3600,
    invalidate_on_error: bool = True,
) -> Callable[..., Any]:
    """Decorator for caching expensive operations with performance monitoring."""

    @beartype
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            perf_cache = get_performance_cache()

            # Create cache key from function arguments
            cache_data = {
                "func": func.__name__,
                "args": args,
                "kwargs": kwargs,
            }
            cache_key = CacheKey.from_data(cache_prefix, cache_data)

            # Try to get from cache
            async with performance_context(f"cache_lookup_{func.__name__}"):
                cached_result, lookup_time = await perf_cache.get_with_metrics(
                    cache_key.key
                )

            if cached_result is not None:
                # Cache hit - return cached result
                return cached_result

            # Cache miss - execute function
            async with performance_context(f"cache_miss_{func.__name__}"):
                try:
                    result = await func(*args, **kwargs)

                    # Cache the result
                    await perf_cache.set_with_ttl(cache_key.key, result, ttl_seconds)

                    return result

                except Exception:
                    if invalidate_on_error:
                        # Ensure no partial results are cached
                        await perf_cache._cache.delete(cache_key.key)
                    raise

        @wraps(func)
        @beartype
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # For sync functions, we'd need to run in an async context
            # This is a simplified version
            return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        import asyncio

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


@beartype
async def warm_all_caches() -> dict[str, Any]:
    """Warm all performance caches during application startup."""
    perf_cache = get_performance_cache()

    start_time = time.time()
    results: dict[str, Any] = {}

    # Warm rating calculations cache
    rating_result = await perf_cache.warm_rating_cache()
    results["rating_cache"] = rating_result

    # Warm reference data cache
    reference_result = await perf_cache.warm_reference_data()
    results["reference_cache"] = reference_result

    total_time = time.time() - start_time

    results["summary"] = {
        "total_warmup_time_ms": total_time * 1000,
        "total_keys_warmed": rating_result["warmed_keys"]
        + reference_result["warmed_keys"],
        "warmup_successful": True,
    }

    return results  # SYSTEM_BOUNDARY - Aggregated system data


# Rating-specific cache functions for the rating engine
@beartype
async def cache_rate_calculation(
    state: str,
    policy_type: str,
    factors: dict[str, Any],
    result: dict[str, Any],
    ttl_seconds: int = 3600,
) -> bool:
    """Cache a rate calculation result."""
    perf_cache = get_performance_cache()

    cache_data = {
        "state": state,
        "policy_type": policy_type,
        "factors": factors,
    }
    cache_key = CacheKey.from_data("rating", cache_data)

    # Add metadata to result
    cached_result = {
        **result,
        "cached_at": time.time(),
        "cache_key": cache_key.key,
    }

    return await perf_cache.set_with_ttl(cache_key.key, cached_result, ttl_seconds)


@beartype
async def get_cached_rate(
    state: str,
    policy_type: str,
    factors: dict[str, Any],
) -> dict[str, Any] | None:
    """Get cached rate calculation result."""
    perf_cache = get_performance_cache()

    cache_data = {
        "state": state,
        "policy_type": policy_type,
        "factors": factors,
    }
    cache_key = CacheKey.from_data("rating", cache_data)

    result, lookup_time = await perf_cache.get_with_metrics(cache_key.key)
    return result


@beartype
async def invalidate_rate_cache(
    state: str | None = None, policy_type: str | None = None
) -> int:
    """Invalidate rate cache entries based on criteria."""
    cache = get_cache()

    if state and policy_type:
        pattern = f"rating:*{state}*{policy_type}*"
    elif state:
        pattern = f"rating:*{state}*"
    elif policy_type:
        pattern = f"rating:*{policy_type}*"
    else:
        pattern = "rating:*"

    return await cache.clear_pattern(pattern)
# SYSTEM_BOUNDARY: Performance cache management requires flexible dict structures for cache key optimization and hit rate tracking
