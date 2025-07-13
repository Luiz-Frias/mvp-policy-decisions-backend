"""Seed initial rate tables for CA, TX, and NY.

This script populates the database with initial rate tables, discount rules,
surcharge rules, and territory factors for demonstration purposes.

Usage:
    python scripts/seed_rate_tables.py
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

load_dotenv()


async def seed_rate_tables(conn: asyncpg.Connection) -> None:
    """Seed rate tables with initial data for CA, TX, and NY."""

    print("Seeding rate tables...")

    # Base rates by state, product, and coverage
    rate_data = [
        # California Auto Rates
        {
            "state": "CA",
            "product_type": "auto",
            "coverage_type": "liability",
            "base_rate": Decimal("0.002500"),  # $250 per $100k coverage
            "min_premium": Decimal("500.00"),
            "max_premium": Decimal("5000.00"),
            "territory_factors": {
                "90210": 1.8,  # Beverly Hills - high
                "94105": 1.5,  # San Francisco - high
                "92101": 1.3,  # San Diego - medium-high
                "90001": 1.4,  # Los Angeles - high
                "95814": 1.1,  # Sacramento - medium
            },
            "vehicle_factors": {
                "luxury": 1.5,
                "sports": 1.4,
                "suv": 1.2,
                "sedan": 1.0,
                "economy": 0.9,
            },
            "driver_factors": {
                "teen": 2.0,
                "young_adult": 1.5,
                "adult": 1.0,
                "senior": 1.1,
            },
            "credit_factors": {
                "excellent": 0.8,
                "good": 0.9,
                "fair": 1.0,
                "poor": 1.3,
            },
        },
        {
            "state": "CA",
            "product_type": "auto",
            "coverage_type": "collision",
            "base_rate": Decimal("0.003000"),
            "min_premium": Decimal("200.00"),
            "max_premium": Decimal("3000.00"),
            "territory_factors": {
                "90210": 1.6,
                "94105": 1.4,
                "92101": 1.2,
                "90001": 1.3,
                "95814": 1.0,
            },
            "vehicle_factors": {
                "luxury": 2.0,
                "sports": 1.8,
                "suv": 1.3,
                "sedan": 1.0,
                "economy": 0.8,
            },
            "driver_factors": {
                "teen": 1.8,
                "young_adult": 1.4,
                "adult": 1.0,
                "senior": 1.1,
            },
            "credit_factors": {
                "excellent": 0.85,
                "good": 0.92,
                "fair": 1.0,
                "poor": 1.25,
            },
        },
        {
            "state": "CA",
            "product_type": "auto",
            "coverage_type": "comprehensive",
            "base_rate": Decimal("0.001500"),
            "min_premium": Decimal("100.00"),
            "max_premium": Decimal("2000.00"),
            "territory_factors": {
                "90210": 1.4,
                "94105": 1.3,
                "92101": 1.1,
                "90001": 1.2,
                "95814": 1.0,
            },
            "vehicle_factors": {
                "luxury": 2.2,
                "sports": 1.9,
                "suv": 1.2,
                "sedan": 1.0,
                "economy": 0.7,
            },
            "driver_factors": {
                "teen": 1.3,
                "young_adult": 1.2,
                "adult": 1.0,
                "senior": 1.0,
            },
            "credit_factors": {
                "excellent": 0.9,
                "good": 0.95,
                "fair": 1.0,
                "poor": 1.15,
            },
        },
        # Texas Auto Rates (generally lower than CA)
        {
            "state": "TX",
            "product_type": "auto",
            "coverage_type": "liability",
            "base_rate": Decimal("0.002200"),
            "min_premium": Decimal("400.00"),
            "max_premium": Decimal("4000.00"),
            "territory_factors": {
                "75201": 1.4,  # Dallas - high
                "77001": 1.4,  # Houston - high
                "78701": 1.2,  # Austin - medium
                "78201": 1.1,  # San Antonio - medium
                "79901": 0.9,  # El Paso - low
            },
            "vehicle_factors": {
                "luxury": 1.4,
                "sports": 1.3,
                "suv": 1.1,  # Popular in TX
                "sedan": 1.0,
                "economy": 0.9,
            },
            "driver_factors": {
                "teen": 1.9,
                "young_adult": 1.4,
                "adult": 1.0,
                "senior": 1.05,
            },
            "credit_factors": {
                "excellent": 0.82,
                "good": 0.91,
                "fair": 1.0,
                "poor": 1.28,
            },
        },
        # New York Auto Rates (highest)
        {
            "state": "NY",
            "product_type": "auto",
            "coverage_type": "liability",
            "base_rate": Decimal("0.003200"),
            "min_premium": Decimal("800.00"),
            "max_premium": Decimal("8000.00"),
            "territory_factors": {
                "10001": 2.0,  # Manhattan - very high
                "11201": 1.8,  # Brooklyn - high
                "10451": 1.7,  # Bronx - high
                "11101": 1.6,  # Queens - high
                "10301": 1.4,  # Staten Island - medium-high
                "12601": 1.0,  # Poughkeepsie - medium
            },
            "vehicle_factors": {
                "luxury": 1.6,
                "sports": 1.5,
                "suv": 1.2,
                "sedan": 1.0,
                "economy": 0.85,
            },
            "driver_factors": {
                "teen": 2.2,
                "young_adult": 1.6,
                "adult": 1.0,
                "senior": 1.15,
            },
            "credit_factors": {
                "excellent": 0.75,
                "good": 0.88,
                "fair": 1.0,
                "poor": 1.35,
            },
        },
        # Florida Auto Rates (high due to hurricanes and fraud)
        {
            "state": "FL",
            "product_type": "auto",
            "coverage_type": "liability",
            "base_rate": Decimal("0.002800"),
            "min_premium": Decimal("600.00"),
            "max_premium": Decimal("6000.00"),
            "territory_factors": {
                "33101": 1.7,  # Miami - very high
                "33601": 1.5,  # Tampa - high
                "32801": 1.4,  # Orlando - high
                "32201": 1.3,  # Jacksonville - medium-high
                "32301": 1.1,  # Tallahassee - medium
            },
            "vehicle_factors": {
                "luxury": 1.5,
                "sports": 1.4,
                "suv": 1.15,
                "sedan": 1.0,
                "economy": 0.88,
            },
            "driver_factors": {
                "teen": 2.0,
                "young_adult": 1.5,
                "adult": 1.0,
                "senior": 1.2,  # Higher due to retiree population
            },
            "credit_factors": {
                "excellent": 0.8,
                "good": 0.9,
                "fair": 1.0,
                "poor": 1.3,
            },
        },
        {
            "state": "FL",
            "product_type": "auto",
            "coverage_type": "comprehensive",
            "base_rate": Decimal("0.002000"),
            "min_premium": Decimal("150.00"),
            "max_premium": Decimal("3000.00"),
            "territory_factors": {
                "33101": 1.8,  # Miami - hurricane risk
                "33601": 1.6,  # Tampa - hurricane risk
                "32801": 1.3,  # Orlando - inland
                "32201": 1.4,  # Jacksonville - coastal
                "32301": 1.1,  # Tallahassee - inland
            },
            "vehicle_factors": {
                "luxury": 2.0,
                "sports": 1.8,
                "suv": 1.2,
                "sedan": 1.0,
                "economy": 0.75,
            },
            "driver_factors": {
                "teen": 1.4,
                "young_adult": 1.2,
                "adult": 1.0,
                "senior": 1.1,
            },
            "credit_factors": {
                "excellent": 0.85,
                "good": 0.92,
                "fair": 1.0,
                "poor": 1.2,
            },
        },
        # Michigan Auto Rates (high due to no-fault insurance)
        {
            "state": "MI",
            "product_type": "auto",
            "coverage_type": "liability",
            "base_rate": Decimal("0.003500"),
            "min_premium": Decimal("900.00"),
            "max_premium": Decimal("9000.00"),
            "territory_factors": {
                "48201": 2.2,  # Detroit - very high
                "48104": 1.3,  # Ann Arbor - medium
                "49503": 1.2,  # Grand Rapids - medium
                "48910": 1.1,  # Lansing - medium
                "49770": 0.9,  # Petoskey - low
            },
            "vehicle_factors": {
                "luxury": 1.7,
                "sports": 1.6,
                "suv": 1.25,
                "sedan": 1.0,
                "economy": 0.8,
            },
            "driver_factors": {
                "teen": 2.3,
                "young_adult": 1.7,
                "adult": 1.0,
                "senior": 1.1,
            },
            "credit_factors": {
                "excellent": 0.7,
                "good": 0.85,
                "fair": 1.0,
                "poor": 1.4,
            },
        },
        {
            "state": "MI",
            "product_type": "auto",
            "coverage_type": "collision",
            "base_rate": Decimal("0.003800"),
            "min_premium": Decimal("300.00"),
            "max_premium": Decimal("4000.00"),
            "territory_factors": {
                "48201": 2.0,  # Detroit
                "48104": 1.2,  # Ann Arbor
                "49503": 1.15,  # Grand Rapids
                "48910": 1.1,  # Lansing
                "49770": 0.85,  # Petoskey
            },
            "vehicle_factors": {
                "luxury": 2.2,
                "sports": 2.0,
                "suv": 1.4,
                "sedan": 1.0,
                "economy": 0.7,
            },
            "driver_factors": {
                "teen": 2.0,
                "young_adult": 1.5,
                "adult": 1.0,
                "senior": 1.15,
            },
            "credit_factors": {
                "excellent": 0.8,
                "good": 0.9,
                "fair": 1.0,
                "poor": 1.3,
            },
        },
        # Pennsylvania Auto Rates (moderate)
        {
            "state": "PA",
            "product_type": "auto",
            "coverage_type": "liability",
            "base_rate": Decimal("0.002400"),
            "min_premium": Decimal("500.00"),
            "max_premium": Decimal("4500.00"),
            "territory_factors": {
                "19101": 1.6,  # Philadelphia - high
                "15201": 1.4,  # Pittsburgh - medium-high
                "18101": 1.2,  # Allentown - medium
                "17101": 1.1,  # Harrisburg - medium
                "16801": 1.0,  # State College - low
            },
            "vehicle_factors": {
                "luxury": 1.45,
                "sports": 1.35,
                "suv": 1.15,
                "sedan": 1.0,
                "economy": 0.88,
            },
            "driver_factors": {
                "teen": 1.9,
                "young_adult": 1.45,
                "adult": 1.0,
                "senior": 1.08,
            },
            "credit_factors": {
                "excellent": 0.82,
                "good": 0.91,
                "fair": 1.0,
                "poor": 1.25,
            },
        },
        {
            "state": "PA",
            "product_type": "auto",
            "coverage_type": "comprehensive",
            "base_rate": Decimal("0.001300"),
            "min_premium": Decimal("100.00"),
            "max_premium": Decimal("1800.00"),
            "territory_factors": {
                "19101": 1.5,  # Philadelphia
                "15201": 1.3,  # Pittsburgh
                "18101": 1.15,  # Allentown
                "17101": 1.1,  # Harrisburg
                "16801": 0.95,  # State College
            },
            "vehicle_factors": {
                "luxury": 2.1,
                "sports": 1.85,
                "suv": 1.15,
                "sedan": 1.0,
                "economy": 0.72,
            },
            "driver_factors": {
                "teen": 1.25,
                "young_adult": 1.15,
                "adult": 1.0,
                "senior": 1.05,
            },
            "credit_factors": {
                "excellent": 0.88,
                "good": 0.94,
                "fair": 1.0,
                "poor": 1.12,
            },
        },
        # Home Insurance Rates
        {
            "state": "CA",
            "product_type": "home",
            "coverage_type": "dwelling",
            "base_rate": Decimal("0.000800"),  # $80 per $100k coverage
            "min_premium": Decimal("600.00"),
            "max_premium": Decimal("10000.00"),
            "territory_factors": {
                "90210": 2.5,  # Fire risk areas
                "94105": 1.8,
                "92101": 1.2,
                "90001": 1.3,
                "95814": 1.5,  # Wildfire risk
            },
            "vehicle_factors": {},  # Not applicable for home
            "driver_factors": {},  # Not applicable for home
            "credit_factors": {
                "excellent": 0.85,
                "good": 0.92,
                "fair": 1.0,
                "poor": 1.2,
            },
        },
    ]

    # Insert rate tables
    for rate in rate_data:
        await conn.execute(
            """
            INSERT INTO rate_tables (
                state, product_type, coverage_type, base_rate,
                min_premium, max_premium, territory_factors,
                vehicle_factors, driver_factors, credit_factors,
                effective_date, filing_id, approved_by
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            rate["state"],
            rate["product_type"],
            rate["coverage_type"],
            rate["base_rate"],
            rate["min_premium"],
            rate["max_premium"],
            json.dumps(rate["territory_factors"]),
            json.dumps(rate["vehicle_factors"]),
            json.dumps(rate["driver_factors"]),
            json.dumps(rate["credit_factors"]),
            date.today(),
            f"{rate['state']}-{rate['product_type']}-2025-001",
            "System Administrator",
        )

    print(f"✓ Inserted {len(rate_data)} rate tables")


