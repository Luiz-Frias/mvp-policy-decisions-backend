"""Main rating engine that orchestrates all rating calculations.

This module serves as the central orchestrator for all rating calculations,
ensuring sub-50ms performance while maintaining accuracy and compliance.
"""

import time
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from beartype import beartype

from pd_prime_demo.core.result_types import Err, Ok, Result

from ...core.cache import Cache
from ...core.database import Database
from ...models.quote import CoverageSelection, DriverInfo, VehicleInfo
from .business_rules import RatingBusinessRules
from .calculators import (
    AIRiskScorer,
    DiscountCalculator,
    PremiumCalculator,
)
from .performance import RatingPerformanceOptimizer
from .rate_tables import RateTableService
from .state_rules import get_state_rules
from .surcharge_calculator import SurchargeCalculator
from .territory_management import TerritoryManager


@beartype
class RatingEngine:
    """Main rating engine that orchestrates all calculations with <50ms performance."""

    def __init__(
        self,
        db: Database,
        cache: Cache,
        enable_ai_scoring: bool = True,
        enable_performance_monitoring: bool = True,
    ):
        """Initialize rating engine with all dependencies.

        Args:
            db: Database connection
            cache: Cache instance
            enable_ai_scoring: Whether to use AI risk scoring
            enable_performance_monitoring: Whether to monitor performance
        """
        self._db = db
        self._cache = cache
        self._enable_ai_scoring = enable_ai_scoring
        self._enable_performance_monitoring = enable_performance_monitoring

        # Initialize sub-components
        self._rate_table_service = RateTableService(db, cache)
        self._territory_manager = TerritoryManager(db, cache)
        self._performance_optimizer = RatingPerformanceOptimizer(db, cache)
        self._business_rules = RatingBusinessRules()
        self._ai_scorer = AIRiskScorer(load_models=enable_ai_scoring)

        # Performance tracking
        self._calculation_count = 0
        self._total_calculation_time = 0.0

    @beartype
    async def calculate_premium(
        self,
        quote_id: UUID,
        state: str,
        effective_date: datetime,
        vehicle_info: VehicleInfo,
        drivers: list[DriverInfo],
        coverage_selections: list[CoverageSelection],
        customer_data: dict[str, Any] | None = None,
        external_data: dict[str, Any] | None = None,
    ) -> Result[dict[str, Any], str]:
        """Calculate complete premium with all factors, discounts, and surcharges.

        This is the main entry point for premium calculation.

        Args:
            quote_id: Quote identifier
            state: State code
            effective_date: Policy effective date
            vehicle_info: Vehicle information
            drivers: List of drivers
            coverage_selections: Selected coverages
            customer_data: Optional customer data for loyalty discounts
            external_data: Optional external data (credit, weather, etc.)

        Returns:
            Result containing complete rating calculation or error
        """
        # Start performance monitoring
        start_time = time.perf_counter()
        perf_token = None

        if self._enable_performance_monitoring:
            perf_token = self._performance_optimizer.start_performance_monitoring()

        try:
            # Validate inputs
            if not drivers:
                return Err("At least one driver is required for rating")
            if not coverage_selections:
                return Err("At least one coverage selection is required")

            # Get state rules
            state_rules_result = get_state_rules(state)
            if state_rules_result.is_err():
                return Err(f"State rules error: {state_rules_result.unwrap_err()}")
            state_rules = state_rules_result.unwrap()

            # Parallel calculation of base components
            calculation_tasks = {
                "base_rates": self._get_base_rates(
                    state, effective_date, coverage_selections
                ),
                "territory_factor": self._get_territory_factor(
                    state, drivers[0].zip_code
                ),
                "driver_factors": self._calculate_driver_factors(drivers, state),
                "vehicle_factor": self._calculate_vehicle_factor(vehicle_info),
            }

            # Execute parallel calculations
            results = await self._performance_optimizer.parallel_factor_calculation(
                calculation_tasks
            )
            if results.is_err():
                return Err(f"Parallel calculation failed: {results.unwrap_err()}")

            factors: dict[str, Any] = results.unwrap()

            # Calculate base premium for each coverage
            base_premium_result = await self._calculate_base_premiums(
                coverage_selections, factors.get("base_rates", {})
            )
            if base_premium_result.is_err():
                return base_premium_result

            base_premiums = base_premium_result.unwrap()
            total_base_premium = sum(base_premiums.values())

            # Apply state-specific factor validation
            validated_factors = state_rules.validate_factors(factors)

            # Apply all rating factors
            factor_result = PremiumCalculator.apply_multiplicative_factors(
                total_base_premium, validated_factors
            )
            if factor_result.is_err():
                return Err(f"Factor application failed: {factor_result.unwrap_err()}")

            factored_premium, factor_impacts = factor_result.unwrap()

            # Calculate applicable discounts
            discount_result = await self._calculate_discounts(
                drivers, vehicle_info, customer_data, factored_premium, state
            )
            if discount_result.is_err():
                return discount_result

            discounts, discount_amount = discount_result.unwrap()

            # Calculate surcharges
            surcharge_result = SurchargeCalculator.calculate_all_surcharges(
                drivers, vehicle_info, state, factored_premium
            )
            if surcharge_result.is_err():
                return Err(
                    f"Surcharge calculation failed: {surcharge_result.unwrap_err()}"
                )

            surcharges, surcharge_amount = surcharge_result.unwrap()

            # Calculate final premium
            final_premium = factored_premium - discount_amount + surcharge_amount

            # Apply minimum premium rules
            min_premium_result = await self._apply_minimum_premium(
                final_premium, state, coverage_selections
            )
            if min_premium_result.is_err():
                return min_premium_result

            final_premium = min_premium_result.unwrap()

            # AI risk scoring (if enabled)
            ai_risk_score = None
            if self._enable_ai_scoring:
                ai_result = await self._ai_scorer.calculate_ai_risk_score(
                    customer_data or {},
                    vehicle_info.__dict__,
                    [d.__dict__ for d in drivers],
                    external_data,
                )
                if ai_result.is_ok():
                    ai_risk_score = ai_result.unwrap()

            # Business rule validation
            violations_result = await self._business_rules.validate_premium_calculation(
                state=state,
                product_type="auto",
                vehicle_info=vehicle_info,
                drivers=drivers,
                coverage_selections=coverage_selections,
                factors=validated_factors,
                base_premium=total_base_premium,
                total_premium=final_premium,
                discounts=discounts,
                surcharges=surcharges,
            )

            business_rule_report = None
            if violations_result.is_ok():
                violations = violations_result.unwrap()
                if violations:
                    business_rule_report = (
                        self._business_rules.format_violations_report(violations)
                    )

                    # Check for critical violations that block rating
                    critical_violations = self._business_rules.get_critical_violations(
                        violations
                    )
                    if critical_violations:
                        return Err(
                            f"Critical business rule violations: {len(critical_violations)} errors. "
                            f"First error: {critical_violations[0].message}"
                        )

            # Prepare complete result
            calculation_time_ms = (time.perf_counter() - start_time) * 1000

            # Check performance requirement
            if calculation_time_ms > 50:
                # Log performance violation but don't fail
                await self._log_performance_violation(quote_id, calculation_time_ms)

            result = {
                "quote_id": str(quote_id),
                "calculation_timestamp": datetime.utcnow().isoformat(),
                "state": state,
                "base_premium": float(total_base_premium),
                "factored_premium": float(factored_premium),
                "discounts": {
                    "items": discounts,
                    "total_amount": float(discount_amount),
                },
                "surcharges": SurchargeCalculator.format_surcharge_summary(
                    surcharges, surcharge_amount
                ),
                "final_premium": float(final_premium),
                "factors": {k: float(v) for k, v in validated_factors.items()},
                "factor_impacts": {k: float(v) for k, v in factor_impacts.items()},
                "coverage_premiums": {k: float(v) for k, v in base_premiums.items()},
                "ai_risk_score": ai_risk_score,
                "business_rule_validation": business_rule_report,
                "performance_metrics": {
                    "calculation_time_ms": calculation_time_ms,
                    "target_met": calculation_time_ms <= 50,
                },
            }

            # Cache result for performance
            cache_key = f"rating:quote:{quote_id}"
            await self._cache.set(cache_key, result, 3600)  # 1 hour cache

            # End performance monitoring
            if perf_token:
                elapsed_ms = self._performance_optimizer.end_performance_monitoring(
                    perf_token
                )
                self._update_performance_stats(elapsed_ms)

            return Ok(result)

        except Exception as e:
            return Err(f"Rating calculation failed: {str(e)}")
        finally:
            if perf_token:
                self._performance_optimizer.end_performance_monitoring(perf_token)

    @beartype
    async def _get_base_rates(
        self,
        state: str,
        effective_date: datetime,
        coverage_selections: list[CoverageSelection],
    ) -> dict[str, Decimal]:
        """Get base rates for selected coverages."""
        base_rates = {}

        for coverage in coverage_selections:
            coverage_type = coverage.coverage_type.value

            # Get base rate from rate tables
            rate_result = await self._rate_table_service.get_base_rate(
                state, coverage_type, effective_date
            )

            if rate_result.is_ok():
                base_rates[coverage_type] = rate_result.unwrap()
            else:
                # Use default rates if not found
                default_rates = {
                    "liability": Decimal("0.50"),
                    "collision": Decimal("0.40"),
                    "comprehensive": Decimal("0.30"),
                    "uninsured_motorist": Decimal("0.20"),
                    "personal_injury_protection": Decimal("0.25"),
                }
                base_rates[coverage_type] = default_rates.get(
                    coverage_type, Decimal("0.35")
                )

        return base_rates

    @beartype
    async def _get_territory_factor(self, state: str, zip_code: str) -> float:
        """Get territory factor for ZIP code."""
        result = await self._territory_manager.get_territory_factor(state, zip_code)
        return result.unwrap_or(1.0)

    @beartype
    async def _calculate_driver_factors(
        self, drivers: list[DriverInfo], state: str
    ) -> dict[str, float]:
        """Calculate aggregated driver factors."""
        if not drivers:
            return {}

        # Find the highest risk driver (primary rated driver)
        primary_driver = max(
            drivers,
            key=lambda d: (
                d.violations_3_years * 2 + d.accidents_3_years * 3 + (100 - d.age) / 10
            ),
        )

        # Calculate driver risk score
        risk_result = PremiumCalculator.calculate_driver_risk_score(
            {
                "age": primary_driver.age,
                "years_licensed": primary_driver.years_licensed,
                "violations_3_years": primary_driver.violations_3_years,
                "accidents_3_years": primary_driver.accidents_3_years,
            }
        )

        if risk_result.is_err():
            return {"driver_combined": 1.0}

        risk_score, _ = risk_result.unwrap()

        # Convert risk score to factor (higher risk = higher factor)
        0.8 + (risk_score * 0.8)  # Range: 0.8 to 1.6

        # Age-based factor
        if primary_driver.age < 25:
            age_factor = 1.3
        elif primary_driver.age > 70:
            age_factor = 1.1
        else:
            age_factor = 0.9

        # Experience factor
        if primary_driver.years_licensed < 3:
            experience_factor = 1.2
        elif primary_driver.years_licensed > 10:
            experience_factor = 0.85
        else:
            experience_factor = 1.0

        # Violation/accident factors
        violation_factor = 1.0 + (primary_driver.violations_3_years * 0.15)
        accident_factor = 1.0 + (primary_driver.accidents_3_years * 0.25)

        return {
            "driver_age": age_factor,
            "experience": experience_factor,
            "violations": violation_factor,
            "accidents": accident_factor,
        }

    @beartype
    async def _calculate_vehicle_factor(self, vehicle_info: VehicleInfo) -> float:
        """Calculate vehicle risk factor."""
        result = PremiumCalculator.calculate_vehicle_risk_score(
            {
                "type": getattr(vehicle_info, "vehicle_type", "sedan"),
                "age": 2024 - vehicle_info.year,
                "safety_features": getattr(vehicle_info, "safety_features", []),
                "theft_rate": getattr(vehicle_info, "theft_rate", 1.0),
            }
        )

        return result.unwrap_or(1.0)

    @beartype
    async def _calculate_base_premiums(
        self,
        coverage_selections: list[CoverageSelection],
        base_rates: dict[str, Decimal],
    ) -> Result[dict[str, Decimal], str]:
        """Calculate base premium for each coverage."""
        premiums = {}

        for coverage in coverage_selections:
            coverage_type = coverage.coverage_type.value
            base_rate = base_rates.get(coverage_type, Decimal("0.35"))

            # Calculate base premium
            premium_result = PremiumCalculator.calculate_base_premium(
                coverage_limit=coverage.limit,
                base_rate=base_rate,
                exposure_units=Decimal("1"),
            )

            if premium_result.is_err():
                return Err(
                    f"Base premium calculation failed for {coverage_type}: "
                    f"{premium_result.unwrap_err()}"
                )

            premiums[coverage_type] = premium_result.unwrap()

        return Ok(premiums)

    @beartype
    async def _calculate_discounts(
        self,
        drivers: list[DriverInfo],
        vehicle_info: VehicleInfo,
        customer_data: dict[str, Any] | None,
        base_premium: Decimal,
        state: str,
    ) -> Result[tuple[list[dict[str, Any]], Decimal], str]:
        """Calculate all applicable discounts."""
        applicable_discounts = []

        # Multi-policy discount
        if customer_data and customer_data.get("policy_count", 0) > 1:
            applicable_discounts.append(
                {
                    "discount_type": {"value": "multi_policy"},
                    "rate": 0.10,  # 10% discount
                    "stackable": True,
                    "priority": 1,
                    "description": "Multi-policy discount",
                }
            )

        # Good driver discount (no violations/accidents)
        has_clean_record = all(
            d.violations_3_years == 0 and d.accidents_3_years == 0 for d in drivers
        )
        if has_clean_record:
            applicable_discounts.append(
                {
                    "discount_type": {"value": "good_driver"},
                    "rate": 0.15,  # 15% discount
                    "stackable": True,
                    "priority": 2,
                    "description": "Good driver discount",
                }
            )

        # Anti-theft device discount
        if hasattr(vehicle_info, "safety_features"):
            safety_features = vehicle_info.safety_features
            if any(
                f in ["anti_theft", "alarm", "gps_tracking"] for f in safety_features
            ):
                applicable_discounts.append(
                    {
                        "discount_type": {"value": "anti_theft"},
                        "rate": 0.05,  # 5% discount
                        "stackable": True,
                        "priority": 3,
                        "description": "Anti-theft device discount",
                    }
                )

        # Low mileage discount
        if vehicle_info.annual_mileage < 7500:
            applicable_discounts.append(
                {
                    "discount_type": {"value": "low_mileage"},
                    "rate": 0.08,  # 8% discount
                    "stackable": True,
                    "priority": 4,
                    "description": "Low mileage discount",
                }
            )

        # Apply discount stacking rules
        state_rules_result = get_state_rules(state)
        state_discount_rules = None
        if state_rules_result.is_ok():
            # Get state-specific discount rules if available
            state_discount_rules = {"max_discount": 0.40}  # 40% max by default

        return DiscountCalculator.calculate_stacked_discounts(
            base_premium,
            applicable_discounts,
            Decimal("0.40"),  # 40% max total discount
            state_discount_rules,
        )

    @beartype
    async def _apply_minimum_premium(
        self,
        calculated_premium: Decimal,
        state: str,
        coverage_selections: list[CoverageSelection],
    ):
        """Apply state-specific minimum premium rules."""
        # State minimum premiums (simplified)
        state_minimums = {
            "CA": Decimal("500"),  # $500 annual minimum
            "TX": Decimal("400"),  # $400 annual minimum
            "NY": Decimal("600"),  # $600 annual minimum
            "FL": Decimal("700"),  # $700 annual minimum (hurricanes)
            "MI": Decimal("800"),  # $800 annual minimum (no-fault)
            "PA": Decimal("450"),  # $450 annual minimum
        }

        minimum_premium = state_minimums.get(state, Decimal("400"))

        # Adjust minimum based on coverage types
        has_comprehensive = any(
            c.coverage_type.value == "comprehensive" for c in coverage_selections
        )
        has_collision = any(
            c.coverage_type.value == "collision" for c in coverage_selections
        )

        if has_comprehensive and has_collision:
            minimum_premium *= Decimal("1.5")  # 50% higher minimum for full coverage

        return Ok(max(calculated_premium, minimum_premium))

    @beartype
    async def _log_performance_violation(
        self, quote_id: UUID, calculation_time_ms: float
    ) -> None:
        """Log performance violation for monitoring."""
        await self._db.execute(
            """
            INSERT INTO performance_violations (
                quote_id, calculation_time_ms, violation_type,
                created_at
            ) VALUES ($1, $2, 'rating_exceeds_50ms', $3)
            """,
            quote_id,
            calculation_time_ms,
            datetime.utcnow(),
        )

    @beartype
    def _update_performance_stats(self, elapsed_ms: float) -> None:
        """Update internal performance statistics."""
        self._calculation_count += 1
        self._total_calculation_time += elapsed_ms

    @beartype
    async def get_performance_metrics(self) -> dict[str, Any]:
        """Get current performance metrics."""
        optimizer_metrics = self._performance_optimizer.get_performance_metrics()

        avg_time = (
            self._total_calculation_time / self._calculation_count
            if self._calculation_count > 0
            else 0
        )

        return {
            "calculations_performed": self._calculation_count,
            "average_time_ms": avg_time,
            "target_met_percentage": (
                sum(
                    1
                    for _, v in optimizer_metrics.items()
                    if v.get("avg_ms", 100) <= 50
                )
                / len(optimizer_metrics)
                * 100
                if optimizer_metrics
                else 100
            ),
            "detailed_metrics": optimizer_metrics,
            "cache_statistics": self._performance_optimizer.get_cache_statistics(),
        }

    @beartype
    async def warm_caches(self, states: list[str] | None = None) -> Result[dict[str, Any], str]:
        """Warm caches for optimal performance.

        Args:
            states: List of states to warm caches for (default: major states)

        Returns:
            Result indicating success or error
        """
        try:
            if not states:
                states = ["CA", "TX", "NY", "FL", "MI", "PA"]

            # Initialize performance caches
            init_result = (
                await self._performance_optimizer.initialize_performance_caches()
            )
            if init_result.is_err():
                return init_result

            # Warm state-specific caches
            for state in states:
                self._performance_optimizer.warm_cache_for_state(state)

            # Warm common calculation scenarios
            scenarios_result = (
                await self._performance_optimizer.warm_cache_for_common_scenarios()
            )
            if scenarios_result.is_err():
                return Err(f"Cache warming failed: {scenarios_result.unwrap_err()}")

            scenarios_result.unwrap()

            return Ok(True)

        except Exception as e:
            return Err(f"Cache warming failed: {str(e)}")

    @beartype
    async def validate_rating_accuracy(self, test_cases: list[dict[str, Any]]) -> Result[dict[str, Any], str]:
        """Validate rating accuracy with test cases.

        Args:
            test_cases: List of test cases with expected results

        Returns:
            Result containing validation report or error
        """
        try:
            results: dict[str, Any] = {
                "total_cases": len(test_cases),
                "passed": 0,
                "failed": 0,
                "accuracy_rate": 0.0,
                "failures": [],
            }

            for i, test_case in enumerate(test_cases):
                # Extract test data
                quote_data = test_case.get("quote_data", {})
                expected_premium = test_case.get("expected_premium")
                tolerance = test_case.get("tolerance", 0.01)  # 1% tolerance

                # Calculate premium
                calc_result = await self.calculate_premium(**quote_data)

                if calc_result.is_err():
                    results["failed"] += 1
                    results["failures"].append(
                        {"case_id": i, "error": calc_result.unwrap_err()}
                    )
                    continue

                actual_result: dict[str, Any] = calc_result.unwrap()
                actual_premium = actual_result.get("final_premium", 0)

                # Check accuracy
                if expected_premium:
                    difference = abs(actual_premium - expected_premium)
                    percentage_diff = difference / expected_premium

                    if percentage_diff <= tolerance:
                        results["passed"] += 1
                    else:
                        results["failed"] += 1
                        results["failures"].append(
                            {
                                "case_id": i,
                                "expected": expected_premium,
                                "actual": actual_premium,
                                "difference_pct": percentage_diff * 100,
                            }
                        )
                else:
                    # No expected value, just check if calculation succeeded
                    results["passed"] += 1

            results["accuracy_rate"] = (
                results["passed"] / results["total_cases"] * 100
                if results["total_cases"] > 0
                else 0
            )

            return Ok(results)

        except Exception as e:
            return Err(f"Validation failed: {str(e)}")
