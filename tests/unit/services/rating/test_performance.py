"""Performance benchmarks for rating calculations to ensure <50ms performance."""

import asyncio
import time
from decimal import Decimal
from typing import Any

import pytest

from pd_prime_demo.services.rating.calculators import (
    DiscountCalculator,
    PremiumCalculator,
)
from pd_prime_demo.services.rating.performance import RatingPerformanceOptimizer


class TestRatingPerformance:
    """Test rating calculation performance to ensure <50ms requirement."""

    @pytest.fixture
    def sample_quote_data(self) -> dict[str, Any]:
        """Generate sample quote data for testing."""
        return {
            "state": "CA",
            "zip_code": "90210",
            "coverage_limit": Decimal("100000"),
            "base_rate": Decimal("0.005"),
            "drivers": [
                {
                    "age": 35,
                    "years_licensed": 15,
                    "violations_3_years": 0,
                    "accidents_3_years": 0,
                },
                {
                    "age": 33,
                    "years_licensed": 12,
                    "violations_3_years": 1,
                    "accidents_3_years": 0,
                },
            ],
            "vehicles": [
                {
                    "type": "sedan",
                    "age": 3,
                    "value": 25000,
                    "safety_features": ["abs", "airbags", "stability_control"],
                    "theft_rate": 1.0,
                },
                {
                    "type": "suv",
                    "age": 5,
                    "value": 35000,
                    "safety_features": ["abs", "airbags"],
                    "theft_rate": 1.1,
                },
            ],
        }

    @pytest.fixture
    def territory_data(self) -> dict[str, Any]:
        """Generate territory data for testing."""
        return {
            "base_loss_cost": 100,
            "90210": {"loss_cost": 120, "credibility": 0.8},
            "10001": {"loss_cost": 150, "credibility": 0.9},
        }

    def test_base_premium_calculation_performance(self, benchmark):
        """Benchmark base premium calculation."""

        def calculate():
            return PremiumCalculator.calculate_base_premium(
                coverage_limit=Decimal("100000"),
                base_rate=Decimal("0.005"),
                exposure_units=Decimal("1"),
            )

        result = benchmark(calculate)
        assert result.is_ok()

        # Ensure calculation takes less than 1ms
        assert benchmark.stats["mean"] < 0.001

    def test_factor_application_performance(self, benchmark):
        """Benchmark factor application performance."""
        base_premium = Decimal("1000.00")
        factors = {
            "territory": 1.2,
            "driver_age": 0.9,
            "experience": 1.1,
            "vehicle_age": 0.95,
            "safety_features": 0.92,
            "credit": 1.05,
            "violations": 1.3,
            "accidents": 1.0,
        }

        def apply_factors():
            return PremiumCalculator.apply_multiplicative_factors(base_premium, factors)

        result = benchmark(apply_factors)
        assert result.is_ok()

        # Ensure calculation takes less than 2ms
        assert benchmark.stats["mean"] < 0.002

    def test_discount_stacking_performance(self, benchmark):
        """Benchmark discount stacking calculation."""
        base_premium = Decimal("1500.00")
        discounts = [
            {"rate": 0.10, "priority": 1, "stackable": True},
            {"rate": 0.05, "priority": 2, "stackable": True},
            {"rate": 0.15, "priority": 3, "stackable": False},
            {"rate": 0.08, "priority": 4, "stackable": True},
            {"rate": 0.03, "priority": 5, "stackable": True},
        ]

        def calculate_discounts():
            return DiscountCalculator.calculate_stacked_discounts(
                base_premium, discounts
            )

        result = benchmark(calculate_discounts)
        assert result.is_ok()

        # Ensure calculation takes less than 2ms
        assert benchmark.stats["mean"] < 0.002

    def test_complete_rating_pipeline_performance(self, benchmark, sample_quote_data):
        """Benchmark complete rating pipeline."""

        def complete_pipeline():
            # 1. Calculate base premium
            base_result = PremiumCalculator.calculate_base_premium(
                sample_quote_data["coverage_limit"],
                sample_quote_data["base_rate"],
            )
            if base_result.is_err():
                return base_result

            base_premium = base_result.unwrap()

            # 2. Calculate territory factor
            territory_result = PremiumCalculator.calculate_territory_factor(
                sample_quote_data["zip_code"],
                {
                    "base_loss_cost": 100,
                    "90210": {"loss_cost": 120, "credibility": 0.8},
                },
            )
            if territory_result.is_err():
                return territory_result

            # 3. Calculate driver scores
            driver_scores = []
            for driver in sample_quote_data["drivers"]:
                score_result = PremiumCalculator.calculate_driver_risk_score(driver)
                if score_result.is_err():
                    return score_result
                driver_scores.append(score_result.unwrap())

            # 4. Calculate vehicle scores
            vehicle_scores = []
            for vehicle in sample_quote_data["vehicles"]:
                score_result = PremiumCalculator.calculate_vehicle_risk_score(vehicle)
                if score_result.is_err():
                    return score_result
                vehicle_scores.append(score_result.unwrap())

            # 5. Apply factors
            factors = {
                "territory": territory_result.unwrap(),
                "driver_age": 0.95,  # Simplified
                "vehicle_age": 0.98,  # Simplified
            }
            factor_result = PremiumCalculator.apply_multiplicative_factors(
                base_premium, factors
            )
            if factor_result.is_err():
                return factor_result

            # 6. Apply discounts
            discounts = [
                {"rate": 0.10, "priority": 1},  # Multi-policy
                {"rate": 0.05, "priority": 2},  # Good driver
            ]
            discount_result = DiscountCalculator.calculate_stacked_discounts(
                factor_result.unwrap()[0], discounts
            )

            return discount_result

        result = benchmark(complete_pipeline)
        assert result.is_ok()

        # Complete pipeline must finish in <50ms
        assert benchmark.stats["mean"] < 0.050

        # Print performance stats for monitoring
        print("\nComplete pipeline performance:")
        print(f"  Mean: {benchmark.stats['mean']*1000:.2f}ms")
        print(f"  Min:  {benchmark.stats['min']*1000:.2f}ms")
        print(f"  Max:  {benchmark.stats['max']*1000:.2f}ms")

    @pytest.mark.asyncio
    async def test_parallel_calculation_performance(self, sample_quote_data):
        """Test parallel calculation performance."""
        optimizer = RatingPerformanceOptimizer()

        # Precompute common scenarios
        optimizer.precompute_common_scenarios()

        start_time = time.perf_counter()

        # Define parallel tasks
        async def territory_task():
            await asyncio.sleep(0.001)  # Simulate DB lookup
            return optimizer.get_cached_territory_factor("CA", "90210")

        async def driver_task():
            await asyncio.sleep(0.002)  # Simulate calculation
            return [0.95, 1.1]  # Mock scores

        async def vehicle_task():
            await asyncio.sleep(0.001)  # Simulate calculation
            return [1.0, 1.05]  # Mock scores

        calculation_tasks = {
            "territory": territory_task,
            "drivers": driver_task,
            "vehicles": vehicle_task,
        }

        result = await optimizer.parallel_factor_calculation(calculation_tasks)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        assert result.is_ok()
        assert elapsed_ms < 50  # Must complete in <50ms

        print(f"\nParallel calculation time: {elapsed_ms:.2f}ms")

    @pytest.mark.asyncio
    async def test_optimized_pipeline_performance(self, sample_quote_data):
        """Test fully optimized calculation pipeline."""
        optimizer = RatingPerformanceOptimizer()
        optimizer.precompute_common_scenarios()

        # Run multiple iterations to test caching
        times = []
        for i in range(10):
            start_time = time.perf_counter()
            result = await optimizer.optimize_calculation_pipeline(sample_quote_data)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            times.append(elapsed_ms)

            assert result.is_ok()
            assert elapsed_ms < 50  # Each iteration must be <50ms

        # First run might be slower, subsequent should be faster due to caching
        print("\nOptimized pipeline performance:")
        print(f"  First run:  {times[0]:.2f}ms")
        print(f"  Cached avg: {sum(times[1:])/len(times[1:]):.2f}ms")
        print(f"  Min:        {min(times):.2f}ms")
        print(f"  Max:        {max(times):.2f}ms")

        # Cached runs should be significantly faster
        assert sum(times[1:]) / len(times[1:]) < times[0] * 0.5  # At least 50% faster

    def test_cache_effectiveness(self):
        """Test cache hit rates and performance improvement."""
        optimizer = RatingPerformanceOptimizer(cache_size=100)

        # Generate test data
        test_data = []
        for i in range(50):
            test_data.append(
                {
                    "state": "CA",
                    "zip_code": f"9{i:04d}",
                    "coverage": Decimal("100000"),
                    "rate": Decimal("0.005"),
                }
            )

        # First pass - populate cache
        start_time = time.perf_counter()
        for data in test_data:
            key = optimizer.create_calculation_hash(data)
            optimizer.cache_calculation(key, {"premium": Decimal("500.00")})
        first_pass_time = time.perf_counter() - start_time

        # Second pass - read from cache
        start_time = time.perf_counter()
        cache_hits = 0
        for data in test_data:
            key = optimizer.create_calculation_hash(data)
            result = optimizer.get_cached_calculation(key)
            if result is not None:
                cache_hits += 1
        second_pass_time = time.perf_counter() - start_time

        # Cache should be 100% hit rate
        assert cache_hits == len(test_data)

        # Reading from cache should be much faster
        assert second_pass_time < first_pass_time * 0.1

        print("\nCache performance:")
        print(f"  Write time: {first_pass_time*1000:.2f}ms")
        print(f"  Read time:  {second_pass_time*1000:.2f}ms")
        print(f"  Hit rate:   {cache_hits/len(test_data)*100:.0f}%")

    def test_performance_metrics_tracking(self):
        """Test performance metrics collection."""
        optimizer = RatingPerformanceOptimizer()

        # Simulate various operations
        for i in range(100):
            optimizer._record_performance_metric("test_op", 10 + i % 40)

        metrics = optimizer.get_performance_metrics()

        assert "test_op" in metrics
        assert metrics["test_op"]["count"] == 100
        assert 10 <= metrics["test_op"]["min_ms"] <= 50
        assert 10 <= metrics["test_op"]["max_ms"] <= 50
        assert metrics["test_op"]["p95_ms"] >= metrics["test_op"]["avg_ms"]

        print("\nPerformance metrics:")
        for op, stats in metrics.items():
            print(f"  {op}:")
            print(f"    Count: {stats['count']}")
            print(f"    Avg:   {stats['avg_ms']:.2f}ms")
            print(f"    P95:   {stats['p95_ms']:.2f}ms")
            print(f"    Min:   {stats['min_ms']:.2f}ms")
            print(f"    Max:   {stats['max_ms']:.2f}ms")


