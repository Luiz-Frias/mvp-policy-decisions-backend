# PolicyCore - Policy Decision Management System
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.
"""Main rating engine that orchestrates all rating calculations.

This module serves as the central orchestrator for all rating calculations,
ensuring sub-50ms performance while maintaining accuracy and compliance.
"""

import time
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from beartype import beartype
from pydantic import Field

from pd_prime_demo.core.cache import Cache
from pd_prime_demo.core.database import Database
from pd_prime_demo.core.result_types import Err, Ok, Result
from pd_prime_demo.models.base import BaseModelConfig

from ...models.quote import CoverageSelection, DriverInfo, VehicleInfo
from ...schemas.rating import PerformanceMetrics
from .business_rules import RatingBusinessRules
from .calculators import AIRiskScorer, DiscountCalculator, PremiumCalculator
from .performance import RatingPerformanceOptimizer
from .rate_tables import RateTableService
from .state_rules import get_state_rules
from .surcharge_calculator import SurchargeCalculator
from .territory_management import TerritoryManager

# Rating engine models


@beartype
class CustomerData(BaseModelConfig):
    """Customer data for rating calculations."""

    customer_id: str | None = Field(default=None, description="Customer identifier")
    loyalty_years: int = Field(default=0, ge=0, description="Years as customer")
    claims_history: list[str] = Field(
        default_factory=list, description="Previous claims"
    )
    credit_score: int | None = Field(
        default=None, ge=300, le=850, description="Credit score"
    )


@beartype
class ExternalData(BaseModelConfig):
    """External data for rating calculations."""

    weather_risk_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Weather risk score"
    )
    traffic_density_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="Traffic density score"
    )
    crime_index: float | None = Field(
        default=None, ge=0.0, description="Area crime index"
    )


@beartype
class BaseRates(BaseModelConfig):
    """Base rates for coverage types."""

    bodily_injury: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    property_damage: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    collision: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    comprehensive: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    uninsured_motorist: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    medical_payments: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))


@beartype
class RatingFactors(BaseModelConfig):
    """Collection of rating factors."""

    base_rates: BaseRates = Field(default_factory=BaseRates)
    territory_factor: float = Field(default=1.0, gt=0)
    driver_factors: list[float] = Field(default_factory=list)
    vehicle_factor: float = Field(default=1.0, gt=0)


@beartype
class DiscountSummary(BaseModelConfig):
    """Summary of applied discounts."""

    items: list[str] = Field(
        default_factory=list, description="List of applied discounts"
    )
    total_amount: float = Field(default=0.0, ge=0, description="Total discount amount")


@beartype
class SurchargeSummary(BaseModelConfig):
    """Summary of applied surcharges."""

    items: list[str] = Field(
        default_factory=list, description="List of applied surcharges"
    )
    total_amount: float = Field(default=0.0, ge=0, description="Total surcharge amount")


@beartype
class CoverageRates(BaseModelConfig):
    """Base rates mapping for coverages."""

    liability: Decimal = Field(default=Decimal("0.50"), ge=Decimal("0"))
    collision: Decimal = Field(default=Decimal("0.40"), ge=Decimal("0"))
    comprehensive: Decimal = Field(default=Decimal("0.30"), ge=Decimal("0"))
    uninsured_motorist: Decimal = Field(default=Decimal("0.20"), ge=Decimal("0"))
    personal_injury_protection: Decimal = Field(
        default=Decimal("0.25"), ge=Decimal("0")
    )


@beartype
class DriverFactors(BaseModelConfig):
    """Driver risk factors."""

    driver_age: float = Field(default=1.0, gt=0)
    experience: float = Field(default=1.0, gt=0)
    violations: float = Field(default=1.0, gt=0)
    accidents: float = Field(default=1.0, gt=0)


@beartype
class CoveragePremiums(BaseModelConfig):
    """Premiums by coverage type."""

    liability: Decimal | None = Field(default=None, ge=Decimal("0"))
    collision: Decimal | None = Field(default=None, ge=Decimal("0"))
    comprehensive: Decimal | None = Field(default=None, ge=Decimal("0"))
    uninsured_motorist: Decimal | None = Field(default=None, ge=Decimal("0"))
    personal_injury_protection: Decimal | None = Field(default=None, ge=Decimal("0"))


