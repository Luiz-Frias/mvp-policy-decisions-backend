"""Customer CRUD endpoints with pagination and search.

This module provides RESTful endpoints for managing customers
with proper validation, caching, and error handling.
"""

from datetime import date, datetime
from uuid import UUID, uuid4

import asyncpg
from beartype import beartype
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from redis.asyncio import Redis

from ...schemas.auth import CurrentUser
from ...schemas.common import PolicySummary
from ..dependencies import PaginationParams, get_current_user, get_db, get_redis

router = APIRouter()


class CustomerBase(BaseModel):
    """Base customer attributes shared across operations."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr = Field(..., description="Customer email address")
    phone: str = Field(..., pattern=r"^\+?1?\d{10,14}$", description="Phone number")
    date_of_birth: date = Field(..., description="Customer's date of birth")

    address_line1: str = Field(..., min_length=1, max_length=200)
    address_line2: str | None = Field(None, max_length=200)
    city: str = Field(..., min_length=1, max_length=100)
    state: str = Field(..., min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    zip_code: str = Field(..., pattern=r"^\d{5}(-\d{4})?$")

    @field_validator("date_of_birth")
    @classmethod
    def validate_age(cls, v: date) -> date:
        """Ensure customer is at least 18 years old."""
        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 18:
            raise ValueError("Customer must be at least 18 years old")
        if age > 120:
            raise ValueError("Invalid date of birth")
        return v


class CustomerCreate(CustomerBase):
    """Model for creating a new customer."""

    marketing_consent: bool = Field(
        False, description="Consent for marketing communications"
    )
    preferred_contact_method: str = Field("email", pattern=r"^(email|phone|sms)$")


class CustomerUpdate(BaseModel):
    """Model for updating customer information."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    first_name: str | None = Field(None, min_length=1, max_length=100)
    last_name: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(None, pattern=r"^\+?1?\d{10,14}$")

    address_line1: str | None = Field(None, min_length=1, max_length=200)
    address_line2: str | None = Field(None, max_length=200)
    city: str | None = Field(None, min_length=1, max_length=100)
    state: str | None = Field(None, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    zip_code: str | None = Field(None, pattern=r"^\d{5}(-\d{4})?$")

    marketing_consent: bool | None = None
    preferred_contact_method: str | None = Field(None, pattern=r"^(email|phone|sms)$")


class Customer(CustomerBase):
    """Complete customer entity with all attributes."""

    id: UUID = Field(..., description="Unique customer identifier")
    created_at: datetime = Field(..., description="Customer creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    marketing_consent: bool = Field(..., description="Marketing consent status")
    preferred_contact_method: str = Field(..., description="Preferred contact method")

    is_active: bool = Field(True, description="Whether customer account is active")
    total_policies: int = Field(0, ge=0, description="Total number of policies")
    total_claims: int = Field(0, ge=0, description="Total number of claims filed")


class CustomerListResponse(BaseModel):
    """Response model for customer list endpoints."""

    model_config = ConfigDict(frozen=True)

    items: list[Customer] = Field(..., description="List of customers")
    total: int = Field(..., ge=0, description="Total number of customers")
    skip: int = Field(..., ge=0, description="Number of items skipped")
    limit: int = Field(..., ge=1, description="Maximum items returned")


class CustomerFilter(BaseModel):
    """Filter parameters for customer queries."""

    model_config = ConfigDict(frozen=True)

    search: str | None = Field(None, description="Search by name or email")
    state: str | None = Field(
        None, pattern=r"^[A-Z]{2}$", description="Filter by state"
    )
    is_active: bool | None = Field(None, description="Filter by active status")
    has_policies: bool | None = Field(
        None, description="Filter customers with/without policies"
    )


@router.get("/", response_model=CustomerListResponse)
@beartype
async def list_customers(
    pagination: PaginationParams = Depends(),
    filters: CustomerFilter = Depends(),
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> CustomerListResponse:
    """List customers with pagination and filtering.

    Args:
        pagination: Pagination parameters (skip, limit)
        filters: Optional filters for customer query
        db: Database session
        redis: Redis client for caching
        current_user: Authenticated user information

    Returns:
        CustomerListResponse: Paginated list of customers
    """
    # Check cache first
    cache_key = (
        f"customers:list:{pagination.skip}:{pagination.limit}:{hash(str(filters))}"
    )
    cached_result = await redis.get(cache_key)

    if cached_result:
        return CustomerListResponse.model_validate_json(cached_result)

    # TODO: Implement actual database query with filters
    # This is a placeholder implementation
    customers: list[Customer] = []
    total = 0

    response = CustomerListResponse(
        items=customers, total=total, skip=pagination.skip, limit=pagination.limit
    )

    # Cache the result for 60 seconds
    await redis.setex(cache_key, 60, response.model_dump_json())

    return response


@router.post("/", response_model=Customer, status_code=status.HTTP_201_CREATED)
@beartype
async def create_customer(
    customer_data: CustomerCreate,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Customer:
    """Create a new customer.

    Args:
        customer_data: Customer creation data
        db: Database session
        redis: Redis client for cache invalidation
        current_user: Authenticated user information

    Returns:
        Customer: Created customer entity

    Raises:
        HTTPException: If customer creation fails
    """
    try:
        # TODO: Check for duplicate email
        # TODO: Implement actual database insertion

        # Invalidate relevant caches
        pattern = "customers:list:*"
        async for key in redis.scan_iter(match=pattern):
            await redis.delete(key)

        # Return mock customer for now
        customer = Customer(
            id=uuid4(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            **customer_data.model_dump(),
        )

        return customer

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create customer: {str(e)}",
        ) from e


@router.get("/{customer_id}", response_model=Customer)
@beartype
async def get_customer(
    customer_id: UUID,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Customer:
    """Retrieve a specific customer by ID.

    Args:
        customer_id: UUID of the customer
        db: Database session
        redis: Redis client for caching
        current_user: Authenticated user information

    Returns:
        Customer: Retrieved customer entity

    Raises:
        HTTPException: If customer not found
    """
    # Check cache first
    cache_key = f"customers:{customer_id}"
    cached_customer = await redis.get(cache_key)

    if cached_customer:
        return Customer.model_validate_json(cached_customer)

    # TODO: Implement actual database query
    # This is a placeholder implementation

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Customer {customer_id} not found",
    )


@router.put("/{customer_id}", response_model=Customer)
@beartype
async def update_customer(
    customer_id: UUID,
    customer_update: CustomerUpdate,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Customer:
    """Update an existing customer.

    Args:
        customer_id: UUID of the customer to update
        customer_update: Fields to update
        db: Database session
        redis: Redis client for cache invalidation
        current_user: Authenticated user information

    Returns:
        Customer: Updated customer entity

    Raises:
        HTTPException: If customer not found or update fails
    """
    # TODO: Implement actual database update
    # This is a placeholder implementation

    # Invalidate caches
    await redis.delete(f"customers:{customer_id}")
    pattern = "customers:list:*"
    async for key in redis.scan_iter(match=pattern):
        await redis.delete(key)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Customer {customer_id} not found",
    )


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
@beartype
async def delete_customer(
    customer_id: UUID,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a customer (soft delete by setting is_active to False).

    Args:
        customer_id: UUID of the customer to delete
        db: Database session
        redis: Redis client for cache invalidation
        current_user: Authenticated user information

    Raises:
        HTTPException: If customer not found or has active policies
    """
    # TODO: Check for active policies before deletion
    # TODO: Implement actual soft delete (is_active = False)
    # This is a placeholder implementation

    # Invalidate caches
    await redis.delete(f"customers:{customer_id}")
    pattern = "customers:list:*"
    async for key in redis.scan_iter(match=pattern):
        await redis.delete(key)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Customer {customer_id} not found",
    )


@router.get("/{customer_id}/policies", response_model=list[PolicySummary])
@beartype
async def get_customer_policies(
    customer_id: UUID,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[PolicySummary]:
    """Get all policies for a specific customer.

    Args:
        customer_id: UUID of the customer
        db: Database session
        redis: Redis client for caching
        current_user: Authenticated user information

    Returns:
        list: List of customer's policies

    Raises:
        HTTPException: If customer not found
    """
    # TODO: Implement actual query to fetch customer's policies
    # This is a placeholder implementation

    return []
