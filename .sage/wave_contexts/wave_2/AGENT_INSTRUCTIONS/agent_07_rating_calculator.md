# Agent 07: Rating Calculator Implementation Expert

## YOUR MISSION

Implement all pricing calculation details, complex rating algorithms, AI risk scoring integration, and performance optimizations to ensure calculations complete in <50ms.

## CRITICAL: NO SILENT FALLBACKS PRINCIPLE

### Calculation Requirements (NON-NEGOTIABLE)

1. **EXPLICIT CALCULATION INPUTS**:
   - NO default factor values when business rules undefined
   - NO fallback discount percentages without approval
   - NO assumed minimum premiums without state validation
   - ALL calculations MUST have explicit input validation

2. **FAIL FAST ON MISSING DATA**:

   ```python
   # ❌ FORBIDDEN - Silent defaults
   def calculate_premium(data: Dict[str, Any]) -> Decimal:
       base_rate = data.get("base_rate", Decimal("0.01"))  # Silent fallback

   # ✅ REQUIRED - Explicit validation
   def calculate_premium(data: Dict[str, Any]) -> Result[Decimal, str]:
       if "base_rate" not in data:
           return Err(
               "Calculation error: base_rate is required but not provided. "
               "Required action: Ensure rate tables are approved and active. "
               "Check: Admin > Rate Management > Active Rates"
           )
   ```

3. **DISCOUNT STACKING VALIDATION**:

   ```python
   # ❌ FORBIDDEN - Assume stacking rules
   total_discount = sum(discount.amount for discount in discounts)  # Dangerous

   # ✅ REQUIRED - Explicit stacking rules
   stacking_result = validate_discount_stacking(discounts, state_rules)
   if stacking_result.is_err():
       return Err(
           f"Discount stacking error: {stacking_result.unwrap_err()}. "
           "Required action: Review discount combination rules in admin panel."
       )
   ```

4. **AI SCORING FAILURES**: When AI models fail, NEVER use placeholder scores

## MANDATORY PRE-WORK

1. Read ALL documents listed in AGENT_TEMPLATE.md FIRST
2. Specifically study:
   - Agent 06's rating engine architecture
   - Mathematical precision requirements for financial calculations
   - `.sage/source_documents/DEMO_OVERALL_PRD.md` for AI integration needs

## SPECIFIC TASKS

### 1. Implement Advanced Calculation Algorithms (`src/pd_prime_demo/services/rating/calculators.py`)

