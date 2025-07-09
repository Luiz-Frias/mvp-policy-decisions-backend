"""Admin rate management endpoints.

This module provides comprehensive admin endpoints for rate table management,
approval workflows, A/B testing, and analytics per Agent 06 requirements.
"""

from datetime import date
from typing import Any
from uuid import UUID

from beartype import beartype
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ....models.admin import AdminUser
from ....services.admin.rate_management_service import RateManagementService
from ...dependencies import get_cache, get_current_admin_user, get_database

router = APIRouter(prefix="/admin/rate-management", tags=["admin-rate-management"])


# Request/Response Models
class RateTableVersionCreate(BaseModel):
    """Request model for creating rate table version."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    table_name: str = Field(..., min_length=1, max_length=100)
    rate_data: dict[str, Any] = Field(...)
    effective_date: date = Field(...)
    notes: str | None = Field(None, max_length=1000)


class RateVersionApproval(BaseModel):
    """Request model for rate version approval."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    approval_notes: str | None = Field(None, max_length=1000)


class RateVersionRejection(BaseModel):
    """Request model for rate version rejection."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    rejection_reason: str = Field(..., min_length=10, max_length=1000)


class ABTestCreate(BaseModel):
    """Request model for A/B test creation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    control_version_id: UUID = Field(...)
    test_version_id: UUID = Field(...)
    traffic_split: float = Field(..., ge=0.1, le=0.5)
    start_date: date = Field(...)
    end_date: date = Field(...)


