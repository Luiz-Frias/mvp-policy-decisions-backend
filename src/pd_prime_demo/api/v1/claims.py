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
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from redis.asyncio import Redis

from pd_prime_demo.api.response_patterns import ErrorResponse, handle_result
from pd_prime_demo.core.result_types import Err

from ...core.cache import Cache
from ...core.database import Database
from ...models.claim import ClaimCreate as ServiceClaimCreate
from ...models.claim import ClaimPriority
from ...models.claim import ClaimStatus as ServiceClaimStatus
from ...models.claim import ClaimStatusUpdate as ServiceClaimStatusUpdate
from ...models.claim import ClaimType as ServiceClaimType
from ...models.claim import ClaimUpdate as ServiceClaimUpdate
from ...schemas.auth import CurrentUser
from ...services.claim_service import ClaimService
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

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

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
    @beartype
    def validate_incident_date(cls, v: date) -> date:
        """Ensure incident date is not in the future."""
        if v > date.today():
            raise ValueError("Incident date cannot be in the future")
        return v

    @model_validator(mode="after")
    @beartype
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

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

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
    @beartype
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

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    items: list[Claim] = Field(..., description="List of claims")
    total: int = Field(..., ge=0, description="Total number of claims")
    skip: int = Field(..., ge=0, description="Number of items skipped")
    limit: int = Field(..., ge=1, description="Maximum items returned")


