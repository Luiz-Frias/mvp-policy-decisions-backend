"""Policy CRUD endpoints with pagination and filtering.

This module provides RESTful endpoints for managing insurance policies
with proper validation, caching, and error handling.
"""

from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

import asyncpg
from beartype import beartype
from fastapi import APIRouter, Depends, status, Response
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis
from typing import Union

from pd_prime_demo.core.result_types import Err
from pd_prime_demo.api.response_patterns import handle_result, ErrorResponse

from ...core.cache import Cache
from ...core.database import Database
from ...models.policy import (
    Policy,
    PolicyCreate,
    PolicyStatus,
    PolicyType,
    PolicyUpdate,
)
from ...schemas.auth import CurrentUser
from ...services.policy_service import PolicyService
from ..dependencies import (
    PaginationParams,
    get_db,
    get_redis,
    get_user_with_demo_fallback,
)

router = APIRouter()


class PolicyListResponse(BaseModel):
    """Response model for policy list endpoints."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    items: list[Policy] = Field(..., description="List of policies")
    total: int = Field(..., ge=0, description="Total number of policies")
    skip: int = Field(..., ge=0, description="Number of items skipped")
    limit: int = Field(..., ge=1, description="Maximum items returned")


class PolicyFilter(BaseModel):
    """Filter parameters for policy queries."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    status: PolicyStatus | None = Field(None, description="Filter by status")
    policy_type: PolicyType | None = Field(None, description="Filter by type")
    customer_id: UUID | None = Field(None, description="Filter by customer")
    min_premium: float | None = Field(None, ge=0, description="Minimum premium")
    max_premium: float | None = Field(None, ge=0, description="Maximum premium")


@router.get("/")
@beartype
async def list_policies(
    response: Response,
    pagination: PaginationParams = Depends(),
    filters: PolicyFilter = Depends(),
    db: AsyncGenerator[asyncpg.Connection, None] = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_user_with_demo_fallback),
) -> Union[PolicyListResponse, ErrorResponse]:
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
        # Initialize services with dependency validation
        if not connection:
            raise ValueError("Database connection required and must be active")
        if not redis:
            raise ValueError("Cache connection required and must be available")

        database = Database(connection)
        cache = Cache(redis)
        service = PolicyService(database, cache)

        # Call service method to list policies
        result = await service.list(
            customer_id=filters.customer_id,
            status=filters.status.value if filters.status else None,
            limit=pagination.limit,
            offset=pagination.skip,
        )

        if isinstance(result, Err):
            return handle_result(result, response)

        policies = result.ok_value

        # Get total count (using same filters)
        count_result = await service.list(
            customer_id=filters.customer_id,
            status=filters.status.value if filters.status else None,
            limit=1000000,  # Large limit to get all
            offset=0,
        )

        total = len(count_result.ok_value) if count_result.is_ok() and count_result.ok_value is not None else 0

        list_response = PolicyListResponse(
            items=policies,
            total=total,
            skip=pagination.skip,
            limit=pagination.limit,
        )
        break  # Use the first (and only) yielded connection

    # Cache the result for 60 seconds
    await redis.setex(cache_key, 60, list_response.model_dump_json())

    return list_response


@router.post("/", status_code=status.HTTP_201_CREATED)
@beartype
async def create_policy(
    policy_data: PolicyCreate,
    response: Response,
    db: AsyncGenerator[asyncpg.Connection, None] = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_user_with_demo_fallback),
) -> Union[Policy, ErrorResponse]:
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
            # Initialize services with dependency validation
            if not connection:
                raise ValueError("Database connection required and must be active")
            if not redis:
                raise ValueError("Cache connection required and must be available")

            database = Database(connection)
            cache = Cache(redis)
            service = PolicyService(database, cache)

            # Extract customer_id from request - in real app, this would come from auth/request
            # For now, generate a new UUID for demo purposes
            customer_id = uuid4()

            # Create policy using service
            result = await service.create(policy_data, customer_id)

            if isinstance(result, Err):
                return handle_result(result, response, success_status=status.HTTP_201_CREATED)

            policy = result.ok_value

            # Invalidate relevant caches
            pattern = "policies:list:*"
            async for key in redis.scan_iter(match=pattern):
                await redis.delete(key)

            break  # Use the first (and only) yielded connection

        return policy

    except Exception as e:
        return handle_result(Err(f"Failed to create policy: {str(e)}"), response, success_status=status.HTTP_201_CREATED)


