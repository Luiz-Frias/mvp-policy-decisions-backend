# Agent 06: Rating Engine Architect

## CRITICAL: READ ALL CONTEXT FIRST

**YOU MUST READ YOUR SPECIFIC INSTRUCTION SET AND FOLLOW ALL INSTRUCTIONS. READ ALL CONTEXT DOCUMENTS BEFORE BEGINNING ANY WORK.**

## YOUR MISSION

Build a comprehensive rating engine with state-specific rules, multiple rating factors, discount calculations, and sub-50ms performance for pricing calculations.

## CRITICAL: NO SILENT FALLBACKS PRINCIPLE

### Configuration Requirements (NON-NEGOTIABLE)

1. **EXPLICIT CONFIGURATION ONLY**:
   - NO `.get(key, default)` patterns for business logic
   - NO try/except blocks that silently continue with defaults
   - NO state rule fallbacks (especially NO defaulting to Texas rules)
   - ALL rate calculations MUST have explicit business rules

2. **FAIL FAST VALIDATION**:

   ```python
   # ❌ FORBIDDEN - Silent fallback to Texas rules
   def get_state_rules(state: str) -> StateRatingRules:
       rules_map = {...}
       return rules_map.get(state, TexasRules())  # VIOLATES MASTER RULESET

   # ✅ REQUIRED - Explicit failure with remediation
   def get_state_rules(state: str) -> Result[StateRatingRules, str]:
       rules_map = {...}
       if state not in rules_map:
           return Err(
               f"State '{state}' is not supported for rating. "
               f"Supported states: {list(rules_map.keys())}. "
               f"Admin must add state support before quotes can proceed. "
               f"Required action: Configure state rules in admin panel."
           )
       return Ok(rules_map[state])
   ```

3. **RATE TABLE VALIDATION**:

   ```python
   # ❌ FORBIDDEN - Default rates
   base_rate = rate_table.get(coverage_type, 0.01)  # Silent fallback

   # ✅ REQUIRED - Explicit rate validation
   if coverage_type not in rate_table:
       return Err(
           f"No approved rate found for coverage '{coverage_type}'. "
           f"Available coverages: {list(rate_table.keys())}. "
           f"Required action: Admin must approve rates for this coverage type."
       )
   ```

4. **EXPLICIT ERROR REMEDIATION**: Every error message MUST include:
   - What configuration is missing
   - Where admin can fix it
   - What the system will do until fixed

## MANDATORY PRE-WORK

1. Read ALL documents listed in AGENT_TEMPLATE.md FIRST
2. Specifically study:
   - `.sage/source_documents/DEMO_OVERALL_PRD.md` for pricing requirements
   - Insurance rating concepts if unfamiliar (use 30-second searches)
   - Agent 04's quote models for data structures
   - Performance requirements (10,000 concurrent users)

## SPECIFIC TASKS

### 1. Create Rating Engine Core (`src/pd_prime_demo/services/rating_engine.py`)

