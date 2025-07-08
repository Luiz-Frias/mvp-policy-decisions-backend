#!/usr/bin/env python3
"""Comprehensive audit of quote and admin models for frozen=True compliance and validation."""

import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from src.pd_prime_demo.models.admin import (
    AdminActivityLog,
    AdminDashboard,
    AdminRoleModel,
    AdminUser,
    AdminUserCreate,
    AdminUserUpdate,
    Permission,
    SystemSetting,
)

# Import all models to audit
from src.pd_prime_demo.models.quote import (
    CoverageSelection,
    Discount,
    DriverInfo,
    Quote,
    QuoteBase,
    QuoteComparison,
    QuoteConversionRequest,
    QuoteCreate,
    QuoteOverrideRequest,
    QuoteStatus,
    QuoteUpdate,
    VehicleInfo,
)


def audit_frozen_compliance():
    """Audit all models for frozen=True compliance."""
    print("🔍 AUDITING FROZEN=True COMPLIANCE")
    print("=" * 50)

    models_to_check = [
        VehicleInfo,
        DriverInfo,
        CoverageSelection,
        Discount,
        QuoteBase,
        Quote,
        QuoteCreate,
        QuoteUpdate,
        QuoteComparison,
        QuoteConversionRequest,
        QuoteOverrideRequest,
        AdminRoleModel,
        AdminUser,
        AdminUserCreate,
        AdminUserUpdate,
        SystemSetting,
        AdminActivityLog,
        AdminDashboard,
    ]

    frozen_compliant = []
    non_compliant = []

    for model in models_to_check:
        try:
            config = model.model_config
            if isinstance(config, dict) and config.get("frozen") is True:
                frozen_compliant.append(model.__name__)
            else:
                non_compliant.append(model.__name__)
        except Exception as e:
            non_compliant.append(f"{model.__name__} (error: {e})")

    print(f"✅ FROZEN=True COMPLIANT: {len(frozen_compliant)} models")
    for model in frozen_compliant:
        print(f"   ✅ {model}")

    if non_compliant:
        print(f"\n❌ NON-COMPLIANT: {len(non_compliant)} models")
        for model in non_compliant:
            print(f"   ❌ {model}")
        return False

    return True


def audit_validation_coverage():
    """Audit field validation coverage."""
    print("\n🔍 AUDITING FIELD VALIDATION COVERAGE")
    print("=" * 50)

    validation_tests = []

    # Test VehicleInfo validation
    try:
        # Test invalid VIN (should fail)
        VehicleInfo(
            vin="INVALID_VIN_TOO_SHORT",
            year=2023,
            make="Toyota",
            model="Camry",
            primary_use="commute",
            annual_mileage=15000,
            garage_zip="90210",
        )
        validation_tests.append(
            "❌ VehicleInfo: VIN validation failed (accepted invalid VIN)"
        )
    except Exception:
        validation_tests.append("✅ VehicleInfo: VIN validation working")

    # Test VehicleInfo with valid data
    try:
        _ = VehicleInfo(
            vin="1HGCM82633A004352",  # Valid VIN
            year=2023,
            make="Toyota",
            model="Camry",
            primary_use="commute",
            annual_mileage=15000,
            garage_zip="90210",
        )
        validation_tests.append("✅ VehicleInfo: Valid data accepted")
    except Exception as e:
        validation_tests.append(f"❌ VehicleInfo: Valid data rejected: {e}")

    # Test DriverInfo validation
    try:
        _ = DriverInfo(
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
            gender="M",
            marital_status="single",
            license_number="D123456789",
            license_state="CA",
            first_licensed_date=date(2008, 1, 1),
        )
        validation_tests.append("✅ DriverInfo: Valid data accepted")
    except Exception as e:
        validation_tests.append(f"❌ DriverInfo: Valid data rejected: {e}")

    # Test invalid driver age
    try:
        DriverInfo(
            first_name="Child",
            last_name="Young",
            date_of_birth=date(2020, 1, 1),  # Too young
            gender="M",
            marital_status="single",
            license_number="D123456789",
            license_state="CA",
            first_licensed_date=date(2008, 1, 1),
        )
        validation_tests.append(
            "❌ DriverInfo: Age validation failed (accepted underage driver)"
        )
    except Exception:
        validation_tests.append("✅ DriverInfo: Age validation working")

    # Test CoverageSelection validation
    try:
        _ = CoverageSelection(
            coverage_type="liability",
            limit=Decimal("50000.00"),
            deductible=Decimal("500.00"),
        )
        validation_tests.append("✅ CoverageSelection: Valid data accepted")
    except Exception as e:
        validation_tests.append(f"❌ CoverageSelection: Valid data rejected: {e}")

    # Test AdminUser password validation
    try:
        AdminUserCreate(
            email="admin@example.com",
            password="weak",  # Should fail
            role_id=uuid4(),
            full_name="Admin User",
        )
        validation_tests.append(
            "❌ AdminUserCreate: Password validation failed (accepted weak password)"
        )
    except Exception:
        validation_tests.append("✅ AdminUserCreate: Password validation working")

    for test in validation_tests:
        print(f"   {test}")

    return all("✅" in test for test in validation_tests)


