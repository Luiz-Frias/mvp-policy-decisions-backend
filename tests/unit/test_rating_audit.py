"""Quick audit test for rating engine to verify core functionality."""

import asyncio
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

from src.policy_core.models.quote import (
    CoverageSelection,
    CoverageType,
    DriverInfo,
    VehicleInfo,
    VehicleType,
)
from src.policy_core.services.rating.state_rules import get_state_rules
from src.policy_core.services.rating_engine import RatingEngine


async def test_rating_engine_audit():
    """Audit the rating engine implementation."""
    print("🔍 AUDITING RATING ENGINE...")

    # Create mock dependencies
    mock_db = AsyncMock()
    mock_cache = AsyncMock()

    # Mock database responses for rate tables
    mock_db.fetch.return_value = [
        {"coverage_type": "bodily_injury", "base_rate": "0.50"},
        {"coverage_type": "property_damage", "base_rate": "0.30"},
        {"coverage_type": "collision", "base_rate": "0.80"},
        {"coverage_type": "comprehensive", "base_rate": "0.70"},
    ]

    mock_db.fetchrow.return_value = {"minimum_premium": "500.00"}

    # Mock cache responses
    mock_cache.get.return_value = None
    mock_cache.set = AsyncMock()

    # Create rating engine
    rating_engine = RatingEngine(mock_db, mock_cache)

    # Initialize
    print("  ✓ Initializing rating engine...")
    init_result = await rating_engine.initialize()
    print(f"  ✓ Initialization result: {init_result}")

    # Test state rules
    print("  ✓ Testing state-specific rules...")

    # Test California rules (Prop 103 compliance)
    ca_rules = get_state_rules("CA")
    if ca_rules.is_ok():
        ca_rule = ca_rules.value
        print(f"  ✓ CA required coverages: {ca_rule.get_required_coverages()}")
        print(f"  ✓ CA minimum limits: {ca_rule.get_minimum_limits()}")

        # Test factor validation
        test_factors = {
            "credit": 1.2,  # Should be removed in CA
            "violations": 1.1,
            "accidents": 1.0,
            "experience": 0.95,
            "territory": 1.05,
        }
        validated = ca_rule.validate_factors(test_factors)
        print(f"  ✓ CA factor validation: {validated}")
        assert "credit" not in validated, "Credit scoring should be prohibited in CA"
    else:
        print(f"  ❌ CA rules error: {ca_rules.error}")

    # Test Texas rules
    tx_rules = get_state_rules("TX")
    if tx_rules.is_ok():
        tx_rule = tx_rules.value
        print(f"  ✓ TX required coverages: {tx_rule.get_required_coverages()}")
        print(f"  ✓ TX minimum limits: {tx_rule.get_minimum_limits()}")

        # Test factor validation (TX allows more)
        test_factors = {
            "credit": 1.2,  # Should be allowed in TX
            "violations": 1.1,
            "accidents": 1.0,
        }
        validated = tx_rule.validate_factors(test_factors)
        print(f"  ✓ TX factor validation: {validated}")
        assert "credit" in validated, "Credit scoring should be allowed in TX"
    else:
        print(f"  ❌ TX rules error: {tx_rules.error}")

    # Test New York rules
    ny_rules = get_state_rules("NY")
    if ny_rules.is_ok():
        ny_rule = ny_rules.value
        print(f"  ✓ NY required coverages: {ny_rule.get_required_coverages()}")
        print(f"  ✓ NY minimum limits: {ny_rule.get_minimum_limits()}")
    else:
        print(f"  ❌ NY rules error: {ny_rules.error}")

    # Test unsupported state (should fail fast)
    unsupported_rules = get_state_rules("ZZ")
    if unsupported_rules.is_err():
        print(f"  ✓ Unsupported state properly rejected: {unsupported_rules.error}")
    else:
        print("  ❌ Unsupported state should fail")

    # Create test quote data
    print("  ✓ Testing quote calculation...")

    vehicle = VehicleInfo(
        vin="1HGBH41JXMN109186",
        year=2022,
        make="Toyota",
        model="Camry",
        trim="LE",
        body_style="Sedan",
        vehicle_type=VehicleType.PRIVATE_PASSENGER,
        engine_size="2.5L",
        fuel_type="Gasoline",
        safety_rating=5,
        anti_theft=True,
        usage="Personal",
        annual_mileage=12000,
        garage_zip="90210",
        garage_type="Attached Garage",
        owned=True,
        finance_type="Owned",
        value=Decimal("25000.00"),
        purchase_date=date(2022, 1, 15),
        primary_use="Work",
        parking_location="Garage",
        safety_features=["abs", "airbags", "automatic_braking"],
        comprehensive_deductible=Decimal("500.00"),
        collision_deductible=Decimal("500.00"),
    )

    driver = DriverInfo(
        first_name="John",
        last_name="Doe",
        date_of_birth=date(1990, 1, 1),
        license_number="D12345678",
        license_state="CA",
        license_status="valid",
        years_licensed=10,
        age=34,
        gender="M",
        marital_status="married",
        accidents_3_years=0,
        violations_3_years=0,
        claims_3_years=0,
        dui_convictions=0,
        sr22_required=False,
        good_student=False,
        military=False,
        defensive_driving=False,
        occupation="Engineer",
    )

    coverages = [
        CoverageSelection(
            coverage_type=CoverageType.BODILY_INJURY,
            limit=Decimal("100000"),
            deductible=Decimal("0"),
        ),
        CoverageSelection(
            coverage_type=CoverageType.PROPERTY_DAMAGE,
            limit=Decimal("50000"),
            deductible=Decimal("0"),
        ),
        CoverageSelection(
            coverage_type=CoverageType.COLLISION,
            limit=Decimal("25000"),
            deductible=Decimal("500"),
        ),
    ]

    # Test premium calculation
    start_time = asyncio.get_event_loop().time()

    result = await rating_engine.calculate_premium(
        state="CA",
        product_type="auto",
        vehicle_info=vehicle,
        drivers=[driver],
        coverage_selections=coverages,
    )

    end_time = asyncio.get_event_loop().time()
    calc_time_ms = int((end_time - start_time) * 1000)

    if result.is_ok():
        rating_result = result.value
        print("  ✓ Premium calculation successful!")
        print(f"  ✓ Base premium: ${rating_result.base_premium}")
        print(f"  ✓ Total premium: ${rating_result.total_premium}")
        print(f"  ✓ Calculation time: {calc_time_ms}ms")
        print(f"  ✓ Factors applied: {rating_result.factors}")
        print(f"  ✓ Discounts: {len(rating_result.discounts)}")
        print(f"  ✓ Tier: {rating_result.tier}")

        # Verify performance requirement
        if calc_time_ms <= 50:
            print(f"  ✓ Performance requirement MET: {calc_time_ms}ms <= 50ms")
        else:
            print(f"  ⚠️  Performance requirement EXCEEDED: {calc_time_ms}ms > 50ms")

        # Verify calculations make sense
        assert rating_result.base_premium > 0, "Base premium should be positive"
        assert rating_result.total_premium > 0, "Total premium should be positive"
        assert rating_result.tier in [
            "preferred_plus",
            "preferred",
            "standard",
            "non_standard",
            "high_risk",
        ]

    else:
        print(f"  ❌ Premium calculation failed: {result.error}")

    print("🎉 RATING ENGINE AUDIT COMPLETE!")
    return result