```python
"""High-performance insurance rating engine."""

import asyncio
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from uuid import UUID

from beartype import beartype
import numpy as np

from ..core.cache import Cache
from ..core.database import Database
from ..models.quote import (
    VehicleInfo, DriverInfo, CoverageSelection,
    Discount, DiscountType, CoverageType
)
from .result import Result, Ok, Err


class RatingResult(BaseModel):
    """Rating calculation result."""

    base_premium: Decimal
    total_premium: Decimal

    # Breakdowns
    coverage_premiums: Dict[CoverageType, Decimal]

    # Adjustments
    discounts: List[Discount]
    total_discount_amount: Decimal
    surcharges: List[Dict[str, Any]]
    total_surcharge_amount: Decimal

    # Factors used
    factors: Dict[str, float]
    tier: str

    # AI enhancements
    ai_risk_score: Optional[float] = None
    ai_risk_factors: List[str] = Field(default_factory=list)

    # Calculation metadata
    calculation_time_ms: int
    rate_version: str
    effective_date: date


class RatingEngine:
    """Core rating engine with caching and performance optimization."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize rating engine."""
        self._db = db
        self._cache = cache
        self._cache_prefix = "rating:"
        self._rate_cache_ttl = 3600  # 1 hour

        # Preload common data
        self._base_rates: Dict[str, Dict] = {}
        self._discount_rules: Dict[str, Any] = {}
        self._territory_factors: Dict[str, float] = {}

    @beartype
    async def initialize(self) -> None:
        """Preload rating data for performance."""
        # Load base rates
        await self._load_base_rates()

        # Load discount rules
        await self._load_discount_rules()

        # Load territory factors
        await self._load_territory_factors()

    @beartype
    async def calculate_premium(
        self,
        state: str,
        product_type: str,
        vehicle_info: Optional[VehicleInfo],
        drivers: List[DriverInfo],
        coverage_selections: List[CoverageSelection],
        customer_id: Optional[UUID] = None,
    ) -> Result[RatingResult, str]:
        """Calculate premium with all factors."""
        start_time = asyncio.get_event_loop().time()

        try:
            # Validate inputs
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
                return Ok(RatingResult(**cached))

            # Get base rates
            base_rates = await self._get_base_rates(state, product_type)
            if not base_rates:
                return Err(f"No rates available for {state} {product_type}")

            # Calculate base premium for each coverage
            coverage_premiums = {}
            total_base = Decimal('0')

            for coverage in coverage_selections:
                base_rate = base_rates.get(coverage.coverage_type.value, Decimal('0.01'))
                coverage_premium = coverage.limit * base_rate
                coverage_premiums[coverage.coverage_type] = coverage_premium
                total_base += coverage_premium

            # Apply rating factors
            factors = await self._calculate_factors(
                state, vehicle_info, drivers, customer_id
            )

            # Apply factors to base premium
            factored_premium = total_base
            for factor_name, factor_value in factors.items():
                factored_premium *= Decimal(str(factor_value))

            # Calculate discounts
            discounts = await self._calculate_discounts(
                state, product_type, vehicle_info, drivers,
                customer_id, factored_premium
            )
            total_discount = sum(d.amount for d in discounts)

            # Calculate surcharges
            surcharges = await self._calculate_surcharges(
                state, drivers, customer_id
            )
            total_surcharge = sum(
                Decimal(str(s['amount'])) for s in surcharges
            )

            # Final premium
            total_premium = factored_premium - total_discount + total_surcharge

            # Ensure minimum premium
            min_premium = await self._get_minimum_premium(state, product_type)
            if total_premium < min_premium:
                total_premium = min_premium

            # Get tier
            tier = self._determine_tier(factors, total_premium)

            # AI risk assessment (if enabled)
            ai_risk_score = None
            ai_risk_factors = []
            if customer_id:
                ai_assessment = await self._get_ai_risk_assessment(
                    customer_id, vehicle_info, drivers
                )
                if ai_assessment:
                    ai_risk_score = ai_assessment['score']
                    ai_risk_factors = ai_assessment['factors']

            # Build result
            calc_time = int((asyncio.get_event_loop().time() - start_time) * 1000)

            result = RatingResult(
                base_premium=total_base,
                total_premium=total_premium.quantize(Decimal('0.01')),
                coverage_premiums=coverage_premiums,
                discounts=discounts,
                total_discount_amount=total_discount,
                surcharges=surcharges,
                total_surcharge_amount=total_surcharge,
                factors=factors,
                tier=tier,
                ai_risk_score=ai_risk_score,
                ai_risk_factors=ai_risk_factors,
                calculation_time_ms=calc_time,
                rate_version="2024.1",
                effective_date=date.today(),
            )

            # Cache result
            await self._cache.set(
                f"{self._cache_prefix}{cache_key}",
                result.model_dump_json(),
                300,  # 5 minute cache
            )

            # Log if slow
            if calc_time > 50:
                await self._log_slow_calculation(calc_time, factors)

            return Ok(result)

        except Exception as e:
            return Err(f"Rating calculation error: {str(e)}")

    @beartype
    async def _calculate_factors(
        self,
        state: str,
        vehicle_info: Optional[VehicleInfo],
        drivers: List[DriverInfo],
        customer_id: Optional[UUID],
    ) -> Dict[str, float]:
        """Calculate all rating factors."""
        factors = {}

        # Territory factor (ZIP-based)
        if vehicle_info:
            territory_factor = await self._get_territory_factor(
                state, vehicle_info.garage_zip
            )
            factors['territory'] = territory_factor

        # Vehicle factors
        if vehicle_info:
            vehicle_factors = await self._calculate_vehicle_factors(vehicle_info)
            factors.update(vehicle_factors)

        # Driver factors
        driver_factors = await self._calculate_driver_factors(drivers)
        factors.update(driver_factors)

        # Credit factor (if allowed in state)
        if customer_id and state not in ['CA', 'MA', 'MI']:
            credit_factor = await self._get_credit_factor(customer_id)
            factors['credit'] = credit_factor

        # Claims history factor
        if customer_id:
            claims_factor = await self._get_claims_factor(customer_id)
            factors['claims_history'] = claims_factor

        return factors

    @beartype
    async def _calculate_vehicle_factors(
        self,
        vehicle: VehicleInfo
    ) -> Dict[str, float]:
        """Calculate vehicle-specific factors."""
        factors = {}

        # Age factor
        vehicle_age = datetime.now().year - vehicle.year
        if vehicle_age <= 1:
            factors['vehicle_age'] = 1.15  # New car surcharge
        elif vehicle_age <= 3:
            factors['vehicle_age'] = 1.05
        elif vehicle_age <= 7:
            factors['vehicle_age'] = 1.00
        elif vehicle_age <= 12:
            factors['vehicle_age'] = 0.95
        else:
            factors['vehicle_age'] = 0.90  # Older car discount

        # Safety features factor
        safety_discount = 1.0
        for feature in vehicle.safety_features:
            if feature in ['abs', 'airbags']:
                safety_discount *= 0.98
            elif feature in ['blind_spot', 'lane_assist']:
                safety_discount *= 0.97
            elif feature in ['automatic_braking']:
                safety_discount *= 0.95

        factors['safety_features'] = safety_discount

        # Anti-theft factor
        if vehicle.anti_theft:
            factors['anti_theft'] = 0.95

        # Usage factor
        if vehicle.annual_mileage < 7500:
            factors['low_mileage'] = 0.90
        elif vehicle.annual_mileage > 20000:
            factors['high_mileage'] = 1.15

        return factors

    @beartype
    async def _calculate_driver_factors(
        self,
        drivers: List[DriverInfo]
    ) -> Dict[str, float]:
        """Calculate driver-specific factors."""
        # Find primary driver (youngest regular driver)
        primary_driver = min(drivers, key=lambda d: d.age)

        factors = {}

        # Age factor
        age = primary_driver.age
        if age < 25:
            factors['driver_age'] = 1.50 if age < 21 else 1.25
        elif age < 30:
            factors['driver_age'] = 1.10
        elif age < 65:
            factors['driver_age'] = 1.00
        else:
            factors['driver_age'] = 1.05  # Senior driver

        # Experience factor
        years_licensed = primary_driver.years_licensed
        if years_licensed < 3:
            factors['experience'] = 1.20
        elif years_licensed < 5:
            factors['experience'] = 1.10
        elif years_licensed < 10:
            factors['experience'] = 1.05
        else:
            factors['experience'] = 1.00

        # Violations factor
        total_violations = sum(d.violations_3_years for d in drivers)
        if total_violations == 0:
            factors['violations'] = 0.95  # Clean record discount
        elif total_violations <= 2:
            factors['violations'] = 1.10
        else:
            factors['violations'] = 1.25 + (total_violations * 0.10)

        # Accidents factor
        total_accidents = sum(d.accidents_3_years for d in drivers)
        if total_accidents == 0:
            factors['accidents'] = 1.00
        elif total_accidents == 1:
            factors['accidents'] = 1.25
        else:
            factors['accidents'] = 1.50 + (total_accidents * 0.25)

        # DUI factor
        total_duis = sum(d.dui_convictions for d in drivers)
        if total_duis > 0:
            factors['dui'] = 2.00 + (total_duis * 0.50)

        return factors

    @beartype
    async def _calculate_discounts(
        self,
        state: str,
        product_type: str,
        vehicle_info: Optional[VehicleInfo],
        drivers: List[DriverInfo],
        customer_id: Optional[UUID],
        base_premium: Decimal,
    ) -> List[Discount]:
        """Calculate applicable discounts."""
        discounts = []

        # Multi-policy discount
        if customer_id:
            policy_count = await self._get_customer_policy_count(customer_id)
            if policy_count > 0:
                discounts.append(Discount(
                    discount_type=DiscountType.MULTI_POLICY,
                    description="Multi-policy discount",
                    amount=base_premium * Decimal('0.10'),
                    percentage=Decimal('10'),
                ))

        # Safe driver discount
        has_violations = any(d.violations_3_years > 0 for d in drivers)
        has_accidents = any(d.accidents_3_years > 0 for d in drivers)

        if not has_violations and not has_accidents:
            discounts.append(Discount(
                discount_type=DiscountType.SAFE_DRIVER,
                description="Safe driver discount",
                amount=base_premium * Decimal('0.15'),
                percentage=Decimal('15'),
            ))

        # Good student discount
        for driver in drivers:
            if driver.age < 25 and driver.good_student:
                discounts.append(Discount(
                    discount_type=DiscountType.GOOD_STUDENT,
                    description=f"Good student discount for {driver.first_name}",
                    amount=base_premium * Decimal('0.08'),
                    percentage=Decimal('8'),
                ))
                break  # Only one good student discount

        # Military/veteran discount
        if any(d.occupation and 'military' in d.occupation.lower() for d in drivers):
            discounts.append(Discount(
                discount_type=DiscountType.MILITARY,
                description="Military discount",
                amount=base_premium * Decimal('0.05'),
                percentage=Decimal('5'),
            ))

        # Loyalty discount
        if customer_id:
            customer_tenure = await self._get_customer_tenure_years(customer_id)
            if customer_tenure >= 5:
                discount_pct = min(customer_tenure * 2, 20)  # Max 20%
                discounts.append(Discount(
                    discount_type=DiscountType.LOYALTY,
                    description=f"Loyalty discount ({customer_tenure} years)",
                    amount=base_premium * Decimal(str(discount_pct / 100)),
                    percentage=Decimal(str(discount_pct)),
                ))

        return discounts

    # ... Additional helper methods for surcharges, tier determination, etc. ...
```

