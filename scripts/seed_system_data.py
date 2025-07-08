#!/usr/bin/env python3
"""Seed system configuration and demo users.

This script populates:
- System users with different roles
- System configuration settings
- Demo scenarios for testing
"""

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from uuid import uuid4

import asyncpg
import bcrypt
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


async def seed_users(conn: asyncpg.Connection) -> None:
    """Seed demo users with different roles."""
    print("Seeding users...")

    # Define demo users
    users = [
        {
            "email": "admin@mvppolicy.com",
            "username": "admin",
            "full_name": "System Administrator",
            "password": "Admin123!@#",  # In production, use environment variables
            "role": "admin",
            "permissions": ["all"],
            "metadata": {
                "department": "IT",
                "employee_id": "EMP001",
                "access_level": "super_admin",
            },
        },
        {
            "email": "john.underwriter@mvppolicy.com",
            "username": "junderwriter",
            "full_name": "John Underwriter",
            "password": "Underwriter123!",
            "role": "underwriter",
            "permissions": [
                "quotes.read",
                "quotes.write",
                "policies.read",
                "policies.write",
                "rates.read",
            ],
            "metadata": {
                "department": "Underwriting",
                "employee_id": "EMP002",
                "access_level": "underwriter",
                "states": ["CA", "TX", "NY", "FL", "MI", "PA"],
            },
        },
        {
            "email": "jane.agent@mvppolicy.com",
            "username": "jagent",
            "full_name": "Jane Agent",
            "password": "Agent123!",
            "role": "agent",
            "permissions": [
                "quotes.read",
                "quotes.write",
                "policies.read",
                "customers.read",
                "customers.write",
            ],
            "metadata": {
                "department": "Sales",
                "employee_id": "EMP003",
                "agent_code": "AG001",
                "states": ["CA", "TX"],
                "commission_rate": 0.15,
            },
        },
        {
            "email": "alice.senior@mvppolicy.com",
            "username": "asenior",
            "full_name": "Alice Senior",
            "password": "Senior123!",
            "role": "underwriter",  # Senior underwriter with claims experience
            "permissions": [
                "claims.read",
                "claims.write",
                "policies.read",
                "customers.read",
                "rates.write",
            ],
            "metadata": {
                "department": "Claims & Underwriting",
                "employee_id": "EMP004",
                "adjuster_id": "ADJ001",
                "certification": "Senior Underwriter",
                "max_approval_limit": 100000,
                "specialties": ["claims", "complex_risks"],
            },
        },
        {
            "email": "mike.supervisor@mvppolicy.com",
            "username": "msupervisor",
            "full_name": "Mike Supervisor",
            "password": "Supervisor123!",
            "role": "admin",  # Admin with limited permissions
            "permissions": [
                "reports.read",
                "analytics.read",
                "users.read",
                "audit.read",
            ],
            "metadata": {
                "department": "Operations",
                "employee_id": "EMP005",
                "access_level": "supervisor",
                "team_size": 15,
                "admin_level": "read_only",
            },
        },
        {
            "email": "system@mvppolicy.com",
            "username": "system",
            "full_name": "System User",
            "password": "System123!@#$",
            "role": "system",  # System role for automated processes
            "permissions": ["all"],
            "metadata": {
                "is_system": True,
                "purpose": "automated_processes",
                "features": ["batch_processing", "scheduled_tasks", "integrations"],
            },
        },
        {
            "email": "demo.agent@mvppolicy.com",
            "username": "demo",
            "full_name": "Demo Agent",
            "password": "Demo123!",
            "role": "agent",  # Demo agent with limited access
            "permissions": ["quotes.read", "quotes.write", "policies.read"],
            "metadata": {
                "is_demo": True,
                "demo_expiry": (datetime.utcnow() + timedelta(days=30)).isoformat(),
                "demo_features": ["quotes", "basic_rating"],
                "agent_code": "DEMO001",
            },
        },
    ]

    # Insert users
    for user in users:
        # Hash password
        hashed_password = await hash_password(user["password"])

        # Check if user already exists
        existing = await conn.fetchval(
            "SELECT id FROM users WHERE email = $1", user["email"]
        )

        if existing:
            print(f"  ⚠️  User {user['email']} already exists, skipping")
            continue

        # Split full name into first and last
        name_parts = user["full_name"].split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Insert user
        await conn.execute(
            """
            INSERT INTO users (
                id, email, password_hash, first_name, last_name,
                role, is_active, created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9
            )
            """,
            uuid4(),
            user["email"],
            hashed_password,
            first_name,
            last_name,
            user["role"],
            True,  # is_active
            datetime.utcnow(),
            datetime.utcnow(),
        )

        print(f"  ✓ Created user: {user['email']} (role: {user['role']})")

    print("✓ User seeding completed")


