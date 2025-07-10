"""Admin pricing override and special rules service."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from beartype import beartype
from pydantic import ConfigDict, Field

from pd_prime_demo.core.cache import Cache
from pd_prime_demo.core.database import Database
from pd_prime_demo.core.result_types import Err, Ok, Result
from pd_prime_demo.models.base import BaseModelConfig

# Auto-generated models


@beartype
class ConditionsData(BaseModelConfig):
    """Conditions for special pricing rules."""

    # Customer criteria
    customer_type: str | None = Field(
        None, description="Type of customer (individual, business, etc.)"
    )
    min_age: int | None = Field(
        None, ge=16, le=100, description="Minimum age requirement"
    )
    max_age: int | None = Field(None, ge=16, le=100, description="Maximum age limit")

    # Policy criteria
    policy_type: str | None = Field(None, description="Type of policy")
    coverage_amount_min: float | None = Field(
        None, ge=0, description="Minimum coverage amount"
    )
    coverage_amount_max: float | None = Field(
        None, ge=0, description="Maximum coverage amount"
    )

    # Geographic criteria
    state: str | None = Field(None, description="State code")
    zip_codes: list[str] = Field(
        default_factory=list, description="Applicable ZIP codes"
    )


@beartype
class AdjustmentsData(BaseModelConfig):
    """Pricing adjustments for special rules."""

    # Percentage adjustments
    premium_adjustment_pct: float | None = Field(
        None, description="Premium adjustment percentage"
    )
    deductible_adjustment_pct: float | None = Field(
        None, description="Deductible adjustment percentage"
    )

    # Fixed adjustments
    premium_adjustment_fixed: float | None = Field(
        None, description="Fixed premium adjustment"
    )
    discount_amount: float | None = Field(
        None, ge=0, description="Fixed discount amount"
    )

    # Coverage adjustments
    coverage_adjustments: dict[str, float] = Field(
        default_factory=dict, description="Coverage-specific adjustments"
    )


class PricingOverrideResponse(BaseModelConfig):
    """Pricing override response model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: UUID
    quote_id: UUID
    admin_user_id: UUID
    override_type: str
    original_amount: Decimal
    new_amount: Decimal
    adjustment_percentage: Decimal
    reason: str
    status: str
    created_at: datetime
    approved_at: datetime | None = None
    approved_by: UUID | None = None
    approval_notes: str | None = None