### 2. Create State-Specific Rules (`src/pd_prime_demo/services/rating/state_rules.py`)

```python
"""State-specific rating rules and regulations."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Dict, Any, List

from beartype import beartype


class StateRatingRules(ABC):
    """Base class for state-specific rules."""

    @abstractmethod
    def validate_factors(self, factors: Dict[str, float]) -> Dict[str, float]:
        """Validate and adjust factors per state regulations."""
        pass

    @abstractmethod
    def get_required_coverages(self) -> List[str]:
        """Get state-mandated coverages."""
        pass

    @abstractmethod
    def get_minimum_limits(self) -> Dict[str, Decimal]:
        """Get state minimum coverage limits."""
        pass


class CaliforniaRules(StateRatingRules):
    """California Proposition 103 compliant rules."""

    @beartype
    def validate_factors(self, factors: Dict[str, float]) -> Dict[str, float]:
        """Apply California-specific factor limits."""
        # Prop 103: Driving record, miles driven, years of experience
        # are primary factors (must account for 80%+ of rating)

        adjusted = factors.copy()

        # Remove prohibited factors
        adjusted.pop('credit', None)  # CA prohibits credit scoring
        adjusted.pop('occupation', None)  # Prohibited
        adjusted.pop('education', None)  # Prohibited

        # Ensure primary factors have appropriate weight
        primary_weight = (
            adjusted.get('violations', 1.0) *
            adjusted.get('accidents', 1.0) *
            adjusted.get('experience', 1.0) *
            adjusted.get('annual_mileage', 1.0)
        )

        # Scale other factors if needed
        if primary_weight < 0.8:
            scale_factor = 0.2 / (1.0 - primary_weight)
            for key in adjusted:
                if key not in ['violations', 'accidents', 'experience', 'annual_mileage']:
                    adjusted[key] = 1.0 + (adjusted[key] - 1.0) * scale_factor

        return adjusted

    @beartype
    def get_required_coverages(self) -> List[str]:
        """California required coverages."""
        return [
            'bodily_injury',  # 15/30
            'property_damage',  # 5
            'uninsured_motorist_bodily_injury',  # 15/30
        ]

    @beartype
    def get_minimum_limits(self) -> Dict[str, Decimal]:
        """California minimum limits."""
        return {
            'bodily_injury_per_person': Decimal('15000'),
            'bodily_injury_per_accident': Decimal('30000'),
            'property_damage': Decimal('5000'),
            'uninsured_motorist_per_person': Decimal('15000'),
            'uninsured_motorist_per_accident': Decimal('30000'),
        }


class TexasRules(StateRatingRules):
    """Texas rating rules."""

    @beartype
    def validate_factors(self, factors: Dict[str, float]) -> Dict[str, float]:
        """Texas allows most rating factors."""
        return factors  # Texas has fewer restrictions

    @beartype
    def get_required_coverages(self) -> List[str]:
        """Texas required coverages."""
        return [
            'bodily_injury',  # 30/60
            'property_damage',  # 25
        ]

    @beartype
    def get_minimum_limits(self) -> Dict[str, Decimal]:
        """Texas minimum limits."""
        return {
            'bodily_injury_per_person': Decimal('30000'),
            'bodily_injury_per_accident': Decimal('60000'),
            'property_damage': Decimal('25000'),
        }


# Factory function
@beartype
def get_state_rules(state: str) -> Result[StateRatingRules, str]:
    """Get rules for a specific state - FAIL FAST if unsupported."""
    rules_map = {
        'CA': CaliforniaRules(),
        'TX': TexasRules(),
        'NY': NewYorkRules(),  # Add all supported states explicitly
        # DO NOT add defaults - explicit state support required
    }

    if state not in rules_map:
        return Err(
            f"State '{state}' is not supported for rating. "
            f"Supported states: {list(rules_map.keys())}. "
            f"Admin must add state support before quotes can proceed."
        )

    return Ok(rules_map[state])
```

