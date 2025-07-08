"""Admin pricing control endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from beartype import beartype
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ....core.security import AdminUser, get_current_admin_user
from ....services.admin.pricing_override_service import PricingOverrideService
from ...dependencies import get_cache, get_database

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
async def get_pricing_service(
    database=Depends(get_database),
    cache=Depends(get_cache),
) -> PricingOverrideService:
    """Get pricing override service instance."""
    return PricingOverrideService(database, cache)


@router.post("/quotes/{quote_id}/pricing-override")
@beartype
async def create_pricing_override(
    quote_id: UUID,
    override_request: PricingOverrideRequest,
    pricing_service: PricingOverrideService = Depends(get_pricing_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Create pricing override for quote.

    Requires 'quote:override' permission.
    """
    if "quote:override" not in admin_user.effective_permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

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
        raise HTTPException(status_code=400, detail=result.unwrap_err())

    return {"override_id": result.unwrap(), "status": "created"}


@router.post("/quotes/{quote_id}/manual-discount")
@beartype
async def apply_manual_discount(
    quote_id: UUID,
    discount_request: ManualDiscountRequest,
    pricing_service: PricingOverrideService = Depends(get_pricing_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, bool]:
    """Apply manual discount to quote.

    Requires 'quote:discount' permission.
    """
    if "quote:discount" not in admin_user.effective_permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await pricing_service.apply_manual_discount(
        quote_id,
        admin_user.id,
        discount_request.discount_amount,
        discount_request.reason,
        discount_request.expires_at,
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.unwrap_err())

    return {"applied": result.unwrap()}


@router.post("/special-rules")
@beartype
async def create_special_pricing_rule(
    rule_request: SpecialPricingRuleRequest,
    pricing_service: PricingOverrideService = Depends(get_pricing_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, Any]:
    """Create special pricing rule.

    Requires 'pricing:rule:create' permission.
    """
    if "pricing:rule:create" not in admin_user.effective_permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await pricing_service.create_special_pricing_rule(
        admin_user.id,
        rule_request.rule_name,
        rule_request.conditions,
        rule_request.adjustments,
        rule_request.effective_date,
        rule_request.expiration_date,
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.unwrap_err())

    return {"rule_id": result.unwrap(), "status": "active"}


@router.get("/overrides/pending")
@beartype
async def get_pending_overrides(
    pricing_service: PricingOverrideService = Depends(get_pricing_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> list[dict[str, Any]]:
    """Get pending pricing overrides for approval.

    Requires 'pricing:override:approve' permission.
    """
    if "pricing:override:approve" not in admin_user.effective_permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await pricing_service.get_pending_overrides(admin_user.id)

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.unwrap_err())

    return result.unwrap()


@router.post("/overrides/{override_id}/approve")
@beartype
async def approve_pricing_override(
    override_id: UUID,
    approval_request: ApprovalRequest,
    pricing_service: PricingOverrideService = Depends(get_pricing_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, bool]:
    """Approve a pending pricing override.

    Requires 'pricing:override:approve' permission.
    """
    if "pricing:override:approve" not in admin_user.effective_permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await pricing_service.approve_pricing_override(
        override_id,
        admin_user.id,
        approval_request.approval_notes,
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.unwrap_err())

    return {"approved": result.unwrap()}


@router.post("/overrides/{override_id}/reject")
@beartype
async def reject_pricing_override(
    override_id: UUID,
    rejection_reason: str,
    pricing_service: PricingOverrideService = Depends(get_pricing_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> dict[str, bool]:
    """Reject a pending pricing override.

    Requires 'pricing:override:approve' permission.
    """
    if "pricing:override:approve" not in admin_user.effective_permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # In production, implement rejection logic
    # For now, return not implemented
    raise HTTPException(
        status_code=501, detail="Rejection functionality not yet implemented"
    )
