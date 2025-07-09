"""Customer CRUD endpoints with pagination and search.

This module provides RESTful endpoints for managing customers
with proper validation, caching, and error handling.
"""

import json
from uuid import UUID

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
from ...models.customer import Customer, CustomerCreate, CustomerUpdate
from ...schemas.auth import CurrentUser
from ...schemas.common import PolicySummary
from ...services.customer_service import CustomerService
from ..dependencies import PaginationParams, get_current_user, get_db, get_redis

router = APIRouter()


class CustomerListResponse(BaseModel):
    """Response model for customer list endpoints."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    items: list[Customer] = Field(..., description="List of customers")
    total: int = Field(..., ge=0, description="Total number of customers")
    skip: int = Field(..., ge=0, description="Number of items skipped")
    limit: int = Field(..., ge=1, description="Maximum items returned")


class CustomerFilter(BaseModel):
    """Filter parameters for customer queries."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

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


@router.get("/")
@beartype
async def list_customers(
    response: Response,
    pagination: PaginationParams = Depends(),
    filters: CustomerFilter = Depends(),
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Union[CustomerListResponse, ErrorResponse]:
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

    # Initialize services with dependency validation
    if not db:
        raise ValueError("Database connection required and must be active")
    if not redis:
        raise ValueError("Cache connection required and must be available")

    database = Database(db)
    cache = Cache(redis)
    service = CustomerService(database, cache)

    # Build query with filters
    where_clauses = []
    params = []

    if filters.search:
        where_clauses.append(
            "(data->>'first_name' ILIKE $1 OR data->>'last_name' ILIKE $1 OR data->>'email' ILIKE $1)"
        )
        params.append(f"%{filters.search}%")

    if filters.state_province:
        param_num = len(params) + 1
        where_clauses.append(f"data->>'state_province' = ${param_num}")
        params.append(filters.state_province)

    if filters.country_code:
        param_num = len(params) + 1
        where_clauses.append(f"data->>'country_code' = ${param_num}")
        params.append(filters.country_code)

    if filters.is_active is not None:
        param_num = len(params) + 1
        status = "ACTIVE" if filters.is_active else "INACTIVE"
        where_clauses.append(f"data->>'status' = ${param_num}")
        params.append(status)

    # Build count query
    count_query = "SELECT COUNT(*) FROM customers"
    if where_clauses:
        count_query += " WHERE " + " AND ".join(where_clauses)

    # Get total count
    total = await db.fetchval(count_query, *params)

    # Build main query with pagination
    query = "SELECT * FROM customers"
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    query += " ORDER BY created_at DESC"

    # Add pagination params
    param_num = len(params) + 1
    query += f" LIMIT ${param_num}"
    params.append(str(pagination.limit))

    param_num = len(params) + 1
    query += f" OFFSET ${param_num}"
    params.append(str(pagination.skip))

    # Execute query
    rows = await db.fetch(query, *params)
    customers = [service._row_to_customer(row) for row in rows]

    list_response = CustomerListResponse(
        items=customers, total=total or 0, skip=pagination.skip, limit=pagination.limit
    )

    # Cache the result for 60 seconds
    await redis.setex(cache_key, 60, list_response.model_dump_json())

    return list_response


@router.post("/", status_code=status.HTTP_201_CREATED)
@beartype
async def create_customer(
    customer_data: CustomerCreate,
    response: Response,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Union[Customer, ErrorResponse]:
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
        # Initialize services with dependency validation
        if not db:
            raise ValueError("Database connection required and must be active")
        if not redis:
            raise ValueError("Cache connection required and must be available")

        database = Database(db)
        cache = Cache(redis)
        service = CustomerService(database, cache)

        # Create customer using service
        result = await service.create(customer_data)

        if result.is_err():
            return handle_result(result, response, success_status=status.HTTP_201_CREATED)

        customer = result.ok_value
        assert customer is not None

        # Invalidate relevant caches
        pattern = "customers:list:*"
        async for key in redis.scan_iter(match=pattern):
            await redis.delete(key)

        return customer

    except Exception as e:
        return handle_result(Err(f"Failed to create customer: {str(e)}"), response, success_status=status.HTTP_201_CREATED)


@router.get("/{customer_id}")
@beartype
async def get_customer(
    customer_id: UUID,
    response: Response,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Union[Customer, ErrorResponse]:
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

    # Initialize services with dependency validation
    if not db:
        raise ValueError("Database connection required and must be active")
    if not redis:
        raise ValueError("Cache connection required and must be available")

    database = Database(db)
    cache = Cache(redis)
    service = CustomerService(database, cache)

    # Get customer using service
    result = await service.get(customer_id)

    if result.is_err():
        return handle_result(result, response)

    customer = result.ok_value
    if not customer:
        return handle_result(Err("Customer not found"), response)

    # Cache the result
    await redis.setex(cache_key, 300, customer.model_dump_json())

    return customer


@router.put("/{customer_id}")
@beartype
async def update_customer(
    customer_id: UUID,
    customer_update: CustomerUpdate,
    response: Response,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Union[Customer, ErrorResponse]:
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
        # Initialize services with dependency validation
        if not db:
            raise ValueError("Database connection required and must be active")
        if not redis:
            raise ValueError("Cache connection required and must be available")

        database = Database(db)
        cache = Cache(redis)
        service = CustomerService(database, cache)

        # Update customer using service
        result = await service.update(customer_id, customer_update)

        if result.is_err():
            return handle_result(result, response)

        customer = result.ok_value
        if not customer:
            return handle_result(Err("Customer not found"), response)

        # Invalidate caches
        await redis.delete(f"customer:{customer_id}")
        pattern = "customers:list:*"
        async for key in redis.scan_iter(match=pattern):
            await redis.delete(key)

        return customer

    except Exception as e:
        return handle_result(Err(f"Failed to update customer: {str(e)}"), response)


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
@beartype
async def delete_customer(
    customer_id: UUID,
    response: Response,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Union[None, ErrorResponse]:
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
        # Initialize services with dependency validation
        if not db:
            raise ValueError("Database connection required and must be active")
        if not redis:
            raise ValueError("Cache connection required and must be available")

        database = Database(db)
        cache = Cache(redis)
        service = CustomerService(database, cache)

        # Delete customer using service
        result = await service.delete(customer_id)

        if result.is_err():
            return handle_result(result, response)

        # Invalidate caches
        await redis.delete(f"customer:{customer_id}")
        pattern = "customers:list:*"
        async for key in redis.scan_iter(match=pattern):
            await redis.delete(key)

        return None

    except Exception as e:
        return handle_result(Err(f"Failed to delete customer: {str(e)}"), response)


@router.get("/{customer_id}/policies")
@beartype
async def get_customer_policies(
    customer_id: UUID,
    response: Response,
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: CurrentUser = Depends(get_current_user),
) -> Union[list[PolicySummary], ErrorResponse]:
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

    # Initialize services with dependency validation
    if not db:
        raise ValueError("Database connection required and must be active")
    if not redis:
        raise ValueError("Cache connection required and must be available")

    database = Database(db)
    cache = Cache(redis)
    service = CustomerService(database, cache)

    # Get customer policies using service
    result = await service.get_policies(customer_id)

    if result.is_err():
        return handle_result(result, response)

    policies = result.ok_value
    
    # Type narrowing - policies should not be None if is_ok() is True
    if policies is None:
        return handle_result(Err("Internal server error: policies result is None"), response)

    # Cache the result for 300 seconds (5 minutes)
    await redis.setex(
        cache_key, 300, json.dumps([policy.model_dump() for policy in policies])
    )

    return policies
