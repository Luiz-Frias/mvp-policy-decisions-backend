# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Pydantic models used as typed payloads for Rating service Result objects.

These models provide structure for what used to be naked tuple / dict payloads
so that mypy and runtime validation both understand the shape.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "FactorizedPremium",
    "DriverRiskScore",
    "Discount",
    "StackedDiscounts",
    "FactorImpact",
    "RiskFactor",
    "RatingFactors",
    "RateTableData",
    "CoverageRates",
    "TerritoryRates",
    "SurchargeFactors",
    "PerformanceMetrics",
    "RiskFactorData",
    "StateRateSettings",
    "TerritoryRiskFactors",
    "SurchargeCalculation",
    "RateTableValidation",
    "PerformanceThresholds",
]


class FactorizedPremium(BaseModel):
    """Final premium after multiplicative factors are applied."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    final_premium: Decimal = Field(..., gt=Decimal("0"))
    factor_impacts: list["FactorImpact"] = Field(
        ..., description="Premium impact per factor"
    )


class DriverRiskScore(BaseModel):
    """Driver risk scoring result."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    risk_score: float = Field(..., ge=0, le=1)
    risk_factors: list["RiskFactor"] = Field(default_factory=list)


class Discount(BaseModel):
    """Represents a single discount entry.

    Structured model with explicit fields instead of dynamic keys
    for proper validation and type safety.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    rate: float = Field(..., ge=0, le=1)
    amount: Decimal | None = None  # populated after calculation
    applied_rate: float | None = None
    stackable: bool = Field(default=True)
    priority: int = Field(default=1, ge=1)


class StackedDiscounts(BaseModel):
    """Response payload for calculated discount stacking."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    applied_discounts: list[Discount]
    total_discount_amount: Decimal = Field(..., ge=Decimal("0"))


class FactorImpact(BaseModel):
    """Individual factor impact on premium calculation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    factor_name: str = Field(..., min_length=1, max_length=100)
    impact_amount: Decimal = Field(..., description="Impact on premium")
    impact_type: str = Field(..., pattern="^(multiplicative|additive|percentage)$")
    description: str | None = Field(None, max_length=255)


class RiskFactor(BaseModel):
    """Individual risk factor for driver scoring."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    factor_type: str = Field(..., min_length=1, max_length=50)
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    impact_score: float = Field(..., ge=0, le=1)
    description: str | None = Field(None, max_length=255)


# =============================================================================
# RATING ENGINE MODELS - Replace dict usage throughout rating system
# =============================================================================


