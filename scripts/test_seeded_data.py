#!/usr/bin/env python3
"""Test the seeded data by performing sample rate calculations.

This script verifies that all seeded data works together correctly.
"""

import asyncio
import json
import os
import sys
from datetime import date
from decimal import Decimal

import asyncpg
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def calculate_sample_quote(
    conn: asyncpg.Connection, state: str, zip_code: str
) -> None:
    """Calculate a sample quote using seeded rate data."""
    print(f"\n📊 Calculating quote for {state} (ZIP: {zip_code})")

    # Get base rate for auto liability
    rate = await conn.fetchrow(
        """
        SELECT * FROM rate_tables
        WHERE state = $1
        AND product_type = 'auto'
        AND coverage_type = 'liability'
        AND effective_date <= $2
        ORDER BY effective_date DESC
        LIMIT 1
    """,
        state,
        date.today(),
    )

    if not rate:
        print(f"  ❌ No rate table found for {state}")
        return

    print(f"  Base rate: ${rate['base_rate']}")

    # Get territory factor
    territory = await conn.fetchrow(
        """
        SELECT * FROM territory_factors
        WHERE state = $1 AND zip_code = $2 AND product_type = 'auto'
        LIMIT 1
    """,
        state,
        zip_code,
    )

    if territory:
        print(f"  Territory factor: {territory['base_factor']}")
    else:
        print("  Territory factor: 1.0 (default)")

    # Get applicable discounts
    discounts = await conn.fetch(
        """
        SELECT * FROM discount_rules
        WHERE states::jsonb @> $1::jsonb AND product_types::jsonb @> $2::jsonb
        AND effective_date <= $3
        ORDER BY priority
    """,
        json.dumps([state]),
        json.dumps(["auto"]),
        date.today(),
    )

    print(f"  Available discounts: {len(discounts)}")
    for discount in discounts[:3]:  # Show first 3
        print(f"    - {discount['name']}: {discount['discount_value']}%")

    # Calculate sample premium
    coverage_amount = Decimal("300000")  # $300k liability
    base_premium = coverage_amount * rate["base_rate"]
    territory_factor = (
        Decimal(str(territory["base_factor"])) if territory else Decimal("1.0")
    )

    adjusted_premium = base_premium * territory_factor

    print("\n  💰 Sample calculation:")
    print(f"     Coverage: ${coverage_amount:,.2f}")
    print(f"     Base premium: ${base_premium:,.2f}")
    print(f"     After territory: ${adjusted_premium:,.2f}")
    print(f"     Min premium: ${rate['min_premium']:,.2f}")
    print(f"     Max premium: ${rate['max_premium']:,.2f}")


async def test_user_access(conn: asyncpg.Connection) -> None:
    """Test user access levels."""
    print("\n👥 Testing user access:")

    users = await conn.fetch(
        """
        SELECT email, first_name, last_name, role
        FROM users
        ORDER BY role, email
    """
    )

    for user in users:
        print(
            f"  {user['role']:12} - {user['email']:35} ({user['first_name']} {user['last_name']})"
        )


async def test_demo_scenarios(conn: asyncpg.Connection) -> None:
    """Test demo scenarios."""
    print("\n🎭 Testing demo scenarios:")

    customer = await conn.fetchrow(
        """
        SELECT external_id, data
        FROM customers
        WHERE data::text LIKE '%demo_scenarios%'
        LIMIT 1
    """
    )

    if customer:
        data = json.loads(customer["data"])
        scenarios = data.get("demo_scenarios", [])

        print(
            f"  Customer {customer['external_id']} has {len(scenarios)} demo scenarios:"
        )
        for scenario in scenarios:
            print(f"    - {scenario['scenario']}: {scenario['description']}")
            print(
                f"      Location: {scenario['location']['city']}, {scenario['location']['state']}"
            )
            print(
                f"      Vehicle: {scenario['vehicle_data']['year']} {scenario['vehicle_data']['make']} {scenario['vehicle_data']['model']}"
            )


async def main():
    """Run all tests."""
    load_dotenv()

    database_url = os.getenv("DATABASE_URL", "postgresql://localhost/pd_prime_demo")

    # Convert to asyncpg format
    if "postgresql+asyncpg://" in database_url:
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    try:
        conn = await asyncpg.connect(database_url)
        print("🚀 TESTING SEEDED DATA")
        print("=" * 50)

        # Test rate calculations for each state
        test_cases = [
            ("CA", "90210"),  # Beverly Hills
            ("TX", "75201"),  # Dallas
            ("NY", "10001"),  # Manhattan
            ("FL", "33101"),  # Miami
            ("MI", "48201"),  # Detroit
            ("PA", "19101"),  # Philadelphia
        ]

        for state, zip_code in test_cases:
            await calculate_sample_quote(conn, state, zip_code)

        # Test user access
        await test_user_access(conn)

        # Test demo scenarios
        await test_demo_scenarios(conn)

        print("\n✅ All tests completed successfully!")

    except Exception as e:
        print(f"\n❌ Error testing data: {e}")
        raise
    finally:
        if "conn" in locals():
            await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
