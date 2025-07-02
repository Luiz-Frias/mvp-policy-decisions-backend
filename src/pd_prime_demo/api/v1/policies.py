"""Policy CRUD endpoints with pagination and filtering.

This module provides RESTful endpoints for managing insurance policies
with proper validation, caching, and error handling.
"""

from uuid import UUID

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
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
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

    # TODO: Implement actual database query with filters
    # This is a placeholder implementation
    policies: list[Policy] = []
    total = 0

    response = PolicyListResponse(
        items=policies, total=total, skip=pagination.skip, limit=pagination.limit
    )

    # Cache the result for 60 seconds
    await redis.setex(cache_key, 60, response.model_dump_json())

    return response


@router.post("/", response_model=Policy, status_code=status.HTTP_201_CREATED)
@beartype
async def create_policy(
    policy_data: PolicyCreate,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
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
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            **policy_data.model_dump(),
        )

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