class RatingFactors(BaseModel):
    """Structured rating factors to replace dict[str, float] usage in state_rules.py.

    Provides type-safe access to rating factors with validation for insurance
    business rules and state regulation compliance.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Primary rating factors (most states - high impact)
    violations: float = Field(
        default=1.0, ge=0.1, le=5.0, description="Moving violations factor"
    )
    accidents: float = Field(
        default=1.0, ge=0.1, le=5.0, description="At-fault accidents factor"
    )
    experience: float = Field(
        default=1.0, ge=0.5, le=2.0, description="Driving experience factor"
    )
    driver_age: float = Field(
        default=1.0, ge=0.5, le=3.0, description="Driver age factor"
    )

    # Mileage-based factors
    low_mileage: float = Field(
        default=1.0, ge=0.7, le=1.0, description="Low mileage discount factor"
    )
    high_mileage: float = Field(
        default=1.0, ge=1.0, le=1.5, description="High mileage surcharge factor"
    )

    # Territory and location factors
    territory: float = Field(
        default=1.0, ge=0.5, le=2.5, description="Territory risk factor"
    )
    catastrophe_risk: float = Field(
        default=1.0, ge=1.0, le=1.5, description="Catastrophe risk factor"
    )

    # Vehicle factors
    vehicle_age: float = Field(
        default=1.0, ge=0.5, le=2.0, description="Vehicle age factor"
    )
    vehicle_type: float = Field(
        default=1.0, ge=0.8, le=2.0, description="Vehicle type factor"
    )

    # Secondary factors (state-dependent - may be prohibited)
    credit: float | None = Field(
        default=None, ge=0.6, le=1.4, description="Credit score factor"
    )
    occupation: float | None = Field(
        default=None, ge=0.9, le=1.1, description="Occupation factor"
    )
    education: float | None = Field(
        default=None, ge=0.9, le=1.1, description="Education factor"
    )
    marital_status: float | None = Field(
        default=None, ge=0.9, le=1.1, description="Marital status factor"
    )

    # Prohibited factors (for compliance tracking)
    gender: float | None = Field(
        default=None, description="Gender factor - prohibited in many states"
    )

    def is_factor_prohibited(self, factor_name: str, state: str) -> bool:
        """Check if a factor is prohibited in a specific state."""
        prohibited_by_state = {
            "CA": {"credit", "occupation", "education", "gender", "marital_status"},
            "MI": {"credit", "gender", "marital_status"},
            "NY": set(),  # More permissive but with caps
            "TX": {"race", "religion", "national_origin"},
            "FL": set(),  # Allows most with caps
            "PA": {"race", "religion", "national_origin"},
        }

        return factor_name in prohibited_by_state.get(state, set())

    def calculate_composite_factor(self) -> float:
        """Calculate multiplicative composite factor from all components."""
        # Start with primary factors
        composite = (
            self.violations
            * self.accidents
            * self.experience
            * self.driver_age
            * self.low_mileage
            * self.high_mileage
            * self.territory
            * self.vehicle_age
            * self.vehicle_type
        )

        # Apply secondary factors if present
        if self.credit is not None:
            composite *= self.credit
        if self.occupation is not None:
            composite *= self.occupation
        if self.education is not None:
            composite *= self.education
        if self.marital_status is not None:
            composite *= self.marital_status

        # Apply catastrophe risk if present
        composite *= self.catastrophe_risk

        # Ensure reasonable bounds (0.1x to 10x base rate)
        return max(0.1, min(10.0, composite))


class RateTableData(BaseModel):
    """Structured rate table data to replace dict[str, Any] usage in rate_tables.py.

    Provides type-safe access to rate table structure with validation for
    insurance coverage rates and rating factors.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Required rate table structure
    coverages: dict[str, Decimal] = Field(
        ..., description="Coverage type to base rate mapping", min_length=1
    )
    base_rates: dict[str, Decimal] = Field(
        ..., description="Base rates by coverage type", min_length=1
    )
    factors: dict[str, "RiskFactorData"] = Field(
        ..., description="Rating factors with min/max ranges", min_length=1
    )

    # Optional metadata
    effective_date: str | None = Field(None, description="Effective date for rates")
    expiration_date: str | None = Field(None, description="Expiration date for rates")
    rate_filing_number: str | None = Field(
        None, max_length=50, description="Regulatory filing number"
    )

    def validate_rate_structure(self) -> list[str]:
        """Validate rate table structure and return any errors."""
        errors = []

        # Check that all coverage rates are positive
        for coverage_type, rate in self.coverages.items():
            if rate <= 0:
                errors.append(
                    f"Coverage {coverage_type} rate must be positive, got {rate}"
                )
            if rate > Decimal("10000"):
                errors.append(
                    f"Coverage {coverage_type} rate exceeds maximum (10000), got {rate}"
                )

        # Check that base rates match coverages
        coverage_types = set(self.coverages.keys())
        base_rate_types = set(self.base_rates.keys())

        if coverage_types != base_rate_types:
            missing_from_base = coverage_types - base_rate_types
            extra_in_base = base_rate_types - coverage_types

            if missing_from_base:
                errors.append(f"Base rates missing for coverages: {missing_from_base}")
            if extra_in_base:
                errors.append(
                    f"Extra base rates for unknown coverages: {extra_in_base}"
                )

        return errors