### 3. Create Rate Table Management (`src/pd_prime_demo/services/rating/rate_tables.py`)

Implement rate table CRUD and versioning.

## SEARCH TRIGGERS (30-second timeout)

If confidence < 95% on:

- Insurance rating → Search: "insurance rating factors explained"
- State regulations → Search: "California Proposition 103 insurance"
- Performance optimization → Search: "python decimal performance optimization"

## DELIVERABLES

1. **Rating Engine Core**: Full calculation engine
2. **State Rules**: Compliant state-specific logic
3. **Rate Tables**: Management and versioning
4. **Performance Tests**: Proof of <50ms calculations
5. **Factor Documentation**: Clear explanation of all factors

## SUCCESS CRITERIA

1. All calculations complete in <50ms
2. State compliance validated
3. Accurate discount stacking
4. Proper factor application
5. Results are reproducible

## PARALLEL COORDINATION

- Agent 01 creates rate tables in database
- Agent 05 uses your engine for quotes
- Agent 04's models define your inputs
- Agent 07 will extend with AI scoring

Document all rating factors and formulas clearly!

## ADDITIONAL REQUIREMENT: Admin Rate Management

**IMPORTANT**: You must ALSO read `.sage/wave_contexts/wave_2/AGENT_DEPLOYMENT_SUMMARY.md` to understand the full system context.

