#!/usr/bin/env python3
"""Demonstration script for rating calculator implementation."""

import sys
from decimal import Decimal
from pathlib import Path

# Ensure project root's `src` directory is on the import path when running directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from policy_core.services.rating.calculators import (
    DiscountCalculator,
    PremiumCalculator,
)


def demo_premium_calculation():
    """Demonstrate premium calculation functionality."""
    print("=== Premium Calculation Demo ===")

    # Test base premium calculation
    result = PremiumCalculator.calculate_base_premium(
        coverage_limit=Decimal("100000"),
        base_rate=Decimal("0.005"),
        exposure_units=Decimal("1"),
    )

    if result.is_ok():
        print(f"✓ Base premium: ${result.unwrap()}")
    else:
        print(f"✗ Error: {result.unwrap_err()}")

    # Test factor application
    if result.is_ok():
        base_premium = result.unwrap()
        factors = {
            "territory": 1.2,
            "driver_age": 0.9,
            "violations": 1.1,
        }

        factor_result = PremiumCalculator.apply_multiplicative_factors(
            base_premium, factors
        )

        if factor_result.is_ok():
            final_premium, impacts = factor_result.unwrap()
            print(f"✓ Premium with factors: ${final_premium}")
            print(f"  Factor impacts: {impacts}")
        else:
            print(f"✗ Factor error: {factor_result.unwrap_err()}")


def demo_discount_calculation():
    """Demonstrate discount calculation functionality."""
    print("\n=== Discount Calculation Demo ===")

    base_premium = Decimal("1000.00")
    discounts = [
        {"rate": 0.10, "priority": 1, "stackable": True, "name": "Multi-policy"},
        {"rate": 0.05, "priority": 2, "stackable": True, "name": "Good driver"},
        {
            "rate": 0.15,
            "priority": 3,
            "stackable": False,
            "name": "First-time customer",
        },
    ]

    result = DiscountCalculator.calculate_stacked_discounts(base_premium, discounts)

    if result.is_ok():
        applied_discounts, total_discount = result.unwrap()
        print(f"✓ Total discount: ${total_discount}")
        print("  Applied discounts:")
        for discount in applied_discounts:
            print(f"    - {discount.get('name', 'Unknown')}: ${discount['amount']}")
        final_premium = base_premium - total_discount
        print(f"  Final premium: ${final_premium}")
    else:
        print(f"✗ Discount error: {result.unwrap_err()}")


def demo_driver_scoring():
    """Demonstrate driver risk scoring."""
    print("\n=== Driver Risk Scoring Demo ===")

    # Young driver with violations
    young_driver = {
        "age": 19,
        "years_licensed": 2,
        "violations_3_years": 1,
        "accidents_3_years": 0,
    }

    result = PremiumCalculator.calculate_driver_risk_score(young_driver)

    if result.is_ok():
        score, factors = result.unwrap()
        print(f"✓ Young driver risk score: {score:.3f}")
        print(f"  Risk factors: {factors}")
    else:
        print(f"✗ Scoring error: {result.unwrap_err()}")

    # Experienced driver
    experienced_driver = {
        "age": 45,
        "years_licensed": 25,
        "violations_3_years": 0,
        "accidents_3_years": 0,
    }

    result = PremiumCalculator.calculate_driver_risk_score(experienced_driver)

    if result.is_ok():
        score, factors = result.unwrap()
        print(f"✓ Experienced driver risk score: {score:.3f}")
        print(f"  Risk factors: {factors}")
    else:
        print(f"✗ Scoring error: {result.unwrap_err()}")


