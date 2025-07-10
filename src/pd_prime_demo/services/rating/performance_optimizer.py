"""Rating engine performance optimization.

This module implements advanced caching strategies and performance
optimizations to ensure sub-50ms rating calculations per Agent 06 requirements.
"""

import time
from decimal import Decimal
from typing import Any

from beartype import beartype
from pydantic import Field

from pd_prime_demo.core.cache import Cache
from pd_prime_demo.core.database import Database
from pd_prime_demo.core.result_types import Err, Ok, Result
from pd_prime_demo.models.base import BaseModelConfig

# Auto-generated models


@beartype
class FactorLookupCacheMetrics(BaseModelConfig):
    """Structured model replacing dict[str, float] usage."""

    average: float = Field(default=0.0, ge=0.0, description="Average value")


@beartype
class CacheHitRatesCounts(BaseModelConfig):
    """Structured model replacing dict[str, int] usage."""

    total: int = Field(default=0, ge=0, description="Total count")


@beartype
class BatchCacheData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


HAS_NUMPY = False  # NumPy not used in current implementation


@beartype
class RatingPerformanceOptimizer:
    """Advanced performance optimizer for rating calculations."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize performance optimizer."""
        self._db = db
        self._cache = cache
        self._cache_prefix = "rating_perf:"

        # Performance monitoring
        self._calculation_times: list[float] = []
        self._cache_hit_rates: CacheHitRatesCounts = {"hits": 0, "misses": 0}

        # Precomputed lookup tables
        self._factor_lookup_cache: FactorLookupCacheMetrics = {}
        self._rate_multiplier_cache: dict[str, Decimal] = {}

        # Batch processing support
        self._batch_cache: BatchCacheData = {}

    @beartype
    async def initialize_performance_caches(self) -> Result[bool, str]:
        """Initialize performance-optimized caches."""
        try:
            # Preload common factor combinations
            await self._preload_factor_combinations()

            # Preload frequently used rate multipliers
            await self._preload_rate_multipliers()

            # Initialize territory factor cache
            await self._preload_territory_factors()

            return Ok(True)

        except Exception as e:
            return Err(f"Performance cache initialization failed: {str(e)}")

    @beartype
    async def _preload_factor_combinations(self) -> None:
        """Preload common factor combinations for instant lookup."""
        # Load most common age/experience combinations
        common_combinations = [
            # (age, years_licensed) -> factor
            (25, 5, 1.15),  # Young experienced
            (30, 10, 1.00),  # Standard
            (45, 20, 0.95),  # Mature experienced
            (65, 40, 1.05),  # Senior
        ]

        for age, years, factor in common_combinations:
            key = f"driver_age_exp:{age}:{years}"
            self._factor_lookup_cache[key] = factor

    @beartype
    async def _preload_rate_multipliers(self) -> None:
        """Preload common rate multipliers."""
        # Load common coverage combinations
        query = """
        SELECT state, product_type, coverage_type, base_rate
        FROM rate_tables
        WHERE state IN ('CA', 'TX', 'NY', 'FL')
            AND product_type = 'auto'
            AND effective_date <= CURRENT_DATE
            AND (expiration_date IS NULL OR expiration_date > CURRENT_DATE)
        ORDER BY state, coverage_type
        """

        rows = await self._db.fetch(query)

        for row in rows:
            key = f"{row['state']}:{row['product_type']}:{row['coverage_type']}"
            self._rate_multiplier_cache[key] = Decimal(str(row["base_rate"]))

    @beartype
    async def _preload_territory_factors(self) -> None:
        """Preload territory factors for major ZIP codes."""
        # Load top 1000 ZIP codes by quote volume
        query = """
        SELECT tf.state, tf.zip_code, tf.base_factor
        FROM territory_factors tf
        INNER JOIN (
            SELECT garage_zip, COUNT(*) as quote_count
            FROM quotes
            WHERE created_at > CURRENT_DATE - INTERVAL '90 days'
            GROUP BY garage_zip
            ORDER BY quote_count DESC
            LIMIT 1000
        ) popular_zips ON tf.zip_code = popular_zips.garage_zip
        WHERE tf.effective_date <= CURRENT_DATE
            AND (tf.expiration_date IS NULL OR tf.expiration_date > CURRENT_DATE)
        """

        rows = await self._db.fetch(query)

        for row in rows:
            key = f"territory:{row['state']}:{row['zip_code']}"
            self._factor_lookup_cache[key] = float(row["base_factor"])

    @beartype
    async def get_optimized_factor(
        self, factor_type: str, *args: Any
    ) -> Result[float, str]:
        """Get factor with optimized lookup."""
        # Build cache key
        key_parts = [factor_type] + [str(arg) for arg in args]
        cache_key = ":".join(key_parts)

        # Check in-memory cache first
        if cache_key in self._factor_lookup_cache:
            self._cache_hit_rates["hits"] += 1
            return Ok(self._factor_lookup_cache[cache_key])

        # Check Redis cache
        cached_value = await self._cache.get(f"{self._cache_prefix}{cache_key}")
        if cached_value:
            factor = float(cached_value)
            self._factor_lookup_cache[cache_key] = factor  # Store in memory
            self._cache_hit_rates["hits"] += 1
            return Ok(factor)

        # Cache miss - calculate factor
        self._cache_hit_rates["misses"] += 1
        return await self._calculate_and_cache_factor(factor_type, cache_key, *args)

    @beartype
    async def _calculate_and_cache_factor(
        self, factor_type: str, cache_key: str, *args: Any
    ) -> Result[float, str]:
        """Calculate factor and cache result."""
        try:
            # Calculate based on factor type
            if factor_type == "driver_age":
                age = int(args[0])
                factor = self._calculate_age_factor(age)
            elif factor_type == "driver_experience":
                years = int(args[0])
                factor = self._calculate_experience_factor(years)
            elif factor_type == "vehicle_age":
                vehicle_age = int(args[0])
                factor = self._calculate_vehicle_age_factor(vehicle_age)
            elif factor_type == "territory":
                state, zip_code = str(args[0]), str(args[1])
                return await self._calculate_territory_factor(state, zip_code)
            else:
                return Err(f"Unknown factor type: {factor_type}")

            # Cache the result
            self._factor_lookup_cache[cache_key] = factor
            await self._cache.set(
                f"{self._cache_prefix}{cache_key}", str(factor), 3600  # 1 hour cache
            )

            return Ok(factor)

        except Exception as e:
            return Err(f"Factor calculation failed: {str(e)}")

    @beartype
    def _calculate_age_factor(self, age: int) -> float:
        """Calculate age factor with optimized logic."""
        if age < 21:
            return 1.50
        elif age < 25:
            return 1.25
        elif age < 30:
            return 1.10
        elif age < 65:
            return 1.00
        else:
            return 1.05

    @beartype
    def _calculate_experience_factor(self, years: int) -> float:
        """Calculate experience factor with optimized logic."""
        if years < 3:
            return 1.20
        elif years < 5:
            return 1.10
        elif years < 10:
            return 1.05
        else:
            return 1.00

    @beartype
    def _calculate_vehicle_age_factor(self, vehicle_age: int) -> float:
        """Calculate vehicle age factor with optimized logic."""
        if vehicle_age <= 1:
            return 1.15
        elif vehicle_age <= 3:
            return 1.05
        elif vehicle_age <= 7:
            return 1.00
        elif vehicle_age <= 12:
            return 0.95
        else:
            return 0.90

    @beartype
    async def _calculate_territory_factor(
        self, state: str, zip_code: str
    ) -> Result[float, str]:
        """Calculate territory factor with database lookup."""
        query = """
        SELECT base_factor
        FROM territory_factors
        WHERE state = $1 AND zip_code = $2
            AND effective_date <= CURRENT_DATE
            AND (expiration_date IS NULL OR expiration_date > CURRENT_DATE)
        ORDER BY effective_date DESC
        LIMIT 1
        """

        row = await self._db.fetchrow(query, state, zip_code)

        if not row:
            # Default factor for unknown territories
            return Ok(1.0)

        return Ok(float(row["base_factor"]))

    @beartype
    async def get_optimized_base_rate(
        self, state: str, product_type: str, coverage_type: str
    ) -> Result[Decimal, str]:
        """Get base rate with optimized lookup."""
        cache_key = f"{state}:{product_type}:{coverage_type}"

        # Check in-memory cache
        if cache_key in self._rate_multiplier_cache:
            self._cache_hit_rates["hits"] += 1
            return Ok(self._rate_multiplier_cache[cache_key])

        # Check Redis cache
        cached_value = await self._cache.get(f"{self._cache_prefix}rate:{cache_key}")
        if cached_value:
            rate = Decimal(cached_value)
            self._rate_multiplier_cache[cache_key] = rate
            self._cache_hit_rates["hits"] += 1
            return Ok(rate)

        # Database lookup
        self._cache_hit_rates["misses"] += 1
        query = """
        SELECT base_rate
        FROM rate_tables
        WHERE state = $1 AND product_type = $2 AND coverage_type = $3
            AND effective_date <= CURRENT_DATE
            AND (expiration_date IS NULL OR expiration_date > CURRENT_DATE)
        ORDER BY effective_date DESC
        LIMIT 1
        """

        row = await self._db.fetchrow(query, state, product_type, coverage_type)

        if not row:
            return Err(f"No base rate found for {state} {product_type} {coverage_type}")

        rate = Decimal(str(row["base_rate"]))

        # Cache the result
        self._rate_multiplier_cache[cache_key] = rate
        await self._cache.set(
            f"{self._cache_prefix}rate:{cache_key}", str(rate), 1800  # 30 minute cache
        )

        return Ok(rate)

    @beartype
    async def batch_calculate_factors(
        self, factor_requests: list[tuple[str, tuple[Any, ...]]]
    ) -> Result[dict[str, Any], str]:
        """Calculate multiple factors in a single optimized batch."""
        results = {}

        try:
            # Group requests by type for optimized processing
            grouped_requests: dict[str, list[tuple[int, Any]]] = {}
            for i, (factor_type, args) in enumerate(factor_requests):
                if factor_type not in grouped_requests:
                    grouped_requests[factor_type] = []
                grouped_requests[factor_type].append((i, args))

            # Process each type in batch
            for factor_type, requests in grouped_requests.items():
                batch_results = await self._batch_process_factor_type(
                    factor_type, requests
                )

                for i, result in batch_results:
                    key = f"{factor_type}:{':'.join(str(arg) for arg in factor_requests[i][1])}"
                    results[key] = result

            return Ok(results)

        except Exception as e:
            return Err(f"Batch factor calculation failed: {str(e)}")

    @beartype
    async def _batch_process_factor_type(
        self, factor_type: str, requests: list[tuple[int, tuple[Any, ...]]]
    ) -> list[tuple[int, float]]:
        """Process a batch of requests for a single factor type."""
        results = []

        if factor_type == "territory":
            # Batch territory lookups
            zip_codes = [args[1] for _, args in requests]
            states = [args[0] for _, args in requests]

            # Single query for all territories
            query = """
            SELECT state, zip_code, base_factor
            FROM territory_factors
            WHERE (state, zip_code) = ANY($1)
                AND effective_date <= CURRENT_DATE
                AND (expiration_date IS NULL OR expiration_date > CURRENT_DATE)
            """

            state_zip_pairs = list(zip(states, zip_codes))
            rows = await self._db.fetch(query, state_zip_pairs)

            # Build lookup map
            territory_map = {}
            for row in rows:
                territory_map[(row["state"], row["zip_code"])] = float(
                    row["base_factor"]
                )

            # Return results in order
            for i, (state, zip_code) in state_zip_pairs:
                factor = territory_map.get((state, zip_code), 1.0)
                results.append((i, factor))

        else:
            # For non-database factors, process individually (already fast)
            for i, args in requests:
                if factor_type == "driver_age":
                    factor = self._calculate_age_factor(int(args[0]))
                elif factor_type == "driver_experience":
                    factor = self._calculate_experience_factor(int(args[0]))
                elif factor_type == "vehicle_age":
                    factor = self._calculate_vehicle_age_factor(int(args[0]))
                else:
                    factor = 1.0

                results.append((i, factor))

        return results

    @beartype
    def start_performance_monitoring(self) -> str:
        """Start performance monitoring for a calculation."""
        return str(time.time_ns())

    @beartype
    def end_performance_monitoring(self, start_token: str) -> int:
        """End performance monitoring and return calculation time in ms."""
        start_time = int(start_token)
        end_time = time.time_ns()
        duration_ms = (end_time - start_time) // 1_000_000

        # Track calculation time
        self._calculation_times.append(duration_ms)

        # Keep only last 1000 calculations for memory efficiency
        if len(self._calculation_times) > 1000:
            self._calculation_times = self._calculation_times[-1000:]

        return duration_ms

    @beartype
    def get_performance_metrics(self) -> dict[str, Any]:
        """Get current performance metrics."""
        if not self._calculation_times:
            return {
                "average_calculation_time_ms": 0,
                "p95_calculation_time_ms": 0,
                "p99_calculation_time_ms": 0,
                "cache_hit_rate": 0,
                "total_calculations": 0,
            }

        times = sorted(self._calculation_times)
        n = len(times)

        total_cache_ops = (
            self._cache_hit_rates["hits"] + self._cache_hit_rates["misses"]
        )
        cache_hit_rate = (
            self._cache_hit_rates["hits"] / total_cache_ops
            if total_cache_ops > 0
            else 0
        )

        return {
            "average_calculation_time_ms": sum(times) / n,
            "p95_calculation_time_ms": times[int(n * 0.95)] if n > 0 else 0,
            "p99_calculation_time_ms": times[int(n * 0.99)] if n > 0 else 0,
            "max_calculation_time_ms": max(times),
            "min_calculation_time_ms": min(times),
            "cache_hit_rate": cache_hit_rate,
            "total_calculations": n,
            "cache_hits": self._cache_hit_rates["hits"],
            "cache_misses": self._cache_hit_rates["misses"],
        }

    @beartype
    async def warm_cache_for_common_scenarios(self) -> Result[int, str]:
        """Warm cache with common rating scenarios."""
        try:
            scenarios_warmed = 0

            # Common age ranges
            for age in [18, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70]:
                await self.get_optimized_factor("driver_age", age)
                scenarios_warmed += 1

            # Common experience ranges
            for years in [1, 2, 3, 5, 8, 10, 15, 20, 25, 30]:
                await self.get_optimized_factor("driver_experience", years)
                scenarios_warmed += 1

            # Common vehicle ages
            for vehicle_age in [0, 1, 2, 3, 5, 7, 10, 12, 15, 20]:
                await self.get_optimized_factor("vehicle_age", vehicle_age)
                scenarios_warmed += 1

            # Top ZIP codes by state
            common_zips = {
                "CA": ["90210", "94102", "90028", "90210", "91210"],
                "TX": ["78701", "77001", "75201", "78201", "79936"],
                "NY": ["10001", "10016", "10019", "10128", "11201"],
                "FL": ["33101", "32801", "33139", "33004", "33021"],
            }

            for state, zip_codes in common_zips.items():
                for zip_code in zip_codes:
                    await self.get_optimized_factor("territory", state, zip_code)
                    scenarios_warmed += 1

            return Ok(scenarios_warmed)

        except Exception as e:
            return Err(f"Cache warming failed: {str(e)}")

    @beartype
    async def clear_performance_caches(self) -> None:
        """Clear all performance caches."""
        self._factor_lookup_cache.clear()
        self._rate_multiplier_cache.clear()
        self._batch_cache.clear()

        # Clear Redis caches
        await self._cache.delete(f"{self._cache_prefix}*")

    @beartype
    def is_performance_target_met(self, target_ms: int = 50) -> bool:
        """Check if performance target is being met."""
        if not self._calculation_times:
            return True  # No data yet

        # Check last 100 calculations
        recent_times = (
            self._calculation_times[-100:]
            if len(self._calculation_times) >= 100
            else self._calculation_times
        )
        p95_time = (
            sorted(recent_times)[int(len(recent_times) * 0.95)] if recent_times else 0
        )

        return p95_time <= target_ms

    @beartype
    async def optimize_slow_calculations(self) -> Result[list[str], str]:
        """Identify and suggest optimizations for slow calculations."""
        try:
            optimizations = []

            metrics = self.get_performance_metrics()

            # Check cache hit rate
            if metrics["cache_hit_rate"] < 0.8:
                optimizations.append(
                    f"Low cache hit rate ({metrics['cache_hit_rate']:.1%}). "
                    f"Consider warming cache for common scenarios."
                )

            # Check average performance
            if metrics["average_calculation_time_ms"] > 30:
                optimizations.append(
                    f"Average calculation time ({metrics['average_calculation_time_ms']:.1f}ms) "
                    f"exceeds 30ms target. Consider preloading more data."
                )

            # Check P99 performance
            if metrics["p99_calculation_time_ms"] > 50:
                optimizations.append(
                    f"P99 calculation time ({metrics['p99_calculation_time_ms']:.1f}ms) "
                    f"exceeds 50ms target. Investigate worst-case scenarios."
                )

            # Check for database bottlenecks
            if metrics["cache_misses"] > metrics["cache_hits"]:
                optimizations.append(
                    "More cache misses than hits. Database may be bottleneck. "
                    "Consider increasing cache TTL or preloading more data."
                )

            return Ok(optimizations)

        except Exception as e:
            return Err(f"Performance optimization analysis failed: {str(e)}")
