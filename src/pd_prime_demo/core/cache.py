"""Redis caching layer with TTL support."""

from __future__ import annotations

import builtins
import json
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import redis.asyncio as redis
from attrs import field, frozen
from beartype import beartype

from .config import get_settings

__all__ = [
    "Cache",
    "get_cache",
    "init_redis_pool",
    "close_redis_pool",
    "get_redis_client",
    "RedisType",
]

if TYPE_CHECKING:
    from redis.asyncio import Redis as RedisType
else:
    RedisType = redis.Redis


@frozen
class CacheConfig:
    """Immutable cache configuration."""

    url: str = field()
    default_ttl: int = field(default=3600)  # 1 hour
    max_connections: int = field(default=10)
    decode_responses: bool = field(default=True)


class Cache:
    """Redis cache manager with async support.

    The constructor now optionally accepts an *already-created* ``redis.asyncio.Redis``
    instance.  This lets dependency-injection helpers do ``Cache(redis_client)``
    without running afoul of the strict ``mypy`` check that previously complained
    about “Too many arguments for \"Cache\"”.
    """

    def __init__(self, redis_client: RedisType | None = None) -> None:  # noqa: D401
        """Create a cache wrapper.

        Args:
            redis_client: Optional existing Redis client.  If provided the
                instance is used directly and :py:meth:`connect` becomes a no-op.
        """

        self._redis: RedisType | None = redis_client
        self._config = self._get_config()

    @beartype
    def _get_config(self) -> CacheConfig:
        """Get cache configuration from settings."""
        settings = get_settings()
        return CacheConfig(
            url=settings.redis_url,
            default_ttl=settings.redis_ttl_seconds,
        )

    @beartype
    async def connect(self) -> None:
        """Create Redis connection pool."""
        # If a client was pre-supplied, assume the caller already established
        # the connection (e.g. FastAPI dependency injection).  Nothing to do.
        if self._redis is not None:
            return

        # Type cast for Redis.from_url returning Any
        self._redis = redis.from_url(
            self._config.url,
            max_connections=self._config.max_connections,
            decode_responses=self._config.decode_responses,
        )

    @beartype
    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._redis is None:
            return

        await self._redis.close()
        self._redis = None

    @beartype
    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        value = await self._redis.get(key)
        if value is None:
            return None

        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    @beartype
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int | timedelta | None = None,
    ) -> bool:
        """Set value in cache with optional TTL."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        if ttl is None:
            ttl = self._config.default_ttl

        if isinstance(ttl, int):
            ttl = timedelta(seconds=ttl)

        # Serialize complex objects to JSON
        if not isinstance(value, (str, int, float, bytes)):
            value = json.dumps(value, default=str)

        # Type cast Redis setex return value to bool
        result = await self._redis.setex(key, ttl, value)
        return bool(result)

    @beartype
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        # Type cast Redis delete return value to bool
        result = await self._redis.delete(key)
        return bool(result > 0)

    @beartype
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        # Type cast Redis exists return value to bool
        result = await self._redis.exists(key)
        return bool(result > 0)

    @beartype
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        keys = []
        async for key in self._redis.scan_iter(match=pattern):
            keys.append(key)

        if keys:
            # Type cast Redis delete return value to int
            result = await self._redis.delete(*keys)
            return int(result)
        return 0

    @beartype
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment counter in cache."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        # Type cast Redis incrby return value to int
        result = await self._redis.incrby(key, amount)
        return int(result)

    @beartype
    async def decrement(self, key: str, amount: int = 1) -> int:
        """Decrement counter in cache."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        # Type cast Redis decrby return value to int
        result = await self._redis.decrby(key, amount)
        return int(result)

    @property
    def is_connected(self) -> bool:
        """Check if cache is connected."""
        return self._redis is not None

    @beartype
    async def health_check(self) -> bool:
        """Perform cache health check."""
        try:
            if not self.is_connected or self._redis is None:
                return False

            await self._redis.ping()
            return True
        except Exception:
            return False

    @beartype
    async def sadd(self, key: str, *values: str) -> int:
        """Add one or more members to a set."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        # Type cast Redis sadd return value to int
        result = await self._redis.sadd(key, *values)  # type: ignore[attr-defined]
        return int(result)

    @beartype
    async def srem(self, key: str, *values: str) -> int:
        """Remove one or more members from a set."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        # Type cast Redis srem return value to int
        result = await self._redis.srem(key, *values)  # type: ignore[attr-defined]
        return int(result)

    # Use typing.Set to avoid name collision with the "set" method on the same class
    @beartype
    async def smembers(self, key: str) -> builtins.set[str]:
        """Get all members of a set."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        # Type cast Redis smembers return value to set
        result = await self._redis.smembers(key)  # type: ignore[attr-defined]
        return set(result) if result else set()

    @beartype
    async def scard(self, key: str) -> int:
        """Get the number of members in a set."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        # Type cast Redis scard return value to int
        result = await self._redis.scard(key)  # type: ignore[attr-defined]
        return int(result)

    @beartype
    async def keys(self, pattern: str) -> list[str]:
        """Get all keys matching pattern."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        keys = []
        async for key in self._redis.scan_iter(match=pattern):
            keys.append(key)
        return keys

    @beartype
    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment counter value."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        result = await self._redis.incr(key, amount)  # type: ignore[attr-defined]
        return int(result)

    @beartype
    async def expire(self, key: str, seconds: int) -> bool:
        """Set key expiration."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        result = await self._redis.expire(key, seconds)  # type: ignore[attr-defined]
        return bool(result)

    @beartype
    async def lpush(self, key: str, *values: str) -> int:
        """Push values to left of list."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        result = await self._redis.lpush(key, *values)  # type: ignore[attr-defined]
        return int(result)

    @beartype
    async def brpoplpush(self, source: str, destination: str, timeout: int = 0) -> str | None:
        """Pop from right of source and push to left of destination."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        result = await self._redis.brpoplpush(source, destination, timeout)  # type: ignore[attr-defined]
        return str(result) if result is not None else None

    @beartype
    async def lrem(self, key: str, count: int, value: str) -> int:
        """Remove elements from list."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        result = await self._redis.lrem(key, count, value)  # type: ignore[attr-defined]
        return int(result)

    @beartype
    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        """Get range of elements from list."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        result = await self._redis.lrange(key, start, end)  # type: ignore[attr-defined]
        return [str(item) for item in result] if result else []

    @beartype
    async def llen(self, key: str) -> int:
        """Get length of list."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        result = await self._redis.llen(key)  # type: ignore[attr-defined]
        return int(result)

    @beartype
    async def hgetall(self, key: str) -> dict[str, str]:
        """Get all fields and values from hash."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        result = await self._redis.hgetall(key)  # type: ignore[attr-defined]
        return {str(k): str(v) for k, v in result.items()} if result else {}

    @beartype
    async def hset(self, key: str, field: str, value: str) -> int:
        """Set field in hash."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        result = await self._redis.hset(key, field, value)  # type: ignore[attr-defined]
        return int(result)

    @beartype
    async def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        """Increment field value in hash."""
        if self._redis is None:
            raise RuntimeError("Cache not connected")

        result = await self._redis.hincrby(key, field, amount)  # type: ignore[attr-defined]
        return int(result)


# Global cache instance
_cache: Cache | None = None


@beartype
def get_cache() -> Cache:
    """Get global cache instance."""
    global _cache
    if _cache is None:
        _cache = Cache()
    return _cache


@beartype
async def init_redis_pool() -> None:
    """Initialize the Redis connection pool."""
    cache = get_cache()
    await cache.connect()


@beartype
async def close_redis_pool() -> None:
    """Close the Redis connection pool."""
    cache = get_cache()
    await cache.disconnect()


@beartype
def get_redis_client() -> RedisType:
    """Get Redis client for dependency injection.

    Returns the underlying Redis client instance.
    """
    cache = get_cache()
    if cache._redis is None:
        raise RuntimeError("Redis not connected")
    return cache._redis
