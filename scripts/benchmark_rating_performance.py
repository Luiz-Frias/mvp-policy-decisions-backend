#!/usr/bin/env python3
"""Benchmark script for rating engine performance validation.

This script validates that the rating engine meets the <50ms performance requirement
under various load scenarios.
"""

import asyncio
import random
import statistics
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
    """Mock cache for benchmarking."""

    def __init__(self):
        self._cache = {}

    async def get(self, key: str):
        # Simulate cache latency
        await asyncio.sleep(0.0001)  # 0.1ms
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
    """Mock database for benchmarking."""

    async def fetch(self, query: str, *args):
        # Simulate database latency
        await asyncio.sleep(0.001)  # 1ms
        return []

    async def fetchrow(self, query: str, *args):
        await asyncio.sleep(0.001)  # 1ms
        return None

    async def execute(self, query: str, *args):
        await asyncio.sleep(0.001)  # 1ms


def generate_test_scenario():
    """Generate random test scenario for benchmarking."""
    # Random vehicle
    vehicle_types = ["sedan", "suv", "truck", "sports", "economy"]
    vehicle = VehicleInfo(
        vin=f"1HGCM{random.randint(10000, 99999)}A{random.randint(100000, 999999)}",
        year=random.randint(2015, 2024),
        make=random.choice(["Honda", "Toyota", "Ford", "Chevrolet", "Tesla"]),
        model="TestModel",
        annual_mileage=random.randint(5000, 30000),
    )
    vehicle.vehicle_type = random.choice(vehicle_types)
    vehicle.safety_features = random.sample(
        ["abs", "airbags", "automatic_braking", "lane_assist", "blind_spot"],
        random.randint(1, 4),
    )

    # Random driver
    driver = DriverInfo(
        id=uuid4(),
        first_name="Test",
        last_name="Driver",
        age=random.randint(18, 80),
        years_licensed=random.randint(0, 40),
        violations_3_years=random.randint(0, 3),
        accidents_3_years=random.randint(0, 2),
        dui_convictions=0 if random.random() > 0.05 else 1,  # 5% chance of DUI
        license_number=f"T{random.randint(100000, 999999)}",
        license_state=random.choice(["CA", "TX", "NY", "FL", "MI", "PA"]),
        zip_code=f"{random.randint(10000, 99999)}",
    )

    # Random coverages
    coverage_types = [
        CoverageType.LIABILITY,
        CoverageType.COLLISION,
        CoverageType.COMPREHENSIVE,
        CoverageType.UNINSURED_MOTORIST,
    ]

    num_coverages = random.randint(1, 4)
    coverages = []
    for i in range(num_coverages):
        if i < len(coverage_types):
            coverages.append(
                CoverageSelection(
                    coverage_type=coverage_types[i],
                    limit=Decimal(
                        random.choice(["50000", "100000", "250000", "500000"])
                    ),
                    deductible=(
                        Decimal(random.choice(["250", "500", "1000"]))
                        if i > 0
                        else None
                    ),
                )
            )

    return vehicle, driver, coverages


async def benchmark_single_calculation(engine: RatingEngine, scenario_num: int):
    """Benchmark a single calculation."""
    vehicle, driver, coverages = generate_test_scenario()

    start_time = time.perf_counter()

    result = await engine.calculate_premium(
        quote_id=uuid4(),
        state=driver.license_state,
        effective_date=datetime.now(),
        vehicle_info=vehicle,
        drivers=[driver],
        coverage_selections=coverages,
    )

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    success = result.is_ok()
    under_50ms = elapsed_ms < 50

    return {
        "scenario": scenario_num,
        "elapsed_ms": elapsed_ms,
        "success": success,
        "under_50ms": under_50ms,
        "error": result.unwrap_err() if result.is_err() else None,
    }


