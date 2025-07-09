"""Admin SSO configuration endpoints."""

from datetime import datetime
from typing import Any
from uuid import UUID

from beartype import beartype
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from ....models.admin import AdminUser, Permission
from ....services.admin.sso_admin_service import SSOAdminService
from ...dependencies import get_current_admin_user, get_sso_admin_service
from ...response_patterns import ErrorResponse

router = APIRouter(prefix="/admin/sso", tags=["admin-sso"])


class SSOProviderCreateRequest(BaseModel):
    """Request model for creating SSO provider."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    provider_name: str = Field(..., description="Unique provider name")
    provider_type: str = Field(
        ..., pattern="^(oidc|saml|oauth2)$", description="Provider type"
    )
    configuration: dict[str, Any] = Field(..., description="Provider configuration")
    is_enabled: bool = Field(False, description="Enable immediately")


class SSOProviderUpdateRequest(BaseModel):
    """Request model for updating SSO provider."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    provider_name: str | None = Field(None, description="New provider name")
    configuration: dict[str, Any] | None = Field(
        None, description="Updated configuration"
    )
    is_enabled: bool | None = Field(None, description="Enable/disable provider")


class GroupMappingCreateRequest(BaseModel):
    """Request model for creating group mapping."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    sso_group: str = Field(..., description="SSO group name")
    internal_role: str = Field(
        ...,
        pattern="^(agent|underwriter|admin|system)$",
        description="Internal role to map to",
    )
    auto_assign: bool = Field(True, description="Auto-assign on login")


class ProvisioningRuleCreateRequest(BaseModel):
    """Request model for creating provisioning rule."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    rule_name: str = Field(..., description="Rule name")
    conditions: dict[str, Any] = Field(..., description="Rule conditions")
    actions: dict[str, Any] = Field(..., description="Actions to perform")
    priority: int = Field(0, ge=0, le=1000, description="Rule priority")
    is_enabled: bool = Field(True, description="Enable rule")


