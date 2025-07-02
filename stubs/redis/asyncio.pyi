"""
🛡️ MASTER RULESET: Redis asyncio module type stubs
NO ANY TYPES - Explicit interfaces for all redis.asyncio functionality we use
"""

from collections.abc import AsyncIterator, Mapping
from datetime import timedelta
from typing import Optional, Union

class Redis:
    """Redis async client with explicit typing for our use cases."""

    # Connection and lifecycle
    @classmethod
    def from_url(
        cls,
        url: str,
        *,
        max_connections: int = 10,
        decode_responses: bool = True,
        **kwargs: Union[str, int, bool],
    ) -> "Redis": ...
    async def close(self) -> None: ...

    # Basic operations
    async def ping(self) -> bytes: ...
    async def info(
        self, section: str = "default"
    ) -> Mapping[str, Union[str, int, float]]: ...

    # String operations
    async def get(self, key: str) -> Optional[str]: ...
    async def set(
        self,
        key: str,
        value: Union[str, int, float, bytes],
        ex: Optional[Union[int, timedelta]] = None,
        px: Optional[Union[int, timedelta]] = None,
        nx: bool = False,
        xx: bool = False,
    ) -> bool: ...
    async def setex(
        self,
        key: str,
        time: Union[int, timedelta],
        value: Union[str, int, float, bytes],
    ) -> bool: ...

    # Key operations
    async def delete(self, *keys: str) -> int: ...
    async def exists(self, *keys: str) -> int: ...
    async def ttl(self, key: str) -> int: ...
    async def keys(self, pattern: str = "*") -> list[str]: ...
    async def type(self, key: str) -> str: ...

    # Scanning
    def scan_iter(
        self,
        match: Optional[str] = None,
        count: Optional[int] = None,
    ) -> AsyncIterator[str]: ...

    # Numeric operations
    async def incrby(self, key: str, amount: int = 1) -> int: ...
    async def decrby(self, key: str, amount: int = 1) -> int: ...

# Module-level functions that mirror the Redis class methods
def from_url(
    url: str,
    *,
    max_connections: int = 10,
    decode_responses: bool = True,
    **kwargs: Union[str, int, bool],
) -> Redis: ...

# Module exports
__all__ = ["Redis", "from_url"]
