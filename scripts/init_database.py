#!/usr/bin/env python3
"""Initialize database with SSO tables and test data.

This script creates the necessary database tables for SSO functionality
and optionally inserts test data for development.
"""

import asyncio
import logging
import sys
from pathlib import Path

import asyncpg
from beartype import beartype

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pd_prime_demo.core.config import get_settings

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@beartype
async def read_sql_file(file_path: Path) -> str:
    """Read SQL file content.

    Args:
        file_path: Path to the SQL file

    Returns:
        SQL content as string
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to read SQL file {file_path}: {e}")
        raise


@beartype
async def execute_sql_file(conn: asyncpg.Connection, file_path: Path) -> None:
    """Execute SQL file.

    Args:
        conn: Database connection
        file_path: Path to the SQL file
    """
    logger.info(f"Executing SQL file: {file_path.name}")

    try:
        sql_content = await read_sql_file(file_path)
        await conn.execute(sql_content)
        logger.info(f"Successfully executed: {file_path.name}")
    except Exception as e:
        logger.error(f"Failed to execute {file_path.name}: {e}")
        raise


@beartype
async def create_database_if_not_exists(database_url: str) -> None:
    """Create database if it doesn't exist.

    Args:
        database_url: Database connection URL
    """
    # Parse database URL to get database name
    url_parts = database_url.split("/")
    db_name = url_parts[-1]

    # Connect to postgres database to create our database
    postgres_url = "/".join(url_parts[:-1]) + "/postgres"

    try:
        conn = await asyncpg.connect(postgres_url)

        # Check if database exists
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", db_name
        )

        if not exists:
            logger.info(f"Creating database: {db_name}")
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            logger.info(f"Database {db_name} created successfully")
        else:
            logger.info(f"Database {db_name} already exists")

        await conn.close()

    except Exception as e:
        logger.error(f"Failed to create database {db_name}: {e}")
        raise


@beartype
async def run_migrations(database_url: str, migrations_dir: Path) -> None:
    """Run database migrations.

    Args:
        database_url: Database connection URL
        migrations_dir: Directory containing migration files
    """
    # Create database if it doesn't exist
    await create_database_if_not_exists(database_url)

    # Connect to the target database
    conn = await asyncpg.connect(database_url)

    try:
        # Create migrations tracking table
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );
        """
        )

        # Get list of migration files
        migration_files = sorted(
            [f for f in migrations_dir.glob("*.sql") if f.is_file()]
        )

        if not migration_files:
            logger.warning(f"No migration files found in {migrations_dir}")
            return

        logger.info(f"Found {len(migration_files)} migration files")

        # Execute migrations
        for migration_file in migration_files:
            version = migration_file.stem

            # Check if migration already applied
            applied = await conn.fetchval(
                "SELECT 1 FROM schema_migrations WHERE version = $1", version
            )

            if applied:
                logger.info(f"Migration {version} already applied, skipping")
                continue

            logger.info(f"Applying migration: {version}")

            try:
                # Execute migration in a transaction
                async with conn.transaction():
                    await execute_sql_file(conn, migration_file)

                    # Record migration
                    await conn.execute(
                        "INSERT INTO schema_migrations (version) VALUES ($1)", version
                    )

                logger.info(f"Migration {version} applied successfully")

            except Exception as e:
                logger.error(f"Failed to apply migration {version}: {e}")
                raise

        logger.info("All migrations completed successfully")

    finally:
        await conn.close()


@beartype
async def verify_sso_tables(database_url: str) -> None:
    """Verify that SSO tables were created correctly.

    Args:
        database_url: Database connection URL
    """
    conn = await asyncpg.connect(database_url)

    try:
        logger.info("Verifying SSO table creation...")

        # List of expected tables
        expected_tables = [
            "users",
            "admin_users",
            "sso_provider_configs",
            "user_sso_links",
            "sso_group_mappings",
            "sso_group_sync_logs",
            "auth_logs",
            "sso_activity_logs",
            "user_provisioning_rules",
        ]

        for table_name in expected_tables:
            exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = $1
                );
            """,
                table_name,
            )

            if exists:
                logger.info(f"✓ Table '{table_name}' exists")

                # Get row count
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table_name}")
                logger.info(f"  └─ {count} rows")
            else:
                logger.error(f"✗ Table '{table_name}' NOT found")

        # Test basic SSO provider query
        providers = await conn.fetch(
            "SELECT provider_name, provider_type, is_enabled FROM sso_provider_configs"
        )

        logger.info(f"SSO Providers configured: {len(providers)}")
        for provider in providers:
            status = "enabled" if provider["is_enabled"] else "disabled"
            logger.info(
                f"  └─ {provider['provider_name']} ({provider['provider_type']}) - {status}"
            )

        logger.info("Database verification completed")

    finally:
        await conn.close()


@beartype
async def main() -> None:
    """Main initialization function."""
    try:
        # Get settings
        settings = get_settings()
        database_url = settings.database_url

        logger.info("Starting database initialization...")
        logger.info(
            f"Database URL: {database_url.split('@')[1] if '@' in database_url else 'LOCAL'}"
        )

        # Find migrations directory
        project_root = Path(__file__).parent.parent
        migrations_dir = project_root / "migrations"

        if not migrations_dir.exists():
            logger.error(f"Migrations directory not found: {migrations_dir}")
            sys.exit(1)

        # Run migrations
        await run_migrations(database_url, migrations_dir)

        # Verify tables
        await verify_sso_tables(database_url)

        logger.info("Database initialization completed successfully!")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