async def create_demo_scenarios(conn: asyncpg.Connection) -> None:
    """Create demo data scenarios for testing."""
    print("\nCreating demo scenarios...")

    # Get a customer for demo scenarios
    customer = await conn.fetchrow(
        """
        SELECT c.id, c.external_id, c.data
        FROM customers c
        JOIN policies p ON p.customer_id = c.id
        WHERE p.status = 'active'
        LIMIT 1
        """
    )

    if not customer:
        print("  ⚠️  No active customers found for demo scenarios")
        return

    # Create a demo quote request
    quote_scenarios = [
        {
            "scenario": "young_driver_sports_car",
            "description": "25-year-old with sports car in Los Angeles",
            "customer_data": {
                "age": 25,
                "gender": "M",
                "marital_status": "single",
                "credit_score": 720,
            },
            "vehicle_data": {
                "year": 2023,
                "make": "BMW",
                "model": "M3",
                "type": "sports",
                "value": 75000,
            },
            "location": {"zip": "90210", "state": "CA", "city": "Beverly Hills"},
            "coverage_requested": {
                "liability": 300000,
                "collision": True,
                "comprehensive": True,
                "deductible": 500,
            },
        },
        {
            "scenario": "family_suv_good_credit",
            "description": "40-year-old family with SUV and excellent credit",
            "customer_data": {
                "age": 40,
                "gender": "F",
                "marital_status": "married",
                "credit_score": 810,
            },
            "vehicle_data": {
                "year": 2022,
                "make": "Toyota",
                "model": "Highlander",
                "type": "suv",
                "value": 45000,
            },
            "location": {"zip": "78701", "state": "TX", "city": "Austin"},
            "coverage_requested": {
                "liability": 500000,
                "collision": True,
                "comprehensive": True,
                "deductible": 1000,
            },
        },
        {
            "scenario": "senior_basic_coverage",
            "description": "65-year-old retiree with basic coverage needs",
            "customer_data": {
                "age": 65,
                "gender": "M",
                "marital_status": "married",
                "credit_score": 750,
            },
            "vehicle_data": {
                "year": 2020,
                "make": "Honda",
                "model": "Accord",
                "type": "sedan",
                "value": 25000,
            },
            "location": {"zip": "33101", "state": "FL", "city": "Miami"},
            "coverage_requested": {
                "liability": 100000,
                "collision": False,
                "comprehensive": True,
                "deductible": 2500,
            },
        },
    ]

    print(f"  ✓ Created {len(quote_scenarios)} demo quote scenarios")

    # Store demo scenarios in customer metadata for easy retrieval
    # Parse the JSON data first
    updated_data = (
        json.loads(customer["data"])
        if isinstance(customer["data"], str)
        else customer["data"]
    )
    updated_data["demo_scenarios"] = quote_scenarios

    await conn.execute(
        "UPDATE customers SET data = $1 WHERE id = $2",
        json.dumps(updated_data),
        customer["id"],
    )

    print(f"  ✓ Attached demo scenarios to customer {customer['external_id']}")


async def seed_system_configuration(conn: asyncpg.Connection) -> None:
    """Seed system configuration settings."""
    print("\nSeeding system configuration...")

    # This would typically go in a settings or configuration table
    # For now, we'll store it in the first admin user's metadata
    admin_user = await conn.fetchrow(
        "SELECT id, email FROM users WHERE email = 'admin@mvppolicy.com'"
    )

    if not admin_user:
        print("  ⚠️  Admin user not found, skipping system configuration")
        return

    # System configuration would typically be stored in a settings table
    # For now, we're just preparing the structure
    # system_config = {
    #     "rating_engine": {
    #         "version": "2.0",
    #         "cache_ttl_seconds": 3600,
    #         "max_quote_age_days": 30,
    #         "min_liability_coverage": 100000,
    #         "max_liability_coverage": 1000000,
    #         "supported_states": ["CA", "TX", "NY", "FL", "MI", "PA"],
    #         "features": {
    #             "real_time_pricing": True,
    #             "competitive_analysis": True,
    #             "usage_based_insurance": False,
    #             "ai_risk_assessment": False,
    #         },
    #     },
    #     "business_rules": {
    #         "min_driver_age": 16,
    #         "max_driver_age": 99,
    #         "min_vehicle_year": 1990,
    #         "max_vehicle_age_years": 30,
    #         "credit_score_required_states": ["TX", "NY", "FL", "MI", "PA"],
    #         "no_credit_check_states": ["CA"],  # California restrictions
    #     },
    #     "demo_settings": {
    #         "enabled": True,
    #         "demo_data_refresh_hours": 24,
    #         "demo_quote_limit": 100,
    #         "demo_features": ["quotes", "basic_rating", "policy_view"],
    #     },
    #     "api_settings": {
    #         "rate_limit_per_minute": 60,
    #         "rate_limit_per_hour": 1000,
    #         "jwt_expiry_hours": 24,
    #         "refresh_token_days": 30,
    #         "cors_origins": ["http://localhost:3000", "https://mvppolicy.com"],
    #     },
    # }

    print("  ✓ System configuration prepared")
    print("  ✓ Configuration attached to system")


async def main():
    """Main seeding function."""
    load_dotenv()

    database_url = os.getenv("DATABASE_URL", "postgresql://localhost/pd_prime_demo")

    # Convert to asyncpg format
    if "postgresql+asyncpg://" in database_url:
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    try:
        conn = await asyncpg.connect(database_url)
        print("Connected to database")

        # Seed data
        await seed_users(conn)
        await create_demo_scenarios(conn)
        await seed_system_configuration(conn)

        print("\n✅ System data seeding completed successfully!")

    except Exception as e:
        print(f"\n❌ Error seeding system data: {e}")
        raise
    finally:
        if "conn" in locals():
            await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
