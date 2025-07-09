"""Claim domain models with strict validation and audit trail support.

This module defines all claim-related models including creation,
updates, and the core claim entity itself.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from beartype import beartype
from pydantic import Field, field_validator, model_validator
from pydantic.types import UUID4

from .base import BaseModelConfig, IdentifiableModel


class ClaimType(str, Enum):
    """Enumeration of claim types."""

    ACCIDENT = "ACCIDENT"
    THEFT = "THEFT"
    DAMAGE = "DAMAGE"
    LIABILITY = "LIABILITY"
    MEDICAL = "MEDICAL"
    NATURAL_DISASTER = "NATURAL_DISASTER"
    OTHER = "OTHER"


class ClaimStatus(str, Enum):
    """Enumeration of claim processing states."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    PENDING_DOCUMENTATION = "PENDING_DOCUMENTATION"
    APPROVED = "APPROVED"
    PARTIALLY_APPROVED = "PARTIALLY_APPROVED"
    DENIED = "DENIED"
    PAID = "PAID"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"


class ClaimPriority(str, Enum):
    """Enumeration of claim priority levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


@beartype
class ClaimBase(BaseModelConfig):  # Inherits frozen=True from BaseModelConfig
    """Base claim attributes shared across all claim operations."""

    policy_id: UUID4 = Field(..., description="Reference to the associated policy")

    claim_type: ClaimType = Field(..., description="Type of claim being filed")

    incident_date: date = Field(..., description="Date when the incident occurred")

    incident_location: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Location where the incident occurred",
    )

    description: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Detailed description of the incident",
    )

    claimed_amount: Decimal = Field(
        ...,
        ge=Decimal("0.01"),
        decimal_places=2,
        max_digits=12,
        description="Amount being claimed",
    )

    @field_validator("incident_date")
    @classmethod
    @beartype
    def validate_incident_date(cls, v: date) -> date:
        """Ensure incident date is not in the future."""
        from datetime import datetime

        if v > datetime.now().date():
            raise ValueError("Incident date cannot be in the future")

        # Claims must be filed within 2 years of incident
        days_ago = (datetime.now().date() - v).days
        if days_ago > 730:  # 2 years
            raise ValueError("Claims must be filed within 2 years of the incident")

        return v


@beartype
class ClaimCreate(ClaimBase):
    """Model for creating a new claim."""

    priority: ClaimPriority = Field(
        default=ClaimPriority.MEDIUM, description="Initial claim priority"
    )

    supporting_documents: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="List of supporting document references",
    )

    contact_phone: str = Field(
        ...,
        min_length=10,
        max_length=20,
        pattern=r"^\+?[1-9]\d{1,14}$",
        description="Contact phone for claim updates",
    )

    contact_email: str | None = Field(
        None, description="Contact email for claim updates"
    )

    @field_validator("supporting_documents")
    @classmethod
    @beartype
    def validate_documents(cls, v: list[str]) -> list[str]:
        """Validate supporting document references."""
        if len(v) > 20:
            raise ValueError("Maximum 20 supporting documents allowed")

        for doc in v:
            if len(doc) < 5 or len(doc) > 100:
                raise ValueError("Document references must be 5-100 characters")

        return v


@beartype
class ClaimUpdate(BaseModelConfig):
    """Model for updating an existing claim.

    All fields are optional to support partial updates.
    """

    status: ClaimStatus | None = Field(None, description="Updated claim status")

    priority: ClaimPriority | None = Field(None, description="Updated claim priority")

    approved_amount: Decimal | None = Field(
        None,
        ge=Decimal("0.00"),
        decimal_places=2,
        max_digits=12,
        description="Approved claim amount",
    )

    denial_reason: str | None = Field(
        None, max_length=1000, description="Reason for claim denial"
    )

    adjuster_notes: str | None = Field(
        None, max_length=5000, description="Internal notes from claim adjuster"
    )

    supporting_documents: list[str] | None = Field(
        None, max_length=20, description="Updated list of supporting documents"
    )

    @model_validator(mode="after")
    @beartype
    def validate_status_transitions(self) -> "ClaimUpdate":
        """Validate claim status transition rules."""
        if self.status == ClaimStatus.DENIED and not self.denial_reason:
            raise ValueError("Denial reason is required when denying a claim")

        if self.status == ClaimStatus.APPROVED and self.approved_amount is None:
            raise ValueError("Approved amount is required when approving a claim")

        if self.approved_amount is not None and self.approved_amount == 0:
            if self.status != ClaimStatus.DENIED:
                raise ValueError("Zero approved amount requires claim to be denied")

        return self

    @model_validator(mode="after")
    @beartype
    def validate_at_least_one_field(self) -> "ClaimUpdate":
        """Ensure at least one field is provided for update."""
        if not any(getattr(self, field) is not None for field in self.model_fields):
            raise ValueError("At least one field must be provided for update")
        return self


@beartype
class ClaimStatusUpdate(BaseModelConfig):
    """Model for updating claim status with additional data."""

    status: ClaimStatus = Field(..., description="New claim status")

    amount_approved: Decimal | None = Field(
        None,
        ge=Decimal("0.00"),
        decimal_places=2,
        max_digits=12,
        description="Approved amount for the claim",
    )

    notes: str | None = Field(
        None, max_length=1000, description="Notes about the status update"
    )


@beartype
class Claim(ClaimBase, IdentifiableModel):
    """Complete claim entity with all attributes."""

    claim_number: str = Field(
        ...,
        min_length=12,
        max_length=20,
        pattern=r"^CLM-[0-9]{4}-[0-9]{7}$",
        description="Unique claim number",
    )

    status: ClaimStatus = Field(..., description="Current claim status")

    priority: ClaimPriority = Field(..., description="Current claim priority")

    approved_amount: Decimal | None = Field(
        None,
        ge=Decimal("0.00"),
        decimal_places=2,
        max_digits=12,
        description="Approved claim amount",
    )

    paid_amount: Decimal | None = Field(
        None,
        ge=Decimal("0.00"),
        decimal_places=2,
        max_digits=12,
        description="Amount actually paid out",
    )

    denial_reason: str | None = Field(
        None, max_length=1000, description="Reason for claim denial"
    )

    adjuster_id: UUID4 | None = Field(None, description="ID of assigned claim adjuster")

    adjuster_notes: str | None = Field(
        None, max_length=5000, description="Internal notes from claim adjuster"
    )

    supporting_documents: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="List of supporting document references",
    )

    submitted_at: datetime | None = Field(
        None, description="Timestamp when claim was submitted"
    )

    approved_at: datetime | None = Field(
        None, description="Timestamp when claim was approved"
    )

    paid_at: datetime | None = Field(None, description="Timestamp when claim was paid")

    closed_at: datetime | None = Field(
        None, description="Timestamp when claim was closed"
    )

    @field_validator("claim_number")
    @classmethod
    @beartype
    def validate_claim_number(cls, v: str) -> str:
        """Ensure claim number follows business format."""
        parts = v.split("-")
        if len(parts) != 3:
            raise ValueError("Claim number must have three parts separated by hyphens")

        year = int(parts[1])
        current_year = datetime.now().year
        if year < 2020 or year > current_year:
            raise ValueError(f"Claim year must be between 2020 and {current_year}")

        return v

    @model_validator(mode="after")
    @beartype
    def validate_claim_amounts(self) -> "Claim":
        """Validate claim amount relationships."""
        if self.approved_amount and self.claimed_amount:
            if self.approved_amount > self.claimed_amount:
                raise ValueError("Approved amount cannot exceed claimed amount")

        if self.paid_amount and self.approved_amount:
            if self.paid_amount > self.approved_amount:
                raise ValueError("Paid amount cannot exceed approved amount")

        return self

    @model_validator(mode="after")
    @beartype
    def validate_timestamps(self) -> "Claim":
        """Validate timestamp relationships."""
        if self.submitted_at and self.created_at:
            if self.submitted_at < self.created_at:
                raise ValueError("Submission timestamp cannot be before creation")

        if self.approved_at and self.submitted_at:
            if self.approved_at < self.submitted_at:
                raise ValueError("Approval timestamp cannot be before submission")

        if self.paid_at and self.approved_at:
            if self.paid_at < self.approved_at:
                raise ValueError("Payment timestamp cannot be before approval")

        return self