```python
"""Advanced rating calculation algorithms."""

import math
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Dict, List, Tuple, Optional
import numpy as np
from scipy import stats

from beartype import beartype

# Set decimal precision for financial calculations
getcontext().prec = 10


class PremiumCalculator:
    """Advanced premium calculation with statistical methods."""

    @beartype
    @staticmethod
    def calculate_base_premium(
        coverage_limit: Decimal,
        base_rate: Decimal,
        exposure_units: Decimal = Decimal('1'),
    ) -> Decimal:
        """Calculate base premium with proper rounding."""
        # Premium = Coverage Limit × Base Rate × Exposure Units
        premium = (coverage_limit * base_rate * exposure_units) / Decimal('1000')
        return premium.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @beartype
    @staticmethod
    def apply_multiplicative_factors(
        base_premium: Decimal,
        factors: Dict[str, float],
    ) -> Tuple[Decimal, Dict[str, Decimal]]:
        """Apply rating factors with detailed breakdown."""
        factor_impacts = {}
        current_premium = base_premium

        # Apply factors in specific order for consistency
        factor_order = [
            'territory', 'driver_age', 'experience', 'vehicle_age',
            'safety_features', 'credit', 'violations', 'accidents'
        ]

        for factor_name in factor_order:
            if factor_name in factors:
                factor_value = Decimal(str(factors[factor_name]))

                # Calculate impact
                impact = current_premium * (factor_value - Decimal('1'))
                factor_impacts[factor_name] = impact.quantize(Decimal('0.01'))

                # Apply factor
                current_premium *= factor_value

        return current_premium.quantize(Decimal('0.01')), factor_impacts

    @beartype
    @staticmethod
    def calculate_territory_factor(
        zip_code: str,
        territory_data: Dict[str, Any],
    ) -> float:
        """Calculate territory factor using actuarial data."""
        # Get loss cost data for ZIP
        base_loss_cost = territory_data.get('base_loss_cost', 100)
        zip_loss_cost = territory_data.get(zip_code, {}).get('loss_cost', base_loss_cost)

        # Calculate relativity
        relativity = zip_loss_cost / base_loss_cost

        # Apply credibility weighting
        credibility = territory_data.get(zip_code, {}).get('credibility', 0.5)

        # Blend with base: Factor = Credibility × Relativity + (1 - Credibility) × 1.0
        factor = credibility * relativity + (1 - credibility) * 1.0

        # Cap factor range
        return max(0.5, min(3.0, factor))

    @beartype
    @staticmethod
    def calculate_driver_risk_score(
        driver_data: Dict[str, Any],
    ) -> Tuple[float, List[str]]:
        """Calculate driver risk score using statistical model."""
        risk_factors = []

        # Base risk components
        age = driver_data.get('age', 30)
        experience = driver_data.get('years_licensed', 10)
        violations = driver_data.get('violations_3_years', 0)
        accidents = driver_data.get('accidents_3_years', 0)

        # Age risk curve (U-shaped)
        age_risk = 0.0
        if age < 25:
            age_risk = 0.3 * (25 - age) / 5  # Linear increase for young
            risk_factors.append(f"Young driver (age {age})")
        elif age > 70:
            age_risk = 0.2 * (age - 70) / 10  # Linear increase for senior
            risk_factors.append(f"Senior driver (age {age})")

        # Experience curve (exponential decay)
        exp_risk = 0.3 * math.exp(-experience / 5)
        if experience < 3:
            risk_factors.append(f"New driver ({experience} years)")

        # Violation risk (linear)
        viol_risk = 0.15 * violations
        if violations > 0:
            risk_factors.append(f"{violations} violations")

        # Accident risk (exponential)
        acc_risk = 0.25 * (math.exp(accidents) - 1)
        if accidents > 0:
            risk_factors.append(f"{accidents} accidents")

        # Combine risks (weighted sum)
        total_risk = age_risk + exp_risk + viol_risk + acc_risk

        # Normalize to 0-1 scale
        risk_score = 1 / (1 + math.exp(-2 * total_risk))

        return risk_score, risk_factors

    @beartype
    @staticmethod
    def calculate_vehicle_risk_score(
        vehicle_data: Dict[str, Any],
    ) -> float:
        """Calculate vehicle risk score based on characteristics."""
        # Base scores by vehicle type
        type_scores = {
            'sedan': 1.0,
            'suv': 1.1,
            'truck': 1.15,
            'sports': 1.4,
            'luxury': 1.3,
            'economy': 0.9,
        }

        vehicle_type = vehicle_data.get('type', 'sedan')
        base_score = type_scores.get(vehicle_type, 1.0)

        # Age factor (depreciation curve)
        age = vehicle_data.get('age', 5)
        age_factor = 1.0 - (0.05 * min(age, 10))  # 5% per year, max 50%

        # Safety feature credits
        safety_features = vehicle_data.get('safety_features', [])
        safety_credit = 1.0

        feature_credits = {
            'abs': 0.02,
            'airbags': 0.03,
            'stability_control': 0.04,
            'blind_spot': 0.03,
            'automatic_braking': 0.05,
            'lane_assist': 0.03,
        }

        for feature in safety_features:
            if feature in feature_credits:
                safety_credit -= feature_credits[feature]

        # Theft risk factor
        theft_rate = vehicle_data.get('theft_rate', 1.0)  # Relative theft rate

        # Combine factors
        vehicle_risk = base_score * age_factor * safety_credit * theft_rate

        return max(0.5, min(2.0, vehicle_risk))


class DiscountCalculator:
    """Calculate and validate discount stacking."""

    @beartype
    @staticmethod
    def calculate_stacked_discounts(
        base_premium: Decimal,
        applicable_discounts: List[Dict[str, Any]],
        max_total_discount: Decimal = Decimal('0.40'),
    ) -> Tuple[List[Dict[str, Any]], Decimal]:
        """Calculate discounts with proper stacking rules."""
        # Sort by priority (higher priority applies first)
        sorted_discounts = sorted(
            applicable_discounts,
            key=lambda d: d.get('priority', 100)
        )

        applied_discounts = []
        remaining_premium = base_premium
        total_discount_amount = Decimal('0')

        for discount in sorted_discounts:
            if discount.get('stackable', True):
                # Apply to remaining premium
                discount_rate = Decimal(str(discount['rate']))
                discount_amount = remaining_premium * discount_rate

                # Check if we exceed max total discount
                if (total_discount_amount + discount_amount) / base_premium > max_total_discount:
                    # Apply partial discount to reach max
                    discount_amount = base_premium * max_total_discount - total_discount_amount
                    discount['applied_rate'] = float(discount_amount / remaining_premium)
                else:
                    discount['applied_rate'] = discount['rate']

                discount['amount'] = discount_amount.quantize(Decimal('0.01'))
                applied_discounts.append(discount)

                total_discount_amount += discount_amount
                remaining_premium -= discount_amount

                # Stop if we've reached max discount
                if total_discount_amount / base_premium >= max_total_discount:
                    break
            else:
                # Non-stackable discount (applies to base)
                discount_rate = Decimal(str(discount['rate']))
                discount_amount = base_premium * discount_rate

                # Only apply if it's better than current total
                if discount_amount > total_discount_amount:
                    applied_discounts = [discount]
                    discount['amount'] = discount_amount.quantize(Decimal('0.01'))
                    discount['applied_rate'] = discount['rate']
                    total_discount_amount = discount_amount

        return applied_discounts, total_discount_amount.quantize(Decimal('0.01'))


class AIRiskScorer:
    """AI-enhanced risk scoring using machine learning models."""

    def __init__(self):
        """Initialize AI models."""
        # In production, load pre-trained models
        self._models = {}

    @beartype
    async def calculate_ai_risk_score(
        self,
        customer_data: Dict[str, Any],
        vehicle_data: Dict[str, Any],
        driver_data: List[Dict[str, Any]],
        external_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Calculate AI risk score using multiple models."""
        features = self._extract_features(
            customer_data, vehicle_data, driver_data, external_data
        )

        # Simulate model predictions (in production, use real ML models)

        # Claim probability model
        claim_prob = self._predict_claim_probability(features)

        # Severity model
        expected_severity = self._predict_claim_severity(features)

        # Fraud risk model
        fraud_risk = self._predict_fraud_risk(features)

        # Combine into overall risk score
        risk_score = (
            0.5 * claim_prob +
            0.3 * (expected_severity / 10000) +  # Normalize severity
            0.2 * fraud_risk
        )

        # Identify key risk factors
        risk_factors = self._identify_risk_factors(features, {
            'claim_prob': claim_prob,
            'severity': expected_severity,
            'fraud': fraud_risk,
        })

        return {
            'score': min(1.0, max(0.0, risk_score)),
            'components': {
                'claim_probability': claim_prob,
                'expected_severity': expected_severity,
                'fraud_risk': fraud_risk,
            },
            'factors': risk_factors,
            'confidence': 0.85,  # Model confidence
        }

    @beartype
    def _extract_features(
        self,
        customer_data: Dict[str, Any],
        vehicle_data: Dict[str, Any],
        driver_data: List[Dict[str, Any]],
        external_data: Optional[Dict[str, Any]],
    ) -> np.ndarray:
        """Extract features for ML models."""
        features = []

        # Customer features
        features.extend([
            customer_data.get('policy_count', 0),
            customer_data.get('years_as_customer', 0),
            customer_data.get('previous_claims', 0),
        ])

        # Vehicle features
        features.extend([
            vehicle_data.get('age', 5),
            vehicle_data.get('value', 20000) / 1000,  # Normalize
            vehicle_data.get('annual_mileage', 12000) / 1000,
            len(vehicle_data.get('safety_features', [])),
        ])

        # Driver features (aggregate)
        primary_driver = driver_data[0] if driver_data else {}
        features.extend([
            primary_driver.get('age', 30),
            primary_driver.get('years_licensed', 10),
            sum(d.get('violations_3_years', 0) for d in driver_data),
            sum(d.get('accidents_3_years', 0) for d in driver_data),
        ])

        # External features (if available)
        if external_data:
            features.extend([
                external_data.get('credit_score', 700) / 100,
                external_data.get('area_crime_rate', 1.0),
                external_data.get('weather_risk', 1.0),
            ])

        return np.array(features)

    @beartype
    def _predict_claim_probability(self, features: np.ndarray) -> float:
        """Predict probability of claim in next 12 months."""
        # Simulate logistic regression model
        # In production, use trained model

        # Mock coefficients
        coefficients = np.array([
            -0.01,  # policy_count (negative = lower risk)
            -0.02,  # years_as_customer
            0.15,   # previous_claims
            0.01,   # vehicle_age
            0.005,  # vehicle_value
            0.02,   # annual_mileage
            -0.05,  # safety_features
            0.03,   # driver_age (U-shaped, simplified)
            -0.02,  # years_licensed
            0.20,   # violations
            0.30,   # accidents
        ])

        # Pad coefficients if needed
        if len(features) > len(coefficients):
            coefficients = np.pad(coefficients, (0, len(features) - len(coefficients)))

        # Calculate logit
        logit = np.dot(features[:len(coefficients)], coefficients) - 2.0

        # Convert to probability
        probability = 1 / (1 + np.exp(-logit))

        return float(probability)

    @beartype
    def _predict_claim_severity(self, features: np.ndarray) -> float:
        """Predict expected claim severity if claim occurs."""
        # Simulate gamma regression model
        # Base severity
        base_severity = 5000

        # Factors that increase severity
        severity_multiplier = 1.0

        # Vehicle value factor
        vehicle_value_normalized = features[4] if len(features) > 4 else 20
        severity_multiplier *= (0.5 + 0.5 * vehicle_value_normalized / 50)

        # Speed/accident factor
        violations = features[9] if len(features) > 9 else 0
        severity_multiplier *= (1 + 0.1 * violations)

        return base_severity * severity_multiplier

    @beartype
    def _predict_fraud_risk(self, features: np.ndarray) -> float:
        """Predict fraud risk score."""
        # Simple rule-based fraud detection
        # In production, use anomaly detection model

        fraud_score = 0.0

        # New customer with high coverage
        if features[1] < 0.5:  # Less than 6 months
            fraud_score += 0.2

        # Multiple recent claims
        if features[2] > 2:
            fraud_score += 0.3

        # Unusual patterns
        # Add more sophisticated checks in production

        return min(1.0, fraud_score)

    @beartype
    def _identify_risk_factors(
        self,
        features: np.ndarray,
        predictions: Dict[str, float],
    ) -> List[str]:
        """Identify top risk factors for explanation."""
        factors = []

        # High claim probability factors
        if predictions['claim_prob'] > 0.3:
            if features[9] > 0:  # violations
                factors.append("Recent traffic violations")
            if features[10] > 0:  # accidents
                factors.append("Previous accidents")

        # High severity factors
        if predictions['severity'] > 7500:
            factors.append("High vehicle value")

        # Fraud risk factors
        if predictions['fraud'] > 0.3:
            factors.append("New customer profile")

        return factors[:5]  # Top 5 factors
```