def audit_computed_fields():
    """Audit computed fields functionality."""
    print("\n🔍 AUDITING COMPUTED FIELDS")
    print("=" * 50)

    try:
        # Create a valid driver first
        driver = DriverInfo(
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
            gender="M",
            marital_status="single",
            license_number="D123456789",
            license_state="CA",
            first_licensed_date=date(2008, 1, 1),
        )

        # Create a valid vehicle
        vehicle = VehicleInfo(
            vin="1HGCM82633A004352",
            year=2023,
            make="Toyota",
            model="Camry",
            primary_use="commute",
            annual_mileage=15000,
            garage_zip="90210",
        )

        # Test Quote computed fields
        quote = Quote(
            customer_id=uuid4(),
            quote_number="QUOT-2024-000001",
            product_type="auto",
            state="CA",
            zip_code="90210",
            effective_date=date.today(),
            email="test@example.com",
            expires_at=datetime.now() + timedelta(days=30),
            drivers=[driver],
            vehicle_info=vehicle,
            total_discount_amount=Decimal("-100.00"),
            status=QuoteStatus.QUOTED,
            total_premium=Decimal("1200.00"),
            id=uuid4(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        print(f"   ✅ Quote.is_expired: {quote.is_expired}")
        print(f"   ✅ Quote.days_until_expiration: {quote.days_until_expiration}")
        print(f"   ✅ Quote.total_savings: {quote.total_savings}")
        print(f"   ✅ Quote.is_convertible: {quote.is_convertible}")

        # Test DriverInfo computed fields
        print(f"   ✅ DriverInfo.age: {driver.age}")
        print(f"   ✅ DriverInfo.years_licensed: {driver.years_licensed}")

        return True

    except Exception as e:
        print(f"   ❌ Computed fields test failed: {e}")
        return False


def audit_immutability():
    """Audit that frozen=True actually prevents mutation."""
    print("\n🔍 AUDITING IMMUTABILITY (FROZEN=True ENFORCEMENT)")
    print("=" * 50)

    immutability_tests = []

    # Test VehicleInfo immutability
    try:
        vehicle = VehicleInfo(
            vin="1HGCM82633A004352",
            year=2023,
            make="Toyota",
            model="Camry",
            primary_use="commute",
            annual_mileage=15000,
            garage_zip="90210",
        )

        try:
            vehicle.make = "Honda"  # Should fail
            immutability_tests.append(
                "❌ VehicleInfo: Immutability failed (field was modified)"
            )
        except Exception:
            immutability_tests.append("✅ VehicleInfo: Immutability enforced")

    except Exception as e:
        immutability_tests.append(
            f"❌ VehicleInfo: Could not create for immutability test: {e}"
        )

    # Test AdminUser immutability
    try:
        admin_role = AdminRoleModel(
            name="test_role",
            permissions=[Permission.USER_READ],
            id=uuid4(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        try:
            admin_role.name = "modified_role"  # Should fail
            immutability_tests.append(
                "❌ AdminRoleModel: Immutability failed (field was modified)"
            )
        except Exception:
            immutability_tests.append("✅ AdminRoleModel: Immutability enforced")

    except Exception as e:
        immutability_tests.append(
            f"❌ AdminRoleModel: Could not create for immutability test: {e}"
        )

    for test in immutability_tests:
        print(f"   {test}")

    return all("✅" in test for test in immutability_tests)


def audit_multi_step_wizard_support():
    """Audit that models support multi-step wizard workflow."""
    print("\n🔍 AUDITING MULTI-STEP WIZARD SUPPORT")
    print("=" * 50)

    wizard_tests = []

    # Test that QuoteCreate allows optional fields for wizard workflow
    try:
        # Should be able to create a quote with minimal data
        _ = QuoteCreate(
            customer_id=uuid4(),
            product_type="auto",
            state="CA",
            zip_code="90210",
            effective_date=date.today(),
            email="test@example.com",
        )
        wizard_tests.append("✅ QuoteCreate: Supports minimal data for wizard start")
    except Exception as e:
        wizard_tests.append(f"❌ QuoteCreate: Cannot create with minimal data: {e}")

    # Test that QuoteUpdate allows partial updates
    try:
        _ = QuoteUpdate(email="updated@example.com")  # Only updating email
        wizard_tests.append("✅ QuoteUpdate: Supports partial updates")
    except Exception as e:
        wizard_tests.append(f"❌ QuoteUpdate: Cannot create partial update: {e}")

    for test in wizard_tests:
        print(f"   {test}")

    return all("✅" in test for test in wizard_tests)


def main():
    """Run comprehensive audit of quote and admin models."""
    print("🚀 STARTING COMPREHENSIVE MODEL AUDIT")
    print("=" * 60)

    # Run all audits
    frozen_ok = audit_frozen_compliance()
    validation_ok = audit_validation_coverage()
    computed_ok = audit_computed_fields()
    immutable_ok = audit_immutability()
    wizard_ok = audit_multi_step_wizard_support()

    # Final summary
    print("\n📋 AUDIT SUMMARY")
    print("=" * 60)

    all_passed = all([frozen_ok, validation_ok, computed_ok, immutable_ok, wizard_ok])

    if all_passed:
        print("🎉 ALL AUDITS PASSED! Models are compliant with master ruleset.")
        return 0
    else:
        print("⚠️  SOME AUDITS FAILED! Please review and fix issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
