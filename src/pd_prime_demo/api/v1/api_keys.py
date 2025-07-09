"""API key management endpoints."""

from datetime import datetime
from typing import Any, Union
from uuid import UUID, uuid4

import asyncpg
from beartype import beartype
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis

from ...core.auth.oauth2 import APIKeyManager
from ...core.cache import Cache
from ...core.database import Database
from ...core.result_types import Err
from ...schemas.auth import CurrentUser
from ..dependencies import get_current_user, get_db_connection, get_redis
from ..response_patterns import handle_result, ErrorResponse, APIResponseHandler

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class APIKeyCreateRequest(BaseModel):
    """Request model for creating API key."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] = Field(..., min_length=1)
    expires_in_days: int | None = Field(None, ge=1, le=365)
    rate_limit_per_minute: int = Field(60, ge=1, le=1000)
    allowed_ips: list[str] | None = Field(None, max_length=100)


class APIKeyResponse(BaseModel):
    """Response model for API key."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    id: UUID
    name: str
    scopes: list[str]
    expires_at: datetime | None
    rate_limit_per_minute: int
    created_at: datetime
    last_used_at: datetime | None
    active: bool


class APIKeyCreateResponse(BaseModel):
    """Response model for created API key."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    id: UUID
    api_key: str
    name: str
    scopes: list[str]
    expires_at: str | None
    rate_limit_per_minute: int
    note: str


def _handle_service_error(error: str, response: Response, success_status: int = 200) -> ErrorResponse:
    """Handle service layer errors by mapping to appropriate HTTP status."""
    response.status_code = APIResponseHandler.map_error_to_status(error)
    return ErrorResponse(error=error)


class APIKeyRevokeResponse(BaseModel):
    """Response model for API key revocation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    message: str


