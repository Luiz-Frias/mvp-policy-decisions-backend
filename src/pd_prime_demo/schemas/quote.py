"""Quote API schemas for request/response models."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional, List, Dict
from uuid import UUID

from beartype import beartype
from pydantic import BaseModel, Field

from ..models.quote import (
    QuoteStatus, VehicleInfo, DriverInfo,
    CoverageSelection, Discount, ProductType, ContactMethod
)


# Request schemas

@beartype
class QuoteCreateRequest(BaseModel):
    """Request schema for creating a quote."""
    
    customer_id: Optional[UUID] = None
    product_type: str = Field(..., pattern=r'^(auto|home|commercial)$')
    state: str = Field(..., pattern=r'^[A-Z]{2}$')
    zip_code: str = Field(..., pattern=r'^\d{5}(-\d{4})?$')
    effective_date: date
    email: Optional[str] = Field(None, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    phone: Optional[str] = Field(None, pattern=r'^\+?1?\d{10,14}$')
    preferred_contact: str = Field(default="email", pattern=r'^(email|phone|text)$')
    vehicle_info: Optional[VehicleInfo] = None
    drivers: List[DriverInfo] = Field(default_factory=list)
    coverage_selections: List[CoverageSelection] = Field(default_factory=list)


@beartype
class QuoteUpdateRequest(BaseModel):
    """Request schema for updating a quote."""
    
    vehicle_info: Optional[VehicleInfo] = None
    drivers: Optional[List[DriverInfo]] = None
    coverage_selections: Optional[List[CoverageSelection]] = None
    effective_date: Optional[date] = None
    email: Optional[str] = Field(None, pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    phone: Optional[str] = Field(None, pattern=r'^\+?1?\d{10,14}$')
    preferred_contact: Optional[str] = Field(None, pattern=r'^(email|phone|text)$')


# Response schemas

@beartype
class QuoteResponse(BaseModel):
    """Response schema for quote details."""
    
    id: UUID
    quote_number: str
    customer_id: Optional[UUID]
    status: QuoteStatus
    product_type: str
    state: str
    zip_code: str
    effective_date: date
    email: Optional[str]
    phone: Optional[str]
    preferred_contact: str
    
    # Details
    vehicle_info: Optional[VehicleInfo]
    drivers: List[DriverInfo]
    coverage_selections: List[CoverageSelection]
    
    # Pricing
    base_premium: Optional[Decimal]
    total_premium: Optional[Decimal]
    monthly_premium: Optional[Decimal]
    discounts_applied: List[Discount]
    surcharges_applied: List[Dict[str, Any]]
    total_discount_amount: Optional[Decimal]
    total_surcharge_amount: Optional[Decimal]
    
    # Rating
    rating_factors: Optional[Dict[str, Any]]
    rating_tier: Optional[str]
    ai_risk_score: Optional[Decimal]
    ai_risk_factors: Optional[Dict[str, Any]]
    
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
    
    quotes: List[QuoteResponse]
    total: int
    limit: int
    offset: int


@beartype
class QuoteConversionResponse(BaseModel):
    """Response schema for quote to policy conversion."""
    
    quote_id: UUID
    policy_id: UUID
    policy_number: str
    effective_date: date
    premium: Decimal
    payment_confirmation: Dict[str, Any]


# Wizard schemas

@beartype
class WizardStepResponse(BaseModel):
    """Response schema for wizard step information."""
    
    step_id: str
    title: str
    description: str
    fields: List[str]
    validations: Dict[str, Any]
    next_step: Optional[str]
    previous_step: Optional[str]
    is_conditional: bool
    condition_field: Optional[str]
    condition_value: Optional[Any]


@beartype
class WizardSessionResponse(BaseModel):
    """Response schema for wizard session state."""
    
    session_id: UUID
    quote_id: Optional[UUID]
    current_step: str
    completed_steps: List[str]
    data: Dict[str, Any]
    validation_errors: Dict[str, List[str]]
    started_at: datetime
    last_updated: datetime
    expires_at: datetime
    is_complete: bool
    completion_percentage: int


@beartype
class WizardValidationResponse(BaseModel):
    """Response schema for wizard validation results."""
    
    is_valid: bool
    errors: Dict[str, List[str]]
    warnings: Dict[str, List[str]]


# Additional schemas for complete API coverage

@beartype
class QuoteListResponse(BaseModel):
    """Response schema for listing quotes."""
    
    quotes: List[QuoteResponse]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    has_next: bool
    has_previous: bool


@beartype
class QuoteCalculateRequest(BaseModel):
    """Request schema for calculating quote premium."""
    
    quote_id: UUID
    force_recalculate: bool = Field(default=False)


@beartype
class QuoteCalculateResponse(BaseModel):
    """Response schema for quote calculation results."""
    
    quote_id: UUID
    base_premium: Decimal
    total_premium: Decimal
    monthly_premium: Decimal
    discounts_applied: List[Discount]
    surcharges_applied: List[Dict[str, Any]]
    rating_factors: Dict[str, Any]
    calculation_timestamp: datetime


@beartype
class QuoteCompareRequest(BaseModel):
    """Request schema for comparing quotes."""
    
    quote_ids: List[UUID] = Field(..., min_items=2, max_items=5)
    comparison_type: str = Field(default="premium", pattern=r'^(premium|coverage|features)$')


@beartype
class QuoteCompareResponse(BaseModel):
    """Response schema for quote comparison."""
    
    quotes: List[QuoteResponse]
    comparison_matrix: Dict[str, Dict[str, Any]]
    recommendation: Optional[str]
    best_value_quote_id: Optional[UUID]


@beartype
class QuoteConvertRequest(BaseModel):
    """Request schema for converting quote to policy."""
    
    quote_id: UUID
    payment_method: str = Field(..., pattern=r'^(credit_card|bank_transfer|check)$')
    payment_info: Dict[str, Any]
    effective_date: Optional[date] = None


@beartype
class QuoteConvertResponse(BaseModel):
    """Response schema for quote to policy conversion."""
    
    quote_id: UUID
    policy_id: UUID
    policy_number: str
    effective_date: date
    premium: Decimal
    payment_confirmation: Dict[str, Any]
    conversion_timestamp: datetime


@beartype
class QuoteSearchRequest(BaseModel):
    """Request schema for searching quotes."""
    
    customer_id: Optional[UUID] = None
    status: Optional[List[QuoteStatus]] = None
    product_type: Optional[str] = Field(None, pattern=r'^(auto|home|commercial)$')
    state: Optional[str] = Field(None, pattern=r'^[A-Z]{2}$')
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    expires_after: Optional[datetime] = None
    expires_before: Optional[datetime] = None
    min_premium: Optional[Decimal] = None
    max_premium: Optional[Decimal] = None
    
    # Sorting
    sort_by: str = Field(default="created_at", pattern=r'^(created_at|updated_at|expires_at|total_premium|quote_number)$')
    sort_order: str = Field(default="desc", pattern=r'^(asc|desc)$')
    
    # Pagination
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


@beartype
class QuoteBulkActionRequest(BaseModel):
    """Request schema for bulk quote actions."""
    
    quote_ids: List[UUID] = Field(..., min_items=1, max_items=100)
    action: str = Field(..., pattern=r'^(expire|archive|delete|assign_agent)$')
    action_data: Optional[Dict[str, Any]] = None
    reason: Optional[str] = Field(None, max_length=500)


@beartype
class QuoteBulkActionResponse(BaseModel):
    """Response schema for bulk quote actions."""
    
    total_requested: int
    successful: int
    failed: int
    results: List[Dict[str, Any]]
    errors: List[Dict[str, str]]


# All quote API schemas are defined above.
# For additional schemas that may be needed, add them above this comment.