async def seed_discount_rules(conn: asyncpg.Connection) -> None:
    """Seed discount rules."""

    print("Seeding discount rules...")

    discounts = [
        {
            "code": "MULTI_POLICY",
            "name": "Multi-Policy Discount",
            "description": "Discount for customers with multiple policies",
            "product_types": ["auto", "home", "renters"],
            "states": ["CA", "TX", "NY", "FL", "MI", "PA"],
            "discount_type": "percentage",
            "discount_value": Decimal("10.00"),
            "eligibility_rules": {
                "min_policies": 2,
                "policy_types": ["auto", "home"],
            },
            "stackable": True,
            "priority": 100,
        },
        {
            "code": "SAFE_DRIVER",
            "name": "Safe Driver Discount",
            "description": "No accidents or violations in 3 years",
            "product_types": ["auto"],
            "states": ["CA", "TX", "NY", "FL", "MI", "PA"],
            "discount_type": "percentage",
            "discount_value": Decimal("15.00"),
            "eligibility_rules": {
                "years_without_claims": 3,
                "years_without_violations": 3,
            },
            "stackable": True,
            "priority": 90,
        },
        {
            "code": "GOOD_STUDENT",
            "name": "Good Student Discount",
            "description": "Full-time student with B average or better",
            "product_types": ["auto"],
            "states": ["CA", "TX", "NY", "FL", "MI", "PA"],
            "discount_type": "percentage",
            "discount_value": Decimal("8.00"),
            "max_discount_amount": Decimal("200.00"),
            "eligibility_rules": {
                "age_range": [16, 25],
                "min_gpa": 3.0,
                "enrollment": "full_time",
            },
            "stackable": True,
            "priority": 80,
        },
        {
            "code": "MILITARY",
            "name": "Military Discount",
            "description": "Active duty or veteran discount",
            "product_types": ["auto", "home"],
            "states": ["CA", "TX", "NY", "FL", "MI", "PA"],
            "discount_type": "percentage",
            "discount_value": Decimal("5.00"),
            "eligibility_rules": {
                "military_status": ["active", "veteran", "reserve"],
            },
            "stackable": True,
            "priority": 70,
        },
        {
            "code": "ANTI_THEFT",
            "name": "Anti-Theft Device Discount",
            "description": "Vehicle equipped with anti-theft device",
            "product_types": ["auto"],
            "states": ["CA", "TX", "NY", "FL", "MI", "PA"],
            "discount_type": "percentage",
            "discount_value": Decimal("5.00"),
            "eligibility_rules": {
                "device_types": ["alarm", "tracking", "immobilizer"],
            },
            "stackable": True,
            "priority": 60,
        },
        {
            "code": "HOME_SECURITY",
            "name": "Home Security Discount",
            "description": "Home with security system",
            "product_types": ["home"],
            "states": ["CA", "TX", "NY", "FL", "MI", "PA"],
            "discount_type": "percentage",
            "discount_value": Decimal("12.00"),
            "eligibility_rules": {
                "security_features": ["alarm", "monitoring", "cameras"],
            },
            "stackable": True,
            "priority": 65,
        },
        {
            "code": "EARLY_QUOTE",
            "name": "Early Quote Discount",
            "description": "Quote submitted 30+ days before effective date",
            "product_types": ["auto", "home"],
            "states": ["CA", "TX", "NY", "FL", "MI", "PA"],
            "discount_type": "fixed",
            "discount_value": Decimal("50.00"),
            "eligibility_rules": {
                "days_before_effective": 30,
            },
            "stackable": False,
            "priority": 50,
        },
    ]

    for discount in discounts:
        await conn.execute(
            """
            INSERT INTO discount_rules (
                code, name, description, product_types, states,
                discount_type, discount_value, max_discount_amount,
                eligibility_rules, stackable, priority,
                effective_date
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            """,
            discount["code"],
            discount["name"],
            discount["description"],
            json.dumps(discount["product_types"]),
            json.dumps(discount["states"]),
            discount["discount_type"],
            discount["discount_value"],
            discount.get("max_discount_amount"),
            json.dumps(discount["eligibility_rules"]),
            discount["stackable"],
            discount["priority"],
            date.today(),
        )

    print(f"✓ Inserted {len(discounts)} discount rules")