### 2. Create Performance Optimization Module (`src/pd_prime_demo/services/rating/performance.py`)

```python
"""Performance optimization for rating calculations."""

import asyncio
from functools import lru_cache
from typing import Dict, Any, Tuple
import hashlib
import pickle

from beartype import beartype


class RatingPerformanceOptimizer:
    """Optimize rating calculations for <50ms performance."""

    def __init__(self):
        """Initialize optimizer."""
        self._calculation_cache = {}
        self._precomputed_factors = {}

    @beartype
    @lru_cache(maxsize=10000)
    def get_cached_territory_factor(
        self,
        state: str,
        zip_code: str,
    ) -> float:
        """Cache territory factors for common ZIPs."""
        # In production, load from database
        # This is called frequently, so cache aggressively
        return self._calculate_territory_factor_internal(state, zip_code)

    @beartype
    def create_calculation_hash(
        self,
        input_data: Dict[str, Any],
    ) -> str:
        """Create hash for calculation caching."""
        # Sort keys for consistent hashing
        sorted_data = sorted(input_data.items())
        data_bytes = pickle.dumps(sorted_data)
        return hashlib.sha256(data_bytes).hexdigest()[:16]

    @beartype
    async def parallel_factor_calculation(
        self,
        calculation_tasks: Dict[str, Any],
    ) -> Dict[str, float]:
        """Calculate factors in parallel for performance."""
        tasks = []
        factor_names = []

        for name, task_func in calculation_tasks.items():
            tasks.append(task_func())
            factor_names.append(name)

        # Run all calculations in parallel
        results = await asyncio.gather(*tasks)

        # Combine results
        return dict(zip(factor_names, results))

    @beartype
    def precompute_common_scenarios(self) -> None:
        """Precompute factors for common scenarios."""
        # Common age groups
        age_groups = [18, 21, 25, 30, 40, 50, 65, 75]

        # Common violation counts
        violation_counts = [0, 1, 2, 3]

        # Precompute driver factors
        for age in age_groups:
            for violations in violation_counts:
                key = f"driver_{age}_{violations}"
                self._precomputed_factors[key] = self._calculate_driver_factor_internal(
                    age, violations
                )
```

