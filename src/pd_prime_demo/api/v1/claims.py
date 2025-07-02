"""Claim CRUD endpoints with workflow management.

This module provides RESTful endpoints for managing insurance claims
with proper validation, state transitions, and audit logging.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

import asyncpg
from beartype import beartype
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from redis.asyncio import Redis

from ...schemas.auth import CurrentUser
from ..dependencies import PaginationParams, get_current_user, get_db, get_redis

router = APIRouter()


class ClaimStatus(str, Enum):
    """Enumeration of claim lifecycle states."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    PENDING_DOCUMENTS = "PENDING_DOCUMENTS"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAID = "PAID"
    CLOSED = "CLOSED"


class ClaimType(str, Enum):
    """Enumeration of claim types."""

    ACCIDENT = "ACCIDENT"
    THEFT = "THEFT"
    DAMAGE = "DAMAGE"
    LIABILITY = "LIABILITY"
    MEDICAL = "MEDICAL"
    OTHER = "OTHER"


class ClaimBase(BaseModel):
    """Base claim attributes shared across operations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: UUID = Field(..., description="Associated policy ID")
    claim_type: ClaimType = Field(..., description="Type of claim")

    incident_date: date = Field(..., description="Date of incident")
    reported_date: date = Field(..., description="Date claim was reported")

    amount_claimed: Decimal = Field(
        ...,
        ge=Decimal("0.01"),
        decimal_places=2,
        max_digits=12,
        description="Amount being claimed",
    )

    description: str = Field(
        ..., min_length=10, max_length=2000, description="Incident description"
    )
    incident_location: str = Field(
        ..., min_length=5, max_length=500, description="Location of incident"
    )

    @field_validator("incident_date")
    @classmethod
    def validate_incident_date(cls, v: date) -> date:
        """Ensure incident date is not in the future."""
        if v > date.today():
            raise ValueError("Incident date cannot be in the future")
        return v

    @model_validator(mode="after")
    def validate_dates(self) -> "ClaimBase":
        """Ensure reported date is after or equal to incident date."""
        if self.reported_date < self.incident_date:
            raise ValueError("Reported date cannot be before incident date")

        # Check reporting window (e.g., must report within 30 days)
        days_difference = (self.reported_date - self.incident_date).days
        if days_difference > 30:
            raise ValueError("Claims must be reported within 30 days of incident")

        return self


class ClaimCreate(ClaimBase):
    """Model for creating a new claim."""

    status: ClaimStatus = Field(
        default=ClaimStatus.DRAFT, description="Initial claim status"
    )

    contact_phone: str = Field(
        ..., pattern=r"^\+?1?\d{10,14}$", description="Contact phone"
    )
    contact_email: str = Field(..., description="Contact email")

    police_report_number: str | None = Field(
        None, max_length=50, description="Police report number if applicable"
    )

    witness_info: str | None = Field(
        None, max_length=1000, description="Witness information if available"
    )


class ClaimUpdate(BaseModel):
    """Model for updating claim information."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ClaimStatus | None = None
    amount_claimed: Decimal | None = Field(
        None, ge=Decimal("0.01"), decimal_places=2, max_digits=12
    )

    description: str | None = Field(None, min_length=10, max_length=2000)
    incident_location: str | None = Field(None, min_length=5, max_length=500)

    contact_phone: str | None = Field(None, pattern=r"^\+?1?\d{10,14}$")
    contact_email: str | None = None

    police_report_number: str | None = Field(None, max_length=50)
    witness_info: str | None = Field(None, max_length=1000)

    adjuster_notes: str | None = Field(
        None, max_length=2000, description="Internal adjuster notes"
    )
    approved_amount: Decimal | None = Field(
        None,
        ge=Decimal("0.00"),
        decimal_places=2,
        max_digits=12,
        description="Approved claim amount",
    )

    @model_validator(mode="after")
    def validate_status_transitions(self) -> "ClaimUpdate":
        """Validate status transitions follow business rules."""
        # Status transition validation would be done against current status
        # This is a simplified version
        if self.status == ClaimStatus.PAID and self.approved_amount is None:
            raise ValueError("Approved amount must be set before marking claim as paid")
        return self