class PricingOverrideService:
    """Service for admin pricing overrides and special rules."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize pricing override service.

        Args:
            db: Database connection
            cache: Cache instance
        """
        self._db = db
        self._cache = cache

    @beartype
    async def create_pricing_override(
        self,
        quote_id: UUID,
        admin_user_id: UUID,
        override_type: str,  # 'premium_adjustment', 'discount_override', 'special_rate'
        original_amount: Decimal,
        new_amount: Decimal,
        reason: str,
        approval_required: bool = True,
    ) -> Result[UUID, str]:
        """Create pricing override requiring approval.

        Args:
            quote_id: Quote ID to override
            admin_user_id: Admin user creating the override
            override_type: Type of override
            original_amount: Original premium amount
            new_amount: New premium amount
            reason: Reason for override
            approval_required: Whether approval is required

        Returns:
            Result containing override ID or error
        """
        try:
            # Validate override type
            valid_types = ["premium_adjustment", "discount_override", "special_rate"]
            if override_type not in valid_types:
                return Err(f"Invalid override type: {override_type}")

            # Validate amounts
            if original_amount <= 0:
                return Err("Original amount must be positive")
            if new_amount <= 0:
                return Err("New amount must be positive")

            # Validate override is within limits
            max_adjustment = await self._get_max_adjustment_limit(admin_user_id)
            adjustment_pct = abs((new_amount - original_amount) / original_amount) * 100

            if adjustment_pct > max_adjustment and approval_required:
                return Err(
                    f"Adjustment {adjustment_pct:.1f}% exceeds limit {max_adjustment}%. "
                    f"Required action: Request approval from senior underwriter. "
                    f"Check: Admin > Pricing Overrides > Request Approval"
                )

            override_id = uuid4()

            await self._db.execute(
                """
                INSERT INTO pricing_overrides (
                    id, quote_id, admin_user_id, override_type,
                    original_amount, new_amount, adjustment_percentage,
                    reason, status, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                override_id,
                quote_id,
                admin_user_id,
                override_type,
                original_amount,
                new_amount,
                adjustment_pct,
                reason,
                "pending" if approval_required else "approved",
                datetime.utcnow(),
            )

            # Invalidate pricing cache
            await self._cache.delete(f"quote:pricing:{quote_id}")

            # Create approval workflow if needed
            if approval_required:
                await self._create_pricing_approval_workflow(
                    override_id, float(adjustment_pct)
                )

            # Log activity
            await self._log_pricing_activity(
                admin_user_id,
                "pricing_override",
                quote_id,
                {
                    "override_id": str(override_id),
                    "type": override_type,
                    "adjustment_pct": adjustment_pct,
                    "reason": reason,
                },
            )

            return Ok(override_id)

        except Exception as e:
            return Err(f"Override creation failed: {str(e)}")

    @beartype
    async def apply_manual_discount(
        self,
        quote_id: UUID,
        admin_user_id: UUID,
        discount_amount: Decimal,
        discount_reason: str,
        expires_at: datetime | None = None,
    ) -> Result[bool, str]:
        """Apply manual discount to quote.

        Args:
            quote_id: Quote to apply discount to
            admin_user_id: Admin applying the discount
            discount_amount: Discount amount
            discount_reason: Reason for discount
            expires_at: Optional expiration date

        Returns:
            Result containing success status or error
        """
        try:
            # Validate discount amount
            if discount_amount <= 0:
                return Err("Discount amount must be positive")

            # Get current quote premium
            quote = await self._db.fetchrow(
                "SELECT total_premium FROM quotes WHERE id = $1", quote_id
            )
            if not quote:
                return Err("Quote not found")

            # Validate discount amount
            max_discount_pct = 25.0  # 25% max manual discount
            discount_pct = (discount_amount / quote["total_premium"]) * 100

            if discount_pct > max_discount_pct:
                return Err(
                    f"Discount {discount_pct:.1f}% exceeds maximum {max_discount_pct}%. "
                    f"Required action: Use pricing override for larger adjustments. "
                    f"Check: Admin > Pricing Overrides > Create Override"
                )

            # Apply discount
            await self._db.execute(
                """
                INSERT INTO manual_discounts (
                    quote_id, admin_user_id, discount_amount,
                    discount_percentage, reason, expires_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                quote_id,
                admin_user_id,
                discount_amount,
                discount_pct,
                discount_reason,
                expires_at,
            )

            # Update quote with new premium
            new_premium = quote["total_premium"] - discount_amount
            await self._db.execute(
                """
                UPDATE quotes
                SET total_premium = $2,
                    has_manual_adjustments = true,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                quote_id,
                new_premium,
            )

            # Clear cache
            await self._cache.delete(f"quote:pricing:{quote_id}")

            # Log activity
            await self._log_pricing_activity(
                admin_user_id,
                "manual_discount",
                quote_id,
                {"amount": float(discount_amount), "reason": discount_reason},
            )

            return Ok(True)

        except Exception as e:
            return Err(f"Discount application failed: {str(e)}")

    @beartype
    async def create_special_pricing_rule(
        self,
        admin_user_id: UUID,
        rule_name: str,
        conditions: ConditionsData,
        adjustments: AdjustmentsData,
        effective_date: datetime,
        expiration_date: datetime | None = None,
    ) -> Result[UUID, str]:
        """Create special pricing rule (e.g., promotional rates).

        Args:
            admin_user_id: Admin creating the rule
            rule_name: Name of the pricing rule
            conditions: Conditions for rule application
            adjustments: Pricing adjustments to apply
            effective_date: When rule becomes effective
            expiration_date: Optional expiration date

        Returns:
            Result containing rule ID or error
        """
        try:
            # Validate rule name
            if not rule_name or len(rule_name) < 3:
                return Err("Rule name must be at least 3 characters")

            # Validate conditions
            if not conditions:
                return Err("Rule must have at least one condition")

            # Validate adjustments
            if not adjustments:
                return Err("Rule must have at least one adjustment")

            # Validate dates
            if expiration_date and expiration_date <= effective_date:
                return Err("Expiration date must be after effective date")

            rule_id = uuid4()

            await self._db.execute(
                """
                INSERT INTO special_pricing_rules (
                    id, rule_name, conditions, adjustments,
                    effective_date, expiration_date, created_by,
                    status, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'active', $8)
                """,
                rule_id,
                rule_name,
                conditions,
                adjustments,
                effective_date,
                expiration_date,
                admin_user_id,
                datetime.utcnow(),
            )

            # Clear pricing cache to force rule evaluation
            await self._cache.clear_pattern("rating:*")

            # Log activity
            await self._log_pricing_activity(
                admin_user_id,
                "special_rule_created",
                None,
                {
                    "rule_id": str(rule_id),
                    "rule_name": rule_name,
                    "conditions": conditions,
                    "adjustments": adjustments,
                },
            )

            return Ok(rule_id)

        except Exception as e:
            return Err(f"Rule creation failed: {str(e)}")

    @beartype
    async def approve_pricing_override(
        self,
        override_id: UUID,
        approver_id: UUID,
        approval_notes: str | None = None,
    ) -> Result[bool, str]:
        """Approve a pending pricing override.

        Args:
            override_id: Override to approve
            approver_id: Admin approving the override
            approval_notes: Optional approval notes

        Returns:
            Result containing success status or error
        """
        try:
            # Get override details
            override = await self._db.fetchrow(
                """
                SELECT status, admin_user_id, quote_id, adjustment_percentage
                FROM pricing_overrides
                WHERE id = $1
                """,
                override_id,
            )

            if not override:
                return Err("Override not found")

            if override["status"] != "pending":
                return Err(f"Override is already {override['status']}")

            # Verify approver is not the creator
            if override["admin_user_id"] == approver_id:
                return Err("Cannot approve your own override")

            # Update override status
            await self._db.execute(
                """
                UPDATE pricing_overrides
                SET status = 'approved',
                    approved_by = $2,
                    approved_at = $3,
                    approval_notes = $4
                WHERE id = $1
                """,
                override_id,
                approver_id,
                datetime.utcnow(),
                approval_notes,
            )

            # Clear quote cache to apply override
            await self._cache.delete(f"quote:pricing:{override['quote_id']}")

            # Log approval
            await self._log_pricing_activity(
                approver_id,
                "override_approved",
                override["quote_id"],
                {
                    "override_id": str(override_id),
                    "adjustment_pct": float(override["adjustment_percentage"]),
                },
            )

            return Ok(True)

        except Exception as e:
            return Err(f"Approval failed: {str(e)}")

    @beartype
    async def get_pending_overrides(
        self,
        admin_user_id: UUID,
    ) -> Result[list[PricingOverrideResponse], str]:
        """Get pending pricing overrides for approval.

        Args:
            admin_user_id: Admin checking overrides

        Returns:
            Result containing list of pending overrides or error
        """
        try:
            # Get admin's approval limit to filter relevant overrides
            max_approval_limit = await self._get_max_approval_limit(admin_user_id)

            rows = await self._db.fetch(
                """
                SELECT
                    po.id, po.quote_id, po.admin_user_id, po.override_type,
                    po.original_amount, po.new_amount, po.adjustment_percentage,
                    po.reason, po.created_at,
                    au.name as admin_name,
                    q.customer_id
                FROM pricing_overrides po
                JOIN admin_users au ON po.admin_user_id = au.id
                JOIN quotes q ON po.quote_id = q.id
                WHERE po.status = 'pending'
                    AND po.admin_user_id != $1
                    AND po.adjustment_percentage <= $2
                ORDER BY po.created_at DESC
                """,
                admin_user_id,
                max_approval_limit,
            )

            overrides = []
            for row in rows:
                override = PricingOverrideResponse(
                    id=row["id"],
                    quote_id=row["quote_id"],
                    admin_user_id=row["admin_user_id"],
                    override_type=row["override_type"],
                    original_amount=row["original_amount"],
                    new_amount=row["new_amount"],
                    adjustment_percentage=row["adjustment_percentage"],
                    reason=row["reason"],
                    status="pending",
                    created_at=row["created_at"],
                )
                overrides.append(override)
            return Ok(overrides)

        except Exception as e:
            return Err(f"Failed to fetch pending overrides: {str(e)}")

    @beartype
    async def _get_max_adjustment_limit(self, admin_user_id: UUID) -> float:
        """Get maximum adjustment limit for admin user.

        Args:
            admin_user_id: Admin user ID

        Returns:
            Maximum adjustment percentage
        """
        # In production, query from admin_users table based on role/permissions
        # For now, return default limits
        return 15.0  # 15% without approval

    @beartype
    async def _get_max_approval_limit(self, admin_user_id: UUID) -> float:
        """Get maximum approval limit for admin user.

        Args:
            admin_user_id: Admin user ID

        Returns:
            Maximum approval percentage
        """
        # In production, query from admin_users table based on role/permissions
        # For now, return default limits
        return 30.0  # Can approve up to 30%

    @beartype
    async def _create_pricing_approval_workflow(
        self,
        override_id: UUID,
        adjustment_pct: float,
    ) -> None:
        """Create approval workflow for pricing override.

        Args:
            override_id: Override requiring approval
            adjustment_pct: Adjustment percentage
        """
        # In production, create workflow entries and send notifications
        # For now, just log the requirement
        await self._db.execute(
            """
            INSERT INTO audit_logs (
                action_type, entity_type, entity_id,
                action_data, created_at
            ) VALUES ('approval_required', 'pricing_override', $1, $2, $3)
            """,
            override_id,
            {"adjustment_pct": adjustment_pct, "status": "pending_approval"},
            datetime.utcnow(),
        )

    @beartype
    async def _log_pricing_activity(
        self,
        admin_user_id: UUID,
        action_type: str,
        quote_id: UUID | None,
        action_data: dict[str, Any],
    ) -> None:
        """Log pricing activity for audit trail.

        Args:
            admin_user_id: Admin performing the action
            action_type: Type of pricing action
            quote_id: Related quote ID if applicable
            action_data: Additional action data
        """
        await self._db.execute(
            """
            INSERT INTO audit_logs (
                user_id, action_type, entity_type, entity_id,
                action_data, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            admin_user_id,
            action_type,
            "quote" if quote_id else "pricing_rule",
            quote_id,
            action_data,
            datetime.utcnow(),
        )
