#!/usr/bin/env python3
"""Database connectivity check utility."""

import asyncio
import sys

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

# Import database configuration
try:
    from policy_core.core.config import settings
    from policy_core.core.database import get_db_session
except ImportError:
    print("❌ Failed to import database configuration")
    print("Make sure the application is properly installed")
    sys.exit(1)


class DatabaseCheckResult(BaseModel):
    """Result of database connectivity check."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    connected: bool = Field(..., description="Whether connection was successful")
    database_name: str | None = Field(None, description="Name of connected database")
    version: str | None = Field(None, description="Database version")
    error: str | None = Field(None, description="Error message if connection failed")
    latency_ms: float | None = Field(
        None, ge=0, description="Connection latency in milliseconds"
    )


@beartype
async def check_database_connection() -> DatabaseCheckResult:
    """Check database connectivity and return detailed results."""
    import time

    start_time = time.perf_counter()

    try:
        # Create engine with minimal pool for testing
        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            poolclass=NullPool,  # No connection pooling for test
        )

        async with engine.begin() as conn:
            # Test basic connectivity
            result = await conn.execute(text("SELECT 1"))
            result.scalar()

            # Get database name
            db_name_result = await conn.execute(text("SELECT current_database()"))
            database_name = db_name_result.scalar()

            # Get PostgreSQL version
            version_result = await conn.execute(text("SELECT version()"))
            version_info = version_result.scalar()

            # Calculate latency
            latency_ms = (time.perf_counter() - start_time) * 1000

            await engine.dispose()

            return DatabaseCheckResult(
                connected=True,
                database_name=database_name,
                version=version_info,
                error=None,
                latency_ms=round(latency_ms, 2),
            )

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        return DatabaseCheckResult(
            connected=False,
            database_name=None,
            version=None,
            error=error_msg,
            latency_ms=None,
        )


@beartype
async def check_database_tables() -> None:
    """Check for expected database tables."""
    try:
        async with get_db_session() as session:
            # Check for common tables
            tables_query = text(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
                """
            )
            result = await session.execute(tables_query)
            tables = [row[0] for row in result]

            if tables:
                print(f"\n📋 Found {len(tables)} tables:")
                for table in tables:
                    print(f"  - {table}")
            else:
                print("\n⚠️  No tables found in public schema")

    except Exception as e:
        print(f"\n❌ Failed to check tables: {e}")


@beartype
async def main() -> None:
    """Run database connectivity checks."""
    print("🗄️  PostgreSQL Database Connectivity Check")
    print("=" * 50)

    # Check basic connectivity
    result = await check_database_connection()

    if result.connected:
        print("\n✅ Successfully connected to database!")
        print(f"  📍 Database: {result.database_name}")
        print(f"  🔢 Version: {result.version}")
        print(f"  ⚡ Latency: {result.latency_ms}ms")

        # Check tables if connected
        await check_database_tables()

        # Test connection pooling
        print("\n🔄 Testing connection pool...")
        try:
            async with get_db_session() as session:
                result = await session.execute(text("SELECT NOW()"))
                timestamp = result.scalar()
                print("  ✅ Pool connection successful")
                print(f"  🕐 Server time: {timestamp}")
        except Exception as e:
            print(f"  ❌ Pool connection failed: {e}")

    else:
        print("\n❌ Failed to connect to database!")
        print(f"  Error: {result.error}")
        print("\n💡 Troubleshooting tips:")
        print("  1. Check DATABASE_URL in .env file")
        print("  2. Ensure PostgreSQL is running")
        print("  3. Verify database credentials")
        print("  4. Check network connectivity")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