class Claim(ClaimBase):
    """Complete claim entity with all attributes."""

    id: UUID = Field(..., description="Unique claim identifier")
    claim_number: str = Field(
        ..., pattern=r"^CLM-\d{4}-\d{6}$", description="Unique claim number"
    )

    created_at: datetime = Field(..., description="Claim creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    status: ClaimStatus = Field(..., description="Current claim status")

    customer_id: UUID = Field(..., description="Customer who filed the claim")
    contact_phone: str = Field(..., description="Contact phone number")
    contact_email: str = Field(..., description="Contact email address")

    police_report_number: str | None = None
    witness_info: str | None = None

    adjuster_id: UUID | None = Field(None, description="Assigned adjuster ID")
    adjuster_notes: str | None = Field(None, description="Internal adjuster notes")

    approved_amount: Decimal | None = Field(None, description="Approved claim amount")
    paid_amount: Decimal | None = Field(None, description="Actually paid amount")

    approved_at: datetime | None = Field(None, description="Approval timestamp")
    rejected_at: datetime | None = Field(None, description="Rejection timestamp")
    paid_at: datetime | None = Field(None, description="Payment timestamp")
    closed_at: datetime | None = Field(None, description="Closure timestamp")


class ClaimListResponse(BaseModel):
    """Response model for claim list endpoints."""

    model_config = ConfigDict(frozen=True)

    items: list[Claim] = Field(..., description="List of claims")
    total: int = Field(..., ge=0, description="Total number of claims")
    skip: int = Field(..., ge=0, description="Number of items skipped")
    limit: int = Field(..., ge=1, description="Maximum items returned")


class ClaimFilter(BaseModel):
    """Filter parameters for claim queries."""

    model_config = ConfigDict(frozen=True)

    status: ClaimStatus | None = None
    claim_type: ClaimType | None = None
    policy_id: UUID | None = None
    customer_id: UUID | None = None
    adjuster_id: UUID | None = None

    min_amount: float | None = Field(None, ge=0)
    max_amount: float | None = Field(None, ge=0)

    incident_date_from: date | None = None
    incident_date_to: date | None = None


class ClaimStatusUpdate(BaseModel):
    """Model for claim status transitions."""

    model_config = ConfigDict(frozen=True)

    status: ClaimStatus = Field(..., description="New status")
    reason: str = Field(
        ..., min_length=10, max_length=500, description="Reason for status change"
    )
    notes: str | None = Field(None, max_length=1000, description="Additional notes")


@router.get("/", response_model=ClaimListResponse)
@beartype
async def list_claims(
    pagination: PaginationParams = Depends(),
    filters: ClaimFilter = Depends(),
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> ClaimListResponse:
    """List claims with pagination and filtering.

    Args:
        pagination: Pagination parameters (skip, limit)
        filters: Optional filters for claim query
        db: Database session
        redis: Redis client for caching
        current_user: Authenticated user information

    Returns:
        ClaimListResponse: Paginated list of claims
    """
    # Check cache first
    cache_key = f"claims:list:{pagination.skip}:{pagination.limit}:{hash(str(filters))}"
    cached_result = await redis.get(cache_key)

    if cached_result:
        return ClaimListResponse.model_validate_json(cached_result)

    # TODO: Implement actual database query with filters
    # This is a placeholder implementation
    claims: list[Claim] = []
    total = 0

    response = ClaimListResponse(
        items=claims, total=total, skip=pagination.skip, limit=pagination.limit
    )

    # Cache the result for 30 seconds (shorter due to frequent updates)
    await redis.setex(cache_key, 30, response.model_dump_json())

    return response


@router.post("/", response_model=Claim, status_code=status.HTTP_201_CREATED)
@beartype
async def create_claim(
    claim_data: ClaimCreate,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Claim:
    """Create a new insurance claim.

    Args:
        claim_data: Claim creation data
        db: Database session
        redis: Redis client for cache invalidation
        current_user: Authenticated user information

    Returns:
        Claim: Created claim entity

    Raises:
        HTTPException: If claim creation fails
    """
    try:
        # TODO: Validate policy exists and is active
        # TODO: Validate customer owns the policy
        # TODO: Generate unique claim number
        # TODO: Implement actual database insertion

        # Invalidate relevant caches
        pattern = "claims:list:*"
        async for key in redis.scan_iter(match=pattern):
            await redis.delete(key)

        # Return mock claim for now
        claim = Claim(
            id=uuid4(),
            claim_number=f"CLM-{datetime.now().year}-{datetime.now().strftime('%m%d%H%M')}",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            customer_id=uuid4(),  # Would come from policy lookup
            **claim_data.model_dump(),
        )

        return claim

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create claim: {str(e)}",
        ) from e


@router.get("/{claim_id}", response_model=Claim)
@beartype
async def get_claim(
    claim_id: UUID,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Claim:
    """Retrieve a specific claim by ID.

    Args:
        claim_id: UUID of the claim
        db: Database session
        redis: Redis client for caching
        current_user: Authenticated user information

    Returns:
        Claim: Retrieved claim entity

    Raises:
        HTTPException: If claim not found
    """
    # Check cache first
    cache_key = f"claims:{claim_id}"
    cached_claim = await redis.get(cache_key)

    if cached_claim:
        return Claim.model_validate_json(cached_claim)

    # TODO: Implement actual database query
    # This is a placeholder implementation

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"Claim {claim_id} not found"
    )


@router.put("/{claim_id}", response_model=Claim)
@beartype
async def update_claim(
    claim_id: UUID,
    claim_update: ClaimUpdate,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Claim:
    """Update an existing claim.

    Args:
        claim_id: UUID of the claim to update
        claim_update: Fields to update
        db: Database session
        redis: Redis client for cache invalidation
        current_user: Authenticated user information

    Returns:
        Claim: Updated claim entity

    Raises:
        HTTPException: If claim not found or update fails
    """
    # TODO: Validate status transitions
    # TODO: Implement actual database update
    # TODO: Create audit log entry
    # This is a placeholder implementation

    # Invalidate caches
    await redis.delete(f"claims:{claim_id}")
    pattern = "claims:list:*"
    async for key in redis.scan_iter(match=pattern):
        await redis.delete(key)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"Claim {claim_id} not found"
    )


@router.post("/{claim_id}/status", response_model=Claim)
@beartype
async def update_claim_status(
    claim_id: UUID,
    status_update: ClaimStatusUpdate,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Claim:
    """Update claim status with audit trail.

    Args:
        claim_id: UUID of the claim
        status_update: New status and reason
        db: Database session
        redis: Redis client for cache invalidation
        current_user: Authenticated user information

    Returns:
        Claim: Updated claim entity

    Raises:
        HTTPException: If claim not found or transition invalid
    """
    # TODO: Fetch current claim
    # TODO: Validate status transition is allowed
    # TODO: Update claim status
    # TODO: Create audit log entry
    # TODO: Send notifications if needed

    # Invalidate caches
    await redis.delete(f"claims:{claim_id}")
    pattern = "claims:list:*"
    async for key in redis.scan_iter(match=pattern):
        await redis.delete(key)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"Claim {claim_id} not found"
    )


@router.delete("/{claim_id}", status_code=status.HTTP_204_NO_CONTENT)
@beartype
async def delete_claim(
    claim_id: UUID,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a claim (only allowed for DRAFT status).

    Args:
        claim_id: UUID of the claim to delete
        db: Database session
        redis: Redis client for cache invalidation
        current_user: Authenticated user information

    Raises:
        HTTPException: If claim not found or not in DRAFT status
    """
    # TODO: Fetch claim and verify it's in DRAFT status
    # TODO: Implement actual deletion
    # This is a placeholder implementation

    # Invalidate caches
    await redis.delete(f"claims:{claim_id}")
    pattern = "claims:list:*"
    async for key in redis.scan_iter(match=pattern):
        await redis.delete(key)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"Claim {claim_id} not found"
    )
