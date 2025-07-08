"""Simple cache stub for connection pool testing."""

from typing import Any, Dict

from beartype import beartype


class Cache:
    """Simple cache stub."""

    def __init__(self) -> None:
        """Initialize cache stub."""
        self._cache: dict[str, Any] = {}

    @beartype
    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        return self._cache.get(key)

    @beartype
    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Set value in cache."""
        self._cache[key] = value


_cache: Cache | None = None


@beartype
def get_cache() -> Cache:
    """Get cache instance."""
    global _cache
    if _cache is None:
        _cache = Cache()
    return _cache
