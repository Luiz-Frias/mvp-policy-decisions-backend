"""Admin OAuth2 client management endpoints."""

from datetime import datetime
from typing import Any, Union
from uuid import UUID

import asyncpg
from beartype import beartype
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from redis.asyncio import Redis

from ....core.auth.oauth2.scopes import SCOPES
from ....models.admin import AdminUser
from ....services.admin.oauth2_admin_service import OAuth2AdminService
from ...dependencies import (
    get_current_admin_user,
    get_db_connection,
    get_oauth2_admin_service,
    get_redis,
)
from ...response_patterns import handle_result, ErrorResponse

router = APIRouter(prefix="/oauth2", tags=["admin-oauth2"])


class OAuth2ClientCreateRequest(BaseModel):
    """Request model for creating OAuth2 client."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    client_name: str = Field(..., min_length=1, max_length=100)
    client_type: str = Field(..., pattern="^(public|confidential)$")
    allowed_grant_types: list[str] = Field(..., min_length=1)
    allowed_scopes: list[str] = Field(..., min_length=1)
    redirect_uris: list[str] = Field(default_factory=list)
    description: str | None = Field(None, max_length=500)
    token_lifetime: int = Field(3600, ge=300, le=86400)  # 5 min to 24 hours
    refresh_token_lifetime: int = Field(
        604800, ge=3600, le=2592000
    )  # 1 hour to 30 days

    @field_validator("allowed_grant_types")
    @classmethod
    def validate_grant_types(cls, v: list[str]) -> list[str]:
        """Validate grant types."""
        valid_grants = {
            "authorization_code",
            "client_credentials",
            "refresh_token",
            "password",
        }
        invalid = set(v) - valid_grants
        if invalid:
            raise ValueError(f"Invalid grant types: {invalid}")
        return v

    @field_validator("allowed_scopes")
    @classmethod
    def validate_scopes(cls, v: list[str]) -> list[str]:
        """Validate scopes."""
        invalid = [s for s in v if s not in SCOPES]
        if invalid:
            raise ValueError(f"Invalid scopes: {invalid}")
        return v

    @field_validator("redirect_uris")
    @classmethod
    def validate_redirect_uris(cls, v: list[str]) -> list[str]:
        """Validate redirect URIs format."""
        # Validate URL format for each URI
        import re
        url_pattern = re.compile(
            r'^https?://[^\s/$.?#].[^\s]*$'
        )
        for uri in v:
            if not url_pattern.match(uri):
                raise ValueError(f"Invalid redirect URI format: {uri}")
        return v


class OAuth2ClientUpdateRequest(BaseModel):
    """Request model for updating OAuth2 client."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    client_name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    allowed_grant_types: list[str] | None = Field(None, min_length=1)
    allowed_scopes: list[str] | None = Field(None, min_length=1)
    redirect_uris: list[str] | None = None
    token_lifetime: int | None = Field(None, ge=300, le=86400)
    refresh_token_lifetime: int | None = Field(None, ge=3600, le=2592000)
    is_active: bool | None = None


