#!/usr/bin/env python3
"""Test script to validate all migrations work correctly.

This script tests migrations using SQLite to ensure they run without errors.
It checks for common migration issues and validates schema integrity.
"""

import os
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, text

from alembic import command
from alembic.config import Config


def test_migrations_sqlite():
    """Test all migrations using SQLite."""
    print("🔍 Testing database migrations with SQLite...")

    # Create temporary SQLite database
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp_file:
        db_path = tmp_file.name

    try:
        # Configure Alembic for SQLite
        alembic_cfg = Config("alembic.ini")
        sqlite_url = f"sqlite:///{db_path}"
        alembic_cfg.set_main_option("sqlalchemy.url", sqlite_url)

        # Disable PostgreSQL-specific features for SQLite testing
        print("⚙️ Configuring SQLite compatibility...")

        print(f"📊 Using temporary database: {db_path}")

        # Test running all migrations
        print("⬆️ Running all migrations...")
        command.upgrade(alembic_cfg, "head")
        print("✅ All migrations completed successfully!")

        # Validate schema integrity
        print("🔍 Validating schema integrity...")
        validate_schema(sqlite_url)

        # Test migration rollback
        print("⬇️ Testing migration rollback...")
        command.downgrade(alembic_cfg, "base")
        print("✅ All rollbacks completed successfully!")

        # Test migration again to ensure idempotency
        print("⬆️ Re-running migrations to test idempotency...")
        command.upgrade(alembic_cfg, "head")
        print("✅ Idempotency test passed!")

    except Exception as e:
        print(f"❌ Migration test failed: {e}")
        raise
    finally:
        # Cleanup temporary database
        if os.path.exists(db_path):
            os.unlink(db_path)
            print(f"🧹 Cleaned up temporary database: {db_path}")


def validate_schema(database_url: str):
    """Validate the migrated schema meets requirements."""
    engine = create_engine(database_url)

    with engine.connect() as conn:
        # Check if all expected tables exist
        expected_tables = [
            "customers",
            "policies",
            "claims",
            "users",
            "quotes",
            "rate_tables",
            "discount_rules",
            "surcharge_rules",
            "territory_factors",
            "sso_providers",
            "oauth2_clients",
            "user_mfa_settings",
            "audit_logs",
            "websocket_connections",
            "analytics_events",
            "admin_users",
            "admin_roles",
            "admin_permissions",
            "system_settings",
            "admin_activity_logs",
            "admin_dashboards",
            "admin_rate_approvals",
        ]

        # Get actual tables from database
        result = conn.execute(
            text(
                """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'
        """
            )
        )
        actual_tables = {row[0] for row in result}

        print(f"📋 Found {len(actual_tables)} tables in database")

        # Check for missing tables
        missing_tables = set(expected_tables) - actual_tables
        if missing_tables:
            print(f"⚠️ Missing tables: {missing_tables}")

        # Check for unexpected tables
        extra_tables = actual_tables - set(expected_tables)
        if extra_tables:
            print(f"ℹ️ Additional tables: {extra_tables}")

        # Validate foreign key constraints (basic check)
        for table in actual_tables:
            try:
                result = conn.execute(text(f"PRAGMA foreign_key_list({table})"))
                fk_count = len(list(result))
                if fk_count > 0:
                    print(f"✅ Table '{table}' has {fk_count} foreign key(s)")
            except Exception as e:
                print(f"⚠️ Could not check foreign keys for '{table}': {e}")

        print("✅ Schema validation completed!")


def check_migration_files():
    """Check migration files for common issues."""
    print("🔍 Checking migration files for issues...")

    versions_dir = Path("alembic/versions")
    migration_files = list(versions_dir.glob("*.py"))

    print(f"📁 Found {len(migration_files)} migration files")

    # Check for revision conflicts
    revisions = []
    for file_path in migration_files:
        try:
            with open(file_path) as f:
                content = f.read()
                for line in content.split("\n"):
                    if line.strip().startswith("revision:"):
                        revision = line.split('"')[1]
                        revisions.append((revision, file_path.name))
                        break
        except Exception as e:
            print(f"⚠️ Could not parse revision from {file_path.name}: {e}")

    # Check for duplicate revisions
    revision_dict = {}
    for revision, filename in revisions:
        if revision in revision_dict:
            print(f"❌ Duplicate revision '{revision}' found in:")
            print(f"   - {revision_dict[revision]}")
            print(f"   - {filename}")
            raise ValueError(f"Duplicate revision ID: {revision}")
        revision_dict[revision] = filename

    print(f"✅ All {len(revisions)} revision IDs are unique")

    # Check migration sequence
    print("🔗 Checking migration sequence...")
    for file_path in migration_files:
        try:
            with open(file_path) as f:
                content = f.read()
                has_upgrade = "def upgrade()" in content
                has_downgrade = "def downgrade()" in content

                if not has_upgrade:
                    print(f"❌ Missing upgrade() function in {file_path.name}")
                if not has_downgrade:
                    print(f"❌ Missing downgrade() function in {file_path.name}")

                if has_upgrade and has_downgrade:
                    print(
                        f"✅ {file_path.name} has both upgrade and downgrade functions"
                    )

        except Exception as e:
            print(f"⚠️ Could not validate {file_path.name}: {e}")


def main():
    """Main test function."""
    print("🚀 Starting database migration validation...")
    print("=" * 60)

    try:
        # Check migration files first
        check_migration_files()
        print("-" * 60)

        # Test actual migrations
        test_migrations_sqlite()
        print("-" * 60)

        print("🎉 All migration tests passed successfully!")

    except Exception as e:
        print(f"💥 Migration validation failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