@router.post("/providers")
@beartype
async def create_sso_provider(
    provider_request: SSOProviderCreateRequest,
    response: Response,
    sso_service: SSOAdminService = Depends(get_sso_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any] | ErrorResponse:
    """Create new SSO provider configuration.

    Requires: admin:write permission
    """
    if Permission.ADMIN_WRITE not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions. Required: admin:write")

    result = await sso_service.create_sso_provider_config(
        admin_user.id,
        provider_request.provider_name,
        provider_request.provider_type,
        provider_request.configuration,
        provider_request.is_enabled,
    )

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = (
            400
            if "invalid" in error_msg.lower() or "already exists" in error_msg.lower()
            else 500
        )
        return ErrorResponse(error=error_msg)

    response.status_code = 201
    return {
        "provider_id": str(result.ok_value),
        "message": "SSO provider created successfully",
    }


@router.get("/providers")
@beartype
async def list_sso_providers(
    response: Response,
    limit: int = Query(50, ge=1, le=100, description="Number of providers"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    sso_service: SSOAdminService = Depends(get_sso_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any] | ErrorResponse:
    """List all SSO provider configurations.

    Requires: admin:read permission
    """
    if Permission.ADMIN_READ not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions. Required: admin:read")

    result = await sso_service.list_sso_providers(limit, offset)

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 500
        return ErrorResponse(error=error_msg)

    return result.unwrap()


@router.get("/providers/{provider_id}")
@beartype
async def get_sso_provider(
    provider_id: UUID,
    response: Response,
    sso_service: SSOAdminService = Depends(get_sso_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any] | ErrorResponse:
    """Get SSO provider configuration details.

    Requires: admin:read permission
    """
    if Permission.ADMIN_READ not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions. Required: admin:read")

    result = await sso_service.get_sso_provider(provider_id)

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 404 if "not found" in error_msg.lower() else 500
        return ErrorResponse(error=error_msg)

    return result.unwrap()


@router.put("/providers/{provider_id}")
@beartype
async def update_sso_provider(
    provider_id: UUID,
    update_request: SSOProviderUpdateRequest,
    response: Response,
    sso_service: SSOAdminService = Depends(get_sso_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any] | ErrorResponse:
    """Update SSO provider configuration.

    Requires: admin:write permission
    """
    if Permission.ADMIN_WRITE not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions. Required: admin:write")

    updates = update_request.model_dump(exclude_none=True)

    result = await sso_service.update_provider_config(
        provider_id, admin_user.id, updates
    )

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 404 if "not found" in error_msg.lower() else 400
        return ErrorResponse(error=error_msg)

    return {"message": "SSO provider updated successfully"}


@router.post("/providers/{provider_id}/test")
@beartype
async def test_sso_provider(
    provider_id: UUID,
    response: Response,
    sso_service: SSOAdminService = Depends(get_sso_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any] | ErrorResponse:
    """Test SSO provider connection.

    Requires: admin:write permission
    """
    if Permission.ADMIN_WRITE not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions. Required: admin:write")

    result = await sso_service.test_provider_connection(provider_id, admin_user.id)

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 404 if "not found" in error_msg.lower() else 500
        return ErrorResponse(error=error_msg)

    return result.unwrap()


@router.post("/providers/{provider_id}/mappings")
@beartype
async def create_group_mapping(
    provider_id: UUID,
    mapping_request: GroupMappingCreateRequest,
    response: Response,
    sso_service: SSOAdminService = Depends(get_sso_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any] | ErrorResponse:
    """Create SSO group to role mapping.

    Requires: admin:write permission
    """
    if Permission.ADMIN_WRITE not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions. Required: admin:write")

    result = await sso_service.create_group_mapping(
        provider_id,
        admin_user.id,
        mapping_request.sso_group,
        mapping_request.internal_role,
        mapping_request.auto_assign,
    )

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = (
            400
            if "invalid" in error_msg.lower() or "already exists" in error_msg.lower()
            else 500
        )
        return ErrorResponse(error=error_msg)

    response.status_code = 201
    return {
        "mapping_id": str(result.ok_value),
        "message": "Group mapping created successfully",
    }


@router.get("/providers/{provider_id}/mappings")
@beartype
async def list_group_mappings(
    provider_id: UUID,
    response: Response,
    sso_service: SSOAdminService = Depends(get_sso_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any] | ErrorResponse:
    """List group mappings for a provider.

    Requires: admin:read permission
    """
    if Permission.ADMIN_READ not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions. Required: admin:read")

    result = await sso_service.list_group_mappings(provider_id)

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 404 if "not found" in error_msg.lower() else 500
        return ErrorResponse(error=error_msg)

    # Ensure we have valid mappings
    mappings = result.unwrap()

    return {"mappings": mappings, "total": len(mappings)}


@router.get("/providers/{provider_id}/rules")
@beartype
async def list_provisioning_rules(
    provider_id: UUID,
    response: Response,
    sso_service: SSOAdminService = Depends(get_sso_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any] | ErrorResponse:
    """List user provisioning rules for a provider.

    Requires: admin:read permission
    """
    if Permission.ADMIN_READ not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions. Required: admin:read")

    result = await sso_service.get_user_provisioning_rules(provider_id)

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 404 if "not found" in error_msg.lower() else 500
        return ErrorResponse(error=error_msg)

    # Ensure we have valid rules
    rules = result.unwrap()

    return {"rules": rules, "total": len(rules)}


@router.get("/analytics")
@beartype
async def get_sso_analytics(
    response: Response,
    date_from: datetime = Query(..., description="Start date"),
    date_to: datetime = Query(..., description="End date"),
    sso_service: SSOAdminService = Depends(get_sso_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any] | ErrorResponse:
    """Get SSO usage analytics.

    Requires: analytics:read permission
    """
    if Permission.ANALYTICS_READ not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions. Required: analytics:read")

    result = await sso_service.get_sso_analytics(date_from, date_to)

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 500
        return ErrorResponse(error=error_msg)

    return result.unwrap()


@router.delete("/providers/{provider_id}")
@beartype
async def delete_sso_provider(
    provider_id: UUID,
    response: Response,
    sso_service: SSOAdminService = Depends(get_sso_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any] | ErrorResponse:
    """Delete SSO provider configuration.

    Requires: admin:delete permission
    """
    if Permission.ADMIN_DELETE not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions. Required: admin:delete")

    result = await sso_service.delete_sso_provider(provider_id, admin_user.id)

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 404 if "not found" in error_msg.lower() else 500
        return ErrorResponse(error=error_msg)

    return {"message": "SSO provider deleted successfully"}


@router.get("/activity")
@beartype
async def get_sso_activity_logs(
    response: Response,
    limit: int = Query(50, ge=1, le=100, description="Number of records"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    provider_id: UUID | None = Query(None, description="Filter by provider"),
    sso_service: SSOAdminService = Depends(get_sso_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any] | ErrorResponse:
    """Get SSO administrative activity logs.

    Requires: audit:read permission
    """
    if Permission.AUDIT_READ not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions. Required: audit:read")

    result = await sso_service.get_activity_logs(limit, offset, provider_id)

    if result.is_err():
        error_msg = result.unwrap_err()
        response.status_code = 500
        return ErrorResponse(error=error_msg)

    return result.unwrap()
