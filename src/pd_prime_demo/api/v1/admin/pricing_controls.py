"""Admin pricing control endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Union
from uuid import UUID

from beartype import beartype
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from ....core.cache import Cache
from ....core.database_enhanced import Database
from ....models.admin import AdminUser
from ....services.admin.pricing_override_service import PricingOverrideService
from ...dependencies import get_cache, get_current_admin_user, get_database
from ...response_patterns import handle_result, ErrorResponse

router = APIRouter(prefix="/admin/pricing", tags=["admin-pricing"])


# Request/Response Models
class PricingOverrideRequest(BaseModel):
    """Request model for pricing override."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    override_type: str = Field(
        ...,
        description="Type of override: premium_adjustment, discount_override, special_rate",
    )
    original_amount: Decimal = Field(..., ge=0, decimal_places=2)
    new_amount: Decimal = Field(..., ge=0, decimal_places=2)
    reason: str = Field(..., min_length=10, max_length=500)
    approval_required: bool = Field(default=True)


class ManualDiscountRequest(BaseModel):
    """Request model for manual discount."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    discount_amount: Decimal = Field(..., gt=0, decimal_places=2)
    reason: str = Field(..., min_length=10, max_length=500)
    expires_at: datetime | None = Field(default=None)


class SpecialPricingRuleRequest(BaseModel):
    """Request model for special pricing rule."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    rule_name: str = Field(..., min_length=3, max_length=100)
    conditions: dict[str, Any] = Field(..., description="Rule conditions")
    adjustments: dict[str, Any] = Field(..., description="Pricing adjustments")
    effective_date: datetime = Field(...)
    expiration_date: datetime | None = Field(default=None)


class ApprovalRequest(BaseModel):
    """Request model for override approval."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    approval_notes: str | None = Field(default=None, max_length=500)


# Helper dependency
@beartype
async def get_pricing_service(
    database: Database = Depends(get_database),
    cache: Cache = Depends(get_cache),
) -> PricingOverrideService:
    """Get pricing override service instance."""
    return PricingOverrideService(database, cache)


@router.post("/quotes/{quote_id}/pricing-override")
@beartype
async def create_pricing_override(
    quote_id: UUID,
    override_request: PricingOverrideRequest,
    response: Response,
    pricing_service: PricingOverrideService = Depends(get_pricing_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Union[dict[str, Any], ErrorResponse]:
    """Create pricing override for quote.

    Requires 'quote:override' permission.
    """
    if "quote:override" not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions")

    result = await pricing_service.create_pricing_override(
        quote_id,
        admin_user.id,
        override_request.override_type,
        override_request.original_amount,
        override_request.new_amount,
        override_request.reason,
        override_request.approval_required,
    )

    if result.is_err():
        return handle_result(result, response)

    response.status_code = 201
    return {"override_id": result.ok_value, "status": "created"}


@router.post("/quotes/{quote_id}/manual-discount")
@beartype
async def apply_manual_discount(
    quote_id: UUID,
    discount_request: ManualDiscountRequest,
    response: Response,
    pricing_service: PricingOverrideService = Depends(get_pricing_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Union[dict[str, bool], ErrorResponse]:
    """Apply manual discount to quote.

    Requires 'quote:discount' permission.
    """
    if "quote:discount" not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions")

    result = await pricing_service.apply_manual_discount(
        quote_id,
        admin_user.id,
        discount_request.discount_amount,
        discount_request.reason,
        discount_request.expires_at,
    )

    if result.is_err():
        return handle_result(result, response)

    return {"applied": result.ok_value or False}


@router.post("/special-rules")
@beartype
async def create_special_pricing_rule(
    rule_request: SpecialPricingRuleRequest,
    response: Response,
    pricing_service: PricingOverrideService = Depends(get_pricing_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Union[dict[str, Any], ErrorResponse]:
    """Create special pricing rule.

    Requires 'pricing:rule:create' permission.
    """
    if "pricing:rule:create" not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions")

    result = await pricing_service.create_special_pricing_rule(
        admin_user.id,
        rule_request.rule_name,
        rule_request.conditions,
        rule_request.adjustments,
        rule_request.effective_date,
        rule_request.expiration_date,
    )

    if result.is_err():
        return handle_result(result, response)

    response.status_code = 201
    return {"rule_id": result.ok_value, "status": "active"}


@router.get("/overrides/pending")
@beartype
async def get_pending_overrides(
    response: Response,
    pricing_service: PricingOverrideService = Depends(get_pricing_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Union[list[dict[str, Any]], ErrorResponse]:
    """Get pending pricing overrides for approval.

    Requires 'pricing:override:approve' permission.
    """
    if "pricing:override:approve" not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions")

    result = await pricing_service.get_pending_overrides(admin_user.id)

    return handle_result(result, response)


@router.post("/overrides/{override_id}/approve")
@beartype
async def approve_pricing_override(
    override_id: UUID,
    approval_request: ApprovalRequest,
    response: Response,
    pricing_service: PricingOverrideService = Depends(get_pricing_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Union[dict[str, bool], ErrorResponse]:
    """Approve a pending pricing override.

    Requires 'pricing:override:approve' permission.
    """
    if "pricing:override:approve" not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions")

    result = await pricing_service.approve_pricing_override(
        override_id,
        admin_user.id,
        approval_request.approval_notes,
    )

    if result.is_err():
        return handle_result(result, response)

    return {"approved": result.ok_value or False}


@router.post("/overrides/{override_id}/reject")
@beartype
async def reject_pricing_override(
    override_id: UUID,
    rejection_reason: str,
    response: Response,
    pricing_service: PricingOverrideService = Depends(get_pricing_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Union[dict[str, bool], ErrorResponse]:
    """Reject a pending pricing override.

    Requires 'pricing:override:approve' permission.
    """
    if "pricing:override:approve" not in admin_user.effective_permissions:
        response.status_code = 403
        return ErrorResponse(error="Insufficient permissions")

    # In production, implement rejection logic
    # For now, return not implemented
    response.status_code = 501
    return ErrorResponse(error="Rejection functionality not yet implemented")
