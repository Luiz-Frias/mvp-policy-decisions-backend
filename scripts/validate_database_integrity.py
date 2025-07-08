#!/usr/bin/env python3
"""Validate database integrity including foreign keys, indexes, and constraints.

This script checks:
1. All foreign key relationships are valid
2. All indexes are properly created
3. All check constraints are enforced
4. Table relationships follow expected patterns
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Tuple

from beartype import beartype

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pd_prime_demo.core.config import get_settings
from src.pd_prime_demo.core.database_enhanced import Database


@beartype
class DatabaseIntegrityValidator:
    """Validate database integrity and relationships."""

    def __init__(self) -> None:
        """Initialize validator."""
        self.db = Database()
        self.settings = get_settings()
        self.issues: list[str] = []
        self.warnings: list[str] = []

    @beartype
    async def validate_all(self) -> tuple[bool, list[str], list[str]]:
        """Run all validation checks."""
        print("🔍 Validating Database Integrity...")
        print("=" * 80)

        await self.db.connect()

        try:
            # Check foreign keys
            await self._validate_foreign_keys()

            # Check indexes
            await self._validate_indexes()

            # Check constraints
            await self._validate_constraints()

            # Check table relationships
            await self._validate_relationships()

            # Check for orphaned records
            await self._check_orphaned_records()

        finally:
            await self.db.disconnect()

        success = len(self.issues) == 0
        return success, self.issues, self.warnings

    @beartype
    async def _validate_foreign_keys(self) -> None:
        """Validate all foreign key relationships."""
        print("\n📋 Checking Foreign Key Relationships...")

        query = """
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            tc.constraint_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = 'public'
        ORDER BY tc.table_name;
        """

        async with self.db.acquire() as conn:
            fks = await conn.fetch(query)

            print(f"  Found {len(fks)} foreign key relationships")

            # Expected foreign keys
            expected_fks = [
                ("quotes", "customer_id", "customers"),
                ("quotes", "parent_quote_id", "quotes"),
                ("quotes", "converted_to_policy_id", "policies"),
                ("quotes", "created_by", "users"),
                ("quotes", "updated_by", "users"),
                ("policies", "customer_id", "customers"),
                ("claims", "policy_id", "policies"),
                ("claims", "customer_id", "customers"),
                ("user_mfa_settings", "user_id", "users"),
                ("oauth2_tokens", "client_id", "oauth2_clients"),
                ("oauth2_tokens", "user_id", "users"),
                ("admin_users", "role_id", "admin_roles"),
                ("admin_users", "created_by", "admin_users"),
                ("admin_activity_logs", "admin_user_id", "admin_users"),
                ("websocket_connections", "user_id", "users"),
                ("analytics_events", "user_id", "users"),
                ("analytics_events", "quote_id", "quotes"),
                ("analytics_events", "policy_id", "policies"),
            ]

            # Check each expected FK exists
            for table, column, ref_table in expected_fks:
                found = any(
                    fk["table_name"] == table
                    and fk["column_name"] == column
                    and fk["foreign_table_name"] == ref_table
                    for fk in fks
                )
                if not found:
                    self.issues.append(
                        f"Missing foreign key: {table}.{column} -> {ref_table}"
                    )
                else:
                    print(f"  ✅ {table}.{column} -> {ref_table}")

    @beartype
    async def _validate_indexes(self) -> None:
        """Validate all indexes are created."""
        print("\n🔍 Checking Database Indexes...")

        query = """
        SELECT
            schemaname,
            tablename,
            indexname,
            indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname;
        """

        async with self.db.acquire() as conn:
            indexes = await conn.fetch(query)

            print(f"  Found {len(indexes)} indexes")

            # Group by table
            by_table = {}
            for idx in indexes:
                table = idx["tablename"]
                if table not in by_table:
                    by_table[table] = []
                by_table[table].append(idx["indexname"])

            # Check critical tables have indexes
            critical_tables = [
                ("quotes", ["quote_number", "customer_id", "status", "expires_at"]),
                ("policies", ["policy_number", "customer_id", "status"]),
                ("customers", ["external_id"]),
                ("claims", ["claim_number", "policy_id", "status"]),
                ("users", ["email"]),
                ("audit_logs", ["user_id", "created_at", "resource_type"]),
            ]

            for table, expected_cols in critical_tables:
                if table not in by_table:
                    self.issues.append(f"Table {table} has no indexes!")
                    continue

                table_indexes = by_table[table]
                for col in expected_cols:
                    # Check if column is indexed (in any index)
                    has_index = any(col in idx for idx in table_indexes)
                    if not has_index:
                        self.warnings.append(
                            f"Column {table}.{col} should be indexed for performance"
                        )
                else:
                    print(f"  ✅ {table} has {len(table_indexes)} indexes")

    @beartype
    async def _validate_constraints(self) -> None:
        """Validate check constraints."""
        print("\n📋 Checking Check Constraints...")

        query = """
        SELECT
            conname AS constraint_name,
            conrelid::regclass AS table_name,
            pg_get_constraintdef(oid) AS constraint_definition
        FROM pg_constraint
        WHERE contype = 'c'
        AND connamespace = 'public'::regnamespace
        ORDER BY conrelid::regclass::text;
        """

        async with self.db.acquire() as conn:
            constraints = await conn.fetch(query)

            print(f"  Found {len(constraints)} check constraints")

            # Validate critical constraints exist
            critical_constraints = [
                (
                    "quotes",
                    "status",
                    ["draft", "calculating", "quoted", "expired", "bound", "declined"],
                ),
                ("policies", "status", ["active", "cancelled", "expired", "suspended"]),
                (
                    "claims",
                    "status",
                    [
                        "submitted",
                        "investigating",
                        "approved",
                        "denied",
                        "paid",
                        "closed",
                    ],
                ),
                ("users", "role", ["agent", "underwriter", "admin", "system"]),
            ]

            for table, column, valid_values in critical_constraints:
                found = False
                for constraint in constraints:
                    if (
                        str(constraint["table_name"]) == table
                        and column in constraint["constraint_definition"]
                    ):
                        found = True
                        print(f"  ✅ {table}.{column} has check constraint")
                        break

                if not found:
                    self.issues.append(f"Missing check constraint on {table}.{column}")

    @beartype
    async def _validate_relationships(self) -> None:
        """Validate table relationships are consistent."""
        print("\n🔗 Checking Table Relationships...")

        async with self.db.acquire() as conn:
            # Check policies reference valid customers
            orphaned_policies = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM policies p
                WHERE NOT EXISTS (
                    SELECT 1 FROM customers c WHERE c.id = p.customer_id
                )
            """
            )

            if orphaned_policies > 0:
                self.issues.append(
                    f"Found {orphaned_policies} policies without valid customers"
                )
            else:
                print("  ✅ All policies have valid customers")

            # Check claims reference valid policies
            orphaned_claims = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM claims c
                WHERE NOT EXISTS (
                    SELECT 1 FROM policies p WHERE p.id = c.policy_id
                )
            """
            )

            if orphaned_claims > 0:
                self.issues.append(
                    f"Found {orphaned_claims} claims without valid policies"
                )
            else:
                print("  ✅ All claims have valid policies")

            # Check quotes with conversion reference valid policies
            invalid_conversions = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM quotes q
                WHERE q.converted_to_policy_id IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM policies p WHERE p.id = q.converted_to_policy_id
                )
            """
            )

            if invalid_conversions > 0:
                self.issues.append(
                    f"Found {invalid_conversions} quotes with invalid policy conversions"
                )
            else:
                print("  ✅ All quote conversions reference valid policies")

    @beartype
    async def _check_orphaned_records(self) -> None:
        """Check for orphaned records that violate business rules."""
        print("\n🔍 Checking for Orphaned Records...")

        async with self.db.acquire() as conn:
            # Check for quotes without customers (should be allowed for anonymous quotes)
            anonymous_quotes = await conn.fetchval(
                """
                SELECT COUNT(*) FROM quotes WHERE customer_id IS NULL
            """
            )

            if anonymous_quotes > 0:
                print(
                    f"  ℹ️  Found {anonymous_quotes} anonymous quotes (this is allowed)"
                )

            # Check for expired quotes that weren't converted
            expired_unconverted = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM quotes
                WHERE status = 'expired'
                AND converted_to_policy_id IS NULL
                AND expires_at < CURRENT_TIMESTAMP
            """
            )

            if expired_unconverted > 0:
                print(
                    f"  ℹ️  Found {expired_unconverted} expired quotes (normal business flow)"
                )

    @beartype
    async def print_summary(
        self, success: bool, issues: list[str], warnings: list[str]
    ) -> None:
        """Print validation summary."""
        print("\n" + "=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)

        if success:
            print("✅ Database integrity validation PASSED!")
        else:
            print("❌ Database integrity validation FAILED!")
            print(f"\nFound {len(issues)} critical issues:")
            for issue in issues:
                print(f"  ❌ {issue}")

        if warnings:
            print(f"\nFound {len(warnings)} warnings:")
            for warning in warnings:
                print(f"  ⚠️  {warning}")

        print("\n" + "=" * 80)


async def main() -> None:
    """Run database integrity validation."""
    validator = DatabaseIntegrityValidator()
    success, issues, warnings = await validator.validate_all()
    await validator.print_summary(success, issues, warnings)

    # Exit with error code if validation failed
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
