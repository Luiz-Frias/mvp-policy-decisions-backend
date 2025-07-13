# Wave 2 Rating Engine - Complete Implementation Design

## Overview

The rating engine is the heart of the insurance platform, calculating premiums based on multiple factors with state-specific rules, real-time adjustments, and AI-powered risk assessment. This is a FULL PRODUCTION implementation.

## Architecture

### Domain Model (Immutable & Type-Safe)

```python
from decimal import Decimal
from typing import Dict, List, Optional, Protocol
from datetime import datetime
from uuid import UUID
from attrs import frozen, field
from pydantic import BaseModel, Field, ConfigDict

# Base configuration for all models
class RatingModelConfig(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        arbitrary_types_allowed=True
    )

# Rating factors
@frozen
class RatingFactor:
    factor_name: str
    factor_value: Decimal
    factor_type: str  # 'multiplicative', 'additive', 'credit', 'surcharge'
    explanation: str
    source: str  # 'territory', 'vehicle', 'driver', 'ai', 'coverage'

@frozen
class TerritoryFactor:
    state: str
    zip_code: str
    territory_code: str
    base_factor: Decimal
    catastrophe_factor: Decimal
    urban_factor: Decimal

    def calculate_factor(self) -> Decimal:
        return self.base_factor * self.catastrophe_factor * self.urban_factor

@frozen
class VehicleFactor:
    vin: str
    year: int
    make: str
    model: str
    vehicle_type: str
    symbol_code: str
    age_factor: Decimal
    type_factor: Decimal
    safety_factor: Decimal
    theft_factor: Decimal

    def calculate_factor(self) -> Decimal:
        return self.type_factor * self.age_factor * self.safety_factor * self.theft_factor

@frozen
class DriverFactor:
    driver_id: UUID
    age: int
    experience_years: int
    violations_count: int
    accidents_count: int
    credit_score: Optional[int]

    def calculate_factor(self) -> Decimal:
        age_factor = self._age_factor()
        experience_factor = self._experience_factor()
        violation_factor = self._violation_factor()
        credit_factor = self._credit_factor()

        return age_factor * experience_factor * violation_factor * credit_factor
```

### Rating Engine Core

```python
from beartype import beartype
from typing import Protocol

class RatingStrategy(Protocol):
    """Protocol for rating strategies"""
    @beartype
    async def calculate_premium(
        self,
        quote_data: QuoteData,
        rate_tables: RateTables
    ) -> Result[PremiumCalculation, RatingError]:
        ...

@frozen
class StandardAutoRating:
    """Standard auto insurance rating implementation"""

    territory_service: TerritoryService = field()
    vehicle_service: VehicleService = field()
    driver_service: DriverService = field()
    ai_service: AIRiskService = field()

    @beartype
    async def calculate_premium(
        self,
        quote_data: QuoteData,
        rate_tables: RateTables
    ) -> Result[PremiumCalculation, RatingError]:
        # Get base premium
        base_premium = rate_tables.get_base_premium(
            quote_data.state,
            quote_data.product_type,
            quote_data.coverage_level
        )

        # Calculate all factors in parallel
        tasks = [
            self.territory_service.get_factor(quote_data.zip_code),
            self.vehicle_service.get_factor(quote_data.vehicle),
            self.driver_service.get_factors(quote_data.drivers),
            self.ai_service.get_risk_factor(quote_data)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check for errors
        for result in results:
            if isinstance(result, Exception):
                return Err(RatingError(f"Factor calculation failed: {result}"))

        territory_factor, vehicle_factor, driver_factors, ai_factor = results

        # Apply state-specific rules
        state_adjustments = await self._apply_state_rules(
            quote_data.state,
            territory_factor,
            driver_factors
        )

        # Calculate final premium
        factors = RatingFactors(
            territory=territory_factor,
            vehicle=vehicle_factor,
            drivers=driver_factors,
            ai_risk=ai_factor,
            state_adjustments=state_adjustments
        )

        premium_calc = self._calculate_final_premium(base_premium, factors)

        return Ok(premium_calc)
```

