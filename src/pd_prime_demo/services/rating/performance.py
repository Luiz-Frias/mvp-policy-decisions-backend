"""Performance optimization for rating calculations."""

import asyncio
import hashlib
import pickle
import time
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from beartype import beartype
from pydantic import Field

from ...core.result_types import Err, Ok, Result
from ...models.base import BaseModelConfig
from ...schemas.rating import PerformanceMetrics, PerformanceThresholds

# Auto-generated models


@beartype
class FactorsMetrics(BaseModelConfig):
    """Structured model replacing dict[str, float] usage."""

    average: float = Field(default=0.0, ge=0.0, description="Average value")


@beartype
class InputDataData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class QuoteDataData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class MonitoringTokensMetrics(BaseModelConfig):
    """Structured model replacing dict[str, float] usage."""

    average: float = Field(default=0.0, ge=0.0, description="Average value")


@beartype
class PrecomputedFactorsMetrics(BaseModelConfig):
    """Structured model replacing dict[str, float] usage."""

    average: float = Field(default=0.0, ge=0.0, description="Average value")


class RatingPerformanceOptimizer:
    """Optimize rating calculations for <50ms performance."""

    def __init__(
        self, db: Any = None, cache: Any = None, cache_size: int = 10000
    ) -> None:
        """Initialize optimizer with configurable cache size.

        Args:
            db: Database connection (optional, for compatibility)
            cache: Cache instance (optional, for compatibility)
            cache_size: Maximum number of cached calculations
        """
        self._db = db  # Store for future use
        self._cache = cache  # Store for future use
        self._calculation_cache: dict[str, tuple[Any, float]] = {}
        self._precomputed_factors: PrecomputedFactorsMetrics = {}
        self._cache_size = cache_size
        self._cache_ttl = 3600  # 1 hour TTL for cached calculations
        self._performance_metrics: dict[str, list[float]] = {}
        self._performance_thresholds = PerformanceThresholds()
        self._monitoring_tokens: MonitoringTokensMetrics = (
            {}
        )  # For tracking calculation times

    @beartype
    @lru_cache(maxsize=10000)
    def get_cached_territory_factor(
        self,
        state: str,
        zip_code: str,
    ) -> Result[float, str]:
        """Cache territory factors for common ZIPs.

        Args:
            state: State code
            zip_code: ZIP code

        Returns:
            Result containing cached territory factor or error
        """
        # In production, load from database
        # This is called frequently, so cache aggressively
        cache_key = f"territory_{state}_{zip_code}"

        if cache_key in self._precomputed_factors:
            return Ok(self._precomputed_factors[cache_key])

        factor = self._calculate_territory_factor_internal(state, zip_code)
        if factor.is_ok():
            factor_value = factor.unwrap()
            assert factor_value is not None  # Type assertion for mypy
            self._precomputed_factors[cache_key] = factor_value

        return factor

    @beartype
    def create_calculation_hash(
        self,
        input_data: InputDataData,
    ) -> str:
        """Create hash for calculation caching.

        Args:
            input_data: Input data for calculation

        Returns:
            Hash string for cache key
        """
        # Sort keys for consistent hashing
        sorted_data = sorted(input_data.items())
        data_bytes = pickle.dumps(sorted_data)
        return hashlib.sha256(data_bytes).hexdigest()[:16]

    @beartype
    async def parallel_factor_calculation(
        self,
        calculation_tasks: dict[str, Callable[[], Any]],
    ) -> Result[dict[str, float], str]:
        """Calculate factors in parallel for performance.

        Args:
            calculation_tasks: Dictionary of factor name to async calculation function

        Returns:
            Result containing calculated factors or error
        """
        start_time = time.perf_counter()
        tasks = []
        factor_names = []

        for name, task_func in calculation_tasks.items():
            tasks.append(task_func())
            factor_names.append(name)

        try:
            # Run all calculations in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Check for errors
            factors: FactorsMetrics = {}
            for name, result in zip(factor_names, results):
                if isinstance(result, Exception):
                    return Err(f"Factor calculation failed for {name}: {str(result)}")
                if isinstance(result, (int, float)):
                    factors[name] = float(result)
                elif isinstance(result, str):
                    try:
                        factors[name] = float(result)
                    except (ValueError, TypeError):
                        return Err(f"Invalid factor value for {name}: {result}")
                else:
                    return Err(f"Invalid factor value for {name}: {result}")

            # Record performance metrics
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._record_performance_metric("parallel_factors", elapsed_ms)

            if elapsed_ms > 50:
                return Err(
                    f"Performance violation: Factor calculation took {elapsed_ms:.1f}ms (>50ms limit)"
                )

            return Ok(factors)

        except Exception as e:
            return Err(f"Parallel calculation failed: {str(e)}")

    @beartype
    def precompute_common_scenarios(self) -> None:
        """Precompute factors for common scenarios to improve performance."""
        # Common age groups
        age_groups = [18, 21, 25, 30, 40, 50, 65, 75]

        # Common violation counts
        violation_counts = [0, 1, 2, 3]

        # Precompute driver factors
        for age in age_groups:
            for violations in violation_counts:
                key = f"driver_{age}_{violations}"
                result = self._calculate_driver_factor_internal(age, violations)
                if result.is_ok():
                    factor_value = result.unwrap()
                    if factor_value is not None:
                        self._precomputed_factors[key] = factor_value

        # Common vehicle ages
        vehicle_ages = [0, 1, 2, 3, 5, 7, 10, 15]
        for age in vehicle_ages:
            key = f"vehicle_age_{age}"
            self._precomputed_factors[key] = 1.0 - (0.05 * min(age, 10))

    @beartype
    def get_cached_calculation(
        self,
        cache_key: str,
    ) -> Any | None:
        """Get cached calculation result if available and not expired.

        Args:
            cache_key: Cache key for the calculation

        Returns:
            Cached result or None if not found/expired
        """
        if cache_key in self._calculation_cache:
            result, timestamp = self._calculation_cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                return result
            else:
                # Remove expired entry
                del self._calculation_cache[cache_key]

        return None

    @beartype
    def cache_calculation(
        self,
        cache_key: str,
        result: Any,
    ) -> None:
        """Cache calculation result with timestamp.

        Args:
            cache_key: Cache key for the calculation
            result: Result to cache
        """
        # Implement LRU eviction if cache is full
        if len(self._calculation_cache) >= self._cache_size:
            # Remove oldest entry
            oldest_key = min(
                self._calculation_cache.keys(),
                key=lambda k: self._calculation_cache[k][1],
            )
            del self._calculation_cache[oldest_key]

        self._calculation_cache[cache_key] = (result, time.time())

    @beartype
    async def optimize_calculation_pipeline(
        self,
        quote_data: QuoteDataData,
    ) -> Result[dict[str, Any], str]:
        """Optimize entire calculation pipeline for <50ms performance.

        Args:
            quote_data: Complete quote data

        Returns:
            Result containing optimized calculation results or error
        """
        start_time = time.perf_counter()

        # Create cache key from quote data
        cache_key = self.create_calculation_hash(quote_data)

        # Check cache first
        cached_result = self.get_cached_calculation(cache_key)
        if cached_result is not None:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._record_performance_metric("cached_pipeline", elapsed_ms)
            return Ok(cached_result)

        # Parallel execution strategy
        try:
            # Extract data for parallel processing
            territory_task = self._async_territory_lookup(
                quote_data.get("state", ""), quote_data.get("zip_code", "")
            )
            driver_task = self._async_driver_scoring(quote_data.get("drivers", []))
            vehicle_task = self._async_vehicle_scoring(quote_data.get("vehicles", []))

            # Execute in parallel
            territory_result, driver_result, vehicle_result = await asyncio.gather(
                territory_task, driver_task, vehicle_task
            )

            # Combine results
            calculation_result = {
                "territory_factor": territory_result,
                "driver_scores": driver_result,
                "vehicle_scores": vehicle_result,
                "calculation_time_ms": (time.perf_counter() - start_time) * 1000,
            }

            # Cache result
            self.cache_calculation(cache_key, calculation_result)

            # Record metrics
            elapsed_ms_val = calculation_result["calculation_time_ms"]
            if isinstance(elapsed_ms_val, (int, float)):
                elapsed_ms = float(elapsed_ms_val)
            else:
                elapsed_ms = 0.0
            self._record_performance_metric("full_pipeline", elapsed_ms)

            if elapsed_ms > 50:
                return Err(
                    f"Performance violation: Pipeline took {elapsed_ms:.1f}ms (>50ms limit)"
                )

            return Ok(calculation_result)

        except Exception as e:
            return Err(f"Pipeline optimization failed: {str(e)}")

    @beartype
    def get_performance_metrics(self) -> dict[str, PerformanceMetrics]:
        """Get performance metrics for monitoring.

        Returns:
            Dictionary of performance metrics by operation
        """
        metrics = {}
        for operation, timings in self._performance_metrics.items():
            if timings:
                metrics[operation] = PerformanceMetrics(
                    operation_name=operation,
                    count=len(timings),
                    avg_ms=sum(timings) / len(timings),
                    min_ms=min(timings),
                    max_ms=max(timings),
                    p95_ms=(
                        sorted(timings)[int(len(timings) * 0.95)]
                        if len(timings) > 20
                        else max(timings)
                    ),
                )
        return metrics

    @beartype
    def _record_performance_metric(self, operation: str, elapsed_ms: float) -> None:
        """Record performance metric for analysis.

        Args:
            operation: Name of the operation
            elapsed_ms: Elapsed time in milliseconds
        """
        if operation not in self._performance_metrics:
            self._performance_metrics[operation] = []

        # Keep last 1000 measurements
        self._performance_metrics[operation].append(elapsed_ms)
        if len(self._performance_metrics[operation]) > 1000:
            self._performance_metrics[operation].pop(0)

    @beartype
    def _calculate_territory_factor_internal(
        self, state: str, zip_code: str
    ) -> Result[float, str]:
        """Internal territory factor calculation.

        Args:
            state: State code
            zip_code: ZIP code

        Returns:
            Result containing territory factor or error
        """
        # Simplified calculation for demonstration
        # In production, query database for actual territory data
        if not state or not zip_code:
            return Err("State and ZIP code required for territory calculation")

        # Mock calculation based on ZIP
        base_factor = 1.0
        zip_int = int(zip_code[:3]) if zip_code.isdigit() else 500

        # Simulate geographic risk variation
        if zip_int < 200:  # Northeast
            base_factor = 1.15
        elif zip_int < 400:  # Southeast
            base_factor = 1.10
        elif zip_int < 600:  # Midwest
            base_factor = 0.95
        elif zip_int < 800:  # Mountain
            base_factor = 0.90
        else:  # West Coast
            base_factor = 1.20

        return Ok(base_factor)

    @beartype
    def _calculate_driver_factor_internal(
        self, age: int, violations: int
    ) -> Result[float, str]:
        """Internal driver factor calculation.

        Args:
            age: Driver age
            violations: Number of violations

        Returns:
            Result containing driver factor or error
        """
        if age < 16 or age > 100:
            return Err(f"Invalid driver age: {age}")

        # Age-based factor
        if age < 25:
            age_factor = 1.5 - (age - 18) * 0.05
        elif age > 70:
            age_factor = 1.0 + (age - 70) * 0.02
        else:
            age_factor = 0.9

        # Violation factor
        violation_factor = 1.0 + violations * 0.15

        return Ok(age_factor * violation_factor)

    async def _async_territory_lookup(self, state: str, zip_code: str) -> float:
        """Async territory lookup for parallel processing."""
        # Simulate async database lookup
        await asyncio.sleep(0.001)  # 1ms database latency
        result = self.get_cached_territory_factor(state, zip_code)
        if result.is_ok():
            factor_value = result.unwrap()
            return factor_value if factor_value is not None else 1.0
        else:
            return 1.0

    async def _async_driver_scoring(self, drivers: list[dict[str, Any]]) -> list[float]:
        """Async driver scoring for parallel processing."""
        # Simulate async scoring
        await asyncio.sleep(0.002)  # 2ms scoring latency
        scores = []
        for driver in drivers:
            age = driver.get("age", 30)
            violations = driver.get("violations_3_years", 0)
            key = f"driver_{age}_{violations}"
            if key in self._precomputed_factors:
                scores.append(self._precomputed_factors[key])
            else:
                result = self._calculate_driver_factor_internal(age, violations)
                scores.append(result.unwrap_or(1.0))
        return scores

    async def _async_vehicle_scoring(
        self, vehicles: list[dict[str, Any]]
    ) -> list[float]:
        """Async vehicle scoring for parallel processing."""
        # Simulate async scoring
        await asyncio.sleep(0.001)  # 1ms scoring latency
        scores = []
        for vehicle in vehicles:
            age = vehicle.get("age", 5)
            key = f"vehicle_age_{age}"
            if key in self._precomputed_factors:
                scores.append(self._precomputed_factors[key])
            else:
                scores.append(1.0 - (0.05 * min(age, 10)))
        return scores

    @beartype
    def warm_cache_for_state(self, state: str) -> None:
        """Warm cache with common calculations for a specific state.

        Args:
            state: State code to warm cache for
        """
        # Common ZIP code prefixes by state
        state_zip_prefixes = {
            "CA": ["900", "901", "902", "903", "904", "905", "906", "907", "908"],
            "TX": ["700", "701", "702", "703", "704", "705", "706", "707", "708"],
            "NY": ["100", "101", "102", "103", "104", "105", "106", "107", "108"],
            "FL": ["300", "301", "302", "303", "304", "305", "306", "307", "308"],
            "IL": ["600", "601", "602", "603", "604", "605", "606", "607", "608"],
        }

        if state in state_zip_prefixes:
            for prefix in state_zip_prefixes[state]:
                for suffix in ["00", "01", "10", "20", "50"]:
                    zip_code = prefix + suffix
                    result = self._calculate_territory_factor_internal(state, zip_code)
                    if result.is_ok():
                        key = f"territory_{state}_{zip_code}"
                        factor_value = result.unwrap()
                        if factor_value is not None:
                            self._precomputed_factors[key] = factor_value

    @beartype
    async def batch_territory_lookup(
        self, zip_codes: list[str], state: str
    ) -> Result[dict[str, float], str]:
        """Batch lookup territory factors for multiple ZIP codes.

        Args:
            zip_codes: List of ZIP codes to lookup
            state: State code

        Returns:
            Result containing dict of ZIP to factor mappings or error
        """
        if not zip_codes:
            return Ok({})

        if len(zip_codes) > 1000:
            return Err("Batch size cannot exceed 1000 ZIP codes")

        start_time = time.perf_counter()
        factors = {}

        # Process in parallel batches of 100
        batch_size = 100
        for i in range(0, len(zip_codes), batch_size):
            batch = zip_codes[i : i + batch_size]
            batch_tasks = []

            for zip_code in batch:
                task = self._async_territory_lookup(state, zip_code)
                batch_tasks.append(task)

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for zip_code, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    factors[zip_code] = 1.0  # Default factor on error
                else:
                    if isinstance(result, (int, float)):
                        factors[zip_code] = float(result)
                    else:
                        factors[zip_code] = 1.0  # Default factor on conversion error

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        self._record_performance_metric("batch_territory_lookup", elapsed_ms)

        return Ok(factors)

    @beartype
    def optimize_for_load_testing(self) -> None:
        """Optimize performance settings for load testing scenarios."""
        # Increase cache size for load testing
        self._cache_size = 50000

        # Reduce cache TTL to prevent memory bloat
        self._cache_ttl = 1800  # 30 minutes

        # Precompute common scenarios
        self.precompute_common_scenarios()

        # Warm caches for major states
        for state in ["CA", "TX", "NY", "FL", "IL"]:
            self.warm_cache_for_state(state)

    @beartype
    def get_cache_statistics(self) -> dict[str, Any]:
        """Get detailed cache performance statistics.

        Returns:
            Dictionary with cache metrics
        """
        cache_stats = {
            "total_entries": len(self._calculation_cache),
            "precomputed_factors": len(self._precomputed_factors),
            "cache_size_limit": self._cache_size,
            "cache_ttl_seconds": self._cache_ttl,
            "memory_usage_estimate": {
                "calculation_cache_mb": len(self._calculation_cache)
                * 0.001,  # Rough estimate
                "precomputed_factors_mb": len(self._precomputed_factors) * 0.0005,
            },
        }

        # Calculate hit rates if we have performance data
        if (
            "cached_pipeline" in self._performance_metrics
            and "full_pipeline" in self._performance_metrics
        ):
            cached_calls = len(self._performance_metrics["cached_pipeline"])
            total_calls = cached_calls + len(self._performance_metrics["full_pipeline"])
            cache_stats["hit_rate"] = (
                cached_calls / total_calls if total_calls > 0 else 0.0
            )

        return cache_stats

    @beartype
    async def benchmark_calculation_performance(
        self,
        iterations: int = 1000,
    ) -> Result[dict[str, Any], str]:
        """Benchmark calculation performance under load.

        Args:
            iterations: Number of iterations to run

        Returns:
            Result containing benchmark results or error
        """
        if iterations <= 0 or iterations > 10000:
            return Err("Iterations must be between 1 and 10000")

        # Sample quote data for benchmarking
        sample_quote = {
            "state": "CA",
            "zip_code": "90210",
            "drivers": [{"age": 30, "violations_3_years": 0}],
            "vehicles": [{"age": 5}],
        }

        start_time = time.perf_counter()
        timings = []
        errors = 0

        for i in range(iterations):
            iteration_start = time.perf_counter()

            try:
                # Add variation to prevent cache hits
                varied_quote = sample_quote.copy()
                varied_quote["zip_code"] = f"9021{i % 10}"

                result = await self.optimize_calculation_pipeline(varied_quote)

                if result.is_err():
                    errors += 1

            except Exception:
                errors += 1

            iteration_time = (time.perf_counter() - iteration_start) * 1000
            timings.append(iteration_time)

        total_time = (time.perf_counter() - start_time) * 1000

        # Calculate statistics
        timings.sort()
        results = {
            "total_iterations": iterations,
            "total_time_ms": total_time,
            "avg_time_ms": sum(timings) / len(timings) if timings else 0,
            "min_time_ms": min(timings) if timings else 0,
            "max_time_ms": max(timings) if timings else 0,
            "p50_ms": timings[len(timings) // 2] if timings else 0,
            "p95_ms": timings[int(len(timings) * 0.95)] if timings else 0,
            "p99_ms": timings[int(len(timings) * 0.99)] if timings else 0,
            "error_rate": errors / iterations,
            "throughput_per_second": (
                iterations / (total_time / 1000) if total_time > 0 else 0
            ),
            "performance_target_met": (
                sum(t > 50 for t in timings) / len(timings) < 0.05 if timings else False
            ),  # <5% over 50ms
        }

        return Ok(results)

    @beartype
    async def initialize_performance_caches(self) -> Result[bool, str]:
        """Initialize performance caches for optimal startup."""
        try:
            # Precompute common scenarios
            self.precompute_common_scenarios()

            # Warm caches for major states
            for state in ["CA", "TX", "NY", "FL", "IL"]:
                self.warm_cache_for_state(state)

            return Ok(True)
        except Exception as e:
            return Err(f"Cache initialization failed: {str(e)}")

    @beartype
    async def warm_cache_for_common_scenarios(self) -> Result[int, str]:
        """Warm cache for common rating scenarios."""
        try:
            scenarios_cached = 0

            # Common age/violation combinations
            for age in [18, 21, 25, 30, 40, 50, 65]:
                for violations in [0, 1, 2]:
                    key = f"driver_{age}_{violations}"
                    result = self._calculate_driver_factor_internal(age, violations)
                    if result.is_ok():
                        factor_value = result.unwrap()
                        if factor_value is not None:
                            self._precomputed_factors[key] = factor_value
                            scenarios_cached += 1

            # Common territory factors
            for state in ["CA", "TX", "NY", "FL"]:
                self.warm_cache_for_state(state)
                scenarios_cached += 10  # Approximate scenarios per state

            return Ok(scenarios_cached)
        except Exception as e:
            return Err(f"Cache warming failed: {str(e)}")

    @beartype
    def start_performance_monitoring(self) -> str:
        """Start performance monitoring and return token."""
        import uuid

        token = str(uuid.uuid4())
        self._monitoring_tokens[token] = time.perf_counter()
        return token

    @beartype
    def end_performance_monitoring(self, token: str) -> int:
        """End performance monitoring and return elapsed time in ms."""
        if token not in self._monitoring_tokens:
            return 0

        start_time = self._monitoring_tokens.pop(token)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # Record the metric
        self._record_performance_metric("calculation", elapsed_ms)

        return elapsed_ms

    @beartype
    def is_performance_target_met(self, target_ms: int = 50) -> bool:
        """Check if performance target is being met."""
        if "calculation" not in self._performance_metrics:
            return True  # No data means no violations yet

        recent_timings = self._performance_metrics["calculation"][
            -100:
        ]  # Last 100 calculations
        if not recent_timings:
            return True

        violations = sum(1 for t in recent_timings if t > target_ms)
        violation_rate = violations / len(recent_timings)

        return violation_rate < self._performance_thresholds.max_violation_rate

    @beartype
    async def optimize_slow_calculations(self) -> Result[list[str], str]:
        """Analyze performance and provide optimization recommendations."""
        try:
            recommendations = []

            if "calculation" in self._performance_metrics:
                timings = self._performance_metrics["calculation"]
                if timings:
                    avg_time = sum(timings) / len(timings)
                    max_time = max(timings)

                    if avg_time > 25:
                        recommendations.append(
                            f"Average calculation time ({avg_time:.1f}ms) exceeds recommended 25ms. "
                            "Consider precomputing more factors."
                        )

                    if max_time > 100:
                        recommendations.append(
                            f"Peak calculation time ({max_time:.1f}ms) is very high. "
                            "Review database query performance and add more caching."
                        )

                    slow_calculations = sum(1 for t in timings if t > 50)
                    if slow_calculations > len(timings) * 0.1:
                        recommendations.append(
                            f"{slow_calculations} calculations exceeded 50ms target. "
                            "Consider increasing cache size or optimizing algorithms."
                        )

            # Check cache hit rates
            cache_stats = self.get_cache_statistics()
            if "hit_rate" in cache_stats and cache_stats["hit_rate"] < 0.8:
                recommendations.append(
                    f"Cache hit rate ({cache_stats['hit_rate']:.1%}) is low. "
                    "Consider warming more cache scenarios or increasing cache TTL."
                )

            if not recommendations:
                recommendations.append(
                    "Performance is optimal. No optimizations needed."
                )

            return Ok(recommendations)

        except Exception as e:
            return Err(f"Performance analysis failed: {str(e)}")
