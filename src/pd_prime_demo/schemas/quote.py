"""Quote API schemas for request/response models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
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
    condition_value: str | int | float | bool | None


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
    errors: list[BulkActionError]


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

    customer_info: "WizardCustomerInfo" = Field(
        default_factory=lambda: WizardCustomerInfo(), description="Customer information collected"
    )
    vehicle_info: "WizardVehicleInfo" = Field(
        default_factory=lambda: WizardVehicleInfo(), description="Vehicle information collected"
    )
    driver_info: "WizardDriverInfo" = Field(
        default_factory=lambda: WizardDriverInfo(), description="Driver information collected"
    )
    coverage_info: "WizardCoverageInfo" = Field(
        default_factory=lambda: WizardCoverageInfo(), description="Coverage selection information"
    )
    payment_info: "WizardPaymentInfo" = Field(
        default_factory=lambda: WizardPaymentInfo(), description="Payment information collected"
    )
    preferences: "WizardPreferences" = Field(
        default_factory=lambda: WizardPreferences(), description="Customer preferences"
    )


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

    field_errors: list[FieldError] = Field(
        default_factory=list, description="Field-specific validation errors"
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

    field_warnings: list[FieldWarning] = Field(
        default_factory=list, description="Field-specific warnings"
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

    premium_comparison: "PremiumComparison" = Field(
        default_factory=lambda: PremiumComparison(), description="Premium comparison data"
    )
    coverage_comparison: "CoverageComparison" = Field(
        default_factory=lambda: CoverageComparison(), description="Coverage comparison data"
    )
    discount_comparison: "DiscountComparison" = Field(
        default_factory=lambda: DiscountComparison(), description="Discount comparison data"
    )
    feature_comparison: "FeatureComparison" = Field(
        default_factory=lambda: FeatureComparison(), description="Feature comparison data"
    )


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
    result_data: "ActionResultData" = Field(
        default_factory=lambda: ActionResultData(), description="Action result data"
    )
    error_message: str | None = Field(
        None, description="Error message if action failed"
    )
    warnings: list[str] = Field(default_factory=list, description="Warning messages")


# Wizard step data models - consolidated and structured


@beartype
class WizardCustomerInfo(BaseModel):
    """Customer information collected during wizard."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    email: str | None = Field(None, pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    phone: str | None = Field(None, pattern=r"^\+?1?\d{10,14}$")
    date_of_birth: date | None = None
    address_line1: str | None = Field(None, min_length=1, max_length=255)
    address_line2: str | None = Field(None, max_length=255)
    city: str | None = Field(None, min_length=1, max_length=100)
    state: str | None = Field(None, pattern=r"^[A-Z]{2}$")
    zip_code: str | None = Field(None, pattern=r"^\d{5}(-\d{4})?$")
    preferred_contact: str | None = Field(None, pattern=r"^(email|phone|text)$")


@beartype
class WizardVehicleInfo(BaseModel):
    """Vehicle information collected during wizard."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    vin: str | None = Field(None, min_length=17, max_length=17)
    year: int | None = Field(None, ge=1900, le=2030)
    make: str | None = Field(None, min_length=1, max_length=50)
    model: str | None = Field(None, min_length=1, max_length=50)
    trim: str | None = Field(None, max_length=50)
    vehicle_type: str | None = Field(None, pattern=r"^(sedan|suv|truck|coupe|wagon|convertible|hatchback)$")
    usage_type: str | None = Field(None, pattern=r"^(personal|business|commercial)$")
    annual_mileage: int | None = Field(None, ge=0, le=100000)
    garage_type: str | None = Field(None, pattern=r"^(garage|carport|street|driveway)$")
    anti_theft_devices: list[str] = Field(default_factory=list)
    safety_features: list[str] = Field(default_factory=list)


@beartype
class WizardDriverInfo(BaseModel):
    """Driver information collected during wizard."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    license_number: str | None = Field(None, min_length=1, max_length=20)
    license_state: str | None = Field(None, pattern=r"^[A-Z]{2}$")
    years_licensed: int | None = Field(None, ge=0, le=80)
    years_experience: int | None = Field(None, ge=0, le=80)
    good_student: bool | None = None
    defensive_driving: bool | None = None
    violations: list[str] = Field(default_factory=list)
    accidents: list[str] = Field(default_factory=list)
    claims_history: list[str] = Field(default_factory=list)
    credit_score_tier: str | None = Field(None, pattern=r"^(excellent|good|fair|poor)$")