## SEARCH TRIGGERS (30-second timeout)

If confidence < 95% on:

- Actuarial math → Search: "insurance actuarial calculations python"
- ML risk scoring → Search: "machine learning insurance risk scoring"
- Performance optimization → Search: "python numerical computation optimization"

## DELIVERABLES

1. **Premium Calculator**: Precise financial calculations
2. **Discount Calculator**: Complex stacking logic
3. **AI Risk Scorer**: ML-based risk assessment
4. **Performance Module**: Sub-50ms optimizations
5. **Unit Tests**: Comprehensive calculation tests

## SUCCESS CRITERIA

1. All calculations accurate to the penny
2. Discount stacking follows business rules
3. AI risk scores are explainable
4. Performance consistently <50ms
5. 100% test coverage on calculations

## PARALLEL COORDINATION

- Agent 06 provides the architecture you implement
- Agent 05 uses your calculations in quotes
- Agent 01's tables store your rates
- Agent 08 will stream your calculations via WebSocket

Ensure all financial calculations use Decimal for precision!

## ADDITIONAL REQUIREMENT: Admin Pricing Controls

**IMPORTANT**: You must ALSO read `.sage/wave_contexts/wave_2/AGENT_DEPLOYMENT_SUMMARY.md` to understand the full system context.

### 3. Create Admin Pricing Override Service (`src/pd_prime_demo/services/admin/pricing_override_service.py`)