class RiskFactorData(BaseModel):
    """Individual risk factor definition for rate tables."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    min_value: float = Field(..., ge=0.1, le=10.0, description="Minimum factor value")
    max_value: float = Field(..., ge=0.1, le=10.0, description="Maximum factor value")
    default_value: float = Field(
        default=1.0, ge=0.1, le=10.0, description="Default factor value"
    )
    description: str | None = Field(
        None, max_length=255, description="Factor description"
    )

    def validate_ranges(self) -> list[str]:
        """Validate factor ranges and return any errors."""
        errors = []

        if self.min_value > self.max_value:
            errors.append(
                f"Min value {self.min_value} cannot exceed max value {self.max_value}"
            )

        if not (self.min_value <= self.default_value <= self.max_value):
            errors.append(
                f"Default value {self.default_value} must be between min {self.min_value} and max {self.max_value}"
            )

        return errors


class CoverageRates(BaseModel):
    """Coverage-specific rate mappings for structured rate management."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Liability coverages
    bodily_injury: Decimal = Field(
        ..., gt=0, description="Bodily injury liability rate"
    )
    property_damage: Decimal = Field(
        ..., gt=0, description="Property damage liability rate"
    )

    # Optional coverages
    comprehensive: Decimal | None = Field(
        None, gt=0, description="Comprehensive coverage rate"
    )
    collision: Decimal | None = Field(None, gt=0, description="Collision coverage rate")
    uninsured_motorist: Decimal | None = Field(
        None, gt=0, description="Uninsured motorist rate"
    )
    personal_injury_protection: Decimal | None = Field(
        None, gt=0, description="PIP coverage rate"
    )

    # State-specific coverages
    medical_payments: Decimal | None = Field(
        None, gt=0, description="Medical payments coverage rate"
    )
    property_protection: Decimal | None = Field(
        None, gt=0, description="Property protection (Michigan)"
    )

    def get_required_coverages(self, state: str) -> dict[str, Decimal]:
        """Get required coverages for a specific state."""
        required_by_state = {
            "CA": {
                "bodily_injury": self.bodily_injury,
                "property_damage": self.property_damage,
                "uninsured_motorist": self.uninsured_motorist or Decimal("0"),
            },
            "TX": {
                "bodily_injury": self.bodily_injury,
                "property_damage": self.property_damage,
            },
            "NY": {
                "bodily_injury": self.bodily_injury,
                "property_damage": self.property_damage,
                "personal_injury_protection": self.personal_injury_protection
                or Decimal("0"),
                "uninsured_motorist": self.uninsured_motorist or Decimal("0"),
            },
            "FL": {
                "property_damage": self.property_damage,
                "personal_injury_protection": self.personal_injury_protection
                or Decimal("0"),
            },
            "MI": {
                "bodily_injury": self.bodily_injury,
                "property_damage": self.property_damage,
                "personal_injury_protection": self.personal_injury_protection
                or Decimal("0"),
                "property_protection": self.property_protection or Decimal("0"),
            },
            "PA": {
                "bodily_injury": self.bodily_injury,
                "property_damage": self.property_damage,
            },
        }

        return required_by_state.get(
            state,
            {
                "bodily_injury": self.bodily_injury,
                "property_damage": self.property_damage,
            },
        )