async def run_performance_benchmark():
    """Run comprehensive performance benchmark."""
    print("🏁 Rating Engine Performance Benchmark")
    print("=" * 60)
    print()

    # Initialize engine
    db = MockDatabase()
    cache = MockCache()
    engine = RatingEngine(
        db, cache, enable_ai_scoring=False
    )  # Disable AI for pure perf test

    # Warm up caches
    print("♨️  Warming up caches...")
    await engine.warm_caches()
    print("✅ Cache warming complete\n")

    # Run benchmarks
    num_scenarios = 100
    results = []

    print(f"🔄 Running {num_scenarios} calculations...")
    progress_interval = num_scenarios // 10

    start_total = time.perf_counter()

    # Sequential execution (more realistic for single-user scenario)
    for i in range(num_scenarios):
        result = await benchmark_single_calculation(engine, i + 1)
        results.append(result)

        if (i + 1) % progress_interval == 0:
            print(f"   Progress: {(i + 1) / num_scenarios * 100:.0f}%")

    total_elapsed = (time.perf_counter() - start_total) * 1000

    # Analyze results
    print("\n📊 Performance Analysis")
    print("-" * 40)

    successful_results = [r for r in results if r["success"]]
    failed_results = [r for r in results if not r["success"]]

    if successful_results:
        times = [r["elapsed_ms"] for r in successful_results]
        under_50ms_count = sum(1 for r in successful_results if r["under_50ms"])

        print(f"✅ Successful calculations: {len(successful_results)}/{num_scenarios}")
        print(f"❌ Failed calculations: {len(failed_results)}/{num_scenarios}")
        print()

        print("⏱️  Timing Statistics (ms):")
        print(f"   Min:     {min(times):7.1f}ms")
        print(f"   Max:     {max(times):7.1f}ms")
        print(f"   Mean:    {statistics.mean(times):7.1f}ms")
        print(f"   Median:  {statistics.median(times):7.1f}ms")
        print(f"   StdDev:  {statistics.stdev(times):7.1f}ms" if len(times) > 1 else "")
        print()

        # Percentiles
        sorted_times = sorted(times)
        p50 = sorted_times[len(sorted_times) // 2]
        p95 = sorted_times[int(len(sorted_times) * 0.95)]
        p99 = sorted_times[int(len(sorted_times) * 0.99)]

        print("📈 Percentiles:")
        print(f"   P50:     {p50:7.1f}ms")
        print(f"   P95:     {p95:7.1f}ms")
        print(f"   P99:     {p99:7.1f}ms")
        print()

        print("🎯 Performance Target (<50ms):")
        print(
            f"   Met:     {under_50ms_count}/{len(successful_results)} ({under_50ms_count/len(successful_results)*100:.1f}%)"
        )
        print(
            f"   Failed:  {len(successful_results) - under_50ms_count}/{len(successful_results)} ({(len(successful_results) - under_50ms_count)/len(successful_results)*100:.1f}%)"
        )
        print()

        print(
            f"🚀 Throughput: {num_scenarios / (total_elapsed / 1000):.1f} calculations/second"
        )

        # Show slowest calculations
        if any(not r["under_50ms"] for r in successful_results):
            print("\n⚠️  Slowest Calculations (>50ms):")
            slow_results = sorted(
                [r for r in successful_results if not r["under_50ms"]],
                key=lambda x: x["elapsed_ms"],
                reverse=True,
            )[:5]
            for r in slow_results:
                print(f"   Scenario {r['scenario']}: {r['elapsed_ms']:.1f}ms")

    else:
        print("❌ All calculations failed!")
        for r in failed_results[:5]:
            print(f"   Error: {r['error']}")

    # Get engine performance metrics
    print("\n📊 Engine Performance Metrics")
    print("-" * 40)
    metrics = await engine.get_performance_metrics()
    print(
        f"Cache Hit Rate: {metrics.get('cache_statistics', {}).get('hit_rate', 0)*100:.1f}%"
    )
    print(
        f"Cache Entries: {metrics.get('cache_statistics', {}).get('total_entries', 0)}"
    )

    # Overall verdict
    print("\n🏆 Overall Performance Rating")
    print("=" * 60)

    if successful_results:
        success_rate = len(successful_results) / num_scenarios * 100
        target_met_rate = under_50ms_count / len(successful_results) * 100

        if success_rate >= 95 and target_met_rate >= 95:
            print("✅ EXCELLENT - Production Ready")
            print("   All performance requirements met!")
        elif success_rate >= 90 and target_met_rate >= 90:
            print("⚠️  GOOD - Minor optimization needed")
            print("   Most calculations meet requirements")
        elif success_rate >= 80 and target_met_rate >= 80:
            print("⚠️  FAIR - Optimization required")
            print("   Performance improvements needed")
        else:
            print("❌ POOR - Major optimization required")
            print("   Significant performance issues")
    else:
        print("❌ FAILED - System not functional")


async def run_concurrent_load_test():
    """Run concurrent load test to simulate multiple users."""
    print("\n\n🔥 Concurrent Load Test")
    print("=" * 60)
    print()

    # Initialize engine
    db = MockDatabase()
    cache = MockCache()
    engine = RatingEngine(db, cache, enable_ai_scoring=False)

    # Warm caches
    await engine.warm_caches()

    # Run concurrent calculations
    concurrent_users = 10
    calculations_per_user = 10

    print(f"👥 Simulating {concurrent_users} concurrent users")
    print(f"📊 Each user: {calculations_per_user} calculations")
    print()

    async def user_session(user_id: int):
        """Simulate a user session."""
        results = []
        for i in range(calculations_per_user):
            result = await benchmark_single_calculation(engine, f"{user_id}-{i}")
            results.append(result)
        return results

    start_time = time.perf_counter()

    # Run all user sessions concurrently
    user_tasks = [user_session(i) for i in range(concurrent_users)]
    all_results = await asyncio.gather(*user_tasks)

    total_elapsed = (time.perf_counter() - start_time) * 1000

    # Flatten results
    flat_results = [r for user_results in all_results for r in user_results]
    successful_results = [r for r in flat_results if r["success"]]

    if successful_results:
        times = [r["elapsed_ms"] for r in successful_results]
        under_50ms_count = sum(1 for r in successful_results if r["under_50ms"])

        print("📊 Concurrent Load Results:")
        print(f"   Total calculations: {len(flat_results)}")
        print(f"   Successful: {len(successful_results)}")
        print(f"   Average time: {statistics.mean(times):.1f}ms")
        print(f"   P95 time: {sorted(times)[int(len(times) * 0.95)]:.1f}ms")
        print(f"   Under 50ms: {under_50ms_count/len(successful_results)*100:.1f}%")
        print(f"   Total time: {total_elapsed:.1f}ms")
        print(
            f"   Throughput: {len(flat_results) / (total_elapsed / 1000):.1f} calc/sec"
        )


if __name__ == "__main__":
    asyncio.run(run_performance_benchmark())
    asyncio.run(run_concurrent_load_test())