class ClaimFilter(BaseModel):
    """Filter parameters for claim queries."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

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

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    status: ClaimStatus = Field(..., description="New status")
    reason: str = Field(
        ..., min_length=10, max_length=500, description="Reason for status change"
    )
    notes: str | None = Field(None, max_length=1000, description="Additional notes")


@router.get("/")
@beartype
async def list_claims(
    response: Response,
    pagination: PaginationParams = Depends(),
    filters: ClaimFilter = Depends(),
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> ClaimListResponse | ErrorResponse:
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

    # Initialize services with dependency validation
    if not db:
        raise ValueError("Database connection required and must be active")
    if not redis:
        raise ValueError("Cache connection required and must be available")

    database = Database(db)
    cache = Cache(redis)
    service = ClaimService(database, cache)

    # Convert API filters to service parameters
    result = await service.list(
        policy_id=filters.policy_id,
        status=filters.status.value if filters.status else None,
        limit=pagination.limit,
        offset=pagination.skip,
    )

    if isinstance(result, Err):
        return handle_result(result, response)

    claim_models = result.ok_value

    # Convert ClaimModel to API Claim
    claims = []
    for cm in claim_models:
        claims.append(
            Claim(
                id=cm.id,
                claim_number=cm.claim_number,
                created_at=cm.created_at,
                updated_at=cm.updated_at,
                policy_id=cm.policy_id,
                claim_type=ClaimType(cm.claim_type.value),
                incident_date=cm.incident_date,
                reported_date=cm.incident_date,  # Using incident_date as reported_date
                amount_claimed=cm.claimed_amount,
                description=cm.description,
                incident_location=cm.incident_location,
                status=ClaimStatus(cm.status.value),
                customer_id=uuid4(),  # Will be fetched from policy
                contact_phone="",  # Not in model
                contact_email="",  # Not in model
                adjuster_id=cm.adjuster_id,
                adjuster_notes=cm.adjuster_notes,
                approved_amount=cm.approved_amount,
                paid_amount=cm.paid_amount,
                approved_at=cm.approved_at,
                paid_at=cm.paid_at,
                closed_at=cm.closed_at,
            )
        )

    # Get total count
    count_result = await service.list(
        policy_id=filters.policy_id,
        status=filters.status.value if filters.status else None,
        limit=1000000,
        offset=0,
    )

    total = (
        len(count_result.ok_value)
        if count_result.is_ok() and count_result.ok_value is not None
        else 0
    )

    list_response = ClaimListResponse(
        items=claims, total=total, skip=pagination.skip, limit=pagination.limit
    )

    # Cache the result for 30 seconds (shorter due to frequent updates)
    await redis.setex(cache_key, 30, list_response.model_dump_json())

    return list_response


@router.post("/", status_code=status.HTTP_201_CREATED)
@beartype
async def create_claim(
    claim_data: ClaimCreate,
    response: Response,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Claim | ErrorResponse:
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
        # Initialize services with dependency validation
        if not db:
            raise ValueError("Database connection required and must be active")
        if not redis:
            raise ValueError("Cache connection required and must be available")

        database = Database(db)
        cache = Cache(redis)
        service = ClaimService(database, cache)

        # Convert API model to service model
        service_claim_data = ServiceClaimCreate(
            policy_id=claim_data.policy_id,
            claim_type=ServiceClaimType(claim_data.claim_type.value),
            incident_date=claim_data.incident_date,
            incident_location=claim_data.incident_location,
            description=claim_data.description,
            claimed_amount=claim_data.amount_claimed,
            priority=ClaimPriority.MEDIUM,  # Default priority
            supporting_documents=[],  # Empty for now
            contact_phone=claim_data.contact_phone,
            contact_email=claim_data.contact_email,
        )

        # Create claim using service
        result = await service.create(service_claim_data, claim_data.policy_id)

        if isinstance(result, Err):
            return handle_result(
                result, response, success_status=status.HTTP_201_CREATED
            )

        claim_model = result.ok_value

        # Invalidate relevant caches
        pattern = "claims:list:*"
        async for key in redis.scan_iter(match=pattern):
            await redis.delete(key)

        # Convert back to API model
        claim = Claim(
            id=claim_model.id,
            claim_number=claim_model.claim_number,
            created_at=claim_model.created_at,
            updated_at=claim_model.updated_at,
            policy_id=claim_model.policy_id,
            claim_type=ClaimType(claim_model.claim_type.value),
            incident_date=claim_model.incident_date,
            reported_date=claim_model.incident_date,
            amount_claimed=claim_model.claimed_amount,
            description=claim_model.description,
            incident_location=claim_model.incident_location,
            status=ClaimStatus(claim_model.status.value),
            customer_id=uuid4(),  # Will be fetched from policy
            contact_phone=claim_data.contact_phone,
            contact_email=claim_data.contact_email,
            adjuster_id=claim_model.adjuster_id,
            adjuster_notes=claim_model.adjuster_notes,
            approved_amount=claim_model.approved_amount,
            paid_amount=claim_model.paid_amount,
            approved_at=claim_model.approved_at,
            paid_at=claim_model.paid_at,
            closed_at=claim_model.closed_at,
        )

        return claim

    except Exception as e:
        return handle_result(
            Err(f"Failed to create claim: {str(e)}"),
            response,
            success_status=status.HTTP_201_CREATED,
        )


@router.get("/{claim_id}")
@beartype
async def get_claim(
    claim_id: UUID,
    response: Response,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Claim | ErrorResponse:
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

    # Initialize services with dependency validation
    if not db:
        raise ValueError("Database connection required and must be active")
    if not redis:
        raise ValueError("Cache connection required and must be available")

    database = Database(db)
    cache = Cache(redis)
    service = ClaimService(database, cache)

    # Get claim using service
    result = await service.get(claim_id)

    if isinstance(result, Err):
        return handle_result(result, response)

    claim_model = result.ok_value
    if not claim_model:
        return handle_result(Err(f"Claim {claim_id} not found"), response)

    # Convert to API model
    claim = Claim(
        id=claim_model.id,
        claim_number=claim_model.claim_number,
        created_at=claim_model.created_at,
        updated_at=claim_model.updated_at,
        policy_id=claim_model.policy_id,
        claim_type=ClaimType(claim_model.claim_type.value),
        incident_date=claim_model.incident_date,
        reported_date=claim_model.incident_date,
        amount_claimed=claim_model.claimed_amount,
        description=claim_model.description,
        incident_location=claim_model.incident_location,
        status=ClaimStatus(claim_model.status.value),
        customer_id=uuid4(),  # Will be fetched from policy
        contact_phone="",  # Not in model
        contact_email="",  # Not in model
        adjuster_id=claim_model.adjuster_id,
        adjuster_notes=claim_model.adjuster_notes,
        approved_amount=claim_model.approved_amount,
        paid_amount=claim_model.paid_amount,
        approved_at=claim_model.approved_at,
        paid_at=claim_model.paid_at,
        closed_at=claim_model.closed_at,
    )

    # Cache the result
    await redis.setex(cache_key, 300, claim.model_dump_json())

    return claim


@router.put("/{claim_id}")
@beartype
async def update_claim(
    claim_id: UUID,
    claim_update: ClaimUpdate,
    response: Response,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Claim | ErrorResponse:
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
    # Initialize services with dependency validation
    if not db:
        raise ValueError("Database connection required and must be active")
    if not redis:
        raise ValueError("Cache connection required and must be available")

    database = Database(db)
    cache = Cache(redis)
    service = ClaimService(database, cache)

    # Convert to service update model
    service_update = ServiceClaimUpdate(
        supporting_documents=[],  # Not exposed in API update
    )

    # Update claim using service
    result = await service.update(claim_id, service_update)

    if isinstance(result, Err):
        return handle_result(result, response)

    claim_model = result.ok_value
    if not claim_model:
        return handle_result(Err(f"Claim {claim_id} not found"), response)

    # If status update requested, handle separately
    if claim_update.status:
        status_result = await service.update_status(
            claim_id,
            ServiceClaimStatusUpdate(
                status=ServiceClaimStatus(claim_update.status.value),
                amount_approved=claim_update.approved_amount,
                notes=claim_update.adjuster_notes,
            ),
        )

        if isinstance(status_result, Err):
            return handle_result(status_result, response)

        claim_model = status_result.ok_value
        if not claim_model:
            return handle_result(
                Err(f"Claim {claim_id} not found after status update"), response
            )

    # Invalidate caches
    await redis.delete(f"claims:{claim_id}")
    pattern = "claims:list:*"
    async for key in redis.scan_iter(match=pattern):
        await redis.delete(key)

    # Convert to API model
    claim = Claim(
        id=claim_model.id,
        claim_number=claim_model.claim_number,
        created_at=claim_model.created_at,
        updated_at=claim_model.updated_at,
        policy_id=claim_model.policy_id,
        claim_type=ClaimType(claim_model.claim_type.value),
        incident_date=claim_model.incident_date,
        reported_date=claim_model.incident_date,
        amount_claimed=claim_model.claimed_amount,
        description=claim_model.description,
        incident_location=claim_model.incident_location,
        status=ClaimStatus(claim_model.status.value),
        customer_id=uuid4(),  # Will be fetched from policy
        contact_phone="",  # Not in model
        contact_email="",  # Not in model
        adjuster_id=claim_model.adjuster_id,
        adjuster_notes=claim_model.adjuster_notes,
        approved_amount=claim_model.approved_amount,
        paid_amount=claim_model.paid_amount,
        approved_at=claim_model.approved_at,
        paid_at=claim_model.paid_at,
        closed_at=claim_model.closed_at,
    )

    return claim


@router.post("/{claim_id}/status")
@beartype
async def update_claim_status(
    claim_id: UUID,
    status_update: ClaimStatusUpdate,
    response: Response,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Claim | ErrorResponse:
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
    # Initialize services with dependency validation
    if not db:
        raise ValueError("Database connection required and must be active")
    if not redis:
        raise ValueError("Cache connection required and must be available")

    database = Database(db)
    cache = Cache(redis)
    service = ClaimService(database, cache)

    # Update claim status using service
    result = await service.update_status(
        claim_id,
        ServiceClaimStatusUpdate(
            status=ServiceClaimStatus(status_update.status.value),
            amount_approved=None,  # Not in this API
            notes=status_update.notes,
        ),
    )

    if isinstance(result, Err):
        return handle_result(result, response)

    claim_model = result.ok_value
    if not claim_model:
        return handle_result(Err(f"Claim {claim_id} not found"), response)

    # Invalidate caches
    await redis.delete(f"claims:{claim_id}")
    pattern = "claims:list:*"
    async for key in redis.scan_iter(match=pattern):
        await redis.delete(key)

    # Convert to API model
    claim = Claim(
        id=claim_model.id,
        claim_number=claim_model.claim_number,
        created_at=claim_model.created_at,
        updated_at=claim_model.updated_at,
        policy_id=claim_model.policy_id,
        claim_type=ClaimType(claim_model.claim_type.value),
        incident_date=claim_model.incident_date,
        reported_date=claim_model.incident_date,
        amount_claimed=claim_model.claimed_amount,
        description=claim_model.description,
        incident_location=claim_model.incident_location,
        status=ClaimStatus(claim_model.status.value),
        customer_id=uuid4(),  # Will be fetched from policy
        contact_phone="",  # Not in model
        contact_email="",  # Not in model
        adjuster_id=claim_model.adjuster_id,
        adjuster_notes=claim_model.adjuster_notes,
        approved_amount=claim_model.approved_amount,
        paid_amount=claim_model.paid_amount,
        approved_at=claim_model.approved_at,
        paid_at=claim_model.paid_at,
        closed_at=claim_model.closed_at,
    )

    return claim


@router.delete("/{claim_id}")
@beartype
async def delete_claim(
    claim_id: UUID,
    response: Response,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> None | ErrorResponse:
    """Delete a claim (only allowed for DRAFT status).

    Args:
        claim_id: UUID of the claim to delete
        db: Database session
        redis: Redis client for cache invalidation
        current_user: Authenticated user information

    Raises:
        HTTPException: If claim not found or not in DRAFT status
    """
    # Initialize services with dependency validation
    if not db:
        raise ValueError("Database connection required and must be active")
    if not redis:
        raise ValueError("Cache connection required and must be available")

    database = Database(db)
    cache = Cache(redis)
    service = ClaimService(database, cache)

    # Delete claim using service
    result = await service.delete(claim_id)

    if isinstance(result, Err):
        return handle_result(result, response)

    # This is a placeholder implementation

    # Invalidate caches
    await redis.delete(f"claims:{claim_id}")
    pattern = "claims:list:*"
    async for key in redis.scan_iter(match=pattern):
        await redis.delete(key)

    return handle_result(Err(f"Claim {claim_id} not found"), response)