class TerritoryRates(BaseModel):
    """Territory-specific rate factors to replace dict usage in territory_management.py."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    territory_id: str = Field(
        ..., min_length=1, max_length=50, description="Territory identifier"
    )
    state: str = Field(..., min_length=2, max_length=2, description="State code")
    base_factor: float = Field(..., ge=0.5, le=2.5, description="Base territory factor")

    # Risk component factors
    crime_rate: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Crime rate risk factor"
    )
    weather_risk: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Weather risk factor"
    )
    traffic_density: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Traffic density factor"
    )
    catastrophe_risk: float = Field(
        default=0.0, ge=-1.0, le=1.0, description="Natural disaster risk"
    )

    # ZIP code mappings
    zip_codes: list[str] = Field(
        ..., min_length=1, description="ZIP codes in this territory"
    )

    def calculate_composite_factor(self) -> float:
        """Calculate composite territory factor from all risk components."""
        composite = self.base_factor

        # Apply risk factor multipliers with industry-standard impacts
        composite *= 1.0 + self.crime_rate * 0.10  # Max 10% crime impact
        composite *= 1.0 + self.weather_risk * 0.15  # Max 15% weather impact
        composite *= 1.0 + self.traffic_density * 0.08  # Max 8% traffic impact
        composite *= 1.0 + self.catastrophe_risk * 0.20  # Max 20% catastrophe impact

        # Ensure factor stays within reasonable bounds
        return max(0.50, min(2.50, composite))

    def get_risk_assessment(self) -> str:
        """Get overall risk assessment for territory."""
        composite_factor = self.calculate_composite_factor()

        if composite_factor >= 1.5:
            return "high"
        elif composite_factor >= 1.2:
            return "elevated"
        elif composite_factor >= 0.9:
            return "standard"
        elif composite_factor >= 0.7:
            return "below_average"
        else:
            return "low"


class SurchargeFactors(BaseModel):
    """Surcharge calculation factors to replace dict usage in surcharge_calculator.py."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # DUI/SR-22 surcharge rates
    dui_first_offense: Decimal = Field(
        default=Decimal("0.50"), ge=0, le=2, description="First DUI surcharge rate"
    )
    dui_second_offense: Decimal = Field(
        default=Decimal("0.75"), ge=0, le=2, description="Second DUI surcharge rate"
    )
    dui_multiple_offense: Decimal = Field(
        default=Decimal("1.00"), ge=0, le=2, description="Multiple DUI surcharge rate"
    )
    sr22_filing_fee: Decimal = Field(
        default=Decimal("25.00"), ge=0, description="SR-22 filing fee"
    )

    # High-risk driver surcharges
    high_risk_moderate: Decimal = Field(
        default=Decimal("0.15"), ge=0, le=1, description="Moderate risk surcharge"
    )
    high_risk_high: Decimal = Field(
        default=Decimal("0.25"), ge=0, le=1, description="High risk surcharge"
    )
    high_risk_very_high: Decimal = Field(
        default=Decimal("0.40"), ge=0, le=1, description="Very high risk surcharge"
    )

    # Young driver surcharges by age
    young_driver_under_18: Decimal = Field(
        default=Decimal("0.50"), ge=0, le=1, description="Under 18 surcharge"
    )
    young_driver_under_21: Decimal = Field(
        default=Decimal("0.35"), ge=0, le=1, description="Under 21 surcharge"
    )
    young_driver_under_23: Decimal = Field(
        default=Decimal("0.20"), ge=0, le=1, description="Under 23 surcharge"
    )
    young_driver_under_25: Decimal = Field(
        default=Decimal("0.10"), ge=0, le=1, description="Under 25 surcharge"
    )

    # Inexperienced driver surcharges
    inexperienced_under_1_year: Decimal = Field(
        default=Decimal("0.30"), ge=0, le=1, description="Under 1 year licensed"
    )
    inexperienced_under_2_years: Decimal = Field(
        default=Decimal("0.20"), ge=0, le=1, description="Under 2 years licensed"
    )
    inexperienced_under_3_years: Decimal = Field(
        default=Decimal("0.10"), ge=0, le=1, description="Under 3 years licensed"
    )

    # Coverage lapse surcharges
    lapse_1_7_days: Decimal = Field(
        default=Decimal("0.05"), ge=0, le=1, description="1-7 day lapse surcharge"
    )
    lapse_8_30_days: Decimal = Field(
        default=Decimal("0.10"), ge=0, le=1, description="8-30 day lapse surcharge"
    )
    lapse_31_90_days: Decimal = Field(
        default=Decimal("0.15"), ge=0, le=1, description="31-90 day lapse surcharge"
    )
    lapse_over_90_days: Decimal = Field(
        default=Decimal("0.25"), ge=0, le=1, description="Over 90 day lapse surcharge"
    )

    # Vehicle-based surcharges
    vehicle_sports_luxury: Decimal = Field(
        default=Decimal("0.20"),
        ge=0,
        le=1,
        description="Sports/luxury vehicle surcharge",
    )
    vehicle_commercial_use: Decimal = Field(
        default=Decimal("0.30"), ge=0, le=1, description="Commercial use surcharge"
    )
    vehicle_modifications: Decimal = Field(
        default=Decimal("0.15"), ge=0, le=1, description="Modified vehicle surcharge"
    )

    def get_state_caps(self) -> dict[str, Decimal]:
        """Get maximum surcharge percentages by state."""
        return {
            "CA": Decimal("1.50"),  # 150% max in California
            "TX": Decimal("2.00"),  # 200% max in Texas
            "NY": Decimal("1.75"),  # 175% max in New York
            "FL": Decimal("2.50"),  # 250% max in Florida
            "MI": Decimal("1.50"),  # 150% max in Michigan
            "PA": Decimal("1.75"),  # 175% max in Pennsylvania
        }


