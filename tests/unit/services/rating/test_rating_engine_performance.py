"""Test rating engine performance requirements.

This module tests that the rating engine meets the <50ms performance
requirement per Agent 06 specifications.
"""

import asyncio
import statistics
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from beartype import beartype

from src.pd_prime_demo.models.quote import CoverageSelection, CoverageType
from src.pd_prime_demo.services.rating_engine import RatingEngine
from tests.fixtures.test_data import (
    create_test_coverage_selections,
    create_test_driver,
    create_test_vehicle,
)


@pytest.mark.asyncio
@beartype
class TestRatingEnginePerformance:
    """Test rating engine performance requirements."""

    async def test_single_quote_performance(self, rating_engine: RatingEngine):
        """Test that single quote calculation completes in <50ms."""
        # Create test data
        vehicle = create_test_vehicle()
        drivers = [create_test_driver()]
        coverages = create_test_coverage_selections()

        # Perform calculation
        result = await rating_engine.calculate_premium(
            state="CA",
            product_type="auto",
            vehicle_info=vehicle,
            drivers=drivers,
            coverage_selections=coverages,
        )

        assert result.is_ok()
        rating_result = result.ok_value

        # Verify performance requirement
        assert rating_result.calculation_time_ms < 50, (
            f"Calculation took {rating_result.calculation_time_ms}ms, "
            f"exceeds 50ms requirement"
        )

    async def test_bulk_quote_performance(self, rating_engine: RatingEngine):
        """Test performance under load with 100 concurrent quotes."""
        # Create 100 different quote scenarios
        scenarios = []
        for i in range(100):
            vehicle = create_test_vehicle(year=2020 + (i % 5))
            drivers = [create_test_driver(age=25 + (i % 40))]
            coverages = create_test_coverage_selections()

            scenarios.append(
                {
                    "state": ["CA", "TX", "NY"][i % 3],
                    "product_type": "auto",
                    "vehicle_info": vehicle,
                    "drivers": drivers,
                    "coverage_selections": coverages,
                }
            )

        # Execute all scenarios concurrently
        start_time = datetime.now()

        tasks = [rating_engine.calculate_premium(**scenario) for scenario in scenarios]
        results = await asyncio.gather(*tasks)

        end_time = datetime.now()
        total_time_ms = (end_time - start_time).total_seconds() * 1000

        # Verify all calculations succeeded
        successful_results = [r for r in results if r.is_ok()]
        assert len(successful_results) >= 95, "At least 95% of quotes should succeed"

        # Verify individual performance
        calculation_times = [r.ok_value.calculation_time_ms for r in successful_results]

        avg_time = statistics.mean(calculation_times)
        p95_time = statistics.quantiles(calculation_times, n=20)[18]  # 95th percentile
        p99_time = statistics.quantiles(calculation_times, n=100)[98]  # 99th percentile

        assert (
            avg_time < 30
        ), f"Average calculation time {avg_time:.1f}ms exceeds 30ms target"
        assert (
            p95_time < 45
        ), f"P95 calculation time {p95_time:.1f}ms exceeds 45ms target"
        assert (
            p99_time < 50
        ), f"P99 calculation time {p99_time:.1f}ms exceeds 50ms target"

        # Verify throughput
        throughput = len(successful_results) / (total_time_ms / 1000)
        assert (
            throughput > 50
        ), f"Throughput {throughput:.1f} quotes/sec below 50/sec target"

    async def test_performance_monitoring(self, rating_engine: RatingEngine):
        """Test that performance monitoring works correctly."""
        # Perform several calculations
        vehicle = create_test_vehicle()
        drivers = [create_test_driver()]
        coverages = create_test_coverage_selections()

        for _ in range(10):
            await rating_engine.calculate_premium(
                state="CA",
                product_type="auto",
                vehicle_info=vehicle,
                drivers=drivers,
                coverage_selections=coverages,
            )

        # Get performance metrics
        metrics = rating_engine.get_performance_metrics()

        assert "average_calculation_time_ms" in metrics
        assert "p95_calculation_time_ms" in metrics
        assert "p99_calculation_time_ms" in metrics
        assert "cache_hit_rate" in metrics
        assert "total_calculations" in metrics

        assert metrics["total_calculations"] >= 10
        assert 0 <= metrics["cache_hit_rate"] <= 1
        assert metrics["average_calculation_time_ms"] > 0

    async def test_performance_target_validation(self, rating_engine: RatingEngine):
        """Test performance target validation."""
        # Perform calculations to generate metrics
        vehicle = create_test_vehicle()
        drivers = [create_test_driver()]
        coverages = create_test_coverage_selections()

        for _ in range(20):
            await rating_engine.calculate_premium(
                state="CA",
                product_type="auto",
                vehicle_info=vehicle,
                drivers=drivers,
                coverage_selections=coverages,
            )

        # Check if performance target is met
        target_met = rating_engine.is_performance_target_met(50)
        assert isinstance(target_met, bool)

        # Should meet target with properly optimized engine
        assert target_met, "Rating engine should meet 50ms performance target"

    async def test_cache_warming_performance(self, rating_engine: RatingEngine):
        """Test that cache warming improves performance."""
        # Perform calculation before cache warming
        vehicle = create_test_vehicle()
        drivers = [create_test_driver()]
        coverages = create_test_coverage_selections()

        result1 = await rating_engine.calculate_premium(
            state="CA",
            product_type="auto",
            vehicle_info=vehicle,
            drivers=drivers,
            coverage_selections=coverages,
        )

        time_before_warming = result1.ok_value.calculation_time_ms

        # Warm caches
        warm_result = await rating_engine.warm_caches()
        assert warm_result.is_ok()
        assert warm_result.ok_value > 0  # Some scenarios should be warmed

        # Perform same calculation after warming
        result2 = await rating_engine.calculate_premium(
            state="CA",
            product_type="auto",
            vehicle_info=vehicle,
            drivers=drivers,
            coverage_selections=coverages,
        )

        time_after_warming = result2.ok_value.calculation_time_ms

        # Performance should improve or stay the same after warming
        assert time_after_warming <= time_before_warming + 5  # Allow 5ms tolerance

    async def test_complex_scenario_performance(self, rating_engine: RatingEngine):
        """Test performance with complex rating scenarios."""
        # Create complex scenario with multiple drivers and coverages
        vehicle = create_test_vehicle(
            year=2020,
            annual_mileage=15000,
            safety_features=["abs", "airbags", "blind_spot", "automatic_braking"],
            anti_theft=True,
        )

        drivers = [
            create_test_driver(
                age=30,
                years_licensed=12,
                violations_3_years=0,
                accidents_3_years=0,
                good_student=False,
            ),
            create_test_driver(
                age=45,
                years_licensed=25,
                violations_3_years=1,
                accidents_3_years=0,
                good_student=False,
            ),
        ]

        coverages = [
            CoverageSelection(
                coverage_type=CoverageType.LIABILITY,
                limit=Decimal("100000"),
            ),
            CoverageSelection(
                coverage_type=CoverageType.COLLISION,
                limit=Decimal("50000"),
                deductible=Decimal("500"),
            ),
            CoverageSelection(
                coverage_type=CoverageType.COMPREHENSIVE,
                limit=Decimal("50000"),
                deductible=Decimal("250"),
            ),
            CoverageSelection(
                coverage_type=CoverageType.MEDICAL,
                limit=Decimal("10000"),
            ),
            CoverageSelection(
                coverage_type=CoverageType.UNINSURED_MOTORIST,
                limit=Decimal("100000"),
            ),
            CoverageSelection(
                coverage_type=CoverageType.RENTAL,
                limit=Decimal("1000"),
            ),
        ]

        # Test with customer ID for additional factor calculations
        customer_id = uuid4()

        result = await rating_engine.calculate_premium(
            state="CA",
            product_type="auto",
            vehicle_info=vehicle,
            drivers=drivers,
            coverage_selections=coverages,
            customer_id=customer_id,
        )

        assert result.is_ok()
        rating_result = result.ok_value

        # Even complex scenarios should meet performance requirement
        assert rating_result.calculation_time_ms < 50, (
            f"Complex scenario took {rating_result.calculation_time_ms}ms, "
            f"exceeds 50ms requirement"
        )

        # Verify comprehensive calculation
        assert rating_result.total_premium > 0
        assert len(rating_result.coverage_premiums) == len(coverages)
        assert len(rating_result.factors) > 0

    async def test_performance_optimization_recommendations(
        self, rating_engine: RatingEngine
    ):
        """Test performance optimization recommendations."""
        # Generate some calculations to have data for analysis
        vehicle = create_test_vehicle()
        drivers = [create_test_driver()]
        coverages = create_test_coverage_selections()

        for _ in range(30):
            await rating_engine.calculate_premium(
                state="CA",
                product_type="auto",
                vehicle_info=vehicle,
                drivers=drivers,
                coverage_selections=coverages,
            )

        # Get optimization recommendations
        optimization_result = await rating_engine.optimize_performance()
        assert optimization_result.is_ok()

        recommendations = optimization_result.ok_value
        assert isinstance(recommendations, list)

        # Recommendations should be strings
        for recommendation in recommendations:
            assert isinstance(recommendation, str)
            assert len(recommendation) > 0

    async def test_state_specific_performance(self, rating_engine: RatingEngine):
        """Test performance across different states."""
        vehicle = create_test_vehicle()
        drivers = [create_test_driver()]
        coverages = create_test_coverage_selections()

        states = ["CA", "TX", "NY", "FL"]
        state_times = {}

        for state in states:
            result = await rating_engine.calculate_premium(
                state=state,
                product_type="auto",
                vehicle_info=vehicle,
                drivers=drivers,
                coverage_selections=coverages,
            )

            assert result.is_ok()
            state_times[state] = result.ok_value.calculation_time_ms

            # Each state should meet performance requirement
            assert result.ok_value.calculation_time_ms < 50, (
                f"State {state} calculation took "
                f"{result.ok_value.calculation_time_ms}ms"
            )

        # Performance should be consistent across states
        max_time = max(state_times.values())
        min_time = min(state_times.values())
        time_variance = max_time - min_time

        assert (
            time_variance < 30
        ), f"Performance variance {time_variance}ms across states too high"

    async def test_memory_efficiency(self, rating_engine: RatingEngine):
        """Test that rating engine is memory efficient."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Perform 1000 calculations
        drivers = [create_test_driver()]
        coverages = create_test_coverage_selections()

        for i in range(1000):
            # Vary the data slightly to avoid excessive caching
            vehicle_variant = create_test_vehicle(year=2020 + (i % 5))
            driver_variant = create_test_driver(age=25 + (i % 30))

            result = await rating_engine.calculate_premium(
                state=["CA", "TX", "NY"][i % 3],
                product_type="auto",
                vehicle_info=vehicle_variant,
                drivers=[driver_variant],
                coverage_selections=coverages,
            )

            assert result.is_ok()

        final_memory = process.memory_info().rss
        memory_growth = final_memory - initial_memory

        # Memory growth should be reasonable (< 50MB for 1000 calculations)
        memory_growth_mb = memory_growth / (1024 * 1024)
        assert (
            memory_growth_mb < 50
        ), f"Memory growth {memory_growth_mb:.1f}MB exceeds 50MB limit"
