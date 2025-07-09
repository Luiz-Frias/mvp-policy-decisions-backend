"""Quote API schemas for request/response models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

from ..models.quote import (
    AIRiskFactors,
    CoverageSelection,
    Discount,
    DriverInfo,
    PaymentDetails,
    QuoteStatus,
    RatingFactors,
    Surcharge,
    VehicleInfo,
)

# Request schemas


@beartype
class QuoteCreateRequest(BaseModel):
    """Request schema for creating a quote."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    customer_id: UUID | None = None
    product_type: str = Field(..., pattern=r"^(auto|home|commercial)$")
    state: str = Field(..., pattern=r"^[A-Z]{2}$")
    zip_code: str = Field(..., pattern=r"^\d{5}(-\d{4})?$")
    effective_date: date
    email: str | None = Field(None, pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    phone: str | None = Field(None, pattern=r"^\+?1?\d{10,14}$")
    preferred_contact: str = Field(default="email", pattern=r"^(email|phone|text)$")
    vehicle_info: VehicleInfo | None = None
    drivers: list[DriverInfo] = Field(default_factory=list)
    coverage_selections: list[CoverageSelection] = Field(default_factory=list)


@beartype
class QuoteUpdateRequest(BaseModel):
    """Request schema for updating a quote."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    vehicle_info: VehicleInfo | None = None
    drivers: list[DriverInfo] | None = None
    coverage_selections: list[CoverageSelection] | None = None
    effective_date: date | None = None
    email: str | None = Field(None, pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    phone: str | None = Field(None, pattern=r"^\+?1?\d{10,14}$")
    preferred_contact: str | None = Field(None, pattern=r"^(email|phone|text)$")


# Response schemas


@beartype
class QuoteResponse(BaseModel):
    """Response schema for quote details."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    id: UUID
    quote_number: str
    customer_id: UUID | None
    status: QuoteStatus
    product_type: str
    state: str
    zip_code: str
    effective_date: date
    email: str | None
    phone: str | None
    preferred_contact: str

    # Details
    vehicle_info: VehicleInfo | None
    drivers: list[DriverInfo]
    coverage_selections: list[CoverageSelection]

    # Pricing
    base_premium: Decimal | None
    total_premium: Decimal | None
    monthly_premium: Decimal | None
    discounts_applied: list[Discount]
    surcharges_applied: list[Surcharge]
    total_discount_amount: Decimal | None
    total_surcharge_amount: Decimal | None

    # Rating
    rating_factors: RatingFactors | None
    rating_tier: str | None
    ai_risk_score: Decimal | None
    ai_risk_factors: AIRiskFactors | None

    # Metadata
    expires_at: datetime
    is_expired: bool
    days_until_expiration: int
    can_be_bound: bool
    version: int
    created_at: datetime
    updated_at: datetime


@beartype
class QuoteSearchResponse(BaseModel):
    """Response schema for quote search results."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    quotes: list[QuoteResponse]
    total: int
    limit: int
    offset: int


@beartype
class QuoteConversionResponse(BaseModel):
    """Response schema for quote to policy conversion."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    quote_id: UUID
    policy_id: UUID
    policy_number: str
    effective_date: date
    premium: Decimal
    payment_confirmation: PaymentDetails


# Wizard schemas


@beartype
class WizardStepResponse(BaseModel):
    """Response schema for wizard step information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    step_id: str
    title: str
    description: str
    fields: list[str]
    validations: WizardValidation
    next_step: str | None
    previous_step: str | None
    is_conditional: bool
    condition_field: str | None
    condition_value: Any | None


@beartype
class WizardSessionResponse(BaseModel):
    """Response schema for wizard session state."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    session_id: UUID
    quote_id: UUID | None
    current_step: str
    completed_steps: list[str]
    data: WizardStepData
    validation_errors: ValidationErrors
    started_at: datetime
    last_updated: datetime
    expires_at: datetime
    is_complete: bool
    completion_percentage: int


@beartype
class WizardValidationResponse(BaseModel):
    """Response schema for wizard validation results."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    is_valid: bool
    errors: ValidationErrors
    warnings: ValidationWarnings


# Additional schemas for complete API coverage


@beartype
class QuoteListResponse(BaseModel):
    """Response schema for listing quotes."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    quotes: list[QuoteResponse]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    has_next: bool
    has_previous: bool


@beartype
class QuoteCalculateRequest(BaseModel):
    """Request schema for calculating quote premium."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    quote_id: UUID
    force_recalculate: bool = Field(default=False)


@beartype
class QuoteCalculateResponse(BaseModel):
    """Response schema for quote calculation results."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    quote_id: UUID
    base_premium: Decimal
    total_premium: Decimal
    monthly_premium: Decimal
    discounts_applied: list[Discount]
    surcharges_applied: list[Surcharge]
    rating_factors: RatingFactors
    calculation_timestamp: datetime


@beartype
class QuoteCompareRequest(BaseModel):
    """Request schema for comparing quotes."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    quote_ids: list[UUID] = Field(..., min_length=2, max_length=5)
    comparison_type: str = Field(
        default="premium", pattern=r"^(premium|coverage|features)$"
    )


@beartype
class QuoteCompareResponse(BaseModel):
    """Response schema for quote comparison."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    quotes: list[QuoteResponse]
    comparison_matrix: ComparisonMatrix
    recommendation: str | None
    best_value_quote_id: UUID | None


@beartype
class QuoteConvertRequest(BaseModel):
    """Request schema for converting quote to policy."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    quote_id: UUID
    payment_method: str = Field(..., pattern=r"^(credit_card|bank_transfer|check)$")
    payment_info: PaymentDetails
    effective_date: date | None = None


@beartype
class QuoteConvertResponse(BaseModel):
    """Response schema for quote to policy conversion."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    quote_id: UUID
    policy_id: UUID
    policy_number: str
    effective_date: date
    premium: Decimal
    payment_confirmation: PaymentDetails
    conversion_timestamp: datetime


@beartype
class QuoteSearchRequest(BaseModel):
    """Request schema for searching quotes."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    customer_id: UUID | None = None
    status: list[QuoteStatus] | None = None
    product_type: str | None = Field(None, pattern=r"^(auto|home|commercial)$")
    state: str | None = Field(None, pattern=r"^[A-Z]{2}$")
    created_after: datetime | None = None
    created_before: datetime | None = None
    expires_after: datetime | None = None
    expires_before: datetime | None = None
    min_premium: Decimal | None = None
    max_premium: Decimal | None = None

    # Sorting
    sort_by: str = Field(
        default="created_at",
        pattern=r"^(created_at|updated_at|expires_at|total_premium|quote_number)$",
    )
    sort_order: str = Field(default="desc", pattern=r"^(asc|desc)$")

    # Pagination
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


@beartype
class QuoteBulkActionRequest(BaseModel):
    """Request schema for bulk quote actions."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    quote_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    action: str = Field(..., pattern=r"^(expire|archive|delete|assign_agent)$")
    action_data: BulkActionData | None = None
    reason: str | None = Field(None, max_length=500)


@beartype
class QuoteBulkActionResponse(BaseModel):
    """Response schema for bulk quote actions."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    total_requested: int
    successful: int
    failed: int
    results: list[BulkActionResult]
    errors: list[dict[str, str]]


# Additional Pydantic models to replace dict usage in schemas


@beartype
class WizardValidation(BaseModel):
    """Wizard validation data structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    required_fields: list[str] = Field(
        default_factory=list, description="Required fields for this step"
    )
    validation_rules: list[str] = Field(
        default_factory=list, description="Validation rules to apply"
    )
    conditional_fields: list[str] = Field(
        default_factory=list, description="Conditionally required fields"
    )
    min_length: int | None = Field(None, ge=0, description="Minimum length validation")
    max_length: int | None = Field(None, ge=0, description="Maximum length validation")
    pattern: str | None = Field(None, description="Regex pattern validation")
    custom_validators: list[str] = Field(
        default_factory=list, description="Custom validator functions"
    )


@beartype
class WizardStepData(BaseModel):
    """Wizard step data structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    customer_info: dict[str, Any] = Field(
        default_factory=dict, description="Customer information collected"
    )
    vehicle_info: dict[str, Any] = Field(
        default_factory=dict, description="Vehicle information collected"
    )
    driver_info: dict[str, Any] = Field(
        default_factory=dict, description="Driver information collected"
    )
    coverage_info: dict[str, Any] = Field(
        default_factory=dict, description="Coverage selection information"
    )
    payment_info: dict[str, Any] = Field(
        default_factory=dict, description="Payment information collected"
    )
    preferences: dict[str, Any] = Field(
        default_factory=dict, description="Customer preferences"
    )

    # TODO: These dict fields should be replaced with proper Pydantic models
    # once the underlying customer/vehicle/driver models are finalized


@beartype
class ValidationErrors(BaseModel):
    """Validation error structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    field_errors: dict[str, list[str]] = Field(
        default_factory=dict, description="Field-specific validation errors"
    )
    form_errors: list[str] = Field(
        default_factory=list, description="Form-level validation errors"
    )
    warning_messages: list[str] = Field(
        default_factory=list, description="Warning messages"
    )


@beartype
class ValidationWarnings(BaseModel):
    """Validation warning structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    field_warnings: dict[str, list[str]] = Field(
        default_factory=dict, description="Field-specific warnings"
    )
    form_warnings: list[str] = Field(
        default_factory=list, description="Form-level warnings"
    )
    info_messages: list[str] = Field(
        default_factory=list, description="Informational messages"
    )


@beartype
class ComparisonMatrix(BaseModel):
    """Quote comparison matrix structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    premium_comparison: dict[str, Any] = Field(
        default_factory=dict, description="Premium comparison data"
    )
    coverage_comparison: dict[str, Any] = Field(
        default_factory=dict, description="Coverage comparison data"
    )
    discount_comparison: dict[str, Any] = Field(
        default_factory=dict, description="Discount comparison data"
    )
    feature_comparison: dict[str, Any] = Field(
        default_factory=dict, description="Feature comparison data"
    )

    # TODO: These dict fields should be replaced with proper typed models
    # once the comparison feature requirements are finalized


@beartype
class BulkActionResult(BaseModel):
    """Bulk action result structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    quote_id: UUID = Field(..., description="Quote ID that was processed")
    action_performed: str = Field(..., description="Action that was performed")
    success: bool = Field(..., description="Whether action was successful")
    result_data: dict[str, Any] = Field(
        default_factory=dict, description="Action result data"
    )
    error_message: str | None = Field(
        None, description="Error message if action failed"
    )
    warnings: list[str] = Field(default_factory=list, description="Warning messages")


@beartype
class BulkActionData(BaseModel):
    """Bulk action data structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    agent_id: UUID | None = Field(None, description="Agent ID for assignment actions")
    expiration_date: datetime | None = Field(
        None, description="New expiration date for expire actions"
    )
    archive_reason: str | None = Field(None, description="Reason for archiving")
    notes: str | None = Field(None, description="Additional notes")
    notify_customer: bool = Field(
        default=False, description="Whether to notify customer"
    )


# All quote API schemas are defined above.
# For additional schemas that may be needed, add them above this comment.