class TestScalabilityBenchmarks:
    """Test scalability with increasing load."""

    def test_bulk_calculation_performance(self, benchmark):
        """Test performance with bulk calculations."""

        def bulk_calculate():
            results = []
            for i in range(100):
                result = PremiumCalculator.calculate_base_premium(
                    coverage_limit=Decimal(str(50000 + i * 1000)),
                    base_rate=Decimal("0.005"),
                )
                results.append(result)
            return results

        results = benchmark(bulk_calculate)

        # Should process 100 calculations quickly
        assert all(r.is_ok() for r in results)
        assert benchmark.stats["mean"] < 0.1  # 100ms for 100 calculations

        print("\nBulk calculation performance:")
        print(f"  100 calculations in {benchmark.stats['mean']*1000:.2f}ms")
        print(f"  Per calculation: {benchmark.stats['mean']*10:.2f}ms")

    @pytest.mark.asyncio
    async def test_concurrent_calculation_performance(self):
        """Test performance under concurrent load."""
        optimizer = RatingPerformanceOptimizer()
        optimizer.precompute_common_scenarios()

        async def single_calculation(quote_id: int):
            data = {
                "state": "CA",
                "zip_code": f"9{quote_id % 100:04d}",
                "drivers": [{"age": 25 + quote_id % 40, "years_licensed": 5}],
                "vehicles": [{"type": "sedan", "age": quote_id % 10}],
            }
            return await optimizer.optimize_calculation_pipeline(data)

        # Simulate 50 concurrent calculations
        start_time = time.perf_counter()
        tasks = [single_calculation(i) for i in range(50)]
        results = await asyncio.gather(*tasks)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # All should succeed
        assert all(r.is_ok() for r in results)

        # Should handle 50 concurrent calculations efficiently
        assert elapsed_ms < 500  # 500ms for 50 concurrent

        print("\nConcurrent calculation performance:")
        print(f"  50 concurrent calculations in {elapsed_ms:.2f}ms")
        print(f"  Throughput: {50/(elapsed_ms/1000):.0f} calculations/second")


