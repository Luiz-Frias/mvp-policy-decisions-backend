#!/usr/bin/env python3
"""Performance benchmark test for rating calculator implementation."""

import sys
import time
import asyncio
from decimal import Decimal
from pathlib import Path
from datetime import datetime

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent / "src"))

from pd_prime_demo.services.rating.calculators import (
    PremiumCalculator,
    DiscountCalculator,
    AIRiskScorer,
    ExternalDataIntegrator,
    StatisticalRatingModels,
)
from pd_prime_demo.services.rating.performance import RatingPerformanceOptimizer


async def benchmark_full_calculation_pipeline():
    """Benchmark a complete rating calculation pipeline."""
    print("=== Performance Benchmark: Full Calculation Pipeline ===")
    
    # Initialize AI scorer with models loaded
    ai_scorer = AIRiskScorer(load_models=True)
    optimizer = RatingPerformanceOptimizer()
    
    # Sample data for testing
    quote_data = {
        "state": "CA",
        "zip_code": "90210",
        "drivers": [
            {
                "age": 30,
                "years_licensed": 12,
                "violations_3_years": 0,
                "accidents_3_years": 0,
            }
        ],
        "vehicles": [
            {
                "age": 3,
                "type": "sedan",
                "value": 25000,
                "annual_mileage": 12000,
                "safety_features": ["abs", "airbags", "stability_control"],
            }
        ],
        "customer": {
            "policy_count": 2,
            "years_as_customer": 5,
            "previous_claims": 0,
        },
        "coverage_limit": 100000,
        "base_rate": 0.005,
    }
    
    # Run multiple iterations to get average timing
    iterations = 100
    timings = []
    
    print(f"Running {iterations} iterations...")
    
    for i in range(iterations):
        start_time = time.perf_counter()
        
        # Step 1: Base premium calculation
        base_result = PremiumCalculator.calculate_base_premium(
            coverage_limit=Decimal(str(quote_data["coverage_limit"])),
            base_rate=Decimal(str(quote_data["base_rate"])),
        )
        
        if base_result.is_err():
            print(f"Base calculation failed: {base_result.unwrap_err()}")
            continue
            
        base_premium = base_result.unwrap()
        
        # Step 2: Calculate rating factors
        driver = quote_data["drivers"][0]
        vehicle = quote_data["vehicles"][0]
        
        # Driver scoring
        driver_result = PremiumCalculator.calculate_driver_risk_score(driver)
        if driver_result.is_err():
            continue
        driver_score, _ = driver_result.unwrap()
        
        # Vehicle scoring
        vehicle_result = PremiumCalculator.calculate_vehicle_risk_score(vehicle)
        if vehicle_result.is_err():
            continue
        vehicle_score = vehicle_result.unwrap()
        
        # Territory factor
        territory_data = {
            "base_loss_cost": 100,
            quote_data["zip_code"]: {"loss_cost": 120, "credibility": 0.8}
        }
        territory_result = PremiumCalculator.calculate_territory_factor(
            quote_data["zip_code"], territory_data
        )
        if territory_result.is_err():
            continue
        territory_factor = territory_result.unwrap()
        
        # External data factors
        weather_result = await ExternalDataIntegrator.get_weather_risk_factor(
            quote_data["zip_code"], 
            datetime.now()
        )
        weather_factor = weather_result.unwrap_or(1.0)
        
        crime_result = await ExternalDataIntegrator.get_crime_risk_factor(
            quote_data["zip_code"]
        )
        crime_factor = crime_result.unwrap_or(1.0)
        
        # Combine factors
        all_factors = {
            "driver_risk": 0.5 + driver_score,  # Convert score to factor
            "vehicle_risk": vehicle_score,
            "territory": territory_factor,
            "weather": weather_factor,
            "crime": crime_factor,
        }
        
        # Step 3: Apply factors
        factor_result = PremiumCalculator.apply_multiplicative_factors(
            base_premium, all_factors
        )
        if factor_result.is_err():
            continue
        factored_premium, _ = factor_result.unwrap()
        
        # Step 4: Calculate AI risk score
        ai_result = await ai_scorer.calculate_ai_risk_score(
            quote_data["customer"],
            vehicle,
            quote_data["drivers"]
        )
        if ai_result.is_ok():
            ai_data = ai_result.unwrap()
            ai_factor = 0.5 + ai_data["score"]
            factored_premium *= Decimal(str(ai_factor))
        
        # Step 5: Apply discounts
        discounts = [
            {"rate": 0.10, "priority": 1, "stackable": True},
            {"rate": 0.05, "priority": 2, "stackable": True},
        ]
        
        discount_result = DiscountCalculator.calculate_stacked_discounts(
            factored_premium, discounts
        )
        if discount_result.is_err():
            continue
        _, total_discount = discount_result.unwrap()
        
        final_premium = factored_premium - total_discount
        
        # Calculate time
        elapsed_time = (time.perf_counter() - start_time) * 1000
        timings.append(elapsed_time)
        
        # Progress indicator
        if (i + 1) % 20 == 0:
            print(f"  Completed {i + 1}/{iterations} iterations")
    
    # Calculate statistics
    if not timings:
        print("❌ No successful calculations completed")
        return
    
    timings.sort()
    avg_time = sum(timings) / len(timings)
    min_time = min(timings)
    max_time = max(timings)
    p50 = timings[len(timings) // 2]
    p95 = timings[int(len(timings) * 0.95)]
    p99 = timings[int(len(timings) * 0.99)]
    
    print(f"\n📊 Performance Results:")
    print(f"  Successful calculations: {len(timings)}/{iterations}")
    print(f"  Average time:    {avg_time:.2f}ms")
    print(f"  Median (P50):    {p50:.2f}ms")
    print(f"  95th percentile: {p95:.2f}ms")
    print(f"  99th percentile: {p99:.2f}ms")
    print(f"  Min time:        {min_time:.2f}ms")
    print(f"  Max time:        {max_time:.2f}ms")
    
    # Check performance requirements
    target_time = 50.0  # 50ms requirement
    violations = [t for t in timings if t > target_time]
    violation_rate = len(violations) / len(timings) * 100
    
    print(f"\n🎯 Performance Target Analysis (50ms):")
    print(f"  Calculations over 50ms: {len(violations)}/{len(timings)} ({violation_rate:.1f}%)")
    
    if violation_rate < 5:  # Allow 5% violations
        print(f"  ✅ PERFORMANCE TARGET MET (< 5% violations)")
    else:
        print(f"  ❌ PERFORMANCE TARGET MISSED (>= 5% violations)")
    
    return avg_time, p95, violation_rate


async def benchmark_individual_components():
    """Benchmark individual calculation components."""
    print("\n=== Component-Level Performance Benchmarks ===")
    
    iterations = 1000
    
    # Benchmark base premium calculation
    print("Benchmarking base premium calculation...")
    start_time = time.perf_counter()
    for _ in range(iterations):
        PremiumCalculator.calculate_base_premium(
            coverage_limit=Decimal("100000"),
            base_rate=Decimal("0.005"),
        )
    elapsed = (time.perf_counter() - start_time) * 1000
    print(f"  Base premium: {elapsed/iterations:.3f}ms per calculation")
    
    # Benchmark factor application
    print("Benchmarking factor application...")
    base_premium = Decimal("1000.00")
    factors = {"territory": 1.2, "driver": 0.9, "vehicle": 1.1}
    start_time = time.perf_counter()
    for _ in range(iterations):
        PremiumCalculator.apply_multiplicative_factors(base_premium, factors)
    elapsed = (time.perf_counter() - start_time) * 1000
    print(f"  Factor application: {elapsed/iterations:.3f}ms per calculation")
    
    # Benchmark discount calculation
    print("Benchmarking discount calculation...")
    discounts = [
        {"rate": 0.10, "priority": 1, "stackable": True},
        {"rate": 0.05, "priority": 2, "stackable": True},
    ]
    start_time = time.perf_counter()
    for _ in range(iterations):
        DiscountCalculator.calculate_stacked_discounts(base_premium, discounts)
    elapsed = (time.perf_counter() - start_time) * 1000
    print(f"  Discount stacking: {elapsed/iterations:.3f}ms per calculation")
    
    # Benchmark driver scoring
    print("Benchmarking driver risk scoring...")
    driver_data = {
        "age": 30,
        "years_licensed": 12,
        "violations_3_years": 0,
        "accidents_3_years": 0,
    }
    start_time = time.perf_counter()
    for _ in range(iterations):
        PremiumCalculator.calculate_driver_risk_score(driver_data)
    elapsed = (time.perf_counter() - start_time) * 1000
    print(f"  Driver scoring: {elapsed/iterations:.3f}ms per calculation")


async def main():
    """Run all performance benchmarks."""
    print("🚀 Rating Calculator Performance Benchmark")
    print("=" * 60)
    
    # Benchmark full pipeline
    avg_time, p95_time, violation_rate = await benchmark_full_calculation_pipeline()
    
    # Benchmark individual components
    await benchmark_individual_components()
    
    print("\n" + "=" * 60)
    print("📋 Summary:")
    print(f"  Full pipeline average: {avg_time:.2f}ms")
    print(f"  Full pipeline P95:     {p95_time:.2f}ms")
    print(f"  Performance violations: {violation_rate:.1f}%")
    
    if violation_rate < 5:
        print("  🎉 OVERALL PERFORMANCE: EXCELLENT")
    elif violation_rate < 15:
        print("  ⚠️  OVERALL PERFORMANCE: GOOD (needs optimization)")
    else:
        print("  ❌ OVERALL PERFORMANCE: POOR (requires immediate optimization)")


if __name__ == "__main__":
    asyncio.run(main())