"""Simple cache stub for connection pool testing."""

from typing import Any

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field


@beartype
class CacheEntry(BaseModel):
    """Cache entry with value and metadata."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    value: Any = Field(..., description="Cached value")
    ttl_seconds: int = Field(default=300, ge=0, description="Time to live in seconds")


@beartype
class CacheStore(BaseModel):
    """Internal cache storage."""

    model_config = ConfigDict(
        frozen=False,  # Mutable for cache operations
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    entries: dict[str, CacheEntry] = Field(
        default_factory=dict, description="Cache entries"
    )


class Cache:
    """Simple cache stub."""

    def __init__(self) -> None:
        """Initialize cache stub."""
        self._store = CacheStore()

    @beartype
    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        entry = self._store.entries.get(key)
        return entry.value if entry else None

    @beartype
    async def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Set value in cache."""
        entry = CacheEntry(value=value, ttl_seconds=ttl_seconds)
        self._store.entries[key] = entry


_cache: Cache | None = None


@beartype
def get_cache() -> Cache:
    """Get cache instance."""
    global _cache
    if _cache is None:
        _cache = Cache()
    return _cache