class TestAdvancedPerformanceFeatures:
    """Test advanced performance optimization features."""

    @pytest.mark.asyncio
    async def test_batch_territory_lookup_performance(self, benchmark):
        """Test batch territory lookup performance."""
        optimizer = RatingPerformanceOptimizer()

        # Generate 100 ZIP codes
        zip_codes = [f"9{i:04d}" for i in range(100)]

        async def batch_lookup():
            return await optimizer.batch_territory_lookup(zip_codes, "CA")

        result = await benchmark.pedantic(batch_lookup, iterations=1, rounds=10)

        assert result.is_ok()
        factors = result.unwrap()
        assert len(factors) == 100

        # Should be significantly faster than individual lookups
        assert benchmark.stats["mean"] < 0.1  # 100ms for 100 lookups

        print("\nBatch territory lookup performance:")
        print(f"  100 ZIP codes in {benchmark.stats['mean']*1000:.2f}ms")

    def test_cache_warming_performance(self, benchmark):
        """Test cache warming performance."""

        def warm_cache():
            optimizer = RatingPerformanceOptimizer()
            optimizer.warm_cache_for_state("CA")
            return optimizer

        optimizer = benchmark(warm_cache)

        # Check that cache was warmed
        assert len(optimizer._precomputed_factors) > 0

        # Should complete quickly
        assert benchmark.stats["mean"] < 0.05  # 50ms

        print("\nCache warming performance:")
        print(
            f"  Warmed {len(optimizer._precomputed_factors)} factors in {benchmark.stats['mean']*1000:.2f}ms"
        )

    def test_load_testing_optimization_performance(self, benchmark):
        """Test load testing optimization setup."""

        def setup_load_testing():
            optimizer = RatingPerformanceOptimizer()
            optimizer.optimize_for_load_testing()
            return optimizer

        optimizer = benchmark(setup_load_testing)

        # Check optimizations were applied
        assert optimizer._cache_size == 50000
        assert optimizer._cache_ttl == 1800
        assert len(optimizer._precomputed_factors) > 1000

        print("\nLoad testing setup performance:")
        print(
            f"  Optimized with {len(optimizer._precomputed_factors)} precomputed factors in {benchmark.stats['mean']*1000:.2f}ms"
        )

    @pytest.mark.asyncio
    async def test_comprehensive_benchmark_performance(self):
        """Test the built-in benchmarking functionality."""
        optimizer = RatingPerformanceOptimizer()

        start_time = time.perf_counter()
        result = await optimizer.benchmark_calculation_performance(iterations=100)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        assert result.is_ok()
        benchmark_results = result.unwrap()

        # Should complete benchmarking quickly
        assert elapsed_ms < 5000  # 5 seconds for 100 iterations

        # Results should be reasonable
        assert benchmark_results["total_iterations"] == 100
        assert benchmark_results["error_rate"] < 0.1  # Less than 10% errors
        assert benchmark_results["throughput_per_second"] > 10  # At least 10/sec

        print("\nBenchmark suite performance:")
        print(f"  100 iterations in {elapsed_ms:.0f}ms")
        print(f"  Average per calculation: {benchmark_results['avg_time_ms']:.2f}ms")
        print(f"  P95: {benchmark_results['p95_ms']:.2f}ms")
        print(f"  Throughput: {benchmark_results['throughput_per_second']:.1f}/sec")
        print(f"  Error rate: {benchmark_results['error_rate']*100:.1f}%")

    def test_cache_statistics_performance(self, benchmark):
        """Test cache statistics gathering performance."""
        optimizer = RatingPerformanceOptimizer()

        # Populate cache with test data
        for i in range(1000):
            optimizer.cache_calculation(f"key_{i}", {"value": i})
            optimizer._precomputed_factors[f"factor_{i}"] = float(i)

        def get_stats():
            return optimizer.get_cache_statistics()

        stats = benchmark(get_stats)

        # Should be very fast
        assert benchmark.stats["mean"] < 0.001  # 1ms

        # Should return comprehensive statistics
        assert stats["total_entries"] == 1000
        assert stats["precomputed_factors"] == 1000

        print("\nCache statistics performance:")
        print(
            f"  Generated stats for 2000 items in {benchmark.stats['mean']*1000:.2f}ms"
        )
