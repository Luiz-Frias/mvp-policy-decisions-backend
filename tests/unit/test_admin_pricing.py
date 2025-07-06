#!/usr/bin/env python3
"""
Test Admin Pricing Override Functionality
"""

import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

from pd_prime_demo.services.admin.pricing_override_service import PricingOverrideService


async def test_admin_pricing_overrides():
    """Test admin pricing override functionality."""

    # Mock database and cache
    mock_db = AsyncMock()
    mock_cache = AsyncMock()

    # Create service
    service = PricingOverrideService(mock_db, mock_cache)

    print("Testing Admin Pricing Override Service...")

    # Test 1: Create pricing override
    quote_id = uuid4()
    admin_id = uuid4()

    # Mock database responses
    mock_db.fetchrow.return_value = {"total_premium": Decimal("1000.00")}

    result = await service.create_pricing_override(
        quote_id=quote_id,
        admin_user_id=admin_id,
        override_type="premium_adjustment",
        original_amount=Decimal("1000.00"),
        new_amount=Decimal("900.00"),
        reason="Customer retention - longtime customer with clean record",
        approval_required=True,
    )

    print(
        f"1. Create Pricing Override: {'✅ SUCCESS' if result.is_ok() else '❌ ERROR'}"
    )
    if result.is_err():
        print(f"   Error: {result.unwrap_err()}")
    else:
        print(f"   Override ID: {result.unwrap()}")

    # Test 2: Apply manual discount
    result = await service.apply_manual_discount(
        quote_id=quote_id,
        admin_user_id=admin_id,
        discount_amount=Decimal("50.00"),
        discount_reason="Good driver discount - no claims in 5 years",
    )

    print(f"2. Apply Manual Discount: {'✅ SUCCESS' if result.is_ok() else '❌ ERROR'}")
    if result.is_err():
        print(f"   Error: {result.unwrap_err()}")

    # Test 3: Create special pricing rule
    conditions = {
        "customer_tenure": {"min_years": 5},
        "territory": {"zip_codes": ["90210", "10001"]},
        "product_type": "auto",
    }
    adjustments = {"base_rate_multiplier": 0.95, "loyalty_discount": 0.05}

    from datetime import datetime

    result = await service.create_special_pricing_rule(
        admin_user_id=admin_id,
        rule_name="Loyalty Customer Special Rate",
        conditions=conditions,
        adjustments=adjustments,
        effective_date=datetime.now(),
        expiration_date=None,
    )

    print(f"3. Create Special Rule: {'✅ SUCCESS' if result.is_ok() else '❌ ERROR'}")
    if result.is_err():
        print(f"   Error: {result.unwrap_err()}")
    else:
        print(f"   Rule ID: {result.unwrap()}")

    # Test 4: Test override with excessive adjustment (should require approval)
    result = await service.create_pricing_override(
        quote_id=quote_id,
        admin_user_id=admin_id,
        override_type="premium_adjustment",
        original_amount=Decimal("1000.00"),
        new_amount=Decimal("700.00"),  # 30% reduction - exceeds 15% limit
        reason="Special circumstances - significant rate reduction needed",
        approval_required=True,
    )

    print(f"4. Large Override (30%): {'✅ SUCCESS' if result.is_ok() else '❌ ERROR'}")
    if result.is_err():
        print(f"   Error: {result.unwrap_err()}")

    # Test 5: Test excessive manual discount (should fail)
    result = await service.apply_manual_discount(
        quote_id=quote_id,
        admin_user_id=admin_id,
        discount_amount=Decimal("300.00"),  # 30% discount - exceeds 25% limit
        discount_reason="Attempted excessive discount",
    )

    print(
        f"5. Excessive Discount (30%): {'❌ ERROR' if result.is_err() else '⚠️ UNEXPECTED SUCCESS'}"
    )
    if result.is_err():
        print(f"   Expected Error: {result.unwrap_err()}")

    print("\n🎯 Admin Pricing Override Tests Completed")


if __name__ == "__main__":
    asyncio.run(test_admin_pricing_overrides())