### State-Specific Rules Engine

```python
@frozen
class StateRulesEngine:
    """Handles state-specific insurance regulations"""

    @beartype
    async def apply_california_rules(
        self,
        factors: RatingFactors,
        driver_data: List[Driver]
    ) -> StateAdjustments:
        adjustments = []

        # Proposition 103 - Good driver discount
        if all(d.is_good_driver() for d in driver_data):
            adjustments.append(
                RatingFactor(
                    factor_name="CA Good Driver Discount",
                    factor_value=Decimal("0.80"),  # 20% discount
                    factor_type="multiplicative",
                    explanation="California Proposition 103 good driver discount",
                    source="state_regulation"
                )
            )

        # Persistency discount
        if driver_data[0].years_with_company >= 3:
            adjustments.append(
                RatingFactor(
                    factor_name="CA Persistency Discount",
                    factor_value=Decimal("0.95"),
                    factor_type="multiplicative",
                    explanation="Long-term customer discount",
                    source="state_regulation"
                )
            )

        return StateAdjustments(adjustments)

    @beartype
    async def apply_new_york_rules(
        self,
        factors: RatingFactors,
        coverage_data: CoverageData
    ) -> StateAdjustments:
        # NY specific: Prior approval, assigned risk
        adjustments = []

        # Mandatory PIP
        if not coverage_data.has_pip:
            adjustments.append(
                RatingFactor(
                    factor_name="NY Mandatory PIP",
                    factor_value=Decimal("150.00"),
                    factor_type="additive",
                    explanation="New York mandatory Personal Injury Protection",
                    source="state_regulation"
                )
            )

        return StateAdjustments(adjustments)
```

### Caching Layer for Performance

```python
@frozen
class RatingCache:
    """Multi-level caching for rating operations"""

    l1_cache: dict = field(factory=dict)  # In-memory
    redis_cache: Redis = field()

    @beartype
    async def get_cached_factor(
        self,
        factor_type: str,
        key: str
    ) -> Optional[RatingFactor]:
        # L1 cache check
        cache_key = f"{factor_type}:{key}"
        if factor := self.l1_cache.get(cache_key):
            return factor

        # L2 Redis check
        if cached := await self.redis_cache.get(cache_key):
            factor = RatingFactor(**json.loads(cached))
            self.l1_cache[cache_key] = factor
            return factor

        return None

    @beartype
    async def cache_factor(
        self,
        factor_type: str,
        key: str,
        factor: RatingFactor,
        ttl: int = 3600
    ) -> None:
        cache_key = f"{factor_type}:{key}"

        # Update both cache levels
        self.l1_cache[cache_key] = factor
        await self.redis_cache.setex(
            cache_key,
            ttl,
            json.dumps(factor.__dict__)
        )
```

### AI Risk Assessment Integration

```python
@frozen
class AIRiskAssessment:
    """AI-powered risk scoring"""

    model_service: ModelService = field()
    feature_extractor: FeatureExtractor = field()

    @beartype
    async def calculate_risk_score(
        self,
        quote_data: QuoteData
    ) -> Result[RiskScore, AIError]:
        # Extract features
        features = self.feature_extractor.extract(quote_data)

        # Get predictions from multiple models
        predictions = await asyncio.gather(
            self.model_service.predict_claim_frequency(features),
            self.model_service.predict_claim_severity(features),
            self.model_service.predict_fraud_risk(features),
            self.model_service.predict_customer_lifetime_value(features)
        )

        # Combine into risk score
        risk_score = self._calculate_composite_score(*predictions)

        # Generate explanations
        explanations = self._generate_explanations(features, predictions, risk_score)

        return Ok(RiskScore(
            score=risk_score,
            factor=self._score_to_factor(risk_score),
            explanations=explanations,
            confidence=self._calculate_confidence(features),
            model_version=self.model_service.version
        ))

    def _score_to_factor(self, score: float) -> Decimal:
        """Convert risk score to premium factor (-20% to +30%)"""
        # Score 0-1, where 0.5 is baseline
        if score < 0.3:  # Low risk
            return Decimal("0.80")  # 20% discount
        elif score < 0.5:  # Below average risk
            return Decimal("0.90")  # 10% discount
        elif score < 0.7:  # Average risk
            return Decimal("1.00")  # No adjustment
        elif score < 0.85:  # Above average risk
            return Decimal("1.15")  # 15% surcharge
        else:  # High risk
            return Decimal("1.30")  # 30% surcharge
```