async def seed_surcharge_rules(conn: asyncpg.Connection) -> None:
    """Seed surcharge rules."""

    print("Seeding surcharge rules...")

    surcharges = [
        {
            "code": "YOUNG_DRIVER",
            "name": "Young Driver Surcharge",
            "description": "Surcharge for drivers under 25",
            "product_types": ["auto"],
            "states": ["CA", "TX", "NY", "FL", "MI", "PA"],
            "surcharge_type": "percentage",
            "surcharge_value": Decimal("25.00"),
            "trigger_conditions": {
                "driver_age": {"min": 16, "max": 24},
            },
            "priority": 100,
        },
        {
            "code": "SR22",
            "name": "SR-22 Filing Surcharge",
            "description": "Required SR-22 insurance filing",
            "product_types": ["auto"],
            "states": ["CA", "TX", "NY", "FL", "MI", "PA"],
            "surcharge_type": "fixed",
            "surcharge_value": Decimal("125.00"),
            "trigger_conditions": {
                "sr22_required": True,
            },
            "priority": 90,
        },
        {
            "code": "POOR_CREDIT",
            "name": "Credit-Based Insurance Score Surcharge",
            "description": "Lower credit score surcharge",
            "product_types": ["auto", "home"],
            "states": ["TX", "NY"],  # CA has restrictions
            "surcharge_type": "percentage",
            "surcharge_value": Decimal("15.00"),
            "max_surcharge_amount": Decimal("500.00"),
            "trigger_conditions": {
                "credit_score": {"max": 600},
            },
            "priority": 80,
        },
        {
            "code": "LAPSE_COVERAGE",
            "name": "Coverage Lapse Surcharge",
            "description": "Previous insurance lapse",
            "product_types": ["auto"],
            "states": ["CA", "TX", "NY", "FL", "MI", "PA"],
            "surcharge_type": "percentage",
            "surcharge_value": Decimal("20.00"),
            "trigger_conditions": {
                "coverage_lapse_days": {"min": 30},
            },
            "priority": 70,
        },
        {
            "code": "HIGH_RISK_AREA",
            "name": "High Risk Area Surcharge",
            "description": "Property in high-risk area",
            "product_types": ["home"],
            "states": ["CA", "TX", "NY", "FL", "MI", "PA"],
            "surcharge_type": "percentage",
            "surcharge_value": Decimal("30.00"),
            "trigger_conditions": {
                "risk_zones": ["flood_zone", "wildfire_zone", "hurricane_zone"],
            },
            "priority": 85,
        },
    ]

    for surcharge in surcharges:
        await conn.execute(
            """
            INSERT INTO surcharge_rules (
                code, name, description, product_types, states,
                surcharge_type, surcharge_value, max_surcharge_amount,
                trigger_conditions, priority, effective_date
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            surcharge["code"],
            surcharge["name"],
            surcharge["description"],
            json.dumps(surcharge["product_types"]),
            json.dumps(surcharge["states"]),
            surcharge["surcharge_type"],
            surcharge["surcharge_value"],
            surcharge.get("max_surcharge_amount"),
            json.dumps(surcharge["trigger_conditions"]),
            surcharge["priority"],
            date.today(),
        )

    print(f"✓ Inserted {len(surcharges)} surcharge rules")


async def seed_territory_factors(conn: asyncpg.Connection) -> None:
    """Seed territory factors for specific ZIP codes."""

    print("Seeding territory factors...")

    # Sample territory factors for major cities
    territories = [
        # California
        {
            "state": "CA",
            "zip_code": "90210",
            "product_type": "auto",
            "base_factor": 1.8,
            "loss_ratio_factor": 1.2,
            "catastrophe_factor": 1.1,
        },
        {
            "state": "CA",
            "zip_code": "94105",
            "product_type": "auto",
            "base_factor": 1.5,
            "loss_ratio_factor": 1.3,
            "catastrophe_factor": 1.0,
        },
        {
            "state": "CA",
            "zip_code": "92101",
            "product_type": "auto",
            "base_factor": 1.3,
            "loss_ratio_factor": 1.1,
            "catastrophe_factor": 1.0,
        },
        {
            "state": "CA",
            "zip_code": "90001",
            "product_type": "auto",
            "base_factor": 1.4,
            "loss_ratio_factor": 1.4,
            "catastrophe_factor": 1.0,
        },
        {
            "state": "CA",
            "zip_code": "95814",
            "product_type": "auto",
            "base_factor": 1.1,
            "loss_ratio_factor": 1.0,
            "catastrophe_factor": 1.2,
        },
        # Texas
        {
            "state": "TX",
            "zip_code": "75201",
            "product_type": "auto",
            "base_factor": 1.4,
            "loss_ratio_factor": 1.2,
            "catastrophe_factor": 1.1,
        },
        {
            "state": "TX",
            "zip_code": "77001",
            "product_type": "auto",
            "base_factor": 1.4,
            "loss_ratio_factor": 1.3,
            "catastrophe_factor": 1.3,
        },
        {
            "state": "TX",
            "zip_code": "78701",
            "product_type": "auto",
            "base_factor": 1.2,
            "loss_ratio_factor": 1.0,
            "catastrophe_factor": 1.1,
        },
        {
            "state": "TX",
            "zip_code": "78201",
            "product_type": "auto",
            "base_factor": 1.1,
            "loss_ratio_factor": 1.0,
            "catastrophe_factor": 1.0,
        },
        # New York
        {
            "state": "NY",
            "zip_code": "10001",
            "product_type": "auto",
            "base_factor": 2.0,
            "loss_ratio_factor": 1.5,
            "catastrophe_factor": 1.0,
        },
        {
            "state": "NY",
            "zip_code": "11201",
            "product_type": "auto",
            "base_factor": 1.8,
            "loss_ratio_factor": 1.4,
            "catastrophe_factor": 1.0,
        },
        {
            "state": "NY",
            "zip_code": "10451",
            "product_type": "auto",
            "base_factor": 1.7,
            "loss_ratio_factor": 1.5,
            "catastrophe_factor": 1.0,
        },
        # Home insurance territories (high catastrophe areas)
        {
            "state": "CA",
            "zip_code": "90210",
            "product_type": "home",
            "base_factor": 1.5,
            "loss_ratio_factor": 1.2,
            "catastrophe_factor": 2.5,
        },  # Wildfire
        {
            "state": "TX",
            "zip_code": "77001",
            "product_type": "home",
            "base_factor": 1.2,
            "loss_ratio_factor": 1.1,
            "catastrophe_factor": 2.0,
        },  # Hurricane
        {
            "state": "NY",
            "zip_code": "11234",
            "product_type": "home",
            "base_factor": 1.3,
            "loss_ratio_factor": 1.1,
            "catastrophe_factor": 1.8,
        },  # Coastal flooding
        # Florida territories
        {
            "state": "FL",
            "zip_code": "33101",
            "product_type": "auto",
            "base_factor": 1.7,
            "loss_ratio_factor": 1.5,
            "catastrophe_factor": 1.2,
        },
        {
            "state": "FL",
            "zip_code": "33601",
            "product_type": "auto",
            "base_factor": 1.5,
            "loss_ratio_factor": 1.4,
            "catastrophe_factor": 1.3,
        },
        {
            "state": "FL",
            "zip_code": "32801",
            "product_type": "auto",
            "base_factor": 1.4,
            "loss_ratio_factor": 1.2,
            "catastrophe_factor": 1.1,
        },
        {
            "state": "FL",
            "zip_code": "33101",
            "product_type": "home",
            "base_factor": 1.6,
            "loss_ratio_factor": 1.4,
            "catastrophe_factor": 3.0,
        },  # Hurricane zone
        # Michigan territories
        {
            "state": "MI",
            "zip_code": "48201",
            "product_type": "auto",
            "base_factor": 2.2,
            "loss_ratio_factor": 1.8,
            "catastrophe_factor": 1.0,
        },
        {
            "state": "MI",
            "zip_code": "48104",
            "product_type": "auto",
            "base_factor": 1.3,
            "loss_ratio_factor": 1.1,
            "catastrophe_factor": 1.0,
        },
        {
            "state": "MI",
            "zip_code": "49503",
            "product_type": "auto",
            "base_factor": 1.2,
            "loss_ratio_factor": 1.1,
            "catastrophe_factor": 1.0,
        },
        # Pennsylvania territories
        {
            "state": "PA",
            "zip_code": "19101",
            "product_type": "auto",
            "base_factor": 1.6,
            "loss_ratio_factor": 1.4,
            "catastrophe_factor": 1.0,
        },
        {
            "state": "PA",
            "zip_code": "15201",
            "product_type": "auto",
            "base_factor": 1.4,
            "loss_ratio_factor": 1.2,
            "catastrophe_factor": 1.0,
        },
        {
            "state": "PA",
            "zip_code": "18101",
            "product_type": "auto",
            "base_factor": 1.2,
            "loss_ratio_factor": 1.0,
            "catastrophe_factor": 1.0,
        },
    ]

    for territory in territories:
        await conn.execute(
            """
            INSERT INTO territory_factors (
                state, zip_code, product_type, base_factor,
                loss_ratio_factor, catastrophe_factor, effective_date
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            territory["state"],
            territory["zip_code"],
            territory["product_type"],
            Decimal(str(territory["base_factor"])),
            Decimal(str(territory["loss_ratio_factor"])),
            Decimal(str(territory["catastrophe_factor"])),
            date.today(),
        )

    print(f"✓ Inserted {len(territories)} territory factors")


async def main():
    """Main function to seed all rate-related tables."""

    # Database connection
    database_url = os.getenv("DATABASE_URL", "postgresql://localhost/policy_core")

    try:
        conn = await asyncpg.connect(database_url)
        print("Connected to database")

        # Check if data already exists
        existing = await conn.fetchval("SELECT COUNT(*) FROM rate_tables")
        if existing > 0:
            print(f"⚠️  Rate tables already contain {existing} records. Skipping seed.")
            return

        # Seed all tables
        await seed_rate_tables(conn)
        await seed_discount_rules(conn)
        await seed_surcharge_rules(conn)
        await seed_territory_factors(conn)

        print("\n✅ Rate table seeding completed successfully!")

    except Exception as e:
        print(f"\n❌ Error seeding rate tables: {e}")
        raise
    finally:
        if "conn" in locals():
            await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
