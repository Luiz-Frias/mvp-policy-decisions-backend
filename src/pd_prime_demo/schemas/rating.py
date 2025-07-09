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