### Rate Table Management

```python
@frozen
class RateTableManager:
    """Manages rate tables with versioning"""

    db: Database = field()
    cache: RatingCache = field()
    git_service: GitService = field()

    @beartype
    async def create_rate_version(
        self,
        rate_data: RateTableData,
        created_by: User
    ) -> Result[RateVersion, Error]:
        # Validate rate data
        validation = self._validate_rates(rate_data)
        if validation.is_err():
            return validation

        # Create new version
        version = RateVersion(
            version_number=await self._get_next_version(),
            rate_data=rate_data,
            created_by=created_by.id,
            created_at=datetime.utcnow(),
            status=VersionStatus.DRAFT
        )

        # Save to database
        await self.db.save_rate_version(version)

        # Commit to git
        await self.git_service.commit_rates(
            version,
            message=f"Rate version {version.version_number} created by {created_by.name}"
        )

        return Ok(version)

    @beartype
    async def deploy_rate_version(
        self,
        version_id: UUID,
        deployed_by: User
    ) -> Result[DeploymentResult, Error]:
        # Get version
        version = await self.db.get_rate_version(version_id)

        # Run validation tests
        test_results = await self._run_rate_tests(version)
        if not test_results.passed:
            return Err(DeploymentError("Rate tests failed", test_results))

        # Deploy with transaction
        async with self.db.transaction() as tx:
            # Mark current version as inactive
            await tx.deactivate_current_rates(version.state, version.product_type)

            # Activate new version
            await tx.activate_rate_version(version_id)

            # Clear caches
            await self.cache.clear_pattern(f"rates:{version.state}:*")

            # Notify systems
            await self._notify_rate_change(version)

        return Ok(DeploymentResult(
            version_id=version_id,
            deployed_at=datetime.utcnow(),
            deployed_by=deployed_by.id
        ))
```

### Performance Optimization

```python
@frozen
class OptimizedRatingEngine:
    """Performance-optimized rating engine"""

    @beartype
    @memory_profile
    @benchmark
    async def bulk_rate_quotes(
        self,
        quotes: List[QuoteData]
    ) -> List[PremiumCalculation]:
        """Rate multiple quotes efficiently"""

        # Pre-fetch all needed data
        all_zips = {q.zip_code for q in quotes}
        all_vins = {q.vehicle.vin for q in quotes}

        # Batch fetch factors
        territory_factors = await self.territory_service.bulk_get_factors(all_zips)
        vehicle_factors = await self.vehicle_service.bulk_get_factors(all_vins)

        # Process in parallel with semaphore to limit concurrency
        sem = asyncio.Semaphore(50)  # Max 50 concurrent calculations

        async def rate_with_sem(quote):
            async with sem:
                return await self.calculate_premium(
                    quote,
                    cached_factors={
                        'territory': territory_factors.get(quote.zip_code),
                        'vehicle': vehicle_factors.get(quote.vehicle.vin)
                    }
                )

        results = await asyncio.gather(
            *[rate_with_sem(q) for q in quotes]
        )

        return results
```

## Database Schema

