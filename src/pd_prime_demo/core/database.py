"""Database connection management with asyncpg and connection pooling."""

import contextlib
from collections.abc import AsyncIterator
from typing import Any, cast

import asyncpg
from attrs import field, frozen
from beartype import beartype

from .config import get_settings


@frozen
class DatabaseConfig:
    """Immutable database configuration."""

    url: str = field()
    min_size: int = field(default=5)
    max_size: int = field(default=20)
    command_timeout: float = field(default=30.0)
    statement_cache_size: int = field(default=100)


class Database:
    """Database connection manager with connection pooling."""

    def __init__(self) -> None:
        """Initialize database manager."""
        self._pool: asyncpg.Pool | None = None
        self._config = self._get_config()

    @beartype
    def _get_config(self) -> DatabaseConfig:
        """Get database configuration from settings."""
        settings = get_settings()
        return DatabaseConfig(
            url=settings.database_url,
            min_size=settings.database_pool_min,
            max_size=settings.database_pool_max,
        )

    @beartype
    async def connect(self) -> None:
        """Create database connection pool."""
        if self._pool is not None:
            return

        self._pool = await asyncpg.create_pool(
            self._config.url,
            min_size=self._config.min_size,
            max_size=self._config.max_size,
            command_timeout=self._config.command_timeout,
            statement_cache_size=self._config.statement_cache_size,
        )

    @beartype
    async def disconnect(self) -> None:
        """Close database connection pool."""
        if self._pool is None:
            return

        await self._pool.close()
        self._pool = None

    @beartype
    async def execute(self, query: str, *args: Any) -> str:
        """Execute a query without returning results."""
        if self._pool is None:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)

    @beartype
    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        """Execute a query and fetch all results."""
        if self._pool is None:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *args)

    @beartype
    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        """Execute a query and fetch a single row."""
        if self._pool is None:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    @beartype
    async def fetchval(self, query: str, *args: Any) -> Any:
        """Execute a query and fetch a single value."""
        if self._pool is None:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    @contextlib.asynccontextmanager
    @beartype
    async def transaction(self) -> AsyncIterator[asyncpg.Connection]:
        """Create a database transaction context."""
        if self._pool is None:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    @contextlib.asynccontextmanager
    @beartype
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        """Acquire a database connection from the pool."""
        if self._pool is None:
            raise RuntimeError("Database not connected")

        async with self._pool.acquire() as conn:
            yield conn

    @property
    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._pool is not None

    @beartype
    async def health_check(self) -> bool:
        """Perform database health check."""
        try:
            if not self.is_connected:
                return False

            result = await self.fetchval("SELECT 1")
            return cast(bool, result == 1)
        except Exception:
            return False


# Global database instance
_database: Database | None = None


@beartype
def get_database() -> Database:
    """Get global database instance."""
    global _database
    if _database is None:
        _database = Database()
    return _database


@beartype
async def init_db_pool() -> None:
    """Initialize the database connection pool."""
    db = get_database()
    await db.connect()


@beartype
async def close_db_pool() -> None:
    """Close the database connection pool."""
    db = get_database()
    await db.disconnect()


@contextlib.asynccontextmanager
@beartype
async def get_db_session() -> AsyncIterator[asyncpg.Connection]:
    """Get a database connection for dependency injection.

    This is used by FastAPI dependencies to get a database connection.
    """
    db = get_database()
    async with db.acquire() as conn:
        yield conn
