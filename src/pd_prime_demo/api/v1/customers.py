"""Customer CRUD endpoints with pagination and search.

This module provides RESTful endpoints for managing customers
with proper validation, caching, and error handling.
"""

import json
from datetime import datetime, timezone
from uuid import UUID

import asyncpg
from beartype import beartype
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis

from ...models.customer import Customer, CustomerCreate, CustomerUpdate
from ...schemas.auth import CurrentUser
from ...schemas.common import PolicySummary
from ..dependencies import PaginationParams, get_current_user, get_db, get_redis

router = APIRouter()


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
    state_province: str | None = Field(
        None, min_length=2, max_length=100, description="Filter by state/province"
    )
    country_code: str | None = Field(
        None,
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
        description="Filter by country",
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
    # This is a placeholder implementation for Wave 1
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
        # TODO: Implement actual database insertion with customer service
        # This is a placeholder implementation for Wave 1

        # Invalidate relevant caches
        pattern = "customers:list:*"
        async for key in redis.scan_iter(match=pattern):
            await redis.delete(key)

        # Return mock customer for Wave 1 (will be replaced with actual service call)
        from uuid import uuid4

        from ...models.customer import CustomerStatus

        customer = Customer(
            id=uuid4(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            customer_number=f"CUST-{str(uuid4())[:10].replace('-', '')}0",
            status=CustomerStatus.ACTIVE,
            tax_id_masked=customer_data.tax_id,  # Already masked by CustomerCreate validator
            total_policies=0,
            risk_score=None,
            # Copy all fields from CustomerCreate (they inherit from CustomerBase)
            customer_type=customer_data.customer_type,
            first_name=customer_data.first_name,
            last_name=customer_data.last_name,
            email=customer_data.email,
            phone_number=customer_data.phone_number,
            date_of_birth=customer_data.date_of_birth,
            address_line1=customer_data.address_line1,
            address_line2=customer_data.address_line2,
            city=customer_data.city,
            state_province=customer_data.state_province,
            postal_code=customer_data.postal_code,
            country_code=customer_data.country_code,
            marketing_consent=customer_data.marketing_consent,
        )

        return customer

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create customer: {str(e)}",
        )


@router.get("/{customer_id}", response_model=Customer)
@beartype
async def get_customer(
    customer_id: UUID,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Customer:
    """Get customer by ID.

    Args:
        customer_id: Unique customer identifier
        db: Database session
        redis: Redis client for caching
        current_user: Authenticated user information

    Returns:
        Customer: Customer entity

    Raises:
        HTTPException: If customer not found
    """
    # Check cache first
    cache_key = f"customer:{customer_id}"
    cached_result = await redis.get(cache_key)

    if cached_result:
        return Customer.model_validate_json(cached_result)

    # TODO: Implement actual database query
    # This is a placeholder for Wave 1
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Customer not found",
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
    """Update customer information.

    Args:
        customer_id: Unique customer identifier
        customer_update: Updated customer data
        db: Database session
        redis: Redis client for cache invalidation
        current_user: Authenticated user information

    Returns:
        Customer: Updated customer entity

    Raises:
        HTTPException: If customer not found or update fails
    """
    try:
        # TODO: Implement actual database update with customer service
        # This is a placeholder for Wave 1

        # Invalidate caches
        await redis.delete(f"customer:{customer_id}")
        pattern = "customers:list:*"
        async for key in redis.scan_iter(match=pattern):
            await redis.delete(key)

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update customer: {str(e)}",
        )


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
@beartype
async def delete_customer(
    customer_id: UUID,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete customer account.

    Args:
        customer_id: Unique customer identifier
        db: Database session
        redis: Redis client for cache invalidation
        current_user: Authenticated user information

    Raises:
        HTTPException: If customer not found or deletion fails
    """
    try:
        # TODO: Implement actual database deletion with customer service
        # This is a placeholder for Wave 1

        # Invalidate caches
        await redis.delete(f"customer:{customer_id}")
        pattern = "customers:list:*"
        async for key in redis.scan_iter(match=pattern):
            await redis.delete(key)

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete customer: {str(e)}",
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
        customer_id: Unique customer identifier
        db: Database session
        redis: Redis client for caching
        current_user: Authenticated user information

    Returns:
        list[PolicySummary]: List of customer's policies

    Raises:
        HTTPException: If customer not found
    """
    # Check cache first
    cache_key = f"customer:{customer_id}:policies"
    cached_result = await redis.get(cache_key)

    if cached_result:
        # Safe JSON deserialization instead of eval()
        try:
            policies_data = json.loads(cached_result)
            return [PolicySummary(**policy) for policy in policies_data]
        except (json.JSONDecodeError, ValueError):
            # Invalid cache data, continue to database query
            await redis.delete(cache_key)

    # TODO: Implement actual database query for customer policies
    # This is a placeholder for Wave 1
    policies: list[PolicySummary] = []

    # Cache the result for 300 seconds (5 minutes)
    await redis.setex(
        cache_key, 300, json.dumps([policy.model_dump() for policy in policies])
    )

    return policies