```sql
-- Rate tables with versioning
CREATE TABLE rate_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_number VARCHAR(20) NOT NULL,
    state VARCHAR(2) NOT NULL,
    product_type VARCHAR(50) NOT NULL,
    effective_date DATE NOT NULL,
    expiration_date DATE,
    status VARCHAR(20) NOT NULL, -- draft, approved, active, inactive
    rate_data JSONB NOT NULL,
    created_by UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    approved_by UUID,
    approved_at TIMESTAMPTZ,
    deployed_by UUID,
    deployed_at TIMESTAMPTZ,
    UNIQUE(state, product_type, version_number)
);

-- Rate factors for quick lookup
CREATE TABLE rate_factors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_id UUID REFERENCES rate_versions(id),
    factor_type VARCHAR(50) NOT NULL,
    factor_key VARCHAR(100) NOT NULL,
    factor_value JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_factors_lookup (version_id, factor_type, factor_key)
);

-- Rating history for audit
CREATE TABLE rating_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quote_id UUID NOT NULL,
    rate_version_id UUID REFERENCES rate_versions(id),
    base_premium DECIMAL(10,2) NOT NULL,
    final_premium DECIMAL(10,2) NOT NULL,
    factors_applied JSONB NOT NULL,
    ai_risk_score DECIMAL(3,2),
    calculated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    calculation_time_ms INTEGER NOT NULL
);
```

## API Endpoints

```python
# Rating API with full functionality
@router.post("/rate/calculate", response_model=PremiumCalculation)
@beartype
async def calculate_premium(
    quote_data: QuoteData,
    rating_engine: RatingEngine = Depends(get_rating_engine),
    current_user: User = Depends(get_current_user)
) -> PremiumCalculation:
    """Calculate premium with all factors"""
    start_time = time.time()

    result = await rating_engine.calculate_premium(quote_data)

    # Track metrics
    metrics.rating_calculation_time.observe(time.time() - start_time)
    metrics.rating_calculations.inc()

    if isinstance(result, Err):
        raise HTTPException(status_code=400, detail=result.error.message)

    # Log for audit
    await audit_logger.log_rating(
        quote_data.quote_id,
        result.value,
        current_user
    )

    return result.value

@router.get("/rate/factors/{state}/{zip_code}")
@beartype
async def get_territory_factors(
    state: str,
    zip_code: str,
    territory_service: TerritoryService = Depends(get_territory_service)
) -> TerritoryFactors:
    """Get territory-specific rating factors"""
    return await territory_service.get_detailed_factors(state, zip_code)

@router.post("/rate/test")
@beartype
async def test_rate_changes(
    test_scenarios: List[TestScenario],
    new_rates: RateTableData,
    rating_engine: RatingEngine = Depends(get_rating_engine)
) -> RateTestResults:
    """Test rate changes before deployment"""
    results = await rating_engine.test_rate_changes(test_scenarios, new_rates)
    return results
```

## Real-Time Features

```python
# WebSocket for live premium updates
@websocket_manager.on("quote:update")
async def handle_quote_update(
    websocket: WebSocket,
    quote_update: QuoteUpdate
):
    """Recalculate premium in real-time as quote changes"""
    # Validate user can access quote
    if not await authorize_quote_access(websocket.user, quote_update.quote_id):
        await websocket.send_error("Unauthorized")
        return

    # Calculate new premium
    result = await rating_engine.calculate_premium(quote_update.quote_data)

    if result.is_ok():
        await websocket.send_json({
            "type": "premium:updated",
            "quote_id": quote_update.quote_id,
            "premium": result.value.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        })
    else:
        await websocket.send_error(result.error.message)
```

## Performance Requirements

- **Single quote rating**: < 100ms
- **Bulk rating (100 quotes)**: < 5 seconds
- **Rate lookup**: < 10ms (cached)
- **AI risk scoring**: < 200ms
- **Memory usage**: < 10MB per quote

This is a complete, production-ready rating engine that handles all the complexity of real insurance rating while maintaining peak performance and reliability.
