"""High-performance insurance rating engine.

This module implements the core rating engine with state-specific rules,
discount calculations, and sub-50ms performance requirements.
"""

import hashlib
import json
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    np = None

from beartype import beartype
from pydantic import Field

from pd_prime_demo.core.result_types import Err, Ok, Result, Result

from ..core.cache import Cache
from ..core.database import Database
from ..models.base import BaseModelConfig
from ..models.quote import (
    CoverageSelection,
    CoverageType,
    Discount,
    DiscountType,
    DriverInfo,
    VehicleInfo,
)
from .performance_monitor import performance_monitor
from .rating.business_rules import RatingBusinessRules
from .rating.performance_optimizer import RatingPerformanceOptimizer
from .rating.territory_management import TerritoryManager


@beartype
class RatingResult(BaseModelConfig):
    """Rating calculation result with all details."""

    base_premium: Decimal = Field(..., ge=0, decimal_places=2)
    total_premium: Decimal = Field(..., ge=0, decimal_places=2)

    # Breakdowns
    coverage_premiums: dict[CoverageType, Decimal] = Field(default_factory=dict)

    # Adjustments
    discounts: list[Discount] = Field(default_factory=list)
    total_discount_amount: Decimal = Field(Decimal("0"), ge=0, decimal_places=2)
    surcharges: list[dict[str, Any]] = Field(default_factory=list)
    total_surcharge_amount: Decimal = Field(Decimal("0"), ge=0, decimal_places=2)

    # Factors used
    factors: dict[str, float] = Field(default_factory=dict)
    tier: str = Field(...)

    # AI enhancements
    ai_risk_score: float | None = Field(None, ge=0, le=1)
    ai_risk_factors: list[str] = Field(default_factory=list)

    # Calculation metadata
    calculation_time_ms: int = Field(..., ge=0)
    rate_version: str = Field(...)
    effective_date: date = Field(...)


