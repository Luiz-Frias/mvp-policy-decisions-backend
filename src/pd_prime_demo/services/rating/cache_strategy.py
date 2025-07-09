"""Caching strategy for rating calculations to improve performance."""

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from beartype import beartype
from pydantic import Field

from pd_prime_demo.core.result_types import Err, Ok, Result

from ...core.cache import Cache
from ...models.base import BaseModelConfig

# Auto-generated models


@beartype
class UsagePatternsMetrics(BaseModelConfig):
    """Structured model replacing dict[str, float] usage."""

    average: float = Field(default=0.0, ge=0.0, description="Average value")


@beartype
class ResultData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class DataData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class DeserializedData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class SerializedData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class CalculationResultData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


class RatingCacheStrategy:
    """Advanced caching strategy for rating calculations."""

    def __init__(self, cache: Cache) -> None:
        """Initialize cache strategy.

        Args:
            cache: Redis cache instance
        """
        self._cache = cache
        self._ttl_config = {
            "territory_factor": 86400,  # 24 hours - changes rarely
            "base_rate": 3600,  # 1 hour - may update more frequently
            "discount_rules": 1800,  # 30 minutes - promotional changes
            "ai_score": 300,  # 5 minutes - real-time factors
            "quote_calculation": 900,  # 15 minutes - customer specific
        }
        self._cache_stats: dict[str, dict[str, int]] = {}

    @beartype
    async def cache_territory_factor(
        self,
        state: str,
        zip_code: str,
        factor: float,
    ) -> Result[None, str]:
        """Cache territory factor with appropriate TTL.

        Args:
            state: State code
            zip_code: ZIP code
            factor: Territory factor value

        Returns:
            Result indicating success or error
        """
        cache_key = f"rating:territory:{state}:{zip_code}"
        cache_value = {
            "factor": factor,
            "cached_at": datetime.utcnow().isoformat(),
        }

        try:
            await self._cache.set(
                cache_key,
                json.dumps(cache_value),
                ttl=self._ttl_config["territory_factor"],
            )
            self._record_cache_operation("territory_factor", "set")
            return Ok(None)
        except Exception as e:
            return Err(f"Failed to cache territory factor: {str(e)}")

    @beartype
    async def get_territory_factor(
        self,
        state: str,
        zip_code: str,
    ) -> Result[float | None, str]:
        """Get cached territory factor.

        Args:
            state: State code
            zip_code: ZIP code

        Returns:
            Result containing factor or None if not cached
        """
        cache_key = f"rating:territory:{state}:{zip_code}"

        try:
            cached = await self._cache.get(cache_key)
            if cached:
                data = json.loads(cached)
                self._record_cache_operation("territory_factor", "hit")
                return Ok(float(data["factor"]))
            else:
                self._record_cache_operation("territory_factor", "miss")
                return Ok(None)
        except Exception as e:
            return Err(f"Failed to get cached territory factor: {str(e)}")

    @beartype
    async def cache_quote_calculation(
        self,
        quote_hash: str,
        calculation_result: CalculationResultData,
    ) -> Result[bool, str]:
        """Cache complete quote calculation result.

        Args:
            quote_hash: Hash of quote inputs
            calculation_result: Complete calculation result

        Returns:
            Result indicating success or error
        """
        cache_key = f"rating:quote:{quote_hash}"

        # Convert Decimal to string for JSON serialization
        cache_value = self._serialize_calculation_result(calculation_result)
        cache_value["cached_at"] = datetime.utcnow().isoformat()

        try:
            await self._cache.set(
                cache_key,
                json.dumps(cache_value),
                ttl=self._ttl_config["quote_calculation"],
            )
            self._record_cache_operation("quote_calculation", "set")
            return Ok(True)
        except Exception as e:
            return Err(f"Failed to cache quote calculation: {str(e)}")

    @beartype
    async def get_quote_calculation(
        self,
        quote_hash: str,
    ) -> Result[dict[str, Any] | None, str]:
        """Get cached quote calculation.

        Args:
            quote_hash: Hash of quote inputs

        Returns:
            Result containing calculation or None if not cached
        """
        cache_key = f"rating:quote:{quote_hash}"

        try:
            cached = await self._cache.get(cache_key)
            if cached:
                data = json.loads(cached)
                result = self._deserialize_calculation_result(data)
                self._record_cache_operation("quote_calculation", "hit")
                return Ok(result)
            else:
                self._record_cache_operation("quote_calculation", "miss")
                return Ok(None)
        except Exception as e:
            return Err(f"Failed to get cached quote calculation: {str(e)}")

    @beartype
    async def cache_discount_rules(
        self,
        state: str,
        rules: list[dict[str, Any]],
    ) -> Result[bool, str]:
        """Cache discount rules for a state.

        Args:
            state: State code
            rules: List of discount rules

        Returns:
            Result indicating success or error
        """
        cache_key = f"rating:discounts:{state}"
        cache_value = {
            "rules": rules,
            "cached_at": datetime.utcnow().isoformat(),
        }

        try:
            await self._cache.set(
                cache_key,
                json.dumps(cache_value),
                ttl=self._ttl_config["discount_rules"],
            )
            self._record_cache_operation("discount_rules", "set")
            return Ok(True)
        except Exception as e:
            return Err(f"Failed to cache discount rules: {str(e)}")

    @beartype
    async def invalidate_quote_calculations(
        self,
        pattern: str | None = None,
    ) -> Result[int, str]:
        """Invalidate cached quote calculations.

        Args:
            pattern: Optional pattern to match (e.g., state code)

        Returns:
            Result containing number of invalidated entries or error
        """
        try:
            if pattern:
                keys = await self._cache.keys(f"rating:quote:*{pattern}*")
            else:
                keys = await self._cache.keys("rating:quote:*")

            if keys:
                deleted = await self._cache.delete(*keys)
                return Ok(deleted)
            return Ok(0)
        except Exception as e:
            return Err(f"Failed to invalidate quote cache: {str(e)}")

    @beartype
    async def warm_cache(
        self,
        common_zip_codes: list[tuple[str, str]],  # List of (state, zip) tuples
    ) -> Result[int, str]:
        """Pre-warm cache with common data.

        Args:
            common_zip_codes: List of common state/ZIP combinations

        Returns:
            Result containing number of warmed entries or error
        """
        warmed = 0

        try:
            # In production, fetch actual data from database
            for state, zip_code in common_zip_codes:
                # Mock territory factor calculation
                factor = 1.0 + (int(zip_code[:3]) % 50) / 100
                result = await self.cache_territory_factor(state, zip_code, factor)
                if result.is_ok():
                    warmed += 1

            return Ok(warmed)
        except Exception as e:
            return Err(f"Cache warming failed: {str(e)}")

    @beartype
    async def get_cache_stats(self) -> dict[str, dict[str, Any]]:
        """Get cache performance statistics.

        Returns:
            Dictionary of cache statistics by operation type
        """
        stats = {}

        for operation, counts in self._cache_stats.items():
            total = counts.get("hit", 0) + counts.get("miss", 0)
            hit_rate = counts.get("hit", 0) / total if total > 0 else 0

            stats[operation] = {
                "hits": counts.get("hit", 0),
                "misses": counts.get("miss", 0),
                "sets": counts.get("set", 0),
                "hit_rate": f"{hit_rate:.1%}",
            }

        return stats  # SYSTEM_BOUNDARY - Aggregated system data

    @beartype
    async def optimize_cache_ttl(
        self,
        usage_patterns: UsagePatternsMetrics,
    ) -> None:
        """Optimize cache TTL based on usage patterns.

        Args:
            usage_patterns: Dictionary of cache type to access frequency
        """
        for cache_type, frequency in usage_patterns.items():
            if cache_type in self._ttl_config:
                # High frequency = longer TTL
                if frequency > 100:  # More than 100 accesses per minute
                    self._ttl_config[cache_type] = min(
                        self._ttl_config[cache_type] * 2, 86400
                    )
                elif frequency < 10:  # Less than 10 accesses per minute
                    self._ttl_config[cache_type] = max(
                        self._ttl_config[cache_type] // 2, 300
                    )

    @beartype
    def _serialize_calculation_result(self, result: ResultData) -> ResultData:
        """Serialize calculation result for caching.

        Args:
            result: Calculation result to serialize

        Returns:
            Serializable dictionary
        """
        serialized: SerializedData = {}
        for key, value in result.items():
            if isinstance(value, Decimal):
                serialized[key] = str(value)
            elif isinstance(value, dict):
                serialized[key] = self._serialize_calculation_result(value)
            elif isinstance(value, list):
                serialized[key] = [
                    self._serialize_calculation_result(v) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                serialized[key] = value
        return serialized

    @beartype
    def _deserialize_calculation_result(self, data: DataData) -> DataData:
        """Deserialize cached calculation result.

        Args:
            data: Cached data to deserialize

        Returns:
            Deserialized calculation result
        """
        # Identify Decimal fields by convention (e.g., fields ending with _amount, _premium)
        decimal_fields = {
            "base_premium",
            "total_premium",
            "final_premium",
            "discount_amount",
            "surcharge_amount",
            "tax_amount",
        }

        deserialized: DeserializedData = {}
        for key, value in data.items():
            if key in decimal_fields and isinstance(value, str):
                deserialized[key] = Decimal(value)
            elif isinstance(value, dict):
                deserialized[key] = self._deserialize_calculation_result(value)
            elif isinstance(value, list):
                deserialized[key] = [
                    (
                        self._deserialize_calculation_result(v)
                        if isinstance(v, dict)
                        else v
                    )
                    for v in value
                ]
            else:
                deserialized[key] = value
        return deserialized

    @beartype
    def _record_cache_operation(self, operation_type: str, operation: str) -> None:
        """Record cache operation for statistics.

        Args:
            operation_type: Type of cache operation (e.g., "territory_factor")
            operation: Operation performed (e.g., "hit", "miss", "set")
        """
        if operation_type not in self._cache_stats:
            self._cache_stats[operation_type] = {}
        if operation not in self._cache_stats[operation_type]:
            self._cache_stats[operation_type][operation] = 0
        self._cache_stats[operation_type][operation] += 1


class RatingCacheManager:
    """Manager for coordinating multiple cache strategies."""

    def __init__(self, cache: Cache) -> None:
        """Initialize cache manager.

        Args:
            cache: Redis cache instance
        """
        self._cache = cache
        self._strategy = RatingCacheStrategy(cache)
        self._invalidation_queue: set[str] = set()

    @beartype
    async def get_or_calculate(
        self,
        cache_key: str,
        calculation_func: Any,  # Callable that returns Result
        cache_type: str = "quote_calculation",
    ) -> Result[Any, str]:
        """Get from cache or calculate if not cached.

        Args:
            cache_key: Cache key
            calculation_func: Function to calculate if not cached
            cache_type: Type of cache for TTL selection

        Returns:
            Result containing cached or calculated value
        """
        # Try cache first
        if cache_type == "territory_factor":
            parts = cache_key.split(":")
            if len(parts) >= 2:
                cached_result = await self._strategy.get_territory_factor(
                    parts[-2], parts[-1]
                )
                if cached_result.is_ok() and cached_result.unwrap() is not None:
                    return Ok(cached_result.unwrap())
        elif cache_type == "quote_calculation":
            quote_result = await self._strategy.get_quote_calculation(cache_key)
            if quote_result.is_ok() and quote_result.unwrap() is not None:
                return Ok(quote_result.unwrap())

        # Calculate if not cached
        calc_result: Result[Any, str] = await calculation_func()
        if calc_result.is_err():
            return calc_result

        # Cache the result
        value = calc_result.unwrap()
        if cache_type == "territory_factor" and isinstance(value, (int, float)):
            parts = cache_key.split(":")
            if len(parts) >= 2:
                await self._strategy.cache_territory_factor(
                    parts[-2], parts[-1], float(value)
                )
        elif cache_type == "quote_calculation" and isinstance(value, dict):
            await self._strategy.cache_quote_calculation(cache_key, value)

        return Ok(value)

    @beartype
    async def batch_invalidate(self) -> Result[int, str]:
        """Process queued cache invalidations.

        Returns:
            Result containing number of invalidated entries or error
        """
        if not self._invalidation_queue:
            return Ok(0)

        total_invalidated = 0
        patterns = list(self._invalidation_queue)
        self._invalidation_queue.clear()

        for pattern in patterns:
            result = await self._strategy.invalidate_quote_calculations(pattern)
            if result.is_ok():
                total_invalidated += result.unwrap()

        return Ok(total_invalidated)

    @beartype
    def queue_invalidation(self, pattern: str) -> None:
        """Queue a cache invalidation pattern.

        Args:
            pattern: Pattern to invalidate
        """
        self._invalidation_queue.add(pattern)