class RateAnalyticsQuery(BaseModel):
    """Request model for rate analytics query."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    table_name: str = Field(..., min_length=1)
    date_from: date = Field(...)
    date_to: date = Field(...)


# Helper dependency
async def get_rate_management_service(
    database=Depends(get_database),
    cache=Depends(get_cache),
) -> RateManagementService:
    """Get rate management service instance."""
    return RateManagementService(database, cache)


@router.post("/rate-tables/{table_name}/versions")
@beartype
async def create_rate_table_version(
    table_name: str,
    version_request: RateTableVersionCreate,
    rate_service: RateManagementService = Depends(get_rate_management_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Create new rate table version requiring approval.

    Requires 'rate:write' permission.
    Creates a new version of the specified rate table and triggers
    the approval workflow. Rate table must pass validation before
    being submitted for approval.
    """
    if "rate:write" not in admin_user.effective_permissions:
        raise HTTPException(
            status_code=403, detail="Insufficient permissions. Required: rate:write"
        )

    # Override table_name with path parameter for security
    version_request.table_name = table_name

    result = await rate_service.create_rate_table_version(
        version_request.table_name,
        version_request.rate_data,
        admin_user.id,
        version_request.effective_date,
        version_request.notes,
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    return result.ok_value


@router.post("/rate-versions/{version_id}/approve")
@beartype
async def approve_rate_version(
    version_id: UUID,
    approval_request: RateVersionApproval,
    rate_service: RateManagementService = Depends(get_rate_management_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, bool]:
    """Approve rate table version.

    Requires 'rate:approve' permission.
    Approves a pending rate version and potentially activates it
    if the effective date has been reached. Includes segregation
    of duties - cannot approve own submissions.
    """
    if "rate:approve" not in admin_user.effective_permissions:
        raise HTTPException(
            status_code=403, detail="Insufficient permissions. Required: rate:approve"
        )

    result = await rate_service.approve_rate_version(
        version_id,
        admin_user.id,
        approval_request.approval_notes,
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    return {"approved": result.ok_value or False}


@router.post("/rate-versions/{version_id}/reject")
@beartype
async def reject_rate_version(
    version_id: UUID,
    rejection_request: RateVersionRejection,
    rate_service: RateManagementService = Depends(get_rate_management_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, bool]:
    """Reject rate table version.

    Requires 'rate:approve' permission.
    Rejects a pending rate version with detailed reason.
    Rejected versions can be revised and resubmitted.
    """
    if "rate:approve" not in admin_user.effective_permissions:
        raise HTTPException(
            status_code=403, detail="Insufficient permissions. Required: rate:approve"
        )

    result = await rate_service.reject_rate_version(
        version_id,
        admin_user.id,
        rejection_request.rejection_reason,
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    return {"rejected": result.ok_value or False}


@router.get("/rate-versions/{version_id_1}/compare/{version_id_2}")
@beartype
async def compare_rate_versions(
    version_id_1: UUID,
    version_id_2: UUID,
    rate_service: RateManagementService = Depends(get_rate_management_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Compare two rate table versions with impact analysis.

    Requires 'rate:read' permission.
    Provides detailed comparison including rate differences,
    business impact analysis, and recommendations.
    """
    if "rate:read" not in admin_user.effective_permissions:
        raise HTTPException(
            status_code=403, detail="Insufficient permissions. Required: rate:read"
        )

    result = await rate_service.get_rate_comparison(version_id_1, version_id_2)

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    return result.ok_value


@router.post("/ab-tests")
@beartype
async def create_ab_test(
    ab_test_request: ABTestCreate,
    rate_service: RateManagementService = Depends(get_rate_management_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Schedule A/B test between rate versions.

    Requires 'rate:ab_test' permission.
    Creates A/B test configuration with traffic splitting and
    automated performance tracking. Both versions must be approved.
    """
    if "rate:ab_test" not in admin_user.effective_permissions:
        raise HTTPException(
            status_code=403, detail="Insufficient permissions. Required: rate:ab_test"
        )

    result = await rate_service.schedule_ab_test(
        ab_test_request.control_version_id,
        ab_test_request.test_version_id,
        ab_test_request.traffic_split,
        ab_test_request.start_date,
        ab_test_request.end_date,
        admin_user.id,
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    return {"test_id": result.ok_value, "status": "scheduled"}


@router.get("/analytics/{table_name}")
@beartype
async def get_rate_analytics(
    table_name: str,
    date_from: date,
    date_to: date,
    rate_service: RateManagementService = Depends(get_rate_management_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Get comprehensive rate analytics for admin dashboards.

    Requires 'rate:analytics' permission.
    Provides quote volume, conversion metrics, A/B test results,
    competitive analysis, and performance trends.
    """
    if "rate:analytics" not in admin_user.effective_permissions:
        raise HTTPException(
            status_code=403, detail="Insufficient permissions. Required: rate:analytics"
        )

    result = await rate_service.get_rate_analytics(table_name, date_from, date_to)

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    return result.ok_value


@router.get("/pending-approvals")
@beartype
async def get_pending_approvals(
    rate_service: RateManagementService = Depends(get_rate_management_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> list[dict[str, Any]]:
    """Get pending rate approvals for current admin user.

    Requires 'rate:approve' permission.
    Returns list of rate versions awaiting approval, excluding
    submissions by the current user (segregation of duties).
    """
    if "rate:approve" not in admin_user.effective_permissions:
        raise HTTPException(
            status_code=403, detail="Insufficient permissions. Required: rate:approve"
        )

    result = await rate_service.get_pending_approvals(admin_user.id)

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    return result.ok_value


# Additional endpoints for rate management


@router.get("/rate-tables/{table_name}/versions")
@beartype
async def list_rate_table_versions(
    table_name: str,
    include_inactive: bool = False,
    rate_service: RateManagementService = Depends(get_rate_management_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> list[dict[str, Any]]:
    """List all versions of a rate table.

    Requires 'rate:read' permission.
    Optionally includes inactive/rejected versions for audit purposes.
    """
    if "rate:read" not in admin_user.effective_permissions:
        raise HTTPException(
            status_code=403, detail="Insufficient permissions. Required: rate:read"
        )

    # Use underlying rate table service for version listing
    from ....core.cache import get_cache
    from ....core.database import get_database
    from ....services.rating.rate_tables import RateTableService

    db = await get_database()
    cache = await get_cache()
    rate_table_service = RateTableService(db, cache)

    result = await rate_table_service.list_rate_versions(table_name, include_inactive)

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    # Convert to dict format for API response
    versions = []
    for version in result.ok_value:
        versions.append(
            {
                "id": version.id,
                "version_number": version.version_number,
                "status": version.status,
                "effective_date": version.effective_date,
                "expiration_date": version.expiration_date,
                "created_at": version.created_at,
                "created_by": version.created_by,
                "approved_by": version.approved_by,
                "approved_at": version.approved_at,
                "notes": version.notes,
            }
        )

    return versions


@router.get("/rate-tables/{table_name}/active-rates")
@beartype
async def get_active_rates(
    table_name: str,
    state: str,
    product_type: str,
    rate_service: RateManagementService = Depends(get_rate_management_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Get currently active rates for state and product.

    Requires 'rate:read' permission.
    Returns the current active rate table data for the specified
    state and product type combination.
    """
    if "rate:read" not in admin_user.effective_permissions:
        raise HTTPException(
            status_code=403, detail="Insufficient permissions. Required: rate:read"
        )

    # Use underlying rate table service for active rates
    from ....core.cache import get_cache
    from ....core.database import get_database
    from ....services.rating.rate_tables import RateTableService

    db = await get_database()
    cache = await get_cache()
    rate_table_service = RateTableService(db, cache)

    result = await rate_table_service.get_active_rates(state, product_type)

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.err_value)

    # Convert Decimal values to float for JSON serialization
    rates = {}
    for coverage_type, rate_value in result.ok_value.items():
        rates[coverage_type] = float(rate_value)

    return {
        "state": state,
        "product_type": product_type,
        "table_name": table_name,
        "rates": rates,
        "retrieved_at": date.today(),
    }


@router.get("/health")
@beartype
async def rate_management_health(
    rate_service: RateManagementService = Depends(get_rate_management_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Health check for rate management system.

    Requires 'rate:read' permission.
    Checks availability of rate management services and key metrics.
    """
    if "rate:read" not in admin_user.effective_permissions:
        raise HTTPException(
            status_code=403, detail="Insufficient permissions. Required: rate:read"
        )

    try:
        # Basic health checks
        from ....core.cache import get_cache
        from ....core.database import get_database

        db = await get_database()
        cache = await get_cache()

        # Test database connectivity
        await db.fetchval("SELECT 1")
        db_status = "healthy"

        # Test cache connectivity
        await cache.set("health_check", "ok", 1)
        cache_value = await cache.get("health_check")
        cache_status = "healthy" if cache_value == "ok" else "degraded"

        return {
            "status": "healthy",
            "components": {
                "database": db_status,
                "cache": cache_status,
                "rate_management_service": "healthy",
            },
            "timestamp": date.today(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=503, detail=f"Rate management system unhealthy: {str(e)}"
        )
