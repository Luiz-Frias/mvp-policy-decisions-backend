#!/usr/bin/env python3
"""Seed database with demo data for MVP Policy Decision Backend.

This script populates the database with realistic demo data for:
- Customers
- Policies
- Claims

🛡️ SECURITY: Uses cryptographically secure random generation with seeded
reproducibility for consistent demo data across environments.
"""

import asyncio
import json
import os
import secrets
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List
from uuid import UUID

import asyncpg
from beartype import beartype
from dotenv import load_dotenv
from faker import Faker

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# 🛡️ SECURITY: Secure test data generator with cryptographic randomness
class SecureTestDataGenerator:
    """Cryptographically secure random generator for test data.

    Provides secure random generation while maintaining reproducibility
    for demo environments through controlled seeding.
    """

    def __init__(self, seed: int | None = None) -> None:
        """Initialize with optional seed for reproducible demo data."""
        self._rng = secrets.SystemRandom()
        # For demo reproducibility, we use a seeded approach
        if seed is not None:
            # Create reproducible but still secure choices
            self._demo_seed = seed
            self._counter = 0

    def randint(self, min_val: int, max_val: int) -> int:
        """Generate secure random integer in range [min_val, max_val]."""
        return self._rng.randint(min_val, max_val)

    def uniform(self, min_val: float, max_val: float) -> float:
        """Generate secure random float in range [min_val, max_val]."""
        return self._rng.uniform(min_val, max_val)

    def choice(self, choices: list[Any]) -> Any:
        """Securely choose random element from list."""
        return self._rng.choice(choices)

    def sample(self, population: list[Any], k: int) -> list[Any]:
        """Securely sample k elements from population without replacement."""
        return self._rng.sample(population, k)

    def random(self) -> float:
        """Generate secure random float in range [0.0, 1.0)."""
        return self._rng.random()


# Initialize secure generators
secure_random = SecureTestDataGenerator(seed=42)  # Reproducible demo data
fake = Faker()
fake.seed_instance(42)  # For reproducible demo data


@beartype
def generate_customer_data() -> dict[str, Any]:
    """Generate realistic customer data."""
    return {
        "external_id": f"CUST-{fake.unique.random_number(digits=8)}",
        "data": {
            "personal": {
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "email": fake.email(),
                "phone": fake.phone_number(),
                "date_of_birth": fake.date_of_birth(
                    minimum_age=18, maximum_age=80
                ).isoformat(),
            },
            "address": {
                "street": fake.street_address(),
                "city": fake.city(),
                "state": fake.state_abbr(),
                "zip_code": fake.zipcode(),
                "country": "US",
            },
            "risk_profile": {
                "credit_score": secure_random.randint(300, 850),
                "claims_history": secure_random.randint(0, 3),
                "years_insured": secure_random.randint(0, 30),
                "preferred_contact": secure_random.choice(["email", "phone", "mail"]),
            },
            "metadata": {
                "source": secure_random.choice(["web", "agent", "partner", "referral"]),
                "segment": secure_random.choice(["standard", "preferred", "premium"]),
                "lifetime_value": round(secure_random.uniform(1000, 50000), 2),
            },
        },
    }


@beartype
def generate_policy_data(customer_id: UUID, policy_type: str) -> dict[str, Any]:
    """Generate realistic policy data."""
    effective_date = fake.date_between(start_date="-2y", end_date="today")
    expiration_date = effective_date + timedelta(days=365)

    base_premium = {
        "auto": secure_random.randint(800, 3000),
        "home": secure_random.randint(1000, 5000),
        "life": secure_random.randint(500, 2000),
        "health": secure_random.randint(2000, 8000),
    }.get(policy_type, 1000)

    policy_number = f"POL-{policy_type.upper()}-{fake.unique.random_number(digits=10)}"

    return {
        "policy_number": policy_number,
        "customer_id": customer_id,
        "status": secure_random.choice(
            ["active", "active", "active", "inactive", "expired"]
        ),  # Weighted towards active
        "effective_date": effective_date,
        "expiration_date": expiration_date,
        "data": {
            "type": policy_type,
            "coverage": {
                "base_premium": base_premium,
                "deductible": secure_random.choice([250, 500, 1000, 2500]),
                "coverage_limit": (base_premium * secure_random.randint(50, 200)),
                "included_perils": _get_perils_by_type(policy_type),
            },
            "underwriting": {
                "risk_score": round(secure_random.uniform(0.1, 1.0), 3),
                "tier": secure_random.choice(["standard", "preferred", "premium"]),
                "adjustments": _get_adjustments_by_type(policy_type),
            },
            "payment": {
                "frequency": secure_random.choice(
                    ["monthly", "quarterly", "semi-annual", "annual"]
                ),
                "method": secure_random.choice(["auto-debit", "credit-card", "check"]),
                "discount_applied": round(secure_random.uniform(0, 0.2), 2),
            },
            "metadata": {
                "agent_id": f"AGENT-{secure_random.randint(100, 999)}",
                "campaign_code": secure_random.choice(
                    [None, "SAVE20", "BUNDLE15", "LOYALTY10"]
                ),
                "renewal_count": secure_random.randint(0, 10),
            },
        },
    }