@beartype
class DiscountInfo(BaseModelConfig):
    """Discount information."""

    discount_type: str = Field(..., description="Type of discount")
    rate: float = Field(..., ge=0, le=1, description="Discount rate")
    stackable: bool = Field(default=True, description="Whether discount is stackable")
    priority: int = Field(..., ge=1, description="Priority for stacking")
    description: str = Field(..., description="Discount description")


@beartype
class DetailedMetrics(BaseModelConfig):
    """Detailed performance metrics."""

    min_time_ms: float = Field(default=0.0, ge=0)
    max_time_ms: float = Field(default=0.0, ge=0)
    p50_time_ms: float = Field(default=0.0, ge=0)
    p95_time_ms: float = Field(default=0.0, ge=0)
    p99_time_ms: float = Field(default=0.0, ge=0)


@beartype
class CacheStatistics(BaseModelConfig):
    """Cache performance statistics."""

    hit_rate: float = Field(default=0.0, ge=0, le=1)
    miss_rate: float = Field(default=0.0, ge=0, le=1)
    total_hits: int = Field(default=0, ge=0)
    total_misses: int = Field(default=0, ge=0)


@beartype
class PerformanceStats(BaseModelConfig):
    """Performance statistics data."""

    calculations_performed: int = Field(..., ge=0)
    average_time_ms: float = Field(..., ge=0)
    target_met_percentage: float = Field(..., ge=0, le=100)
    detailed_metrics: DetailedMetrics = Field(default_factory=DetailedMetrics)
    cache_statistics: CacheStatistics = Field(default_factory=CacheStatistics)


@beartype
class CacheWarmingResult(BaseModelConfig):
    """Result of cache warming operation."""

    cache_warming_completed: bool = Field(...)
    states_warmed: list[str] = Field(default_factory=list)


@beartype
class QuoteTestData(BaseModelConfig):
    """Quote data for testing."""

    quote_id: str = Field(..., description="Quote identifier")
    state: str = Field(..., min_length=2, max_length=2)
    vehicle_year: int = Field(..., ge=1900, le=2030)
    driver_age: int = Field(..., ge=16, le=100)
    coverage_type: str = Field(..., description="Coverage type")


@beartype
class TestCase(BaseModelConfig):
    """Test case for rating validation."""

    quote_data: QuoteTestData = Field(..., description="Quote data for test")
    expected_premium: Decimal | None = Field(default=None, ge=Decimal("0"))
    tolerance: float = Field(default=0.01, gt=0, le=1)


@beartype
class ValidationFailure(BaseModelConfig):
    """Validation failure details."""

    case_id: int = Field(..., ge=0)
    error: str | None = Field(default=None)
    expected: Decimal | None = Field(default=None)
    actual: Decimal | None = Field(default=None)
    difference_pct: float | None = Field(default=None)


@beartype
class ValidationResults(BaseModelConfig):
    """Validation results summary."""

    total_cases: int = Field(..., ge=0)
    passed: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    accuracy_rate: float = Field(..., ge=0, le=100)
    failures: list[ValidationFailure] = Field(default_factory=list)