class SurchargeCalculation(BaseModel):
    """Individual surcharge calculation result."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    surcharge_type: str = Field(
        ..., min_length=1, max_length=50, description="Type of surcharge"
    )
    driver_id: int | None = Field(None, description="Driver ID (null for policy-level)")
    driver_name: str = Field(
        ..., min_length=1, max_length=100, description="Driver name"
    )
    reason: str = Field(
        ..., min_length=1, max_length=255, description="Reason for surcharge"
    )
    rate: float = Field(..., ge=0, description="Surcharge rate (0 for flat fees)")
    amount: Decimal = Field(..., ge=0, description="Surcharge amount")
    severity: str = Field(
        ..., pattern="^(low|medium|high)$", description="Severity level"
    )
    is_flat_fee: bool = Field(default=False, description="Is this a flat fee?")
    risk_score: int | None = Field(None, ge=0, description="Risk score if applicable")

    # Capping fields
    capped: bool = Field(default=False, description="Was this surcharge capped?")
    original_amount: Decimal | None = Field(
        None, description="Original amount before capping"
    )


class PerformanceMetrics(BaseModel):
    """Performance metrics to replace dict usage in performance.py."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    operation_name: str = Field(
        ..., min_length=1, max_length=50, description="Operation being measured"
    )
    count: int = Field(..., ge=0, description="Number of measurements")
    avg_ms: float = Field(..., ge=0, description="Average time in milliseconds")
    min_ms: float = Field(..., ge=0, description="Minimum time in milliseconds")
    max_ms: float = Field(..., ge=0, description="Maximum time in milliseconds")
    p95_ms: float = Field(..., ge=0, description="95th percentile time in milliseconds")

    # Performance thresholds
    target_ms: float = Field(
        default=50.0, gt=0, description="Target performance threshold"
    )
    violation_threshold: float = Field(
        default=0.05, ge=0, le=1, description="Violation rate threshold"
    )

    def is_performance_acceptable(self) -> bool:
        """Check if performance metrics meet acceptable thresholds."""
        # Check if P95 is within target
        if self.p95_ms > self.target_ms:
            return False

        # Check if average is reasonable (half of target)
        if self.avg_ms > self.target_ms / 2:
            return False

        return True

    def get_performance_grade(self) -> str:
        """Get performance grade based on metrics."""
        if self.p95_ms <= self.target_ms * 0.5:
            return "excellent"
        elif self.p95_ms <= self.target_ms * 0.75:
            return "good"
        elif self.p95_ms <= self.target_ms:
            return "acceptable"
        elif self.p95_ms <= self.target_ms * 1.5:
            return "marginal"
        else:
            return "poor"


class StateRateSettings(BaseModel):
    """State-specific rate settings for regulatory compliance."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    state: str = Field(..., min_length=2, max_length=2, description="State code")
    young_driver_age_limit: int = Field(
        default=25, ge=18, le=30, description="Young driver age limit"
    )

    # Minimum coverage limits
    bodily_injury_per_person: Decimal = Field(
        ..., ge=0, description="BI per person minimum"
    )
    bodily_injury_per_accident: Decimal = Field(
        ..., ge=0, description="BI per accident minimum"
    )
    property_damage: Decimal = Field(..., ge=0, description="Property damage minimum")

    # Optional state requirements
    uninsured_motorist_per_person: Decimal | None = Field(
        None, description="UM per person minimum"
    )
    uninsured_motorist_per_accident: Decimal | None = Field(
        None, description="UM per accident minimum"
    )
    personal_injury_protection: Decimal | None = Field(None, description="PIP minimum")
    property_protection: Decimal | None = Field(
        None, description="Property protection minimum"
    )

    # Prohibited factors
    prohibited_factors: list[str] = Field(
        default_factory=list, description="Prohibited rating factors"
    )

    def get_minimum_limits(self) -> dict[str, Decimal]:
        """Get all minimum limits for the state."""
        limits = {
            "bodily_injury_per_person": self.bodily_injury_per_person,
            "bodily_injury_per_accident": self.bodily_injury_per_accident,
            "property_damage": self.property_damage,
        }

        if self.uninsured_motorist_per_person is not None:
            limits["uninsured_motorist_per_person"] = self.uninsured_motorist_per_person
        if self.uninsured_motorist_per_accident is not None:
            limits["uninsured_motorist_per_accident"] = (
                self.uninsured_motorist_per_accident
            )
        if self.personal_injury_protection is not None:
            limits["personal_injury_protection"] = self.personal_injury_protection
        if self.property_protection is not None:
            limits["property_protection"] = self.property_protection

        return limits


class TerritoryRiskFactors(BaseModel):
    """Territory risk factors with validation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    crime_rate: float = Field(..., ge=-1.0, le=1.0, description="Crime rate factor")
    weather_risk: float = Field(..., ge=-1.0, le=1.0, description="Weather risk factor")
    traffic_density: float = Field(
        ..., ge=-1.0, le=1.0, description="Traffic density factor"
    )
    catastrophe_risk: float = Field(
        ..., ge=-1.0, le=1.0, description="Catastrophe risk factor"
    )

    def get_risk_impact(self, factor_name: str) -> float:
        """Get the impact percentage for a specific risk factor."""
        factor_value = getattr(self, factor_name, 0.0)

        impact_multipliers = {
            "crime_rate": 0.10,
            "weather_risk": 0.15,
            "traffic_density": 0.08,
            "catastrophe_risk": 0.20,
        }

        multiplier = impact_multipliers.get(factor_name, 0.05)
        return factor_value * multiplier

    def get_risk_description(self, factor_name: str) -> str:
        """Get human-readable description of risk factor."""
        factor_value = getattr(self, factor_name, 0.0)

        if factor_value > 0.5:
            level = "high"
        elif factor_value > 0.2:
            level = "elevated"
        elif factor_value > -0.2:
            level = "average"
        else:
            level = "low"

        descriptions = {
            "crime_rate": f"{level.title()} crime rate impact",
            "weather_risk": f"{level.title()} weather-related risk",
            "traffic_density": f"{level.title()} traffic density impact",
            "catastrophe_risk": f"{level.title()} natural disaster risk",
        }

        return descriptions.get(factor_name, f"{level.title()} risk factor")


