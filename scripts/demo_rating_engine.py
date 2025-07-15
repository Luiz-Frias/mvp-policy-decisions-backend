#!/usr/bin/env python3
"""Demo script showcasing comprehensive rating engine with sub-50ms performance.

This script demonstrates:
1. Complete premium calculation with all factors
2. Discount stacking logic
3. Surcharge calculations
4. Performance monitoring
5. Business rule validation
"""

import asyncio
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from policy_core.models.quote import (
    CoverageSelection,
    CoverageType,
    DriverInfo,
    VehicleInfo,
)
from policy_core.services.rating import RatingEngine


class MockCache:
    """Mock cache for demo purposes."""

    def __init__(self):
        self._cache = {}

    async def get(self, key: str):
        return self._cache.get(key)

    async def set(self, key: str, value, ttl: int):
        self._cache[key] = value

    async def delete(self, key: str):
        self._cache.pop(key, None)

    async def delete_pattern(self, pattern: str):
        keys_to_delete = [k for k in self._cache if pattern.replace("*", "") in k]
        for key in keys_to_delete:
            del self._cache[key]


class MockDatabase:
    """Mock database for demo purposes."""

    async def fetch(self, query: str, *args):
        return []

    async def fetchrow(self, query: str, *args):
        return None

    async def execute(self, query: str, *args):
        pass