You must also implement comprehensive admin pricing control features:

```python
"""Admin pricing override and special rules service."""

from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from beartype import beartype

from ...core.cache import Cache
from ...core.database import Database
from ..result import Result, Ok, Err

class PricingOverrideService:
    """Service for admin pricing overrides and special rules."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize pricing override service."""
        self._db = db
        self._cache = cache

    @beartype
    async def create_pricing_override(
        self,
        quote_id: UUID,
        admin_user_id: UUID,
        override_type: str,  # 'premium_adjustment', 'discount_override', 'special_rate'
        original_amount: Decimal,
        new_amount: Decimal,
        reason: str,
        approval_required: bool = True,
    ) -> Result[UUID, str]:
        """Create pricing override requiring approval."""
        try:
            # Validate override is within limits
            max_adjustment = await self._get_max_adjustment_limit(admin_user_id)
            adjustment_pct = abs((new_amount - original_amount) / original_amount) * 100

            if adjustment_pct > max_adjustment and approval_required:
                return Err(f"Adjustment {adjustment_pct:.1f}% exceeds limit {max_adjustment}%")

            override_id = uuid4()

            await self._db.execute(
                """
                INSERT INTO pricing_overrides (
                    id, quote_id, admin_user_id, override_type,
                    original_amount, new_amount, adjustment_percentage,
                    reason, status, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                override_id, quote_id, admin_user_id, override_type,
                original_amount, new_amount, adjustment_pct,
                reason, 'pending' if approval_required else 'approved',
                datetime.utcnow()
            )

            # Invalidate pricing cache
            await self._cache.delete(f"quote:pricing:{quote_id}")

            # Create approval workflow if needed
            if approval_required:
                await self._create_pricing_approval_workflow(override_id)

            return Ok(override_id)

        except Exception as e:
            return Err(f"Override creation failed: {str(e)}")

    @beartype
    async def apply_manual_discount(
        self,
        quote_id: UUID,
        admin_user_id: UUID,
        discount_amount: Decimal,
        discount_reason: str,
        expires_at: Optional[datetime] = None,
    ) -> Result[bool, str]:
        """Apply manual discount to quote."""
        try:
            # Get current quote premium
            quote = await self._db.fetchrow(
                "SELECT total_premium FROM quotes WHERE id = $1",
                quote_id
            )
            if not quote:
                return Err("Quote not found")

            # Validate discount amount
            max_discount_pct = 25.0  # 25% max manual discount
            discount_pct = (discount_amount / quote['total_premium']) * 100

            if discount_pct > max_discount_pct:
                return Err(f"Discount {discount_pct:.1f}% exceeds maximum {max_discount_pct}%")

            # Apply discount
            await self._db.execute(
                """
                INSERT INTO manual_discounts (
                    quote_id, admin_user_id, discount_amount,
                    discount_percentage, reason, expires_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                quote_id, admin_user_id, discount_amount,
                discount_pct, discount_reason, expires_at
            )

            # Update quote with new premium
            new_premium = quote['total_premium'] - discount_amount
            await self._db.execute(
                """
                UPDATE quotes
                SET total_premium = $2,
                    has_manual_adjustments = true,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                quote_id, new_premium
            )

            # Log activity
            await self._log_pricing_activity(
                admin_user_id, "manual_discount", quote_id,
                {"amount": discount_amount, "reason": discount_reason}
            )

            return Ok(True)

        except Exception as e:
            return Err(f"Discount application failed: {str(e)}")

    @beartype
    async def create_special_pricing_rule(
        self,
        admin_user_id: UUID,
        rule_name: str,
        conditions: Dict[str, Any],
        adjustments: Dict[str, Any],
        effective_date: datetime,
        expiration_date: Optional[datetime] = None,
    ) -> Result[UUID, str]:
        """Create special pricing rule (e.g., promotional rates)."""
        try:
            rule_id = uuid4()

            await self._db.execute(
                """
                INSERT INTO special_pricing_rules (
                    id, rule_name, conditions, adjustments,
                    effective_date, expiration_date, created_by,
                    status, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'active', $8)
                """,
                rule_id, rule_name, conditions, adjustments,
                effective_date, expiration_date, admin_user_id,
                datetime.utcnow()
            )

            # Clear pricing cache to force rule evaluation
            await self._cache.delete_pattern("rating:*")

            return Ok(rule_id)

        except Exception as e:
            return Err(f"Rule creation failed: {str(e)}")
```