@beartype
class WizardCoverageInfo(BaseModel):
    """Coverage information collected during wizard."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    liability_limits: str | None = Field(None, pattern=r"^\d+/\d+/\d+$")
    comprehensive_deductible: int | None = Field(None, ge=0, le=5000)
    collision_deductible: int | None = Field(None, ge=0, le=5000)
    uninsured_motorist: bool | None = None
    personal_injury_protection: bool | None = None
    rental_coverage: bool | None = None
    roadside_assistance: bool | None = None
    gap_coverage: bool | None = None
    new_car_replacement: bool | None = None


@beartype
class WizardPaymentInfo(BaseModel):
    """Payment information collected during wizard."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    payment_method: str | None = Field(None, pattern=r"^(credit_card|bank_transfer|check|paypal)$")
    payment_schedule: str | None = Field(None, pattern=r"^(monthly|quarterly|semi_annual|annual)$")
    auto_pay: bool | None = None
    paperless_billing: bool | None = None
    down_payment_amount: Decimal | None = Field(None, ge=Decimal("0"))
    payment_day: int | None = Field(None, ge=1, le=28)


@beartype
class WizardPreferences(BaseModel):
    """Customer preferences collected during wizard."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    communication_preferences: list[str] = Field(default_factory=list)
    marketing_opt_in: bool | None = None
    language_preference: str | None = Field(None, pattern=r"^(en|es|fr|de|it|pt|zh|ja|ko)$")
    accessibility_needs: list[str] = Field(default_factory=list)
    agent_preference: str | None = Field(None, pattern=r"^(online|phone|in_person|no_preference)$")
    policy_start_preference: str | None = Field(None, pattern=r"^(immediate|future_date|next_month)$")


# Comparison models - consolidated and structured


@beartype
class PremiumComparison(BaseModel):
    """Premium comparison data."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    current_premium: Decimal | None = Field(None, ge=Decimal("0"))
    competitive_premiums: list[Decimal] = Field(default_factory=list)
    market_average: Decimal | None = Field(None, ge=Decimal("0"))
    savings_potential: Decimal | None = Field(None)
    price_ranking: int | None = Field(None, ge=1)
    value_score: float | None = Field(None, ge=0, le=10)


@beartype
class CoverageComparison(BaseModel):
    """Coverage comparison data."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    current_coverage: list[str] = Field(default_factory=list)
    recommended_coverage: list[str] = Field(default_factory=list)
    coverage_gaps: list[str] = Field(default_factory=list)
    coverage_score: float | None = Field(None, ge=0, le=10)
    adequacy_rating: str | None = Field(None, pattern=r"^(excellent|good|adequate|insufficient)$")


@beartype
class DiscountComparison(BaseModel):
    """Discount comparison data."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    available_discounts: list[str] = Field(default_factory=list)
    applied_discounts: list[str] = Field(default_factory=list)
    potential_discounts: list[str] = Field(default_factory=list)
    total_discount_amount: Decimal | None = Field(None, ge=Decimal("0"))
    discount_percentage: float | None = Field(None, ge=0, le=1)


@beartype
class FeatureComparison(BaseModel):
    """Feature comparison data."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    available_features: list[str] = Field(default_factory=list)
    included_features: list[str] = Field(default_factory=list)
    optional_features: list[str] = Field(default_factory=list)
    competitor_features: list[str] = Field(default_factory=list)
    unique_features: list[str] = Field(default_factory=list)
    feature_score: float | None = Field(None, ge=0, le=10)


@beartype
class ActionResultData(BaseModel):
    """Action result data."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    affected_records: int | None = Field(None, ge=0)
    processing_time_ms: int | None = Field(None, ge=0)
    status_code: int | None = Field(None, ge=100, le=599)
    response_metadata: list[str] = Field(default_factory=list)
    validation_results: list[str] = Field(default_factory=list)
    performance_metrics: list[str] = Field(default_factory=list)


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


@beartype
class FieldError(BaseModel):
    """Field-specific validation error structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    field_name: str = Field(..., description="Name of the field with error")
    error_messages: list[str] = Field(..., description="List of error messages for this field")
    error_code: str | None = Field(None, description="Error code identifier")
    suggested_fix: str | None = Field(None, description="Suggested fix for the error")


@beartype
class FieldWarning(BaseModel):
    """Field-specific validation warning structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    field_name: str = Field(..., description="Name of the field with warning")
    warning_messages: list[str] = Field(..., description="List of warning messages for this field")
    warning_code: str | None = Field(None, description="Warning code identifier")
    severity: str = Field(
        default="low", pattern=r"^(low|medium|high)$", description="Warning severity level"
    )


@beartype
class BulkActionError(BaseModel):
    """Bulk action error structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    quote_id: UUID = Field(..., description="Quote ID that had an error")
    error_code: str = Field(..., description="Error code identifier")
    error_message: str = Field(..., description="Human-readable error message")
    field_name: str | None = Field(None, description="Field that caused the error")
    error_type: str = Field(
        ..., pattern=r"^(validation|permission|system|business_rule|timeout)$"
    )
    retry_possible: bool = Field(default=False, description="Whether this error can be retried")
    timestamp: datetime = Field(default_factory=datetime.now, description="When the error occurred")


# All quote API schemas are defined above.
# For additional schemas that may be needed, add them above this comment.
