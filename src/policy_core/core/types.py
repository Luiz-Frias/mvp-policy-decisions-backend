from __future__ import annotations

"""Core lightweight protocol interfaces so that production classes and async test mocks both satisfy them.

These protocols are **runtime_checkable** so beartype `isinstance` calls succeed against
`unittest.mock.AsyncMock` as long as the mocked attributes exist.  They intentionally
cover only the narrow surface required by RatingEngine / TerritoryManager, keeping our
public contract minimal.
"""

from typing import Any, Awaitable, Protocol, runtime_checkable


@runtime_checkable
class DatabaseLike(Protocol):
    """Minimal async database interface used by services."""

    async def fetch(self, query: str, *params: Any) -> Any: ...  # noqa: D401,E701

    async def fetchrow(self, query: str, *params: Any) -> Any: ...

    async def execute(self, query: str, *params: Any) -> Any: ...

    async def transaction(self) -> Any: ...


@runtime_checkable
class CacheLike(Protocol):
    """Minimal async cache interface used by services."""

    async def get(self, key: str) -> Awaitable[str | None]: ...

    async def set(self, key: str, value: str, ttl: int) -> Awaitable[None]: ...

    async def delete(self, key: str) -> Awaitable[None]: ...
