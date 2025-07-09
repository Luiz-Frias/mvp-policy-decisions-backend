"""Pydantic models used as typed payloads for Rating service Result objects.

These models provide structure for what used to be naked tuple / dict payloads
so that mypy and runtime validation both understand the shape.
"""

from decimal import Decimal
from typing import Dict, List

from pydantic import BaseModel, Extra, Field

__all__ = [
    "FactorizedPremium",
    "DriverRiskScore",
    "Discount",
    "StackedDiscounts",
]


class FactorizedPremium(BaseModel):
    """Final premium after multiplicative factors are applied."""

    final_premium: Decimal = Field(..., gt=Decimal("0"))
    factor_impacts: Dict[str, Decimal] = Field(
        ..., description="Premium impact per factor"
    )


class DriverRiskScore(BaseModel):
    """Driver risk scoring result."""

    risk_score: float = Field(..., ge=0, le=1)
    risk_factors: List[str] = Field(default_factory=list)


class Discount(BaseModel, extra=Extra.allow):
    """Represents a single discount entry.

    Uses *extra=allow* so existing dynamic keys (e.g. applied_rate) are preserved
    without breaking strict validation.
    """

    rate: float = Field(..., ge=0, le=1)
    amount: Decimal | None = None  # populated after calculation
    applied_rate: float | None = None
    stackable: bool | None = None
    priority: int | None = None


class StackedDiscounts(BaseModel):
    """Response payload for calculated discount stacking."""

    applied_discounts: List[Discount]
    total_discount_amount: Decimal = Field(..., ge=Decimal("0"))
