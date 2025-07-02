"""Policy CRUD endpoints with pagination and filtering.

This module provides RESTful endpoints for managing insurance policies
with proper validation, caching, and error handling.
"""

from collections.abc import AsyncGenerator
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import asyncpg
from beartype import beartype
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis

from ...models.policy import (
    Policy,
    PolicyCreate,
    PolicyStatus,
    PolicyType,
    PolicyUpdate,
)
from ...schemas.auth import CurrentUser
from ..dependencies import PaginationParams, get_current_user, get_db, get_redis

router = APIRouter()


class PolicyListResponse(BaseModel):
    """Response model for policy list endpoints."""

    model_config = ConfigDict(frozen=True)

    items: list[Policy] = Field(..., description="List of policies")
    total: int = Field(..., ge=0, description="Total number of policies")
    skip: int = Field(..., ge=0, description="Number of items skipped")
    limit: int = Field(..., ge=1, description="Maximum items returned")


class PolicyFilter(BaseModel):
    """Filter parameters for policy queries."""

    model_config = ConfigDict(frozen=True)

    status: PolicyStatus | None = Field(None, description="Filter by status")
    policy_type: PolicyType | None = Field(None, description="Filter by type")
    customer_id: UUID | None = Field(None, description="Filter by customer")
    min_premium: float | None = Field(None, ge=0, description="Minimum premium")
    max_premium: float | None = Field(None, ge=0, description="Maximum premium")


@router.get("/", response_model=PolicyListResponse)
@beartype
async def list_policies(
    pagination: PaginationParams = Depends(),
    filters: PolicyFilter = Depends(),
    db: AsyncGenerator[asyncpg.Connection, None] = Depends(get_db),
    redis: Redis = Depends(get_redis),
    # current_user: CurrentUser = Depends(get_current_user),  # Demo mode
) -> PolicyListResponse:
    """List policies with pagination and filtering.

    Args:
        pagination: Pagination parameters (skip, limit)
        filters: Optional filters for policy query
        db: Database session
        redis: Redis client for caching
        current_user: Authenticated user information

    Returns:
        PolicyListResponse: Paginated list of policies
    """
    # Check cache first
    cache_key = (
        f"policies:list:{pagination.skip}:{pagination.limit}:{hash(str(filters))}"
    )
    cached_result = await redis.get(cache_key)

    if cached_result:
        return PolicyListResponse.model_validate_json(cached_result)

    # Properly handle async generator from FastAPI dependency
    async for connection in db:
        # TODO: Implement actual database query with filters
        # For now, return mock data for demo
        mock_policies = [
            Policy(
                id=uuid4(),
                policy_number="POL-2025-000001",
                policy_type=PolicyType.AUTO,
                customer_id=uuid4(),
                premium_amount=Decimal("150.00"),
                coverage_amount=Decimal("50000.00"),
                deductible=Decimal("500.00"),
                effective_date=date(2025, 1, 1),
                expiration_date=date(2025, 12, 31),
                status=PolicyStatus.ACTIVE,
                notes="Demo auto policy",
                cancelled_at=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
            Policy(
                id=uuid4(),
                policy_number="POL-2025-000002",
                policy_type=PolicyType.HOME,
                customer_id=uuid4(),
                premium_amount=Decimal("275.00"),
                coverage_amount=Decimal("150000.00"),
                deductible=Decimal("1000.00"),
                effective_date=date(2025, 1, 15),
                expiration_date=date(2026, 1, 15),
                status=PolicyStatus.ACTIVE,
                notes="Demo home policy",
                cancelled_at=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            ),
        ]

        response = PolicyListResponse(
            items=mock_policies,
            total=len(mock_policies),
            skip=pagination.skip,
            limit=pagination.limit,
        )
        break  # Use the first (and only) yielded connection

    # Cache the result for 60 seconds
    await redis.setex(cache_key, 60, response.model_dump_json())

    return response


@router.post("/", response_model=Policy, status_code=status.HTTP_201_CREATED)
@beartype
async def create_policy(
    policy_data: PolicyCreate,
    db: AsyncGenerator[asyncpg.Connection, None] = Depends(get_db),
    redis: Redis = Depends(get_redis),
    # current_user: CurrentUser = Depends(get_current_user),  # Demo mode
) -> Policy:
    """Create a new insurance policy.

    Args:
        policy_data: Policy creation data
        db: Database session
        redis: Redis client for cache invalidation
        current_user: Authenticated user information

    Returns:
        Policy: Created policy entity

    Raises:
        HTTPException: If policy creation fails
    """
    try:
        # Properly handle async generator from FastAPI dependency
        async for connection in db:
            # TODO: Implement actual database insertion
            # This is a placeholder implementation

            # Invalidate relevant caches
            pattern = "policies:list:*"
            async for key in redis.scan_iter(match=pattern):
                await redis.delete(key)

            # Return mock policy for now
            from datetime import datetime
            from uuid import uuid4

            policy = Policy(
                id=uuid4(),
                cancelled_at=None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                **policy_data.model_dump(),
            )
            break  # Use the first (and only) yielded connection

        return policy

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create policy: {str(e)}",
        ) from e


@router.get("/{policy_id}", response_model=Policy)
@beartype
async def get_policy(
    policy_id: UUID,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Policy:
    """Retrieve a specific policy by ID.

    Args:
        policy_id: UUID of the policy
        db: Database session
        redis: Redis client for caching
        current_user: Authenticated user information

    Returns:
        Policy: Retrieved policy entity

    Raises:
        HTTPException: If policy not found
    """
    # Check cache first
    cache_key = f"policies:{policy_id}"
    cached_policy = await redis.get(cache_key)

    if cached_policy:
        return Policy.model_validate_json(cached_policy)

    # TODO: Implement actual database query
    # This is a placeholder implementation

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"Policy {policy_id} not found"
    )


@router.put("/{policy_id}", response_model=Policy)
@beartype
async def update_policy(
    policy_id: UUID,
    policy_update: PolicyUpdate,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Policy:
    """Update an existing policy.

    Args:
        policy_id: UUID of the policy to update
        policy_update: Fields to update
        db: Database session
        redis: Redis client for cache invalidation
        current_user: Authenticated user information

    Returns:
        Policy: Updated policy entity

    Raises:
        HTTPException: If policy not found or update fails
    """
    # TODO: Implement actual database update
    # This is a placeholder implementation

    # Invalidate caches
    await redis.delete(f"policies:{policy_id}")
    pattern = "policies:list:*"
    async for key in redis.scan_iter(match=pattern):
        await redis.delete(key)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"Policy {policy_id} not found"
    )


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
@beartype
async def delete_policy(
    policy_id: UUID,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Delete a policy (soft delete by setting status to CANCELLED).

    Args:
        policy_id: UUID of the policy to delete
        db: Database session
        redis: Redis client for cache invalidation
        current_user: Authenticated user information

    Raises:
        HTTPException: If policy not found or deletion fails
    """
    # TODO: Implement actual soft delete (status change to CANCELLED)
    # This is a placeholder implementation

    # Invalidate caches
    await redis.delete(f"policies:{policy_id}")
    pattern = "policies:list:*"
    async for key in redis.scan_iter(match=pattern):
        await redis.delete(key)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"Policy {policy_id} not found"
    )