class TokenRevocationRequest(BaseModel):
    """Request model for token revocation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    reason: str = Field(..., min_length=1, max_length=200)


@router.post("/clients", response_model=dict[str, Any])
@beartype
async def create_oauth2_client(
    client_request: OAuth2ClientCreateRequest,
    response: Response,
    oauth2_service: OAuth2AdminService = Depends(get_oauth2_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Union[dict[str, Any], ErrorResponse]:
    """Create new OAuth2 client application.

    Required permission: admin:clients

    Args:
        client_request: Client creation request
        oauth2_service: OAuth2 admin service
        admin_user: Current admin user

    Returns:
        Created client details including client_id and client_secret

    Raises:
        HTTPException: If creation fails or insufficient permissions
    """
    if "admin:clients" not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions")

    result = await oauth2_service.create_oauth2_client(
        admin_user.id,
        client_request.client_name,
        client_request.client_type,
        client_request.allowed_grant_types,
        client_request.allowed_scopes,
        client_request.redirect_uris,
        client_request.description,
        client_request.token_lifetime,
        client_request.refresh_token_lifetime,
    )

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 400 if "invalid" in error_msg.lower() or "already exists" in error_msg.lower() else 500
        return ErrorResponse(error=error_msg)

    response.status_code = 201
    return result.unwrap()


@router.get("/clients", response_model=list[dict[str, Any]])
@beartype
async def list_oauth2_clients(
    response: Response,
    active_only: bool = Query(True, description="Show only active clients"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    oauth2_service: OAuth2AdminService = Depends(get_oauth2_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Union[list[dict[str, Any]], ErrorResponse]:
    """List OAuth2 clients.

    Required permission: admin:clients

    Args:
        active_only: Filter for active clients only
        limit: Maximum number of results
        offset: Offset for pagination
        oauth2_service: OAuth2 admin service
        admin_user: Current admin user

    Returns:
        List of OAuth2 clients

    Raises:
        HTTPException: If listing fails or insufficient permissions
    """
    if "admin:clients" not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions")

    result = await oauth2_service.list_clients(active_only, limit, offset)

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 500
        return ErrorResponse(error=error_msg)

    return result.unwrap()


@router.get("/clients/{client_id}", response_model=dict[str, Any])
@beartype
async def get_oauth2_client(
    client_id: str,
    response: Response,
    oauth2_service: OAuth2AdminService = Depends(get_oauth2_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Union[dict[str, Any], ErrorResponse]:
    """Get OAuth2 client details.

    Args:
        client_id: OAuth2 client ID
        oauth2_service: OAuth2 admin service
        admin_user: Current admin user

    Returns:
        Client details

    Raises:
        HTTPException: If client not found or insufficient permissions
    """
    result = await oauth2_service.get_client_details(client_id)

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 404 if "not found" in error_msg.lower() else 500
        return ErrorResponse(error=error_msg)

    return result.unwrap()


@router.patch("/clients/{client_id}", response_model=dict[str, Any])
@beartype
async def update_oauth2_client(
    client_id: str,
    update_request: OAuth2ClientUpdateRequest,
    response: Response,
    oauth2_service: OAuth2AdminService = Depends(get_oauth2_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Union[dict[str, Any], ErrorResponse]:
    """Update OAuth2 client configuration.

    Required permission: admin:clients

    Args:
        client_id: OAuth2 client ID
        update_request: Update request
        oauth2_service: OAuth2 admin service
        admin_user: Current admin user

    Returns:
        Success response

    Raises:
        HTTPException: If update fails or insufficient permissions
    """
    if "admin:clients" not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions")

    # Build updates dict excluding None values
    updates = update_request.model_dump(exclude_none=True)

    if not updates:
        response.status_code = 400
        return ErrorResponse(error="No fields to update")

    result = await oauth2_service.update_client_config(
        client_id, admin_user.id, updates
    )

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 404 if "not found" in error_msg.lower() else 400
        return ErrorResponse(error=error_msg)

    return {"success": True, "message": "Client updated successfully"}


@router.post("/clients/{client_id}/regenerate-secret", response_model=dict[str, Any])
@beartype
async def regenerate_client_secret(
    client_id: str,
    response: Response,
    oauth2_service: OAuth2AdminService = Depends(get_oauth2_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Union[dict[str, Any], ErrorResponse]:
    """Regenerate client secret.

    Required permission: admin:clients

    This will revoke all existing tokens for the client.

    Args:
        client_id: OAuth2 client ID
        oauth2_service: OAuth2 admin service
        admin_user: Current admin user

    Returns:
        New client secret

    Raises:
        HTTPException: If regeneration fails or insufficient permissions
    """
    if "admin:clients" not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions")

    result = await oauth2_service.regenerate_client_secret(client_id, admin_user.id)

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 404 if "not found" in error_msg.lower() else 400
        return ErrorResponse(error=error_msg)

    return {
        "client_secret": result.ok_value,
        "note": "Store this securely. It cannot be retrieved later.",
    }


@router.get("/clients/{client_id}/analytics", response_model=dict[str, Any])
@beartype
async def get_client_analytics(
    client_id: str,
    response: Response,
    date_from: datetime = Query(..., description="Start date for analytics"),
    date_to: datetime = Query(..., description="End date for analytics"),
    oauth2_service: OAuth2AdminService = Depends(get_oauth2_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Union[dict[str, Any], ErrorResponse]:
    """Get OAuth2 client usage analytics.

    Args:
        client_id: OAuth2 client ID
        date_from: Start date for analytics period
        date_to: End date for analytics period
        oauth2_service: OAuth2 admin service
        admin_user: Current admin user

    Returns:
        Analytics data including token statistics, scope usage, and timeline

    Raises:
        HTTPException: If analytics fails
    """
    if date_from >= date_to:
        response.status_code = 400
        return ErrorResponse(error="date_from must be before date_to")

    result = await oauth2_service.get_client_analytics(client_id, date_from, date_to)

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 404 if "not found" in error_msg.lower() else 500
        return ErrorResponse(error=error_msg)

    return result.unwrap()


@router.post("/clients/{client_id}/revoke", response_model=dict[str, Any])
@beartype
async def revoke_client_access(
    client_id: str,
    revocation_request: TokenRevocationRequest,
    response: Response,
    oauth2_service: OAuth2AdminService = Depends(get_oauth2_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Union[dict[str, Any], ErrorResponse]:
    """Revoke all access tokens for a client.

    Required permission: admin:clients

    This will immediately revoke all active tokens for the specified client.

    Args:
        client_id: OAuth2 client ID
        revocation_request: Revocation details
        oauth2_service: OAuth2 admin service
        admin_user: Current admin user

    Returns:
        Number of tokens revoked

    Raises:
        HTTPException: If revocation fails or insufficient permissions
    """
    if "admin:clients" not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions")

    result = await oauth2_service.revoke_client_access(
        client_id, admin_user.id, revocation_request.reason
    )

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 404 if "not found" in error_msg.lower() else 400
        return ErrorResponse(error=error_msg)

    return {
        "tokens_revoked": result.ok_value,
        "message": f"Successfully revoked {result.ok_value} tokens",
    }


class CertificateUploadRequest(BaseModel):
    """Request model for certificate upload."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    certificate_pem: str = Field(..., min_length=1)
    certificate_name: str = Field(..., min_length=1, max_length=100)