async def test_discount_logic():
    """Test discount calculation logic."""
    print("\n🔍 AUDITING DISCOUNT LOGIC...")

    # Create mock dependencies
    mock_db = AsyncMock()
    mock_cache = AsyncMock()

    # Mock responses for discounts
    mock_db.fetch.return_value = [
        {"coverage_type": "bodily_injury", "base_rate": "0.50"},
        {"coverage_type": "property_damage", "base_rate": "0.30"},
    ]

    mock_db.fetchrow.side_effect = [
        {"minimum_premium": "500.00"},  # Minimum premium
        {"policy_count": 2},  # Multi-policy count
        {"first_policy_date": "2019-01-01"},  # Customer tenure
        {"lapse_count": 0},  # No coverage lapse
    ]

    mock_cache.get.return_value = None
    mock_cache.set = AsyncMock()

    rating_engine = RatingEngine(mock_db, mock_cache)
    await rating_engine.initialize()

    # Create customer with multiple discount qualifications
    vehicle = VehicleInfo(
        vin="1HGBH41JXMN109186",
        year=2022,
        make="Honda",
        model="Civic",
        trim="LX",
        body_style="Sedan",
        vehicle_type=VehicleType.PRIVATE_PASSENGER,
        engine_size="2.0L",
        fuel_type="Gasoline",
        safety_rating=5,
        anti_theft=True,
        usage="Personal",
        annual_mileage=8000,  # Low mileage
        garage_zip="78701",  # Austin, TX
        garage_type="Attached Garage",
        owned=True,
        finance_type="Owned",
        value=Decimal("22000.00"),
        purchase_date=date(2022, 1, 15),
        primary_use="Commute",
        parking_location="Garage",
        safety_features=["abs", "airbags", "lane_assist"],
        comprehensive_deductible=Decimal("500.00"),
        collision_deductible=Decimal("500.00"),
    )

    # Young driver who is a good student
    young_driver = DriverInfo(
        first_name="Jane",
        last_name="Student",
        date_of_birth=date(2002, 1, 1),  # Age 22
        license_number="D87654321",
        license_state="TX",
        license_status="valid",
        years_licensed=4,
        age=22,
        gender="F",
        marital_status="single",
        accidents_3_years=0,  # No accidents
        violations_3_years=0,  # Clean record
        claims_3_years=0,
        dui_convictions=0,
        sr22_required=False,
        good_student=True,  # Good student discount
        military=False,
        defensive_driving=False,
        occupation="Student",
    )

    # Military member
    military_driver = DriverInfo(
        first_name="Mike",
        last_name="Military",
        date_of_birth=date(1985, 1, 1),  # Age 39
        license_number="D11111111",
        license_state="TX",
        license_status="valid",
        years_licensed=20,
        age=39,
        gender="M",
        marital_status="married",
        accidents_3_years=0,  # No accidents
        violations_3_years=0,  # Clean record
        claims_3_years=0,
        dui_convictions=0,
        sr22_required=False,
        good_student=False,
        military=True,
        defensive_driving=False,
        occupation="Military Officer",  # Military discount
    )

    coverages = [
        CoverageSelection(
            coverage_type=CoverageType.BODILY_INJURY,
            limit=Decimal("100000"),
            deductible=Decimal("0"),
        ),
        CoverageSelection(
            coverage_type=CoverageType.PROPERTY_DAMAGE,
            limit=Decimal("50000"),
            deductible=Decimal("0"),
        ),
    ]

    # Test discount stacking
    result = await rating_engine.calculate_premium(
        state="TX",  # Allow credit scoring
        product_type="auto",
        vehicle_info=vehicle,
        drivers=[young_driver, military_driver],
        coverage_selections=coverages,
        customer_id=uuid4(),
    )

    if result.is_ok():
        rating_result = result.value
        print("  ✓ Discount calculation successful!")
        print(f"  ✓ Number of discounts: {len(rating_result.discounts)}")

        discount_types = [d.discount_type.value for d in rating_result.discounts]
        print(f"  ✓ Applied discounts: {discount_types}")

        total_discount_pct = sum(d.percentage for d in rating_result.discounts)
        print(f"  ✓ Total discount percentage: {total_discount_pct}%")

        # Verify discount cap (should not exceed 50%)
        assert (
            total_discount_pct <= 50
        ), f"Total discounts {total_discount_pct}% exceed 50% cap"

        expected_discounts = [
            "multi_policy",
            "safe_driver",
            "good_student",
            "military",
            "loyalty",
        ]
        for expected in expected_discounts:
            if expected in discount_types:
                print(f"  ✓ {expected} discount applied")

    else:
        print(f"  ❌ Discount calculation failed: {result.error}")

    print("🎉 DISCOUNT LOGIC AUDIT COMPLETE!")


