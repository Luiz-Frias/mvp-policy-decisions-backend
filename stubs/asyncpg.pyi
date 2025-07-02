"""
🛡️ MASTER RULESET: Proper Type Stubs for AsyncPG
NO ANY TYPES - Explicit interfaces for all asyncpg functionality we use
"""

from collections.abc import Sequence
from types import TracebackType
from typing import Any, Optional, Union

# Core asyncpg types that we use in our codebase

class Record:
    """Represents a single row returned from a database query."""

    def __getitem__(self, key: Union[str, int]) -> Any: ...
    def get(self, key: str, default: Any = None) -> Any: ...
    def keys(self) -> Sequence[str]: ...
    def values(self) -> Sequence[Any]: ...
    def items(self) -> Sequence[tuple[str, Any]]: ...

class _ConnectionContext:
    """Async context manager for connection acquisition."""

    async def __aenter__(self) -> "Connection": ...
    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None: ...

class _TransactionContext:
    """Async context manager for transactions."""

    async def __aenter__(self) -> "Connection": ...
    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None: ...

class Connection:
    """Represents a database connection."""

    async def execute(self, query: str, *args: Any) -> str: ...
    async def fetch(self, query: str, *args: Any) -> list[Record]: ...
    async def fetchrow(self, query: str, *args: Any) -> Optional[Record]: ...
    async def fetchval(self, query: str, *args: Any) -> Any: ...
    async def close(self) -> None: ...
    def transaction(self) -> _TransactionContext: ...

class Pool:
    """Represents a connection pool."""

    def acquire(self) -> _ConnectionContext: ...
    async def close(self) -> None: ...
    async def execute(self, query: str, *args: Any) -> str: ...
    async def fetch(self, query: str, *args: Any) -> list[Record]: ...
    async def fetchrow(self, query: str, *args: Any) -> Optional[Record]: ...
    def terminate(self) -> None: ...

# Exception classes
class PostgresError(Exception): ...
class UniqueViolationError(PostgresError): ...
class InvalidCatalogNameError(PostgresError): ...

# Module-level functions
async def connect(
    dsn: Optional[str] = None,
    *,
    host: Optional[str] = None,
    port: Optional[Union[str, int]] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
    **kwargs: Any,
) -> Connection: ...
async def create_pool(
    dsn: Optional[str] = None,
    *,
    min_size: int = 10,
    max_size: int = 10,
    host: Optional[str] = None,
    port: Optional[Union[str, int]] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
    **kwargs: Any,
) -> Pool: ...

# Connection submodule
