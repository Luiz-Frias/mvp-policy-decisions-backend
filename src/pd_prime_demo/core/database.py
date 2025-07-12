"""Database connection management with asyncpg and connection pooling.

This module provides backward compatibility while using the enhanced database implementation.
"""

# Re-export everything from the enhanced database module
from .database_enhanced import (
    Database,
    DatabaseConfig,
    PoolConfig,
    PoolMetrics,
    RecoveryConfig,
    close_db_pool,
    get_database,
    get_db_session,
    init_db_pool,
)

__all__ = [
    "Database",
    "DatabaseConfig",
    "PoolConfig",
    "PoolMetrics",
    "RecoveryConfig",
    "close_db_pool",
    "get_database",
    "get_db_session",
    "init_db_pool",
]