@beartype
class RatingEngine:
    """Core rating engine with caching and performance optimization."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize rating engine with dependencies."""
        self._db = db
        self._cache = cache
        self._cache_prefix = "rating:"
        self._rate_cache_ttl = 3600  # 1 hour

        # Preloaded data for performance
        self._base_rates: dict[str, dict[str, Decimal]] = {}
        self._discount_rules: dict[str, Any] = {}
        self._territory_factors: dict[str, float] = {}
        self._state_rules: dict[str, Any] = {}

        # Business rule validation and territory management
        self._business_rules = RatingBusinessRules()
        self._territory_manager = TerritoryManager(db, cache)

        # Performance optimizer for sub-50ms calculations
        self._performance_optimizer = RatingPerformanceOptimizer(db, cache)

    @beartype
    @performance_monitor("rating_engine_initialize")
    async def initialize(self) -> Result[bool, str]:
        """Preload rating data for performance."""
        try:
            # Load base rates
            load_rates = await self._load_base_rates()
            if isinstance(load_rates, Err):
                return load_rates

            # Load discount rules
            load_discounts = await self._load_discount_rules()
            if isinstance(load_discounts, Err):
                return load_discounts

            # Load territory factors
            load_territory = await self._load_territory_factors()
            if isinstance(load_territory, Err):
                return load_territory

            # Load state rules
            load_states = await self._load_state_rules()
            if isinstance(load_states, Err):
                return load_states

            # Initialize performance optimizer
            perf_init = (
                await self._performance_optimizer.initialize_performance_caches()
            )
            if isinstance(perf_init, Err):
                return perf_init

            # Warm cache for common scenarios
            await self._performance_optimizer.warm_cache_for_common_scenarios()

            return Ok(True)
        except Exception as e:
            return Err(f"Rating engine initialization failed: {str(e)}")

    @beartype
    @performance_monitor("calculate_premium", max_duration_ms=50)
    async def calculate_premium(
        self,
        state: str,
        product_type: str,
        vehicle_info: VehicleInfo | None,
        drivers: list[DriverInfo],
        coverage_selections: list[CoverageSelection],
        customer_id: UUID | None = None,
    ):
        """Calculate premium with all factors - MUST complete in <50ms."""
        # Start performance monitoring
        perf_token = self._performance_optimizer.start_performance_monitoring()

        try:
            # Validate inputs - FAIL FAST
            validation = self._validate_rating_inputs(
                state, product_type, drivers, coverage_selections
            )
            if isinstance(validation, Err):
                return validation

            # Check cache for recent calculation
            cache_key = self._generate_cache_key(
                state, product_type, vehicle_info, drivers, coverage_selections
            )
            cached = await self._cache.get(f"{self._cache_prefix}{cache_key}")
            if cached:
                return Ok(RatingResult(**json.loads(cached)))

            # Get base rates - NO FALLBACKS
            base_rates = await self._get_base_rates(state, product_type)
            if isinstance(base_rates, Err):
                return base_rates

            # Calculate base premium for each coverage
            coverage_premiums = {}
            total_base = Decimal("0")

            for coverage in coverage_selections:
                # EXPLICIT rate lookup - no defaults
                if coverage.coverage_type.value not in base_rates.value:
                    return Err(
                        f"No approved rate found for coverage '{coverage.coverage_type.value}' in {state}. "
                        f"Available coverages: {list(base_rates.value.keys())}. "
                        f"Admin must approve rates for this coverage type before quotes can proceed."
                    )

                base_rate = base_rates.value[coverage.coverage_type.value]
                coverage_premium = (
                    coverage.limit * base_rate / Decimal("1000")
                )  # Rate per $1000
                coverage_premiums[coverage.coverage_type] = coverage_premium.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                total_base += coverage_premium

            # Apply rating factors
            factors = await self._calculate_factors(
                state, vehicle_info, drivers, customer_id
            )
            if isinstance(factors, Err):
                return factors

            # Apply factors to base premium
            factored_premium = total_base
            for factor_name, factor_value in factors.value.items():
                factored_premium *= Decimal(str(factor_value))

            # Calculate discounts
            discounts = await self._calculate_discounts(
                state,
                product_type,
                vehicle_info,
                drivers,
                customer_id,
                factored_premium,
            )
            if isinstance(discounts, Err):
                return discounts

            total_discount = sum(d.amount for d in discounts.value)

            # Calculate surcharges
            surcharges = await self._calculate_surcharges(state, drivers, customer_id)
            if isinstance(surcharges, Err):
                return surcharges

            total_surcharge = sum(Decimal(str(s["amount"])) for s in surcharges.value)

            # Final premium calculation
            total_premium = factored_premium - total_discount + total_surcharge

            # Ensure minimum premium
            min_premium = await self._get_minimum_premium(state, product_type)
            if isinstance(min_premium, Err):
                return min_premium

            if total_premium < min_premium.value:
                total_premium = min_premium.value

            # Determine tier
            tier = self._determine_tier(factors.value, total_premium)

            # AI risk assessment (if enabled and customer exists)
            ai_risk_score = None
            ai_risk_factors = []
            if customer_id:
                ai_assessment = await self._get_ai_risk_assessment(
                    customer_id, vehicle_info, drivers
                )
                if isinstance(ai_assessment, Ok):
                    ai_risk_score = ai_assessment.value.get("score")
                    ai_risk_factors = ai_assessment.value.get("factors", [])

            # Validate business rules before finalizing result
            business_validation = (
                await self._business_rules.validate_premium_calculation(
                    state=state,
                    product_type=product_type,
                    vehicle_info=vehicle_info,
                    drivers=drivers,
                    coverage_selections=coverage_selections,
                    factors=factors.value,
                    base_premium=total_base,
                    total_premium=total_premium,
                    discounts=discounts.value,
                    surcharges=surcharges.value,
                )
            )

            if isinstance(business_validation, Err):
                return business_validation

            violations = business_validation.value
            critical_violations = self._business_rules.get_critical_violations(
                violations
            )

            # Fail if critical business rule violations exist
            if critical_violations:
                violation_messages = [v.message for v in critical_violations]
                return Err(
                    f"Critical business rule violations prevent rating: {'; '.join(violation_messages)}"
                )

            # Build result and get calculation time
            calc_time = self._performance_optimizer.end_performance_monitoring(
                perf_token
            )

            result = RatingResult(
                base_premium=total_base.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                total_premium=total_premium.quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                ),
                coverage_premiums=coverage_premiums,
                discounts=discounts.value,
                total_discount_amount=total_discount,
                surcharges=surcharges.value,
                total_surcharge_amount=total_surcharge,
                factors=factors.value,
                tier=tier,
                ai_risk_score=ai_risk_score,
                ai_risk_factors=ai_risk_factors,
                calculation_time_ms=calc_time,
                rate_version="2024.1",
                effective_date=date.today(),
            )

            # Cache result for 5 minutes
            await self._cache.set(
                f"{self._cache_prefix}{cache_key}",
                result.model_dump_json(),
                300,
            )

            # Log if slow (>50ms requirement)
            if calc_time > 50:
                await self._log_slow_calculation(calc_time, factors.value)

            return Ok(result)

        except Exception as e:
            return Err(f"Rating calculation error: {str(e)}")

    @beartype
    @performance_monitor("validate_rating_inputs")
    def _validate_rating_inputs(
        self,
        state: str,
        product_type: str,
        drivers: list[DriverInfo],
        coverage_selections: list[CoverageSelection],
    ):
        """Validate rating inputs - FAIL FAST."""
        # Validate state support
        if state not in self._state_rules:
            return Err(
                f"State '{state}' is not supported for rating. "
                f"Supported states: {list(self._state_rules.keys())}. "
                f"Admin must configure state rules before quotes can proceed."
            )

        # Validate product type
        valid_products = ["auto", "home", "renters"]
        if product_type not in valid_products:
            return Err(
                f"Product type '{product_type}' is not supported. "
                f"Valid products: {valid_products}"
            )

        # Validate drivers
        if not drivers:
            return Err("At least one driver is required for rating")

        if len(drivers) > 10:
            return Err("Maximum 10 drivers allowed per policy")

        # Validate coverages
        if not coverage_selections:
            return Err("At least one coverage selection is required")

        # Check for required coverages based on state
        required_coverages = self._state_rules[state].get("required_coverages", [])
        selected_types = {c.coverage_type.value for c in coverage_selections}

        missing_required = set(required_coverages) - selected_types
        if missing_required:
            return Err(
                f"State {state} requires these coverages: {list(missing_required)}. "
                f"Selected: {list(selected_types)}"
            )

        return Ok(True)

    @beartype
    @performance_monitor("get_base_rates")
    async def _get_base_rates(self, state: str, product_type: str) -> Result[dict[str, float], str]:
        """Get base rates for state/product - NO DEFAULTS."""
        cache_key = f"base_rates:{state}:{product_type}"

        # Check cache first
        cached = await self._cache.get(f"{self._cache_prefix}{cache_key}")
        if cached:
            return Ok(json.loads(cached))

        # Check preloaded rates
        key = f"{state}:{product_type}"
        if key in self._base_rates:
            return Ok(self._base_rates[key])

        # Load from database
        query = """
            SELECT coverage_type, base_rate
            FROM rate_tables
            WHERE state = $1 AND product_type = $2
                AND status = 'active'
                AND effective_date <= CURRENT_DATE
                AND (expiration_date IS NULL OR expiration_date > CURRENT_DATE)
        """

        rows = await self._db.fetch(query, state, product_type)

        if not rows:
            return Err(
                f"No active rate table found for {state} {product_type}. "
                f"Admin must create and approve rate tables before quotes can proceed. "
                f"Required action: Configure rates in admin panel -> Rate Management."
            )

        rates = {row["coverage_type"]: Decimal(str(row["base_rate"])) for row in rows}

        # Cache for performance
        await self._cache.set(
            f"{self._cache_prefix}{cache_key}",
            json.dumps({k: str(v) for k, v in rates.items()}),
            self._rate_cache_ttl,
        )

        return Ok(rates)

    @beartype
    @performance_monitor("calculate_factors")
    async def _calculate_factors(
        self,
        state: str,
        vehicle_info: VehicleInfo | None,
        drivers: list[DriverInfo],
        customer_id: UUID | None,
    ) -> Result[dict[str, Any], str]:
        """Calculate all rating factors."""
        factors = {}

        # Territory factor (ZIP-based)
        if vehicle_info:
            territory_result = await self._get_territory_factor(
                state, vehicle_info.garage_zip
            )
            if isinstance(territory_result, Err):
                return territory_result
            factors["territory"] = territory_result.value

        # Vehicle factors
        if vehicle_info:
            vehicle_factors = await self._calculate_vehicle_factors(vehicle_info)
            if isinstance(vehicle_factors, Err):
                return vehicle_factors
            factors.update(vehicle_factors.value)

        # Driver factors
        driver_factors = await self._calculate_driver_factors(drivers)
        if isinstance(driver_factors, Err):
            return driver_factors
        factors.update(driver_factors.value)

        # Credit factor (if allowed in state)
        if customer_id and state not in ["CA", "MA", "MI"]:
            credit_factor = await self._get_credit_factor(customer_id)
            if isinstance(credit_factor, Ok):
                factors["credit"] = credit_factor.value

        # Claims history factor
        if customer_id:
            claims_factor = await self._get_claims_factor(customer_id)
            if isinstance(claims_factor, Ok):
                factors["claims_history"] = claims_factor.value

        # Apply state-specific factor validation
        validated_factors = self._apply_state_factor_rules(state, factors)
        if isinstance(validated_factors, Err):
            return validated_factors

        return Ok(validated_factors.value)

    @beartype
    @performance_monitor("calculate_vehicle_factors")
    async def _calculate_vehicle_factors(self, vehicle: VehicleInfo) -> Result[dict[str, float], str]:
        """Calculate vehicle-specific factors."""
        factors = {}

        # Age factor
        vehicle_age = datetime.now().year - vehicle.year
        if vehicle_age <= 1:
            factors["vehicle_age"] = 1.15  # New car surcharge
        elif vehicle_age <= 3:
            factors["vehicle_age"] = 1.05
        elif vehicle_age <= 7:
            factors["vehicle_age"] = 1.00
        elif vehicle_age <= 12:
            factors["vehicle_age"] = 0.95
        else:
            factors["vehicle_age"] = 0.90  # Older car discount

        # Safety features factor
        safety_discount = 1.0
        for feature in vehicle.safety_features:
            if feature.lower() in ["abs", "airbags"]:
                safety_discount *= 0.98
            elif feature.lower() in ["blind_spot", "lane_assist"]:
                safety_discount *= 0.97
            elif feature.lower() in ["automatic_braking", "collision_warning"]:
                safety_discount *= 0.95

        factors["safety_features"] = round(safety_discount, 4)

        # Anti-theft factor
        if vehicle.anti_theft:
            factors["anti_theft"] = 0.95

        # Usage factor
        if vehicle.annual_mileage < 7500:
            factors["low_mileage"] = 0.90
        elif vehicle.annual_mileage > 20000:
            factors["high_mileage"] = 1.15

        return Ok(factors)

    @beartype
    @performance_monitor("calculate_driver_factors")
    async def _calculate_driver_factors(self, drivers: list[DriverInfo]) -> Result[dict[str, float], str]:
        """Calculate driver-specific factors."""
        # Find primary driver (youngest regular driver typically has highest impact)
        primary_driver = min(drivers, key=lambda d: d.age)

        factors = {}

        # Age factor
        age = primary_driver.age
        if age < 25:
            factors["driver_age"] = 1.50 if age < 21 else 1.25
        elif age < 30:
            factors["driver_age"] = 1.10
        elif age < 65:
            factors["driver_age"] = 1.00
        else:
            factors["driver_age"] = 1.05  # Senior driver

        # Experience factor
        years_licensed = primary_driver.years_licensed
        if years_licensed < 3:
            factors["experience"] = 1.20
        elif years_licensed < 5:
            factors["experience"] = 1.10
        elif years_licensed < 10:
            factors["experience"] = 1.05
        else:
            factors["experience"] = 1.00

        # Violations factor
        total_violations = sum(d.violations_3_years for d in drivers)
        if total_violations == 0:
            factors["violations"] = 0.95  # Clean record discount
        elif total_violations <= 2:
            factors["violations"] = 1.10
        else:
            factors["violations"] = min(1.25 + (total_violations * 0.10), 2.00)

        # Accidents factor
        total_accidents = sum(d.accidents_3_years for d in drivers)
        if total_accidents == 0:
            factors["accidents"] = 1.00
        elif total_accidents == 1:
            factors["accidents"] = 1.25
        else:
            factors["accidents"] = min(1.50 + (total_accidents * 0.25), 3.00)

        # DUI factor
        total_duis = sum(d.dui_convictions for d in drivers)
        if total_duis > 0:
            factors["dui"] = min(2.00 + (total_duis * 0.50), 4.00)

        return Ok(factors)

    @beartype
    @performance_monitor("calculate_discounts")
    async def _calculate_discounts(
        self,
        state: str,
        product_type: str,
        vehicle_info: VehicleInfo | None,
        drivers: list[DriverInfo],
        customer_id: UUID | None,
        base_premium: Decimal,
    ) -> Result[dict[str, Any], str]:
        """Calculate applicable discounts."""
        discounts = []

        # Multi-policy discount
        if customer_id:
            policy_count = await self._get_customer_policy_count(customer_id)
            if isinstance(policy_count, Ok) and policy_count.value > 0:
                discounts.append(
                    Discount(
                        discount_type=DiscountType.MULTI_POLICY,
                        description="Multi-policy discount",
                        amount=(base_premium * Decimal("0.10")).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        ),
                        percentage=Decimal("10"),
                    )
                )

        # Safe driver discount
        has_violations = any(d.violations_3_years > 0 for d in drivers)
        has_accidents = any(d.accidents_3_years > 0 for d in drivers)

        if not has_violations and not has_accidents:
            discounts.append(
                Discount(
                    discount_type=DiscountType.SAFE_DRIVER,
                    description="Safe driver discount",
                    amount=(base_premium * Decimal("0.15")).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    percentage=Decimal("15"),
                )
            )

        # Good student discount
        for driver in drivers:
            if driver.age < 25 and driver.good_student:
                discounts.append(
                    Discount(
                        discount_type=DiscountType.GOOD_STUDENT,
                        description=f"Good student discount for {driver.first_name}",
                        amount=(base_premium * Decimal("0.08")).quantize(
                            Decimal("0.01"), rounding=ROUND_HALF_UP
                        ),
                        percentage=Decimal("8"),
                    )
                )
                break  # Only one good student discount

        # Military/veteran discount
        if any(d.occupation and "military" in d.occupation.lower() for d in drivers):
            discounts.append(
                Discount(
                    discount_type=DiscountType.MILITARY,
                    description="Military discount",
                    amount=(base_premium * Decimal("0.05")).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    ),
                    percentage=Decimal("5"),
                )
            )

        # Loyalty discount
        if customer_id:
            tenure = await self._get_customer_tenure_years(customer_id)
            if isinstance(tenure, Ok) and tenure.value >= 5:
                discount_pct = min(tenure.value * 2, 20)  # Max 20%
                discounts.append(
                    Discount(
                        discount_type=DiscountType.LOYALTY,
                        description=f"Loyalty discount ({tenure.value} years)",
                        amount=(
                            base_premium * Decimal(str(discount_pct / 100))
                        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                        percentage=Decimal(str(discount_pct)),
                    )
                )

        # Validate discount stacking limits
        total_discount_pct = sum(d.percentage for d in discounts)
        if total_discount_pct > Decimal("50"):
            # Cap total discounts at 50%
            scale_factor = Decimal("50") / total_discount_pct
            for discount in discounts:
                discount.amount *= scale_factor
                discount.percentage *= scale_factor

        return Ok(discounts)

    @beartype
    @performance_monitor("calculate_surcharges")
    async def _calculate_surcharges(
        self, state: str, drivers: list[DriverInfo], customer_id: UUID | None
    ) -> Result[dict[str, Any], str]:
        """Calculate applicable surcharges."""
        surcharges = []

        # SR-22 surcharge (if any driver has DUI)
        if any(d.dui_convictions > 0 for d in drivers):
            surcharges.append(
                {
                    "type": "sr22_filing",
                    "description": "SR-22 filing required",
                    "amount": Decimal("250.00"),
                }
            )

        # Lapse in coverage surcharge
        if customer_id:
            lapse = await self._check_coverage_lapse(customer_id)
            if isinstance(lapse, Ok) and lapse.value:
                surcharges.append(
                    {
                        "type": "coverage_lapse",
                        "description": "Prior coverage lapse",
                        "amount": Decimal("100.00"),
                    }
                )

        # High-risk driver surcharge
        high_risk_drivers = [
            d for d in drivers if d.violations_3_years > 3 or d.accidents_3_years > 2
        ]
        if high_risk_drivers:
            surcharges.append(
                {
                    "type": "high_risk",
                    "description": f"High-risk driver surcharge ({len(high_risk_drivers)} drivers)",
                    "amount": Decimal("150.00") * len(high_risk_drivers),
                }
            )

        return Ok(surcharges)

    @beartype
    @performance_monitor("determine_tier")
    def _determine_tier(self, factors: dict[str, float], premium: Decimal) -> str:
        """Determine rating tier based on factors and premium."""
        # Calculate composite risk score
        risk_score = 1.0
        for factor_value in factors.values():
            risk_score *= factor_value

        # Assign tier based on risk score
        if risk_score < 0.8:
            return "preferred_plus"
        elif risk_score < 0.95:
            return "preferred"
        elif risk_score < 1.1:
            return "standard"
        elif risk_score < 1.3:
            return "non_standard"
        else:
            return "high_risk"

    @beartype
    @performance_monitor("generate_cache_key")
    def _generate_cache_key(
        self,
        state: str,
        product_type: str,
        vehicle_info: VehicleInfo | None,
        drivers: list[DriverInfo],
        coverage_selections: list[CoverageSelection],
    ) -> str:
        """Generate cache key for rating calculation."""
        # Create deterministic key from inputs
        key_parts = [
            state,
            product_type,
            json.dumps(
                vehicle_info.model_dump() if vehicle_info else None, sort_keys=True
            ),
            json.dumps(
                [d.model_dump() for d in sorted(drivers, key=lambda x: x.last_name)],
                sort_keys=True,
            ),
            json.dumps(
                [
                    c.model_dump()
                    for c in sorted(
                        coverage_selections, key=lambda x: x.coverage_type.value
                    )
                ],
                sort_keys=True,
            ),
        ]

        key_string = "|".join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    @beartype
    async def _get_territory_factor(self, state: str, zip_code: str):
        """Get territory factor for ZIP code using territory manager."""
        return await self._territory_manager.get_territory_factor(state, zip_code)

    @beartype
    async def _get_credit_factor(self, customer_id: UUID):
        """Get credit-based insurance score factor."""
        # Mock implementation for now
        # In production, this would call a credit bureau API
        return Ok(1.0)

    @beartype
    @performance_monitor("get_claims_factor")
    async def _get_claims_factor(self, customer_id: UUID):
        """Get claims history factor."""
        query = """
            SELECT COUNT(*) as claim_count
            FROM claims
            WHERE customer_id = $1
                AND claim_date > CURRENT_DATE - INTERVAL '5 years'
                AND status IN ('paid', 'settled')
        """

        row = await self._db.fetchrow(query, customer_id)
        claim_count = row["claim_count"] if row else 0

        if claim_count == 0:
            return Ok(0.95)  # Claims-free discount
        elif claim_count == 1:
            return Ok(1.10)
        elif claim_count == 2:
            return Ok(1.25)
        else:
            return Ok(1.50)

    @beartype
    @performance_monitor("get_minimum_premium")
    async def _get_minimum_premium(self, state: str, product_type: str):
        """Get minimum premium for state/product."""
        query = """
            SELECT minimum_premium
            FROM state_product_rules
            WHERE state = $1 AND product_type = $2
        """

        row = await self._db.fetchrow(query, state, product_type)

        if not row:
            return Err(
                f"No minimum premium configured for {state} {product_type}. "
                f"Admin must configure state rules before quotes can proceed."
            )

        return Ok(Decimal(str(row["minimum_premium"])))

    @beartype
    async def _get_customer_policy_count(self, customer_id: UUID):
        """Get count of active policies for customer."""
        query = """
            SELECT COUNT(*) as policy_count
            FROM policies
            WHERE customer_id = $1 AND status = 'active'
        """

        row = await self._db.fetchrow(query, customer_id)
        return Ok(row["policy_count"] if row else 0)

    @beartype
    @performance_monitor("get_customer_tenure_years")
    async def _get_customer_tenure_years(self, customer_id: UUID):
        """Get customer tenure in years."""
        query = """
            SELECT MIN(created_at) as first_policy_date
            FROM policies
            WHERE customer_id = $1
        """

        row = await self._db.fetchrow(query, customer_id)

        if not row or not row["first_policy_date"]:
            return Ok(0)

        tenure_days = (datetime.now() - row["first_policy_date"]).days
        return Ok(tenure_days // 365)

    @beartype
    async def _check_coverage_lapse(self, customer_id: UUID):
        """Check if customer had coverage lapse."""
        # Simplified check - in production would be more sophisticated
        query = """
            SELECT COUNT(*) as lapse_count
            FROM policy_history
            WHERE customer_id = $1
                AND coverage_gap_days > 30
                AND gap_date > CURRENT_DATE - INTERVAL '3 years'
        """

        row = await self._db.fetchrow(query, customer_id)
        return Ok(row["lapse_count"] > 0 if row else False)

    @beartype
    @performance_monitor("get_ai_risk_assessment")
    async def _get_ai_risk_assessment(
        self,
        customer_id: UUID,
        vehicle_info: VehicleInfo | None,
        drivers: list[DriverInfo],
    ) -> Result[dict[str, Any], str]:
        """Get AI risk assessment if available."""
        # Import here to avoid circular imports
        from .rating.calculators import AIRiskScorer

        try:
            # Initialize AI scorer
            ai_scorer = AIRiskScorer(load_models=True)

            # Get customer data
            customer_data = await self._get_customer_data_for_ai(customer_id)
            if customer_data.is_err():
                return Err(
                    f"Customer data retrieval failed: {customer_data.unwrap_err()}"
                )

            # Convert vehicle info to dict
            vehicle_data = {}
            if vehicle_info:
                vehicle_data = {
                    "age": vehicle_info.age,
                    "value": float(vehicle_info.value) if vehicle_info.value else 25000,
                    "annual_mileage": vehicle_info.annual_mileage,
                    "safety_features": vehicle_info.safety_features,
                    "type": vehicle_info.make.lower() if vehicle_info.make else "sedan",
                }
            else:
                # Provide default vehicle data
                vehicle_data = {
                    "age": 5,
                    "value": 25000,
                    "annual_mileage": 12000,
                    "safety_features": [],
                    "type": "sedan",
                }

            # Convert driver info to dict
            driver_data = []
            for driver in drivers:
                driver_dict = {
                    "age": driver.age,
                    "years_licensed": driver.years_licensed,
                    "violations_3_years": driver.violations_3_years,
                    "accidents_3_years": driver.accidents_3_years,
                    "good_student": getattr(driver, "good_student", False),
                    "occupation": getattr(driver, "occupation", None),
                }
                driver_data.append(driver_dict)

            # Get external data factors if available
            external_data = await self._get_external_data_for_ai(
                customer_id, vehicle_info
            )

            # Calculate AI risk score
            ai_result = await ai_scorer.calculate_ai_risk_score(
                customer_data.unwrap(),
                vehicle_data,
                driver_data,
                external_data.unwrap_or(None),
            )

            if ai_result.is_err():
                # Fallback to simplified scoring if AI fails
                return Err(f"AI scoring failed: {ai_result.unwrap_err()}")

            return ai_result

        except Exception as e:
            # Fallback to simplified scoring if AI completely fails
            return Err(f"AI risk assessment error: {str(e)}")

    @beartype
    @performance_monitor("get_customer_data_for_ai")
    async def _get_customer_data_for_ai(self, customer_id: UUID) -> Result[dict[str, Any], str]:
        """Get customer data formatted for AI scoring."""
        try:
            # Query customer data from database
            customer_query = """
                SELECT
                    COUNT(CASE WHEN status = 'active' THEN 1 END) as policy_count,
                    MIN(created_at) as first_policy_date,
                    COUNT(CASE WHEN claim_date > CURRENT_DATE - INTERVAL '5 years' THEN 1 END) as recent_claims
                FROM policies p
                LEFT JOIN claims c ON p.id = c.policy_id
                WHERE p.customer_id = $1
                GROUP BY p.customer_id
            """

            row = await self._db.fetchrow(customer_query, customer_id)

            if not row:
                # New customer
                return Ok(
                    {
                        "policy_count": 0,
                        "years_as_customer": 0,
                        "previous_claims": 0,
                    }
                )

            # Calculate years as customer
            first_policy_date = row["first_policy_date"]
            if first_policy_date:
                from datetime import datetime

                years_as_customer = (datetime.now() - first_policy_date).days / 365.25
            else:
                years_as_customer = 0

            return Ok(
                {
                    "policy_count": row["policy_count"] or 0,
                    "years_as_customer": years_as_customer,
                    "previous_claims": row["recent_claims"] or 0,
                }
            )

        except Exception as e:
            return Err(f"Customer data query failed: {str(e)}")

    @beartype
    @performance_monitor("get_external_data_for_ai")
    async def _get_external_data_for_ai(
        self, customer_id: UUID, vehicle_info: VehicleInfo | None
    ) -> Result[dict[str, Any], str]:
        """Get external data factors for AI scoring."""
        try:
            external_data = {}

            # Get credit score if available and allowed
            credit_result = await self._get_credit_factor(customer_id)
            if credit_result.is_ok():
                # Convert factor back to approximate credit score
                credit_factor = credit_result.unwrap()
                if credit_factor == 0.85:
                    credit_score = 780  # Excellent
                elif credit_factor == 0.95:
                    credit_score = 720  # Good
                elif credit_factor == 1.00:
                    credit_score = 675  # Fair
                elif credit_factor == 1.10:
                    credit_score = 625  # Poor
                else:
                    credit_score = 575  # Very poor

                external_data["credit_score"] = credit_score

            # Get geographical risk factors if vehicle location available
            if vehicle_info and hasattr(vehicle_info, "garage_zip"):
                from .rating.calculators import ExternalDataIntegrator

                # Get crime risk
                crime_result = await ExternalDataIntegrator.get_crime_risk_factor(
                    vehicle_info.garage_zip
                )
                if crime_result.is_ok():
                    external_data["area_crime_rate"] = crime_result.unwrap()

                # Get weather risk
                from datetime import datetime

                weather_result = await ExternalDataIntegrator.get_weather_risk_factor(
                    vehicle_info.garage_zip, datetime.now()
                )
                if weather_result.is_ok():
                    external_data["weather_risk"] = weather_result.unwrap()

            return Ok(external_data if external_data else None)

        except Exception:
            # Return None for external data if there are issues
            return Ok(None)

    @beartype
    async def _log_slow_calculation(
        self, calc_time_ms: int, factors: dict[str, float]
    ) -> None:
        """Log slow calculation for monitoring."""
        # In production, this would send to monitoring system
        print(f"WARNING: Slow rating calculation: {calc_time_ms}ms, factors: {factors}")

    @beartype
    @performance_monitor("load_base_rates")
    async def _load_base_rates(self) -> Result[bool, str]:
        """Load base rates into memory."""
        query = """
            SELECT state, product_type, coverage_type, base_rate
            FROM rate_tables
            WHERE status = 'active'
                AND effective_date <= CURRENT_DATE
                AND (expiration_date IS NULL OR expiration_date > CURRENT_DATE)
        """

        rows = await self._db.fetch(query)

        for row in rows:
            key = f"{row['state']}:{row['product_type']}"
            if key not in self._base_rates:
                self._base_rates[key] = {}

            self._base_rates[key][row["coverage_type"]] = Decimal(str(row["base_rate"]))

        return Ok(True)

    @beartype
    async def _load_discount_rules(self) -> Result[bool, str]:
        """Load discount rules."""
        # In production, load from database
        # For now, rules are hardcoded in calculate_discounts
        return Ok(True)

    @beartype
    async def _load_territory_factors(self) -> Result[bool, str]:
        """Load common territory factors."""
        # In production, preload most common ZIP codes
        return Ok(True)

    @beartype
    @performance_monitor("load_state_rules")
    async def _load_state_rules(self) -> Result[bool, str]:
        """Load state-specific rules."""
        query = """
            SELECT state, rules_data
            FROM state_rating_rules
            WHERE active = true
        """

        rows = await self._db.fetch(query)

        for row in rows:
            self._state_rules[row["state"]] = json.loads(row["rules_data"])

        # Hardcode some essential states if not in DB
        if "CA" not in self._state_rules:
            self._state_rules["CA"] = {
                "required_coverages": ["bodily_injury", "property_damage"],
                "prohibited_factors": ["credit", "occupation", "education"],
                "minimum_limits": {
                    "bodily_injury_per_person": 15000,
                    "bodily_injury_per_accident": 30000,
                    "property_damage": 5000,
                },
            }

        if "TX" not in self._state_rules:
            self._state_rules["TX"] = {
                "required_coverages": ["bodily_injury", "property_damage"],
                "prohibited_factors": [],
                "minimum_limits": {
                    "bodily_injury_per_person": 30000,
                    "bodily_injury_per_accident": 60000,
                    "property_damage": 25000,
                },
            }

        return Ok(True)

    @beartype
    @performance_monitor("apply_state_factor_rules")
    def _apply_state_factor_rules(self, state: str, factors: dict[str, float]) -> dict[str, float]:
        """Apply state-specific factor validation rules."""
        if state not in self._state_rules:
            return Err(f"No rules configured for state {state}")

        rules = self._state_rules[state]
        adjusted_factors = factors.copy()

        # Remove prohibited factors
        for prohibited in rules.get("prohibited_factors", []):
            adjusted_factors.pop(prohibited, None)

        # Apply California Prop 103 rules
        if state == "CA":
            # Ensure primary factors (driving record, miles, experience)
            # account for at least 80% of rating
            primary_factors = [
                "violations",
                "accidents",
                "experience",
                "low_mileage",
                "high_mileage",
            ]
            primary_weight = 1.0
            secondary_weight = 1.0

            for factor_name, factor_value in adjusted_factors.items():
                if factor_name in primary_factors:
                    primary_weight *= factor_value
                else:
                    secondary_weight *= factor_value

            # If secondary factors have too much impact, scale them down
            if secondary_weight < 0.8 or secondary_weight > 1.2:
                scale = (
                    0.2 / abs(1.0 - secondary_weight)
                    if secondary_weight != 1.0
                    else 1.0
                )
                for factor_name in adjusted_factors:
                    if factor_name not in primary_factors:
                        # Move factor closer to 1.0
                        adjusted_factors[factor_name] = (
                            1.0 + (adjusted_factors[factor_name] - 1.0) * scale
                        )

        return Ok(adjusted_factors)

    @beartype
    def get_performance_metrics(self) -> dict[str, Any]:
        """Get current performance metrics for monitoring."""
        return self._performance_optimizer.get_performance_metrics()

    @beartype
    def is_performance_target_met(self, target_ms: int = 50) -> bool:
        """Check if rating engine is meeting performance targets."""
        return self._performance_optimizer.is_performance_target_met(target_ms)

    @beartype
    async def optimize_performance(self) -> Result[dict[str, Any], str]:
        """Get performance optimization recommendations."""
        return await self._performance_optimizer.optimize_slow_calculations()

    @beartype
    async def warm_caches(self) -> Result[int, str]:
        """Warm caches for better performance."""
        return await self._performance_optimizer.warm_cache_for_common_scenarios()