### 4. Create Admin Pricing API Endpoints (`src/pd_prime_demo/api/v1/admin/pricing_controls.py`)

```python
"""Admin pricing control endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal

from beartype import beartype

from ....services.admin.pricing_override_service import PricingOverrideService
from ...dependencies import get_pricing_override_service, get_current_admin_user
from ....models.admin import AdminUser

router = APIRouter()

@router.post("/quotes/{quote_id}/pricing-override")
@beartype
async def create_pricing_override(
    quote_id: UUID,
    override_request: PricingOverrideRequest,
    pricing_service: PricingOverrideService = Depends(get_pricing_override_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Create pricing override for quote."""
    if "quote:override" not in admin_user.effective_permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await pricing_service.create_pricing_override(
        quote_id,
        admin_user.id,
        override_request.override_type,
        override_request.original_amount,
        override_request.new_amount,
        override_request.reason
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)

    return {"override_id": result.value}

@router.post("/quotes/{quote_id}/manual-discount")
@beartype
async def apply_manual_discount(
    quote_id: UUID,
    discount_request: ManualDiscountRequest,
    pricing_service: PricingOverrideService = Depends(get_pricing_override_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Dict[str, bool]:
    """Apply manual discount to quote."""
    result = await pricing_service.apply_manual_discount(
        quote_id,
        admin_user.id,
        discount_request.discount_amount,
        discount_request.reason,
        discount_request.expires_at
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)

    return {"applied": result.value}
```

### 5. Add Pricing Control Tables

Tell Agent 01 to also create:

```sql
-- Pricing overrides and adjustments
CREATE TABLE pricing_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID REFERENCES quotes(id),
    admin_user_id UUID REFERENCES admin_users(id),
    override_type VARCHAR(50) NOT NULL, -- 'premium_adjustment', 'discount_override', 'special_rate'
    original_amount DECIMAL(10,2) NOT NULL,
    new_amount DECIMAL(10,2) NOT NULL,
    adjustment_percentage DECIMAL(5,2) NOT NULL,
    reason TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    approved_by UUID REFERENCES admin_users(id),
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Manual discounts applied by admins
CREATE TABLE manual_discounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID REFERENCES quotes(id),
    admin_user_id UUID REFERENCES admin_users(id),
    discount_amount DECIMAL(10,2) NOT NULL,
    discount_percentage DECIMAL(5,2) NOT NULL,
    reason TEXT NOT NULL,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Special pricing rules (promotional rates, etc.)
CREATE TABLE special_pricing_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name VARCHAR(100) NOT NULL,
    conditions JSONB NOT NULL, -- Conditions for rule application
    adjustments JSONB NOT NULL, -- Pricing adjustments to apply
    effective_date TIMESTAMPTZ NOT NULL,
    expiration_date TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'active',
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

Make sure all pricing operations include comprehensive audit logging and permission checks!