### 4. Create Admin Rate Management Service (`src/pd_prime_demo/services/admin/rate_management_service.py`)

You must also implement comprehensive admin rate management features:

```python
"""Admin rate management service."""

from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal

from beartype import beartype

from ...core.cache import Cache
from ...core.database import Database
from ..result import Result, Ok, Err

class RateManagementService:
    """Service for admin rate management and approval workflows."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize rate management service."""
        self._db = db
        self._cache = cache

    @beartype
    async def create_rate_table_version(
        self,
        table_name: str,
        rate_data: Dict[str, Any],
        admin_user_id: UUID,
        effective_date: date,
        notes: Optional[str] = None,
    ) -> Result[Dict[str, Any], str]:
        """Create new version of rate table requiring approval."""
        try:
            # Validate rate structure
            validation = await self._validate_rate_structure(table_name, rate_data)
            if isinstance(validation, Err):
                return validation

            # Create pending rate version
            version_id = uuid4()
            await self._db.execute(
                """
                INSERT INTO rate_table_versions (
                    id, table_name, version_number, rate_data,
                    effective_date, created_by, status, notes
                ) VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7)
                """,
                version_id, table_name, await self._get_next_version(table_name),
                rate_data, effective_date, admin_user_id, notes
            )

            # Create approval workflow
            await self._create_approval_workflow(version_id, admin_user_id)

            # Invalidate rate cache
            await self._cache.delete_pattern("rating:rates:*")

            return Ok({
                "version_id": version_id,
                "status": "pending_approval",
                "approval_required": True
            })

        except Exception as e:
            return Err(f"Rate creation failed: {str(e)}")

    @beartype
    async def approve_rate_version(
        self,
        version_id: UUID,
        admin_user_id: UUID,
        approval_notes: Optional[str] = None,
    ) -> Result[bool, str]:
        """Approve rate table version."""
        try:
            # Check approval permissions
            has_permission = await self._check_approval_permission(admin_user_id)
            if not has_permission:
                return Err("Insufficient permissions for rate approval")

            # Get version details
            version = await self._db.fetchrow(
                "SELECT * FROM rate_table_versions WHERE id = $1",
                version_id
            )
            if not version:
                return Err("Rate version not found")

            if version['status'] != 'pending':
                return Err(f"Cannot approve version in {version['status']} status")

            # Mark as approved
            await self._db.execute(
                """
                UPDATE rate_table_versions
                SET status = 'approved', approved_by = $2, approved_at = $3,
                    approval_notes = $4
                WHERE id = $1
                """,
                version_id, admin_user_id, datetime.utcnow(), approval_notes
            )

            # Update active version if effective date is reached
            if version['effective_date'] <= date.today():
                await self._activate_rate_version(version_id)

            # Log approval activity
            await self._log_rate_activity(
                admin_user_id, "approve_rate", version_id,
                {"table": version['table_name'], "notes": approval_notes}
            )

            return Ok(True)

        except Exception as e:
            return Err(f"Approval failed: {str(e)}")

    @beartype
    async def get_rate_comparison(
        self,
        version_id_1: UUID,
        version_id_2: UUID,
    ) -> Result[Dict[str, Any], str]:
        """Compare two rate table versions."""
        try:
            version1 = await self._get_rate_version(version_id_1)
            version2 = await self._get_rate_version(version_id_2)

            if not version1 or not version2:
                return Err("One or both versions not found")

            # Calculate differences
            comparison = {
                "version_1": {
                    "id": version_id_1,
                    "version": version1['version_number'],
                    "effective_date": version1['effective_date'],
                    "status": version1['status'],
                },
                "version_2": {
                    "id": version_id_2,
                    "version": version2['version_number'],
                    "effective_date": version2['effective_date'],
                    "status": version2['status'],
                },
                "differences": await self._calculate_rate_differences(
                    version1['rate_data'], version2['rate_data']
                ),
                "impact_analysis": await self._analyze_rate_impact(
                    version1['rate_data'], version2['rate_data']
                )
            }

            return Ok(comparison)

        except Exception as e:
            return Err(f"Comparison failed: {str(e)}")

    @beartype
    async def schedule_ab_test(
        self,
        control_version_id: UUID,
        test_version_id: UUID,
        traffic_split: float,
        start_date: date,
        end_date: date,
        admin_user_id: UUID,
    ) -> Result[UUID, str]:
        """Schedule A/B test between rate versions."""
        try:
            if not 0.1 <= traffic_split <= 0.5:
                return Err("Traffic split must be between 10% and 50%")

            test_id = uuid4()

            await self._db.execute(
                """
                INSERT INTO rate_ab_tests (
                    id, control_version_id, test_version_id,
                    traffic_split, start_date, end_date,
                    created_by, status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'scheduled')
                """,
                test_id, control_version_id, test_version_id,
                traffic_split, start_date, end_date, admin_user_id
            )

            # Set up test routing
            await self._configure_ab_test_routing(test_id)

            return Ok(test_id)

        except Exception as e:
            return Err(f"A/B test setup failed: {str(e)}")

    @beartype
    async def get_rate_analytics(
        self,
        table_name: str,
        date_from: date,
        date_to: date,
    ) -> Result[Dict[str, Any], str]:
        """Get rate usage analytics for admin dashboards."""
        try:
            # Get quote volume by rate version
            quote_analytics = await self._db.fetch(
                """
                SELECT
                    rv.version_number,
                    rv.effective_date,
                    COUNT(q.id) as quote_count,
                    AVG(q.total_premium) as avg_premium,
                    COUNT(*) FILTER (WHERE q.status = 'bound') as conversion_count,
                    CAST(COUNT(*) FILTER (WHERE q.status = 'bound') AS FLOAT) /
                        NULLIF(COUNT(q.id), 0) as conversion_rate
                FROM rate_table_versions rv
                LEFT JOIN quotes q ON q.rate_version = rv.version_number
                WHERE rv.table_name = $1
                    AND q.created_at BETWEEN $2 AND $3
                GROUP BY rv.version_number, rv.effective_date
                ORDER BY rv.effective_date DESC
                """,
                table_name, date_from, date_to
            )

            # Get A/B test results
            ab_test_results = await self._get_ab_test_performance(
                table_name, date_from, date_to
            )

            return Ok({
                "rate_performance": [dict(row) for row in quote_analytics],
                "ab_test_results": ab_test_results,
                "period": {"from": date_from, "to": date_to},
                "summary": await self._calculate_rate_summary(quote_analytics)
            })

        except Exception as e:
            return Err(f"Analytics failed: {str(e)}")
```