@router.get("/{policy_id}")
@beartype
async def get_policy(
    policy_id: UUID,
    response: Response,
    db: AsyncGenerator[asyncpg.Connection, None] = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_user_with_demo_fallback),
) -> Union[Policy, ErrorResponse]:
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

    # Properly handle async generator from FastAPI dependency
    async for connection in db:
        # Initialize services with dependency validation
        if not connection:
            raise ValueError("Database connection required and must be active")
        if not redis:
            raise ValueError("Cache connection required and must be available")

        database = Database(connection)
        cache = Cache(redis)
        service = PolicyService(database, cache)

        # Get policy using service
        result = await service.get(policy_id)

        if isinstance(result, Err):
            return handle_result(result, response)

        policy = result.ok_value
        if not policy:
            return handle_result(Err(f"Policy {policy_id} not found"), response)

        # Cache the result
        await redis.setex(cache_key, 300, policy.model_dump_json())

        return policy
    
    # This should never be reached as the dependency should provide a connection
    return handle_result(Err("Database connection not available"), response)


@router.put("/{policy_id}")
@beartype
async def update_policy(
    policy_id: UUID,
    policy_update: PolicyUpdate,
    response: Response,
    db: AsyncGenerator[asyncpg.Connection, None] = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_user_with_demo_fallback),
) -> Union[Policy, ErrorResponse]:
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
    # Properly handle async generator from FastAPI dependency
    async for connection in db:
        # Initialize services with dependency validation
        if not connection:
            raise ValueError("Database connection required and must be active")
        if not redis:
            raise ValueError("Cache connection required and must be available")

        database = Database(connection)
        cache = Cache(redis)
        service = PolicyService(database, cache)

        # Update policy using service
        result = await service.update(policy_id, policy_update)

        if isinstance(result, Err):
            return handle_result(result, response)

        policy = result.ok_value
        if not policy:
            return handle_result(Err(f"Policy {policy_id} not found"), response)

        # Invalidate caches
        await redis.delete(f"policies:{policy_id}")
        pattern = "policies:list:*"
        async for key in redis.scan_iter(match=pattern):
            await redis.delete(key)

        return policy
    
    # This should never be reached as the dependency should provide a connection
    return handle_result(Err("Database connection not available"), response)


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
@beartype
async def delete_policy(
    policy_id: UUID,
    response: Response,
    db: AsyncGenerator[asyncpg.Connection, None] = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_user_with_demo_fallback),
) -> Union[None, ErrorResponse]:
    """Delete a policy (soft delete by setting status to CANCELLED).

    Args:
        policy_id: UUID of the policy to delete
        db: Database session
        redis: Redis client for cache invalidation
        current_user: Authenticated user information

    Raises:
        HTTPException: If policy not found or deletion fails
    """
    # Properly handle async generator from FastAPI dependency
    async for connection in db:
        # Initialize services with dependency validation
        if not connection:
            raise ValueError("Database connection required and must be active")
        if not redis:
            raise ValueError("Cache connection required and must be available")

        database = Database(connection)
        cache = Cache(redis)
        service = PolicyService(database, cache)

        # Delete (soft delete) policy using service
        result = await service.delete(policy_id)

        if isinstance(result, Err):
            return handle_result(result, response)

        deleted = result.ok_value
        if not deleted:
            return handle_result(Err(f"Policy {policy_id} not found"), response)

        # Invalidate caches
        await redis.delete(f"policies:{policy_id}")
        pattern = "policies:list:*"
        async for key in redis.scan_iter(match=pattern):
            await redis.delete(key)
        
        return None
