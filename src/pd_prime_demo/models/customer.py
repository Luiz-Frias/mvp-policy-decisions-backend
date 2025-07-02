"""Customer domain models with strict validation and PII protection.

This module defines all customer-related models including creation,
updates, and the core customer entity itself.
"""

from datetime import date
from enum import Enum

from beartype import beartype
from pydantic import EmailStr, Field, field_validator, model_validator

from .base import BaseModelConfig, IdentifiableModel


class CustomerType(str, Enum):
    """Enumeration of customer types."""

    INDIVIDUAL = "INDIVIDUAL"
    BUSINESS = "BUSINESS"
    GOVERNMENT = "GOVERNMENT"
    NON_PROFIT = "NON_PROFIT"


class CustomerStatus(str, Enum):
    """Enumeration of customer account states."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    BLACKLISTED = "BLACKLISTED"


@beartype
class CustomerBase(BaseModelConfig):  # Inherits frozen=True from BaseModelConfig
    """Base customer attributes shared across all customer operations."""

    customer_type: CustomerType = Field(..., description="Type of customer entity")

    first_name: str = Field(
        ..., min_length=1, max_length=100, description="Customer's first name"
    )

    last_name: str = Field(
        ..., min_length=1, max_length=100, description="Customer's last name"
    )

    email: EmailStr = Field(..., description="Customer's email address")

    phone_number: str = Field(
        ...,
        min_length=10,
        max_length=20,
        pattern=r"^\+?[1-9]\d{1,14}$",
        description="Customer's phone number in E.164 format",
    )

    date_of_birth: date = Field(..., description="Customer's date of birth")

    address_line1: str = Field(
        ..., min_length=1, max_length=200, description="Primary address line"
    )

    address_line2: str | None = Field(
        None, max_length=200, description="Secondary address line"
    )

    city: str = Field(..., min_length=1, max_length=100, description="City name")

    state_province: str = Field(
        ..., min_length=2, max_length=100, description="State or province"
    )

    postal_code: str = Field(
        ..., min_length=3, max_length=20, description="Postal or ZIP code"
    )

    country_code: str = Field(
        ...,
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
        description="ISO 3166-1 alpha-2 country code",
    )

    @field_validator("date_of_birth")
    @classmethod
    def validate_age(cls, v: date) -> date:
        """Ensure customer is at least 18 years old."""
        from datetime import datetime

        today = datetime.now().date()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))

        if age < 18:
            raise ValueError("Customer must be at least 18 years old")
        if age > 120:
            raise ValueError("Invalid date of birth")

        return v

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: EmailStr) -> EmailStr:
        """Additional email validation rules."""
        email_str = str(v).lower()

        # Block disposable email domains
        disposable_domains = [
            "tempmail.com",
            "throwaway.email",
            "guerrillamail.com",
            "mailinator.com",
            "10minutemail.com",
        ]

        domain = email_str.split("@")[1]
        if domain in disposable_domains:
            raise ValueError("Disposable email addresses are not allowed")

        return v


@beartype
class CustomerCreate(CustomerBase):
    """Model for creating a new customer."""

    tax_id: str = Field(
        ...,
        min_length=9,
        max_length=20,
        description="Tax identification number (SSN/EIN)",
    )

    marketing_consent: bool = Field(
        default=False, description="Customer consent for marketing communications"
    )

    @field_validator("tax_id")
    @classmethod
    def validate_tax_id(cls, v: str) -> str:
        """Validate basic tax ID format."""
        # Remove any formatting characters
        cleaned = "".join(c for c in v if c.isdigit())

        # Basic validation for US SSN (9 digits) or EIN (9 digits)
        if len(cleaned) not in [9]:
            raise ValueError("Tax ID must be 9 digits")

        # Mask for storage (keep only last 4 digits visible)
        return f"XXX-XX-{cleaned[-4:]}"


@beartype
class CustomerUpdate(BaseModelConfig):
    """Model for updating an existing customer.

    All fields are optional to support partial updates.
    """

    email: EmailStr | None = Field(None, description="Updated email address")

    phone_number: str | None = Field(
        None,
        min_length=10,
        max_length=20,
        pattern=r"^\+?[1-9]\d{1,14}$",
        description="Updated phone number",
    )

    address_line1: str | None = Field(
        None, min_length=1, max_length=200, description="Updated primary address line"
    )

    address_line2: str | None = Field(
        None, max_length=200, description="Updated secondary address line"
    )

    city: str | None = Field(
        None, min_length=1, max_length=100, description="Updated city name"
    )

    state_province: str | None = Field(
        None, min_length=2, max_length=100, description="Updated state or province"
    )

    postal_code: str | None = Field(
        None, min_length=3, max_length=20, description="Updated postal or ZIP code"
    )

    marketing_consent: bool | None = Field(
        None, description="Updated marketing consent"
    )

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "CustomerUpdate":
        """Ensure at least one field is provided for update."""
        if not any(getattr(self, field) is not None for field in self.model_fields):
            raise ValueError("At least one field must be provided for update")
        return self


@beartype
class Customer(CustomerBase, IdentifiableModel):
    """Complete customer entity with all attributes."""

    customer_number: str = Field(
        ...,
        min_length=10,
        max_length=20,
        pattern=r"^CUST-[0-9]{10}$",
        description="Unique customer number",
    )

    status: CustomerStatus = Field(..., description="Current customer status")

    tax_id_masked: str = Field(..., description="Masked tax identification number")

    marketing_consent: bool = Field(
        ..., description="Customer consent for marketing communications"
    )

    total_policies: int = Field(
        default=0, ge=0, description="Total number of policies held"
    )

    risk_score: int | None = Field(
        None, ge=0, le=100, description="Customer risk assessment score (0-100)"
    )

    @field_validator("customer_number")
    @classmethod
    def validate_customer_number(cls, v: str) -> str:
        """Ensure customer number follows business format."""
        if not v.startswith("CUST-"):
            raise ValueError("Customer number must start with 'CUST-'")
        return v