### 5. Create Admin Rate API Endpoints (`src/pd_prime_demo/api/v1/admin/rate_management.py`)

```python
"""Admin rate management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from datetime import date
from uuid import UUID

from beartype import beartype

from ....services.admin.rate_management_service import RateManagementService
from ...dependencies import get_rate_management_service, get_current_admin_user
from ....models.admin import AdminUser

router = APIRouter()

@router.post("/rate-tables/{table_name}/versions")
@beartype
async def create_rate_version(
    table_name: str,
    rate_data: Dict[str, Any],
    effective_date: date,
    notes: Optional[str] = None,
    rate_service: RateManagementService = Depends(get_rate_management_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Create new rate table version."""
    if "rate:write" not in admin_user.effective_permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await rate_service.create_rate_table_version(
        table_name, rate_data, admin_user.id, effective_date, notes
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)

    return result.value

@router.post("/rate-versions/{version_id}/approve")
@beartype
async def approve_rate_version(
    version_id: UUID,
    approval_notes: Optional[str] = None,
    rate_service: RateManagementService = Depends(get_rate_management_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Dict[str, bool]:
    """Approve rate table version."""
    if "rate:approve" not in admin_user.effective_permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await rate_service.approve_rate_version(
        version_id, admin_user.id, approval_notes
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)

    return {"approved": result.value}

@router.get("/rate-analytics/{table_name}")
@beartype
async def get_rate_analytics(
    table_name: str,
    date_from: date,
    date_to: date,
    rate_service: RateManagementService = Depends(get_rate_management_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Get rate analytics for dashboards."""
    result = await rate_service.get_rate_analytics(
        table_name, date_from, date_to
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)

    return result.value
```

### 6. Add Rate Management Tables

Tell Agent 01 to also create:

```sql
-- Rate table versions with approval workflow
CREATE TABLE rate_table_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(100) NOT NULL,
    version_number INTEGER NOT NULL,
    rate_data JSONB NOT NULL,
    effective_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'approved', 'active', 'superseded'

    -- Audit fields
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    approved_by UUID REFERENCES admin_users(id),
    approved_at TIMESTAMPTZ,
    approval_notes TEXT,
    notes TEXT,

    UNIQUE(table_name, version_number)
);

-- A/B testing framework for rates
CREATE TABLE rate_ab_tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    control_version_id UUID REFERENCES rate_table_versions(id),
    test_version_id UUID REFERENCES rate_table_versions(id),
    traffic_split DECIMAL(3,2) NOT NULL, -- Percentage for test version
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'scheduled',
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

Make sure all rate management operations include proper admin authentication and audit logging!