@router.post("/clients/{client_id}/certificates", response_model=dict[str, Any])
@beartype
async def upload_client_certificate(
    client_id: str,
    cert_request: CertificateUploadRequest,
    response: Response,
    admin_user: AdminUser = Depends(get_current_admin_user),
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: Redis = Depends(get_redis),
) -> Union[dict[str, Any], ErrorResponse]:
    """Upload a client certificate for mTLS authentication.

    Required permission: admin:clients

    Args:
        client_id: OAuth2 client ID
        cert_request: Certificate upload request
        admin_user: Current admin user
        db: Database connection
        redis: Redis client

    Returns:
        Certificate details

    Raises:
        HTTPException: If upload fails or insufficient permissions
    """
    if "admin:clients" not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions")

    from ....core.auth.oauth2.client_certificates import ClientCertificateManager
    from ....core.cache import Cache
    from ....core.database import Database

    database = Database(db)
    cache = Cache(redis)
    cert_manager = ClientCertificateManager(database, cache)

    result = await cert_manager.register_client_certificate(
        client_id,
        cert_request.certificate_pem,
        cert_request.certificate_name,
        admin_user.id,
    )

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 400 if "invalid" in error_msg.lower() else 404 if "not found" in error_msg.lower() else 500
        return ErrorResponse(error=error_msg)

    response.status_code = 201
    return result.unwrap()


@router.get("/clients/{client_id}/certificates", response_model=list[dict[str, Any]])
@beartype
async def list_client_certificates(
    client_id: str,
    response: Response,
    include_revoked: bool = Query(False, description="Include revoked certificates"),
    admin_user: AdminUser = Depends(get_current_admin_user),
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: Redis = Depends(get_redis),
) -> Union[list[dict[str, Any]], ErrorResponse]:
    """List certificates for a client.

    Required permission: admin:clients

    Args:
        client_id: OAuth2 client ID
        include_revoked: Whether to include revoked certificates
        admin_user: Current admin user
        db: Database connection
        redis: Redis client

    Returns:
        List of client certificates

    Raises:
        HTTPException: If listing fails or insufficient permissions
    """
    if "admin:clients" not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions")

    from ....core.auth.oauth2.client_certificates import ClientCertificateManager
    from ....core.cache import Cache
    from ....core.database import Database

    database = Database(db)
    cache = Cache(redis)
    cert_manager = ClientCertificateManager(database, cache)

    result = await cert_manager.list_client_certificates(client_id, include_revoked)

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 404 if "not found" in error_msg.lower() else 500
        return ErrorResponse(error=error_msg)

    return result.unwrap()


@router.delete("/certificates/{certificate_id}", response_model=dict[str, Any])
@beartype
async def revoke_client_certificate(
    certificate_id: UUID,
    response: Response,
    reason: str = Query(..., description="Reason for revocation"),
    admin_user: AdminUser = Depends(get_current_admin_user),
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: Redis = Depends(get_redis),
) -> Union[dict[str, Any], ErrorResponse]:
    """Revoke a client certificate.

    Required permission: admin:clients

    Args:
        certificate_id: Certificate ID to revoke
        reason: Reason for revocation
        admin_user: Current admin user
        db: Database connection
        redis: Redis client

    Returns:
        Success response

    Raises:
        HTTPException: If revocation fails or insufficient permissions
    """
    if "admin:clients" not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions")

    from ....core.auth.oauth2.client_certificates import ClientCertificateManager
    from ....core.cache import Cache
    from ....core.database import Database

    database = Database(db)
    cache = Cache(redis)
    cert_manager = ClientCertificateManager(database, cache)

    result = await cert_manager.revoke_client_certificate(
        certificate_id, reason, admin_user.id
    )

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 404 if "not found" in error_msg.lower() else 400
        return ErrorResponse(error=error_msg)

    return {"success": True, "message": "Certificate revoked successfully"}