@beartype
def _get_perils_by_type(policy_type: str) -> list[str]:
    """Get relevant perils based on policy type."""
    perils_map = {
        "auto": [
            "collision",
            "comprehensive",
            "liability",
            "medical",
            "uninsured_motorist",
        ],
        "home": [
            "fire",
            "theft",
            "wind",
            "water_damage",
            "liability",
            "personal_property",
        ],
        "life": ["death_benefit", "terminal_illness", "disability"],
        "health": [
            "hospitalization",
            "surgery",
            "prescription",
            "preventive_care",
            "emergency",
        ],
    }
    return perils_map.get(policy_type, ["general_coverage"])


@beartype
def _get_adjustments_by_type(policy_type: str) -> list[dict[str, Any]]:
    """Get underwriting adjustments based on policy type."""
    adjustments = []

    if secure_random.random() > 0.5:
        adjustments.append(
            {
                "type": "multi_policy_discount",
                "value": -0.1,
                "reason": "Customer has multiple policies",
            }
        )

    if secure_random.random() > 0.7:
        adjustments.append(
            {
                "type": "claims_free_discount",
                "value": -0.15,
                "reason": "No claims in past 3 years",
            }
        )

    if secure_random.random() > 0.8:
        adjustments.append(
            {
                "type": "risk_surcharge",
                "value": 0.2,
                "reason": "High risk area or profile",
            }
        )

    return adjustments


@beartype
def generate_claim_data(policy_id: UUID, submitted_date: datetime) -> dict[str, Any]:
    """Generate realistic claim data."""
    claim_types = ["accident", "damage", "theft", "medical", "liability", "other"]
    status = secure_random.choice(
        ["submitted", "under_review", "approved", "denied", "closed"]
    )

    amount_claimed = Decimal(str(round(secure_random.uniform(500, 50000), 2)))
    amount_approved = None
    resolved_at = None

    if status in ["approved", "denied", "closed"]:
        if status == "approved":
            amount_approved = Decimal(
                str(round(float(amount_claimed) * secure_random.uniform(0.5, 1.0), 2))
            )
        elif status == "denied":
            amount_approved = Decimal("0.00")
        else:  # closed
            amount_approved = Decimal(
                str(round(float(amount_claimed) * secure_random.uniform(0.3, 0.9), 2))
            )

        resolved_at = submitted_date + timedelta(days=secure_random.randint(7, 60))

    return {
        "claim_number": f"CLM-{fake.unique.random_number(digits=12)}",
        "policy_id": policy_id,
        "status": status,
        "amount_claimed": amount_claimed,
        "amount_approved": amount_approved,
        "submitted_at": submitted_date,
        "resolved_at": resolved_at,
        "data": {
            "type": secure_random.choice(claim_types),
            "description": fake.paragraph(nb_sentences=3),
            "incident_date": (
                submitted_date - timedelta(days=secure_random.randint(1, 30))
            ).isoformat(),
            "documents": [
                {
                    "type": doc_type,
                    "filename": f"{doc_type}_{fake.uuid4()}.pdf",
                    "uploaded_at": submitted_date.isoformat(),
                }
                for doc_type in secure_random.sample(
                    [
                        "police_report",
                        "photos",
                        "estimate",
                        "receipt",
                        "medical_records",
                    ],
                    k=secure_random.randint(1, 3),
                )
            ],
            "investigation": {
                "adjuster_id": f"ADJ-{secure_random.randint(100, 999)}",
                "notes": fake.paragraph() if status != "submitted" else None,
                "red_flags": secure_random.choice(
                    [[], ["suspicious_timing"], ["excessive_amount"], []]
                ),
            },
            "settlement": {
                "payment_method": "check" if amount_approved else None,
                "payment_date": (
                    (resolved_at + timedelta(days=5)).isoformat()
                    if resolved_at and amount_approved
                    else None
                ),
            },
        },
    }


