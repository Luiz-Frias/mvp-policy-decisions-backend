"""Policy domain models with strict validation and business rules.

This module defines all policy-related models including creation,
updates, and the core policy entity itself.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from beartype import beartype
from pydantic import Field, field_validator, model_validator
from pydantic.types import UUID4

from .base import BaseModelConfig, IdentifiableModel


class PolicyType(str, Enum):
    """Enumeration of available policy types."""

    AUTO = "AUTO"
    HOME = "HOME"
    LIFE = "LIFE"
    HEALTH = "HEALTH"
    BUSINESS = "BUSINESS"
    TRAVEL = "TRAVEL"


class PolicyStatus(str, Enum):
    """Enumeration of policy lifecycle states."""

    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


@beartype
class PolicyBase(BaseModelConfig):  # Inherits frozen=True from BaseModelConfig
    """Base policy attributes shared across all policy operations."""

    policy_number: str = Field(
        ...,
        min_length=10,
        max_length=20,
        pattern=r"^POL-[0-9]{4}-[0-9]{6}$",
        description="Unique policy number in format POL-YYYY-NNNNNN",
    )

    policy_type: PolicyType = Field(..., description="Type of insurance policy")

    customer_id: UUID4 = Field(..., description="Reference to the policy holder")

    premium_amount: Decimal = Field(
        ...,
        ge=Decimal("0.01"),
        decimal_places=2,
        max_digits=10,
        description="Monthly premium amount",
    )

    coverage_amount: Decimal = Field(
        ...,
        ge=Decimal("1000.00"),
        decimal_places=2,
        max_digits=12,
        description="Maximum coverage amount",
    )

    deductible: Decimal = Field(
        ...,
        ge=Decimal("0.00"),
        decimal_places=2,
        max_digits=10,
        description="Policy deductible amount",
    )

    effective_date: date = Field(..., description="Date when policy coverage begins")

    expiration_date: date = Field(..., description="Date when policy coverage ends")

    @field_validator("policy_number")
    @classmethod
    @beartype
    def validate_policy_number(cls, v: str) -> str:
        """Ensure policy number follows business format."""
        parts = v.split("-")
        if len(parts) != 3:
            raise ValueError("Policy number must have three parts separated by hyphens")

        year = int(parts[1])
        current_year = datetime.now().year
        if year < 2020 or year > current_year:
            raise ValueError(f"Policy year must be between 2020 and {current_year}")

        return v

    @model_validator(mode="after")
    @beartype
    def validate_dates(self) -> "PolicyBase":
        """Ensure expiration date is after effective date."""
        if self.expiration_date <= self.effective_date:
            raise ValueError("Expiration date must be after effective date")
        return self


@beartype
class PolicyCreate(PolicyBase):
    """Model for creating a new policy."""

    status: PolicyStatus = Field(
        default=PolicyStatus.DRAFT, description="Initial policy status"
    )

    notes: str | None = Field(
        None, max_length=1000, description="Additional notes or comments"
    )


@beartype
class PolicyUpdate(BaseModelConfig):
    """Model for updating an existing policy.

    All fields are optional to support partial updates.
    """

    premium_amount: Decimal | None = Field(
        None,
        ge=Decimal("0.01"),
        decimal_places=2,
        max_digits=10,
        description="Updated monthly premium amount",
    )

    coverage_amount: Decimal | None = Field(
        None,
        ge=Decimal("1000.00"),
        decimal_places=2,
        max_digits=12,
        description="Updated maximum coverage amount",
    )

    deductible: Decimal | None = Field(
        None,
        ge=Decimal("0.00"),
        decimal_places=2,
        max_digits=10,
        description="Updated policy deductible amount",
    )

    status: PolicyStatus | None = Field(None, description="Updated policy status")

    notes: str | None = Field(
        None, max_length=1000, description="Updated notes or comments"
    )

    @model_validator(mode="after")
    @beartype
    def validate_at_least_one_field(self) -> "PolicyUpdate":
        """Ensure at least one field is provided for update."""
        if not any(getattr(self, field) is not None for field in self.model_fields):
            raise ValueError("At least one field must be provided for update")
        return self


@beartype
class Policy(PolicyBase, IdentifiableModel):
    """Complete policy entity with all attributes."""

    status: PolicyStatus = Field(..., description="Current policy status")

    notes: str | None = Field(
        None, max_length=1000, description="Additional notes or comments"
    )

    cancelled_at: datetime | None = Field(
        None, description="Timestamp when policy was cancelled"
    )

    @model_validator(mode="after")
    @beartype
    def validate_cancellation(self) -> "Policy":
        """Ensure cancelled_at is set only when status is CANCELLED."""
        if self.status == PolicyStatus.CANCELLED and not self.cancelled_at:
            raise ValueError("Cancelled policies must have a cancellation timestamp")
        if self.status != PolicyStatus.CANCELLED and self.cancelled_at:
            raise ValueError(
                "Only cancelled policies can have a cancellation timestamp"
            )
        return self
