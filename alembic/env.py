"""Alembic environment configuration."""

import asyncio
import os
from logging.config import fileConfig
from typing import Any

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Import your declarative base and models here
# This will be updated when models are implemented
# from src.policy_core.models import Base

# This is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object here
# for 'autogenerate' support
# target_metadata = Base.metadata
target_metadata = None  # Will be updated when models are implemented

# Import our settings to use the effective database URL logic
import sys
from pathlib import Path

# Add src to path so we can import our configuration
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from policy_core.core.config import get_settings

# Use our smart URL selection logic
settings = get_settings()
DATABASE_URL = settings.effective_database_url

# Override the sqlalchemy.url from alembic.ini with environment variable
if "sqlite" in DATABASE_URL or "sqlite" in config.get_main_option("sqlalchemy.url", ""):
    # For SQLite testing, use the URL as-is (synchronous)
    pass
else:
    # For PostgreSQL, convert to async driver
    config.set_main_option(
        "sqlalchemy.url", DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Any) -> None:
    """Execute migrations using provided connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        raise ValueError("sqlalchemy.url is not set in alembic.ini")

    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
        future=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.
    """
    url = config.get_main_option("sqlalchemy.url")
    if url and "sqlite" in url:
        # Use synchronous SQLite for testing
        run_sync_migrations()
    else:
        # Handle async migrations for PostgreSQL
        asyncio.run(run_async_migrations())


def run_sync_migrations() -> None:
    """Run migrations in synchronous mode for SQLite."""
    from sqlalchemy import create_engine

    url = config.get_main_option("sqlalchemy.url")
    engine = create_engine(url)

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