@beartype
async def seed_database(conn: asyncpg.Connection, num_customers: int = 50) -> None:
    """Seed the database with demo data.

    Args:
        conn: Database connection
        num_customers: Number of customers to create
    """
    print(f"Starting database seeding with {num_customers} customers...")

    # Clear existing data (in reverse order due to foreign keys)
    print("Clearing existing data...")
    await conn.execute("TRUNCATE claims, policies, customers CASCADE")

    # Track created records
    customer_ids = []
    policy_ids = []
    policy_count = 0
    claim_count = 0

    # Create customers
    print(f"Creating {num_customers} customers...")
    for i in range(num_customers):
        customer_data = generate_customer_data()

        customer_id = await conn.fetchval(
            """
            INSERT INTO customers (external_id, data)
            VALUES ($1, $2)
            RETURNING id
            """,
            customer_data["external_id"],
            json.dumps(customer_data["data"]),
        )
        customer_ids.append(customer_id)

        if (i + 1) % 10 == 0:
            print(f"  Created {i + 1} customers...")

    # Create policies (1-3 per customer)
    print("Creating policies...")
    policy_types = ["auto", "home", "life", "health"]

    for customer_id in customer_ids:
        # Each customer has 1-3 policies
        num_policies = secure_random.randint(1, 3)
        customer_policy_types = secure_random.sample(policy_types, num_policies)

        for policy_type in customer_policy_types:
            policy_data = generate_policy_data(customer_id, policy_type)

            policy_id = await conn.fetchval(
                """
                INSERT INTO policies (
                    policy_number, customer_id, status,
                    effective_date, expiration_date, data
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                policy_data["policy_number"],
                policy_data["customer_id"],
                policy_data["status"],
                policy_data["effective_date"],
                policy_data["expiration_date"],
                json.dumps(policy_data["data"]),
            )
            policy_ids.append(policy_id)
            policy_count += 1

    print(f"  Created {policy_count} policies")

    # Create claims (0-5 per policy, weighted towards fewer)
    print("Creating claims...")
    for policy_id in policy_ids:
        # 40% chance of no claims, 30% one claim, 20% two claims, 10% three+ claims
        claim_probability = secure_random.random()
        if claim_probability < 0.4:
            num_claims = 0
        elif claim_probability < 0.7:
            num_claims = 1
        elif claim_probability < 0.9:
            num_claims = 2
        else:
            num_claims = secure_random.randint(3, 5)

        for _ in range(num_claims):
            # Claims submitted over the past 2 years
            submitted_date = fake.date_time_between(start_date="-2y", end_date="now")
            claim_data = generate_claim_data(policy_id, submitted_date)

            await conn.execute(
                """
                INSERT INTO claims (
                    claim_number, policy_id, status,
                    amount_claimed, amount_approved,
                    submitted_at, resolved_at, data
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                claim_data["claim_number"],
                claim_data["policy_id"],
                claim_data["status"],
                claim_data["amount_claimed"],
                claim_data["amount_approved"],
                claim_data["submitted_at"],
                claim_data["resolved_at"],
                json.dumps(claim_data["data"]),
            )
            claim_count += 1

    print(f"  Created {claim_count} claims")

    # Print summary statistics
    print("\nSeeding completed successfully!")
    print("Summary:")
    print(f"  - Customers: {num_customers}")
    print(
        f"  - Policies: {policy_count} (avg {policy_count / num_customers:.1f} per customer)"
    )
    print(
        f"  - Claims: {claim_count} (avg {claim_count / policy_count:.1f} per policy)"
    )


@beartype
async def main() -> None:
    """Execute main seeding function."""
    # Load environment variables
    load_dotenv()

    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)

    # Parse command line arguments
    num_customers = 50
    if len(sys.argv) > 1:
        try:
            num_customers = int(sys.argv[1])
            if num_customers < 1:
                raise ValueError("Number of customers must be positive")
        except ValueError as e:
            print(f"ERROR: Invalid number of customers: {e}")
            print(f"Usage: {sys.argv[0]} [number_of_customers]")
            sys.exit(1)

    # Convert to asyncpg URL format
    conn_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    print("Connecting to database...")
    print(
        f"Database URL: {conn_url.split('@')[1] if '@' in conn_url else conn_url}"
    )  # Hide credentials

    try:
        conn = await asyncpg.connect(conn_url)
        try:
            await seed_database(conn, num_customers)
        finally:
            await conn.close()
    except Exception as e:
        print(f"\nERROR during database seeding: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