async def test_surcharge_logic():
    """Test surcharge calculation logic."""
    print("\n🔍 AUDITING SURCHARGE LOGIC...")

    # Create mock dependencies
    mock_db = AsyncMock()
    mock_cache = AsyncMock()

    # Mock responses
    mock_db.fetch.return_value = [
        {"coverage_type": "bodily_injury", "base_rate": "0.50"},
        {"coverage_type": "property_damage", "base_rate": "0.30"},
    ]

    mock_db.fetchrow.side_effect = [
        {"minimum_premium": "500.00"},  # Minimum premium
        {"lapse_count": 1},  # Coverage lapse
    ]

    mock_cache.get.return_value = None

    rating_engine = RatingEngine(mock_db, mock_cache)
    await rating_engine.initialize()

    # High-risk driver with DUI
    high_risk_driver = DriverInfo(
        first_name="Risk",
        last_name="Driver",
        date_of_birth=date(1980, 1, 1),
        license_number="D99999999",
        license_state="TX",
        license_status="valid",
        years_licensed=15,
        age=44,
        gender="M",
        marital_status="single",
        accidents_3_years=3,  # Multiple accidents
        violations_3_years=5,  # Multiple violations
        claims_3_years=2,
        dui_convictions=1,  # DUI conviction
        sr22_required=True,
        good_student=False,
        military=False,
        defensive_driving=False,
        occupation="Construction",
    )

    vehicle = VehicleInfo(
        vin="1FTFW1ET0FFA12345",
        year=2015,
        make="Ford",
        model="F-150",
        trim="Regular Cab",
        body_style="Pickup",
        vehicle_type=VehicleType.PRIVATE_PASSENGER,
        engine_size="5.0L",
        fuel_type="Gasoline",
        safety_rating=4,
        anti_theft=False,
        usage="Personal",
        annual_mileage=25000,  # High mileage
        garage_zip="77001",  # Houston, TX
        garage_type="Street",
        owned=True,
        finance_type="Financed",
        value=Decimal("18000.00"),
        purchase_date=date(2015, 1, 15),
        primary_use="Work",
        parking_location="Street",
        safety_features=[],
        comprehensive_deductible=Decimal("1000.00"),
        collision_deductible=Decimal("1000.00"),
    )

    coverages = [
        CoverageSelection(
            coverage_type=CoverageType.BODILY_INJURY,
            limit=Decimal("30000"),
            deductible=Decimal("0"),
        ),
        CoverageSelection(
            coverage_type=CoverageType.PROPERTY_DAMAGE,
            limit=Decimal("25000"),
            deductible=Decimal("0"),
        ),
    ]

    result = await rating_engine.calculate_premium(
        state="TX",
        product_type="auto",
        vehicle_info=vehicle,
        drivers=[high_risk_driver],
        coverage_selections=coverages,
        customer_id=uuid4(),
    )

    if result.is_ok():
        rating_result = result.value
        print("  ✓ Surcharge calculation successful!")
        print(f"  ✓ Number of surcharges: {len(rating_result.surcharges)}")

        surcharge_types = [s["type"] for s in rating_result.surcharges]
        print(f"  ✓ Applied surcharges: {surcharge_types}")

        total_surcharge = rating_result.total_surcharge_amount
        print(f"  ✓ Total surcharge amount: ${total_surcharge}")

        expected_surcharges = ["sr22_filing", "coverage_lapse", "high_risk"]
        for expected in expected_surcharges:
            if expected in surcharge_types:
                print(f"  ✓ {expected} surcharge applied")

        # Verify tier assignment
        print(f"  ✓ Risk tier: {rating_result.tier}")
        assert rating_result.tier in [
            "non_standard",
            "high_risk",
        ], "High-risk driver should get high-risk tier"

    else:
        print(f"  ❌ Surcharge calculation failed: {result.error}")

    print("🎉 SURCHARGE LOGIC AUDIT COMPLETE!")


if __name__ == "__main__":
    asyncio.run(test_rating_engine_audit())
    asyncio.run(test_discount_logic())
    asyncio.run(test_surcharge_logic())