class APIKeyUsageResponse(BaseModel):
    """Response model for API key usage statistics."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    key_id: str
    name: str
    client_id: str
    created_at: datetime
    last_used_at: datetime | None
    total_requests: int
    period_days: int


@beartype
async def get_api_key_manager(
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: Redis = Depends(get_redis),
) -> APIKeyManager:
    """Get API key manager instance."""
    database = Database(db)
    cache = Cache(redis)

    return APIKeyManager(database, cache)


@router.post("/", response_model=APIKeyCreateResponse)
@beartype
async def create_api_key(
    request: APIKeyCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    api_key_manager: APIKeyManager = Depends(get_api_key_manager),
    response: Response = Depends(lambda: Response()),
) -> Union[APIKeyCreateResponse, ErrorResponse]:
    """Create a new API key.

    The API key will be associated with the current user's OAuth2 client.
    Store the returned API key securely as it cannot be retrieved later.

    Args:
        request: API key creation request
        current_user: Current authenticated user
        api_key_manager: API key manager instance

    Returns:
        Created API key details including the key value

    Raises:
        HTTPException: If creation fails
    """
    # Check if user has permission to create API keys
    if "api:write" not in current_user.scopes:
        response.status_code = 403
        return ErrorResponse(
            error="Insufficient permissions to create API keys"
        )

    # Use client_id from current user's OAuth2 token
    client_id = current_user.client_id

    result = await api_key_manager.create_api_key(
        name=request.name,
        client_id=client_id,
        scopes=request.scopes,
        expires_in_days=request.expires_in_days,
        rate_limit_per_minute=request.rate_limit_per_minute,
        allowed_ips=request.allowed_ips,
    )

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    key_data = result.ok_value
    if key_data is None:
        return _handle_service_error("Unexpected null result", response)
    
    # Convert to response and return with proper status
    response.status_code = 201
    return APIKeyCreateResponse(
        id=key_data["id"],
        api_key=key_data["api_key"],
        name=key_data["name"],
        scopes=key_data["scopes"],
        expires_at=key_data["expires_at"],
        rate_limit_per_minute=key_data["rate_limit_per_minute"],
        note=key_data["note"],
    )


@router.get("/", response_model=list[APIKeyResponse])
@beartype
async def list_api_keys(
    active_only: bool = Query(True, description="Show only active keys"),
    current_user: CurrentUser = Depends(get_current_user),
    api_key_manager: APIKeyManager = Depends(get_api_key_manager),
    response: Response = Depends(lambda: Response()),
) -> Union[list[APIKeyResponse], ErrorResponse]:
    """List API keys for the current user.

    Args:
        active_only: Whether to show only active keys
        current_user: Current authenticated user
        api_key_manager: API key manager instance

    Returns:
        List of API keys (without the actual key values)

    Raises:
        HTTPException: If listing fails
    """
    # Use client_id from current user's OAuth2 token
    client_id = current_user.client_id

    result = await api_key_manager.list_api_keys(
        client_id=client_id,
        active_only=active_only,
    )

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    keys = []
    key_list = result.ok_value
    if key_list is not None:
        for key_data in key_list:
            keys.append(
                APIKeyResponse(
                    id=UUID(key_data["id"]) if isinstance(key_data["id"], str) else key_data["id"],
                    name=str(key_data["name"]),
                    scopes=list(key_data["scopes"]) if key_data["scopes"] else [],
                    expires_at=datetime.fromisoformat(key_data["expires_at"]) if key_data.get("expires_at") and isinstance(key_data["expires_at"], str) else key_data.get("expires_at"),
                    rate_limit_per_minute=int(key_data["rate_limit_per_minute"]),
                    created_at=datetime.fromisoformat(key_data["created_at"]) if isinstance(key_data["created_at"], str) else key_data["created_at"],
                    last_used_at=datetime.fromisoformat(key_data["last_used_at"]) if key_data.get("last_used_at") and isinstance(key_data["last_used_at"], str) else key_data.get("last_used_at"),
                    active=bool(key_data["active"]),
                )
            )

    # Return success
    response.status_code = 200
    return keys


@router.delete("/{key_id}", response_model=APIKeyRevokeResponse)
@beartype
async def revoke_api_key(
    key_id: UUID,
    reason: str = Query(..., description="Reason for revocation"),
    current_user: CurrentUser = Depends(get_current_user),
    api_key_manager: APIKeyManager = Depends(get_api_key_manager),
    response: Response = Depends(lambda: Response()),
) -> Union[APIKeyRevokeResponse, ErrorResponse]:
    """Revoke an API key.

    Args:
        key_id: ID of the API key to revoke
        reason: Reason for revocation
        current_user: Current authenticated user
        api_key_manager: API key manager instance

    Returns:
        Success message

    Raises:
        HTTPException: If revocation fails
    """
    if "api:write" not in current_user.scopes:
        response.status_code = 403
        return ErrorResponse(
            error="Insufficient permissions to revoke API keys"
        )

    # Verify key belongs to user's client
    ownership_result = await api_key_manager.verify_key_ownership(
        key_id, current_user.client_id
    )
    if ownership_result.is_err():
        return _handle_service_error(ownership_result.unwrap_err(), response)

    result = await api_key_manager.revoke_api_key(key_id, reason)

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    # Return success
    response.status_code = 200
    return APIKeyRevokeResponse(message="API key revoked successfully")


@router.post("/{key_id}/rotate", response_model=APIKeyCreateResponse)
@beartype
async def rotate_api_key(
    key_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    api_key_manager: APIKeyManager = Depends(get_api_key_manager),
    response: Response = Depends(lambda: Response()),
) -> Union[APIKeyCreateResponse, ErrorResponse]:
    """Rotate an API key.

    This will revoke the old key and create a new one with the same settings.

    Args:
        key_id: ID of the API key to rotate
        current_user: Current authenticated user
        api_key_manager: API key manager instance

    Returns:
        New API key details

    Raises:
        HTTPException: If rotation fails
    """
    if "api:write" not in current_user.scopes:
        response.status_code = 403
        return ErrorResponse(
            error="Insufficient permissions to rotate API keys"
        )

    # Verify key belongs to user's client
    ownership_result = await api_key_manager.verify_key_ownership(
        key_id, current_user.client_id
    )
    if ownership_result.is_err():
        return _handle_service_error(ownership_result.unwrap_err(), response)

    result = await api_key_manager.rotate_api_key(key_id)

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    key_data = result.ok_value
    if key_data is None:
        return _handle_service_error("Unexpected null result", response)
    
    # Convert to response and return with proper status
    response.status_code = 201
    return APIKeyCreateResponse(
        id=key_data["id"],
        api_key=key_data["api_key"],
        name=key_data["name"],
        scopes=key_data["scopes"],
        expires_at=key_data["expires_at"],
        rate_limit_per_minute=key_data["rate_limit_per_minute"],
        note=key_data["note"],
    )


@router.get("/{key_id}/usage", response_model=APIKeyUsageResponse)
@beartype
async def get_api_key_usage(
    key_id: UUID,
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
    current_user: CurrentUser = Depends(get_current_user),
    api_key_manager: APIKeyManager = Depends(get_api_key_manager),
    response: Response = Depends(lambda: Response()),
) -> Union[APIKeyUsageResponse, ErrorResponse]:
    """Get usage statistics for an API key.

    Args:
        key_id: ID of the API key
        days: Number of days of history to retrieve
        current_user: Current authenticated user
        api_key_manager: API key manager instance

    Returns:
        Usage statistics

    Raises:
        HTTPException: If retrieval fails
    """
    # Verify key belongs to user's client
    ownership_result = await api_key_manager.verify_key_ownership(
        key_id, current_user.client_id
    )
    if ownership_result.is_err():
        return _handle_service_error(ownership_result.unwrap_err(), response)

    result = await api_key_manager.get_usage_statistics(key_id, days)

    if result.is_err():
        return _handle_service_error(result.unwrap_err(), response)

    stats = result.ok_value
    if stats is None:
        return _handle_service_error("Unexpected null result", response)
    
    # Return success
    response.status_code = 200
    return APIKeyUsageResponse(
        key_id=stats["key_id"],
        name=stats["name"],
        client_id=stats["client_id"],
        created_at=stats["created_at"],
        last_used_at=stats["last_used_at"],
        total_requests=stats["total_requests"],
        period_days=stats["period_days"],
    )