async def demo_rating_scenarios():
    """Run various rating scenarios to demonstrate capabilities."""

    # Initialize rating engine
    db = MockDatabase()
    cache = MockCache()
    engine = RatingEngine(db, cache, enable_ai_scoring=True)

    print("🚀 P&C Insurance Rating Engine Demo")
    print("=" * 60)
    print()

    # Scenario 1: Safe Driver with Good Credit
    print("📊 Scenario 1: Safe Driver Profile")
    print("-" * 40)

    vehicle1 = VehicleInfo(
        vin="1HGCM82633A123456",
        year=2022,
        make="Honda",
        model="Accord",
        annual_mileage=10000,
    )
    vehicle1.vehicle_type = "sedan"
    vehicle1.safety_features = ["abs", "airbags", "automatic_braking", "lane_assist"]

    driver1 = DriverInfo(
        id=uuid4(),
        first_name="Sarah",
        last_name="Safe",
        age=35,
        years_licensed=17,
        violations_3_years=0,
        accidents_3_years=0,
        dui_convictions=0,
        license_number="S123456",
        license_state="CA",
        zip_code="90210",
    )

    coverages1 = [
        CoverageSelection(
            coverage_type=CoverageType.LIABILITY,
            limit=Decimal("300000"),
            deductible=None,
        ),
        CoverageSelection(
            coverage_type=CoverageType.COLLISION,
            limit=Decimal("50000"),
            deductible=Decimal("500"),
        ),
        CoverageSelection(
            coverage_type=CoverageType.COMPREHENSIVE,
            limit=Decimal("50000"),
            deductible=Decimal("500"),
        ),
    ]

    customer_data1 = {
        "policy_count": 2,  # Multi-policy discount
        "years_as_customer": 5,
    }

    start_time = time.perf_counter()
    result1 = await engine.calculate_premium(
        quote_id=uuid4(),
        state="CA",
        effective_date=datetime.now(),
        vehicle_info=vehicle1,
        drivers=[driver1],
        coverage_selections=coverages1,
        customer_data=customer_data1,
    )
    calc_time1 = (time.perf_counter() - start_time) * 1000

    if result1.is_ok():
        data = result1.unwrap()
        print(f"✅ Base Premium: ${data['base_premium']:,.2f}")
        print(f"✅ Discounts: ${data['discounts']['total_amount']:,.2f}")
        print(f"✅ Surcharges: ${data['surcharges']['total_surcharge_amount']:,.2f}")
        print(f"✅ Final Premium: ${data['final_premium']:,.2f}")
        print(
            f"⏱️  Calculation Time: {calc_time1:.1f}ms {'✅' if calc_time1 < 50 else '❌'}"
        )
        print()
    else:
        print(f"❌ Error: {result1.unwrap_err()}")
        print()

    # Scenario 2: High-Risk Young Driver
    print("📊 Scenario 2: High-Risk Young Driver")
    print("-" * 40)

    vehicle2 = VehicleInfo(
        vin="1G1YY22G465123456",
        year=2019,
        make="Chevrolet",
        model="Corvette",
        annual_mileage=15000,
    )
    vehicle2.vehicle_type = "sports"
    vehicle2.safety_features = ["abs", "airbags"]

    driver2 = DriverInfo(
        id=uuid4(),
        first_name="Johnny",
        last_name="Speed",
        age=19,
        years_licensed=1,
        violations_3_years=3,
        accidents_3_years=1,
        dui_convictions=0,
        license_number="J123456",
        license_state="TX",
        zip_code="75001",
    )

    coverages2 = [
        CoverageSelection(
            coverage_type=CoverageType.LIABILITY,
            limit=Decimal("100000"),  # State minimum
            deductible=None,
        ),
        CoverageSelection(
            coverage_type=CoverageType.COLLISION,
            limit=Decimal("30000"),
            deductible=Decimal("1000"),
        ),
    ]

    start_time = time.perf_counter()
    result2 = await engine.calculate_premium(
        quote_id=uuid4(),
        state="TX",
        effective_date=datetime.now(),
        vehicle_info=vehicle2,
        drivers=[driver2],
        coverage_selections=coverages2,
    )
    calc_time2 = (time.perf_counter() - start_time) * 1000

    if result2.is_ok():
        data = result2.unwrap()
        print(f"✅ Base Premium: ${data['base_premium']:,.2f}")
        print(f"✅ Discounts: ${data['discounts']['total_amount']:,.2f}")
        print(f"✅ Surcharges: ${data['surcharges']['total_surcharge_amount']:,.2f}")
        print(
            f"   - High Risk: {data['surcharges']['by_type'].get('high_risk_driver', {}).get('count', 0)}"
        )
        print(
            f"   - Young Driver: {data['surcharges']['by_type'].get('young_driver', {}).get('count', 0)}"
        )
        print(
            f"   - Inexperienced: {data['surcharges']['by_type'].get('inexperienced_driver', {}).get('count', 0)}"
        )
        print(f"✅ Final Premium: ${data['final_premium']:,.2f}")
        print(
            f"⏱️  Calculation Time: {calc_time2:.1f}ms {'✅' if calc_time2 < 50 else '❌'}"
        )
        print()
    else:
        print(f"❌ Error: {result2.unwrap_err()}")
        print()

    # Scenario 3: DUI Driver with SR-22 Requirement
    print("📊 Scenario 3: DUI Driver with SR-22")
    print("-" * 40)

    vehicle3 = VehicleInfo(
        vin="1FTFW1ET5DFC12345",
        year=2015,
        make="Ford",
        model="F-150",
        annual_mileage=20000,
    )
    vehicle3.vehicle_type = "truck"

    driver3 = DriverInfo(
        id=uuid4(),
        first_name="Mike",
        last_name="Mistake",
        age=42,
        years_licensed=24,
        violations_3_years=1,
        accidents_3_years=0,
        dui_convictions=1,
        license_number="M123456",
        license_state="FL",
        zip_code="33101",
    )

    coverages3 = [
        CoverageSelection(
            coverage_type=CoverageType.LIABILITY,
            limit=Decimal("50000"),  # State minimum
            deductible=None,
        ),
        CoverageSelection(
            coverage_type=CoverageType.PERSONAL_INJURY_PROTECTION,
            limit=Decimal("10000"),  # Florida requirement
            deductible=None,
        ),
    ]

    start_time = time.perf_counter()
    result3 = await engine.calculate_premium(
        quote_id=uuid4(),
        state="FL",
        effective_date=datetime.now(),
        vehicle_info=vehicle3,
        drivers=[driver3],
        coverage_selections=coverages3,
    )
    calc_time3 = (time.perf_counter() - start_time) * 1000

    if result3.is_ok():
        data = result3.unwrap()
        print(f"✅ Base Premium: ${data['base_premium']:,.2f}")
        print(f"✅ Discounts: ${data['discounts']['total_amount']:,.2f}")
        print(f"✅ Surcharges: ${data['surcharges']['total_surcharge_amount']:,.2f}")
        print(
            f"   - DUI Surcharge: {data['surcharges']['by_type'].get('dui_conviction', {}).get('count', 0)}"
        )
        print(
            f"   - SR-22 Filing: {'Yes' if data['surcharges']['requires_sr22'] else 'No'}"
        )
        print(f"✅ Final Premium: ${data['final_premium']:,.2f}")
        print(
            f"⏱️  Calculation Time: {calc_time3:.1f}ms {'✅' if calc_time3 < 50 else '❌'}"
        )
        print()
    else:
        print(f"❌ Error: {result3.unwrap_err()}")
        print()

    # Performance Summary
    print("📈 Performance Summary")
    print("=" * 60)

    metrics = await engine.get_performance_metrics()
    print(f"Total Calculations: {metrics['calculations_performed']}")
    print(f"Average Time: {metrics['average_time_ms']:.1f}ms")
    print(f"Target Met: {metrics['target_met_percentage']:.1f}%")

    # Show factor breakdown for one scenario
    print("\n📊 Factor Breakdown (Scenario 1)")
    print("-" * 40)
    if result1.is_ok():
        data = result1.unwrap()
        for factor, value in data["factors"].items():
            impact = data["factor_impacts"].get(factor, 0)
            print(f"{factor:20} {value:6.2f}x  Impact: ${impact:8.2f}")

    # Business rule validation example
    print("\n📋 Business Rule Validation")
    print("-" * 40)
    if result1.is_ok() and data.get("business_rule_validation"):
        validation = data["business_rule_validation"]
        print(f"Status: {validation['compliance_status'].upper()}")
        print(f"Total Violations: {validation['total_violations']}")
        print(f"  - Critical: {validation['critical_violations']}")
        print(f"  - Warnings: {validation['warnings']}")
        print(f"  - Info: {validation['info_messages']}")
    else:
        print("✅ All business rules passed")

    print("\n✨ Demo Complete!")


if __name__ == "__main__":
    asyncio.run(demo_rating_scenarios())
