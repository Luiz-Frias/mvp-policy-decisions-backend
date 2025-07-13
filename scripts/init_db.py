#!/usr/bin/env python3
"""Initialize database for MVP Policy Decision Backend.

This script:
1. Creates the database if it doesn't exist
2. Runs all migrations
3. Validates the schema
"""

import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from beartype import beartype
from dotenv import load_dotenv

from alembic import command
from alembic.config import Config

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@beartype
async def create_database_if_not_exists(database_url: str) -> None:
    """Create database if it doesn't exist.

    Args:
        database_url: PostgreSQL connection URL
    """
    # Parse the database URL to extract components
    if database_url.startswith("postgresql://"):
        url_parts = database_url.replace("postgresql://", "").split("/")
    elif database_url.startswith("postgresql+asyncpg://"):
        url_parts = database_url.replace("postgresql+asyncpg://", "").split("/")
    else:
        raise ValueError(f"Invalid database URL format: {database_url}")

    if len(url_parts) < 2:
        raise ValueError(f"Database name not found in URL: {database_url}")

    user_host = url_parts[0]
    db_name = url_parts[1].split("?")[0]  # Remove any query parameters

    # Connect to postgres database to create the target database
    postgres_url = f"postgresql://{user_host}/postgres"

    try:
        # First, try to connect to the target database
        target_conn = await asyncpg.connect(
            database_url.replace("postgresql+asyncpg://", "postgresql://")
        )
        await target_conn.close()
        print(f"Database '{db_name}' already exists.")
    except asyncpg.InvalidCatalogNameError:
        # Database doesn't exist, create it
        print(f"Database '{db_name}' does not exist. Creating...")
        conn = await asyncpg.connect(postgres_url)
        try:
            # Check if database exists
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = $1)",
                db_name,
            )
            if not exists:
                await conn.execute(f'CREATE DATABASE "{db_name}"')
                print(f"Database '{db_name}' created successfully.")
            else:
                print(f"Database '{db_name}' already exists.")
        finally:
            await conn.close()
    except Exception as e:
        print(f"Error connecting to database: {e}")
        raise


@beartype
def run_migrations(alembic_ini_path: Path) -> None:
    """Run all pending migrations.

    Args:
        alembic_ini_path: Path to alembic.ini file
    """
    print("Running database migrations...")
    alembic_cfg = Config(str(alembic_ini_path))

    # Set script location relative to config file
    alembic_cfg.set_main_option(
        "script_location", str(alembic_ini_path.parent / "alembic")
    )

    try:
        # Upgrade to the latest revision
        command.upgrade(alembic_cfg, "head")
        print("Migrations completed successfully.")
    except Exception as e:
        print(f"Error running migrations: {e}")
        raise


@beartype
async def validate_schema(database_url: str) -> None:
    """Validate that all expected tables and columns exist.

    Args:
        database_url: PostgreSQL connection URL
    """
    print("Validating database schema...")

    # Convert to asyncpg URL format
    conn_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(conn_url)

    try:
        # Check for expected tables
        expected_tables = ["customers", "policies", "claims"]

        tables = await conn.fetch(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename = ANY($1::text[])
            """,
            expected_tables,
        )

        found_tables = {row["tablename"] for row in tables}
        missing_tables = set(expected_tables) - found_tables

        if missing_tables:
            raise ValueError(f"Missing tables: {missing_tables}")

        print(f"All expected tables found: {expected_tables}")

        # Validate indexes exist
        indexes = await conn.fetch(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND tablename = ANY($1::text[])
            """,
            expected_tables,
        )

        index_names = {row["indexname"] for row in indexes}
        print(f"Found {len(index_names)} indexes")

        # Validate triggers exist
        triggers = await conn.fetch(
            """
            SELECT trigger_name
            FROM information_schema.triggers
            WHERE trigger_schema = 'public'
            """,
        )

        trigger_names = {row["trigger_name"] for row in triggers}
        expected_triggers = {f"update_{table}_updated_at" for table in expected_tables}
        missing_triggers = expected_triggers - trigger_names

        if missing_triggers:
            raise ValueError(f"Missing triggers: {missing_triggers}")

        print("Schema validation completed successfully.")

    finally:
        await conn.close()


@beartype
async def main() -> None:
    """Execute main initialization function."""
    # Load environment variables
    load_dotenv()

    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Please set DATABASE_URL in your .env file or environment")
        print(
            "Example: DATABASE_URL=postgresql://user:password@localhost:5432/policy_core"
        )
        sys.exit(1)

    # Ensure async compatibility
    if "postgresql://" in database_url and "+asyncpg" not in database_url:
        async_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    else:
        async_url = database_url

    print("Initializing database...")
    print(
        f"Database URL: {database_url.split('@')[1] if '@' in database_url else database_url}"
    )  # Hide credentials

    try:
        # Create database if needed
        await create_database_if_not_exists(database_url)

        # Run migrations
        alembic_ini = PROJECT_ROOT / "alembic.ini"
        if not alembic_ini.exists():
            raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")

        # Update alembic.ini with the database URL
        os.environ["DATABASE_URL"] = database_url

        run_migrations(alembic_ini)

        # Validate schema
        await validate_schema(async_url)

        print("\nDatabase initialization completed successfully!")

    except Exception as e:
        print(f"\nERROR during database initialization: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