class RateTableValidation(BaseModel):
    """Rate table validation results."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    is_valid: bool = Field(..., description="Overall validation result")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")

    # Validation statistics
    total_coverages: int = Field(..., ge=0, description="Total number of coverages")
    total_factors: int = Field(..., ge=0, description="Total number of factors")
    rate_range_min: Decimal = Field(..., ge=0, description="Minimum rate in table")
    rate_range_max: Decimal = Field(..., ge=0, description="Maximum rate in table")

    def add_error(self, error: str) -> None:
        """Add validation error (creates new instance due to frozen=True)."""
        # Note: Due to frozen=True, this would need to be handled differently
        # in practice, but shown for interface completeness
        pass

    def add_warning(self, warning: str) -> None:
        """Add validation warning."""
        # Note: Due to frozen=True, this would need to be handled differently
        pass


class PerformanceThresholds(BaseModel):
    """Performance thresholds for monitoring."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Primary thresholds
    target_response_ms: float = Field(
        default=50.0, gt=0, description="Target response time"
    )
    max_response_ms: float = Field(
        default=100.0, gt=0, description="Maximum acceptable response time"
    )

    # Violation thresholds
    max_violation_rate: float = Field(
        default=0.05, ge=0, le=1, description="Maximum violation rate"
    )
    monitoring_window_size: int = Field(
        default=100, ge=10, le=1000, description="Monitoring window size"
    )

    # Cache thresholds
    min_cache_hit_rate: float = Field(
        default=0.80, ge=0, le=1, description="Minimum cache hit rate"
    )
    max_cache_size: int = Field(
        default=50000, ge=1000, description="Maximum cache size"
    )

    # Memory thresholds
    max_memory_mb: float = Field(
        default=100.0, gt=0, description="Maximum memory usage in MB"
    )
    memory_growth_limit_mb: float = Field(
        default=1.0, gt=0, description="Memory growth limit per operation"
    )

    def is_performance_acceptable(self, metrics: PerformanceMetrics) -> bool:
        """Check if performance metrics meet thresholds."""
        # Check response time
        if metrics.p95_ms > self.target_response_ms:
            return False

        # Check if average is reasonable
        if metrics.avg_ms > self.target_response_ms / 2:
            return False

        return True

    def get_violation_assessment(self, violation_count: int, total_count: int) -> str:
        """Assess violation rate."""
        if total_count == 0:
            return "no_data"

        violation_rate = violation_count / total_count

        if violation_rate == 0:
            return "excellent"
        elif violation_rate <= self.max_violation_rate / 2:
            return "good"
        elif violation_rate <= self.max_violation_rate:
            return "acceptable"
        else:
            return "poor"