@beartype
class RatingCalculationResult(BaseModelConfig):
    """Complete rating calculation result."""

    quote_id: str = Field(description="Quote identifier")
    calculation_timestamp: str = Field(description="ISO timestamp of calculation")
    state: str = Field(min_length=2, max_length=2, description="State code")
    base_premium: float = Field(ge=0, description="Base premium amount")
    factored_premium: float = Field(ge=0, description="Premium after factors")
    discounts: DiscountSummary = Field(description="Applied discounts")
    surcharges: SurchargeSummary = Field(description="Applied surcharges")
    final_premium: float = Field(ge=0, description="Final premium amount")
    factors: dict[str, float] = Field(
        default_factory=dict, description="Applied rating factors"
    )
    factor_impacts: dict[str, float] = Field(
        default_factory=dict, description="Factor impact amounts"
    )
    coverage_premiums: dict[str, float] = Field(
        default_factory=dict, description="Premium by coverage"
    )
    ai_risk_score: float | None = Field(
        default=None, ge=0.0, le=1.0, description="AI risk score"
    )
    business_rule_validation: str | None = Field(
        default=None, description="Business rule validation report"
    )
    performance_metrics: PerformanceMetrics = Field(description="Performance metrics")


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
        customer_data: CustomerData | None = None,
        external_data: ExternalData | None = None,
    ) -> Result[RatingCalculationResult, str]:
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
                "base_rates": lambda: self._get_base_rates(
                    state, effective_date, coverage_selections
                ),
                "territory_factor": lambda: self._get_territory_factor(
                    state, vehicle_info.garage_zip
                ),
                "driver_factors": lambda: self._calculate_driver_factors(
                    drivers, state
                ),
                "vehicle_factor": lambda: self._calculate_vehicle_factor(vehicle_info),
            }

            # Execute parallel calculations
            results = await self._performance_optimizer.parallel_factor_calculation(
                calculation_tasks
            )
            if results.is_err():
                return Err(f"Parallel calculation failed: {results.unwrap_err()}")

            factors_dict = results.unwrap()

            # Convert to RatingFactors model
            factors = RatingFactors(
                base_rates=factors_dict.get("base_rates", BaseRates()),
                territory_factor=factors_dict.get("territory_factor", 1.0),
                driver_factors=factors_dict.get("driver_factors", []),
                vehicle_factor=factors_dict.get("vehicle_factor", 1.0),
            )

            # Calculate base premium for each coverage
            base_premium_result = await self._calculate_base_premiums(
                coverage_selections, factors.base_rates
            )
            if base_premium_result.is_err():
                return base_premium_result

            base_premiums = base_premium_result.unwrap()
            total_base_premium = Decimal(str(sum(base_premiums.values())))

            # Apply state-specific factor validation
            # Convert factors to dict for state rules validation
            factors_dict_for_validation = {
                "territory": factors.territory_factor,
                "vehicle": factors.vehicle_factor,
            }
            if factors.driver_factors:
                factors_dict_for_validation["driver"] = sum(
                    factors.driver_factors
                ) / len(factors.driver_factors)

            validated_factors = state_rules.validate_factors(
                factors_dict_for_validation
            )

            # Apply all rating factors
            factor_result = PremiumCalculator.apply_multiplicative_factors(
                total_base_premium, validated_factors
            )
            if factor_result.is_err():
                return Err(f"Factor application failed: {factor_result.unwrap_err()}")

            factored_result = factor_result.unwrap()
            factored_premium = factored_result.final_premium
            factor_impacts = factored_result.factor_impacts

            # Calculate applicable discounts
            discount_result = await self._calculate_discounts(
                drivers, vehicle_info, customer_data, factored_premium, state
            )
            if discount_result.is_err():
                return Err(discount_result.unwrap_err())

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
                return Err(min_premium_result.unwrap_err())

            final_premium = min_premium_result.unwrap()

            # AI risk scoring (if enabled)
            ai_risk_score = None
            if self._enable_ai_scoring:
                ai_result = await self._ai_scorer.calculate_ai_risk_score(
                    customer_data or CustomerData(),
                    vehicle_info,
                    drivers,
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

            # Format surcharge summary
            surcharge_summary = SurchargeCalculator.format_surcharge_summary(
                surcharges, surcharge_amount
            )

            result = RatingCalculationResult(
                quote_id=str(quote_id),
                calculation_timestamp=datetime.utcnow().isoformat(),
                state=state,
                base_premium=float(total_base_premium),
                factored_premium=float(factored_premium),
                discounts=DiscountSummary(
                    items=discounts, total_amount=float(discount_amount)
                ),
                surcharges=SurchargeSummary(
                    items=surcharge_summary.get("items", []),
                    total_amount=surcharge_summary.get("total_amount", 0.0),
                    details=surcharge_summary.get("details", []),
                ),
                final_premium=float(final_premium),
                factors={k: float(v) for k, v in validated_factors.items()},
                factor_impacts={
                    impact.factor_name: float(impact.impact_amount)
                    for impact in factor_impacts
                },
                coverage_premiums={
                    k: float(v)
                    for k, v in (base_premiums.items() if base_premiums else [])
                },
                ai_risk_score=ai_risk_score,
                business_rule_validation=business_rule_report,
                performance_metrics=PerformanceMetrics(
                    calculation_time_ms=calculation_time_ms,
                    target_met=calculation_time_ms <= 50,
                ),
            )

            # Cache result for performance
            cache_key = f"rating:quote:{quote_id}"
            await self._cache.set(cache_key, result.model_dump(), 3600)  # 1 hour cache

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
    ) -> BaseRates:
        """Get base rates for selected coverages."""
        base_rates = BaseRates()

        for coverage in coverage_selections:
            coverage_type = coverage.coverage_type.value

            # Get base rate from rate tables
            rate_result = await self._rate_table_service.get_active_rates(
                state, "auto"  # product_type is auto
            )

            if rate_result.is_ok():
                rates_dict = rate_result.unwrap()
                if hasattr(base_rates, coverage_type):
                    setattr(
                        base_rates,
                        coverage_type,
                        rates_dict.get(coverage_type, Decimal("0.35")),
                    )
            else:
                # Use default rates if not found
                default_rates = BaseRates()
                if hasattr(base_rates, coverage_type):
                    setattr(
                        base_rates,
                        coverage_type,
                        getattr(default_rates, coverage_type, Decimal("0.35")),
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
    ) -> DriverFactors:
        """Calculate aggregated driver factors."""
        if not drivers:
            return DriverFactors()

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
            return DriverFactors()

        driver_risk_result = risk_result.unwrap()
        risk_score = driver_risk_result.risk_score

        # Convert risk score to factor (higher risk = higher factor)
        driver_risk_factor = 0.8 + (risk_score * 0.8)  # Range: 0.8 to 1.6

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

        return DriverFactors(
            driver_age=age_factor,
            experience=experience_factor,
            violations=violation_factor,
            accidents=accident_factor,
        )

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
        base_rates: CoverageRates,
    ) -> Result[CoveragePremiums, str]:
        """Calculate base premium for each coverage."""
        premiums = CoveragePremiums()

        for coverage in coverage_selections:
            coverage_type = coverage.coverage_type.value
            base_rate = getattr(base_rates, coverage_type, Decimal("0.35"))

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

            if hasattr(premiums, coverage_type):
                setattr(premiums, coverage_type, premium_result.unwrap())

        return Ok(premiums)

    @beartype
    async def _calculate_discounts(
        self,
        drivers: list[DriverInfo],
        vehicle_info: VehicleInfo,
        customer_data: CustomerData | None,
        base_premium: Decimal,
        state: str,
    ) -> Result[tuple[list[DiscountInfo], Decimal], str]:
        """Calculate all applicable discounts."""
        applicable_discounts = []

        # Multi-policy discount
        if customer_data and customer_data.policy_count > 1:
            applicable_discounts.append(
                DiscountInfo(
                    discount_type="multi_policy",
                    rate=0.10,  # 10% discount
                    stackable=True,
                    priority=1,
                    description="Multi-policy discount",
                )
            )

        # Good driver discount (no violations/accidents)
        has_clean_record = all(
            d.violations_3_years == 0 and d.accidents_3_years == 0 for d in drivers
        )
        if has_clean_record:
            applicable_discounts.append(
                DiscountInfo(
                    discount_type="good_driver",
                    rate=0.15,  # 15% discount
                    stackable=True,
                    priority=2,
                    description="Good driver discount",
                )
            )

        # Anti-theft device discount
        if hasattr(vehicle_info, "safety_features"):
            safety_features = vehicle_info.safety_features
            if any(
                f in ["anti_theft", "alarm", "gps_tracking"] for f in safety_features
            ):
                applicable_discounts.append(
                    DiscountInfo(
                        discount_type="anti_theft",
                        rate=0.05,  # 5% discount
                        stackable=True,
                        priority=3,
                        description="Anti-theft device discount",
                    )
                )

        # Low mileage discount
        if vehicle_info.annual_mileage < 7500:
            applicable_discounts.append(
                DiscountInfo(
                    discount_type="low_mileage",
                    rate=0.08,  # 8% discount
                    stackable=True,
                    priority=4,
                    description="Low mileage discount",
                )
            )

        # Apply discount stacking rules
        state_rules_result = get_state_rules(state)
        state_discount_rules = None
        if state_rules_result.is_ok():
            # Get state-specific discount rules if available
            state_discount_rules = {"max_discount": 0.40}  # 40% max by default

        # Convert DiscountInfo objects to dicts for DiscountCalculator
        discount_dicts = [discount.model_dump() for discount in applicable_discounts]
        stacked_result = DiscountCalculator.calculate_stacked_discounts(
            base_premium,
            discount_dicts,
            Decimal("0.40"),  # 40% max total discount
            state_discount_rules,
        )
        if stacked_result.is_err():
            return Err(stacked_result.unwrap_err())

        stacked_discounts = stacked_result.unwrap()
        # Return the original DiscountInfo objects that were applied
        applied_discount_infos = [
            d
            for d in applicable_discounts
            if any(
                applied.discount_type == d.discount_type
                for applied in stacked_discounts.applied_discounts
            )
        ]
        return Ok((applied_discount_infos, stacked_discounts.total_discount_amount))

    @beartype
    async def _apply_minimum_premium(
        self,
        calculated_premium: Decimal,
        state: str,
        coverage_selections: list[CoverageSelection],
    ) -> Result[Decimal, str]:
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
    async def get_performance_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics."""
        optimizer_metrics = self._performance_optimizer.get_performance_metrics()

        avg_time = (
            self._total_calculation_time / self._calculation_count
            if self._calculation_count > 0
            else 0
        )

        target_met_percentage = (
            sum(1 for _, v in optimizer_metrics.items() if v.get("avg_ms", 100) <= 50)
            / len(optimizer_metrics)
            * 100
            if optimizer_metrics
            else 100
        )

        return PerformanceMetrics(
            calculations_performed=self._calculation_count,
            average_time_ms=avg_time,
            target_met_percentage=target_met_percentage,
            detailed_metrics=optimizer_metrics,
            cache_statistics=self._performance_optimizer.get_cache_statistics(),
        )

    @beartype
    async def warm_caches(
        self, states: list[str] | None = None
    ) -> Result[CacheWarmingResult, str]:
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
                return Err(init_result.unwrap_err())

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

            return Ok(
                CacheWarmingResult(cache_warming_completed=True, states_warmed=states)
            )

        except Exception as e:
            return Err(f"Cache warming failed: {str(e)}")

    @beartype
    async def validate_rating_accuracy(
        self, test_cases: list[TestCase]
    ) -> Result[ValidationResults, str]:
        """Validate rating accuracy with test cases.

        Args:
            test_cases: List of test cases with expected results

        Returns:
            Result containing validation report or error
        """
        try:
            failures: list[ValidationFailure] = []
            passed = 0
            failed = 0

            for i, test_case in enumerate(test_cases):
                # Extract test data
                quote_data = test_case.quote_data
                expected_premium = test_case.expected_premium
                tolerance = test_case.tolerance  # 1% tolerance

                # Calculate premium
                calc_result = await self.calculate_premium(**quote_data)

                if calc_result.is_err():
                    failed += 1
                    failures.append(
                        ValidationFailure(case_id=i, error=calc_result.unwrap_err())
                    )
                    continue

                actual_result = calc_result.unwrap()
                actual_premium = actual_result.get("final_premium", Decimal("0"))

                # Check accuracy
                if expected_premium:
                    difference = abs(actual_premium - expected_premium)
                    percentage_diff = difference / expected_premium

                    if percentage_diff <= tolerance:
                        passed += 1
                    else:
                        failed += 1
                        failures.append(
                            ValidationFailure(
                                case_id=i,
                                expected=expected_premium,
                                actual=actual_premium,
                                difference_pct=percentage_diff * 100,
                            )
                        )
                else:
                    # No expected value, just check if calculation succeeded
                    passed += 1

            total_cases = len(test_cases)
            accuracy_rate = passed / total_cases * 100 if total_cases > 0 else 0

            return Ok(
                ValidationResults(
                    total_cases=total_cases,
                    passed=passed,
                    failed=failed,
                    accuracy_rate=accuracy_rate,
                    failures=failures,
                )
            )

        except Exception as e:
            return Err(f"Validation failed: {str(e)}")