def demo_vehicle_scoring():
    """Demonstrate vehicle risk scoring."""
    print("\n=== Vehicle Risk Scoring Demo ===")

    # Sports car
    sports_car = {
        "type": "sports",
        "age": 2,
        "safety_features": ["abs", "airbags"],
        "theft_rate": 1.3,
    }

    result = PremiumCalculator.calculate_vehicle_risk_score(sports_car)

    if result.is_ok():
        score = result.unwrap()
        print(f"✓ Sports car risk score: {score:.3f}")
    else:
        print(f"✗ Scoring error: {result.unwrap_err()}")

    # Economy car with safety features
    economy_car = {
        "type": "economy",
        "age": 5,
        "safety_features": ["abs", "airbags", "stability_control", "automatic_braking"],
        "theft_rate": 0.8,
    }

    result = PremiumCalculator.calculate_vehicle_risk_score(economy_car)

    if result.is_ok():
        score = result.unwrap()
        print(f"✓ Economy car risk score: {score:.3f}")
    else:
        print(f"✗ Scoring error: {result.unwrap_err()}")


def demo_complete_calculation():
    """Demonstrate complete premium calculation workflow."""
    print("\n=== Complete Calculation Workflow ===")

    # Step 1: Base premium
    base_result = PremiumCalculator.calculate_base_premium(
        coverage_limit=Decimal("250000"),
        base_rate=Decimal("0.008"),
    )

    if base_result.is_err():
        print(f"✗ Base calculation failed: {base_result.unwrap_err()}")
        return

    base_premium = base_result.unwrap()
    print(f"1. Base premium: ${base_premium}")

    # Step 2: Apply factors
    factors = {
        "territory": 1.15,  # Higher risk area
        "driver_age": 0.95,  # Mature driver
        "experience": 0.92,  # Experienced
        "vehicle_age": 0.98,  # Nearly new
        "safety_features": 0.88,  # Good safety features
        "credit": 1.02,  # Average credit
    }

    factor_result = PremiumCalculator.apply_multiplicative_factors(
        base_premium, factors
    )

    if factor_result.is_err():
        print(f"✗ Factor application failed: {factor_result.unwrap_err()}")
        return

    factored_premium, impacts = factor_result.unwrap()
    print(f"2. Premium with factors: ${factored_premium}")

    # Step 3: Apply discounts
    discounts = [
        {"rate": 0.12, "priority": 1, "stackable": True, "name": "Multi-policy"},
        {"rate": 0.06, "priority": 2, "stackable": True, "name": "Good driver"},
        {"rate": 0.04, "priority": 3, "stackable": True, "name": "Electronic billing"},
    ]

    discount_result = DiscountCalculator.calculate_stacked_discounts(
        factored_premium, discounts
    )

    if discount_result.is_err():
        print(f"✗ Discount calculation failed: {discount_result.unwrap_err()}")
        return

    applied_discounts, total_discount = discount_result.unwrap()
    final_premium = factored_premium - total_discount

    print(f"3. Total discounts: ${total_discount}")
    print(f"4. FINAL PREMIUM: ${final_premium}")

    # Summary
    savings = base_premium - final_premium
    savings_pct = (savings / base_premium) * 100
    print("\nSummary:")
    print(f"  Base premium:     ${base_premium}")
    print(f"  Final premium:    ${final_premium}")
    print(f"  Total savings:    ${savings} ({savings_pct:.1f}%)")


if __name__ == "__main__":
    print("🚀 Rating Calculator Implementation Demo")
    print("=" * 50)

    try:
        demo_premium_calculation()
        demo_discount_calculation()
        demo_driver_scoring()
        demo_vehicle_scoring()
        demo_complete_calculation()

        print("\n✅ All rating calculator demonstrations completed successfully!")
        print("\nKey Features Implemented:")
        print("  ✓ Penny-precise decimal calculations")
        print("  ✓ Comprehensive input validation")
        print("  ✓ Detailed error messages with remediation")
        print("  ✓ Factor application with impact tracking")
        print("  ✓ Discount stacking with business rules")
        print("  ✓ Risk scoring with explanatory factors")
        print("  ✓ Result type pattern (no exceptions)")

    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback

        traceback.print_exc()
