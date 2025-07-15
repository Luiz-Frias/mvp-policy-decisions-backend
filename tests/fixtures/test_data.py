"""Test data fixtures and factories for comprehensive testing.

This module provides test data factories and fixtures following MASTER RULESET principles.
All data models use Pydantic with frozen=True for immutability and strict validation.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from beartype import beartype
from pydantic import Field, model_validator

from policy_core.models.base import BaseModelConfig, IdentifiableModel
from policy_core.models.quote import (
    CoverageSelection,
    CoverageType,
    DriverInfo,
    VehicleInfo,
    VehicleType,
)


@beartype
class PolicyTestModel(IdentifiableModel):
    """Test model for policy entities."""

    policy_id: str = Field(..., min_length=1, max_length=50)
    policy_holder: str = Field(..., min_length=1, max_length=200)
    premium: Decimal = Field(..., ge=0, decimal_places=2)
    coverage_amount: Decimal = Field(..., ge=0, decimal_places=2)
    start_date: datetime
    end_date: datetime
    status: str = Field(..., pattern="^(active|inactive|pending|cancelled)$")

    @model_validator(mode="after")
    def validate_dates(self) -> "PolicyTestModel":
        """Ensure end date is after start date."""
        if self.end_date <= self.start_date:
            raise ValueError("End date must be after start date")
        return self

    @property
    def is_active(self) -> bool:
        """Check if policy is currently active."""
        now = datetime.now(timezone.utc)
        return self.status == "active" and self.start_date <= now <= self.end_date


@beartype
class DecisionFactorModel(BaseModelConfig):
    """Model for decision factors."""

    name: str = Field(..., min_length=1, max_length=100)
    value: float = Field(..., ge=0, le=1)
    weight: float = Field(..., ge=0, le=1)
    description: str | None = Field(None, max_length=500)


@beartype
class PolicyDecisionModel(IdentifiableModel):
    """Test model for policy decision entities."""

    policy_id: str = Field(..., min_length=1, max_length=50)
    decision_type: str = Field(..., pattern="^(approval|rejection|review)$")
    confidence_score: float = Field(..., ge=0, le=1)
    factors: list[DecisionFactorModel] = Field(..., min_length=1)
    reason: str | None = Field(None, max_length=1000)

    @property
    def is_approved(self) -> bool:
        """Check if decision is approved."""
        return self.decision_type == "approval"


@beartype
class TestDataFactory:
    """Factory for generating test data with realistic values."""

    @staticmethod
    def create_policy(
        **kwargs: Any,
    ) -> PolicyTestModel:  # SYSTEM_BOUNDARY: Test fixtures
        """Create a test policy with default values."""
        now = datetime.now(timezone.utc)
        defaults: dict[str, Any] = {
            "id": uuid4(),
            "policy_id": f"POL-{now.year}-{uuid4().hex[:6].upper()}",
            "policy_holder": "Test Policy Holder",
            "premium": Decimal("1500.00"),
            "coverage_amount": Decimal("100000.00"),
            "start_date": now,
            "end_date": now + timedelta(days=365),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        defaults.update(kwargs)
        # Type-safe construction using model_validate instead of **kwargs
        return PolicyTestModel.model_validate(defaults)

    @staticmethod
    def create_decision(**kwargs: Any) -> PolicyDecisionModel:
        """Create a test policy decision with default values."""
        now = datetime.now(timezone.utc)
        defaults: dict[str, Any] = {
            "id": uuid4(),
            "policy_id": f"POL-{now.year}-{uuid4().hex[:6].upper()}",
            "decision_type": "approval",
            "confidence_score": 0.95,
            "factors": [
                DecisionFactorModel(
                    name="risk_score",
                    value=0.3,
                    weight=0.4,
                    description="Overall risk assessment",
                ),
                DecisionFactorModel(
                    name="credit_score",
                    value=0.85,
                    weight=0.3,
                    description="Credit worthiness",
                ),
                DecisionFactorModel(
                    name="claims_history",
                    value=0.9,
                    weight=0.3,
                    description="Previous claims record",
                ),
            ],
            "reason": "All criteria met for automatic approval",
            "created_at": now,
            "updated_at": now,
        }
        defaults.update(kwargs)
        # Type-safe construction using model_validate instead of **kwargs
        return PolicyDecisionModel.model_validate(defaults)

    @staticmethod
    def create_batch_policies(count: int = 10, **kwargs: Any) -> list[PolicyTestModel]:
        """Create multiple test policies."""
        return [
            TestDataFactory.create_policy(
                policy_id=f"POL-2024-{i:06d}",
                policy_holder=f"Test Holder {i}",
                **kwargs,
            )
            for i in range(count)
        ]

    @staticmethod
    def create_invalid_policy_data() -> list[dict[str, Any]]:
        """Create invalid policy data for validation testing."""
        return [
            # Missing required fields
            {"policy_holder": "John Doe"},
            # Invalid premium (negative)
            {
                "policy_id": "POL-001",
                "policy_holder": "John Doe",
                "premium": "-100.00",
                "coverage_amount": "50000.00",
                "start_date": datetime.now(timezone.utc).isoformat(),
                "end_date": (
                    datetime.now(timezone.utc) + timedelta(days=365)
                ).isoformat(),
                "status": "active",
            },
            # Invalid status
            {
                "policy_id": "POL-002",
                "policy_holder": "Jane Doe",
                "premium": "1000.00",
                "coverage_amount": "50000.00",
                "start_date": datetime.now(timezone.utc).isoformat(),
                "end_date": (
                    datetime.now(timezone.utc) + timedelta(days=365)
                ).isoformat(),
                "status": "invalid_status",
            },
            # End date before start date
            {
                "policy_id": "POL-003",
                "policy_holder": "Bob Smith",
                "premium": "1000.00",
                "coverage_amount": "50000.00",
                "start_date": datetime.now(timezone.utc).isoformat(),
                "end_date": (
                    datetime.now(timezone.utc) - timedelta(days=1)
                ).isoformat(),
                "status": "active",
            },
        ]

    @staticmethod
    def create_edge_case_data() -> dict[str, Any]:
        """Create edge case test data."""
        return {
            "max_decimal": Decimal("999999999999.99"),
            "min_decimal": Decimal("0.01"),
            "empty_string": "",
            "long_string": "x" * 1000,
            "max_confidence": 1.0,
            "min_confidence": 0.0,
            "unicode_string": "测试数据 🚀 Tëst Dätä",
            "special_chars": "!@#$%^&*()_+-=[]{}|;':\",./<>?",
            "sql_injection": "'; DROP TABLE policies; --",
            "xss_attempt": "<script>alert('xss')</script>",
        }


@beartype
class PerformanceTestData:
    """Test data for performance and benchmark testing."""

    @staticmethod
    def create_large_dataset(size: int = 1000) -> list[dict[str, Any]]:
        """Create large dataset for performance testing."""
        return [
            {
                "id": str(uuid4()),
                "data": f"test_data_{i}" * 100,  # Simulate larger payload
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "value": float(i),
            }
            for i in range(size)
        ]

    @staticmethod
    def create_nested_structure(depth: int = 5) -> dict[str, Any]:
        """Create deeply nested data structure for parsing tests."""

        def create_level(current_depth: int) -> dict[str, Any]:
            if current_depth <= 0:
                return {"value": f"leaf_{uuid4().hex[:6]}"}

            return {
                "level": current_depth,
                "data": {
                    f"child_{i}": create_level(current_depth - 1) for i in range(3)
                },
                "metadata": {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "id": str(uuid4()),
                },
            }

        return create_level(depth)


# Export commonly used test data
VALID_POLICY_DATA = {
    "policy_id": "POL-2024-TEST01",
    "policy_holder": "Test User",
    "premium": "2500.00",
    "coverage_amount": "150000.00",
    "start_date": datetime.now(timezone.utc).isoformat(),
    "end_date": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
    "status": "active",
}

VALID_DECISION_DATA = {
    "policy_id": "POL-2024-TEST01",
    "decision_type": "approval",
    "confidence_score": 0.89,
    "factors": [
        {"name": "risk_assessment", "value": 0.25, "weight": 0.5},
        {"name": "financial_stability", "value": 0.90, "weight": 0.5},
    ],
    "reason": "Meets all approval criteria",
}

# Test user data for authentication tests
TEST_USER_DATA = {
    "username": "testuser",
    "email": "testuser@example.com",
    "password": "SecureTestPassword123!",
    "is_active": True,
    "is_superuser": False,
}

# API response templates
SUCCESS_RESPONSE_TEMPLATE = {
    "status": "success",
    "data": None,
    "message": None,
    "timestamp": None,
}

ERROR_RESPONSE_TEMPLATE = {
    "status": "error",
    "error": {
        "code": None,
        "message": None,
        "details": None,
    },
    "timestamp": None,
}


# Rating engine test data helpers
@beartype
def create_test_driver(**kwargs: Any) -> DriverInfo:
    """Create a test driver with default values."""
    defaults = {
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": date(1985, 5, 15),
        "license_number": "D12345678",
        "license_state": "CA",
        "license_status": "valid",
        "first_licensed_date": date(2005, 5, 15),
        "gender": "M",
        "marital_status": "married",
        "accidents_3_years": 0,
        "violations_3_years": 0,
        "claims_3_years": 0,
        "sr22_required": False,
        "good_student": False,
        "military": False,
        "senior": False,
        "defensive_driving": False,
    }
    defaults.update(kwargs)
    return DriverInfo(**defaults)


@beartype
def create_test_vehicle(**kwargs: Any) -> VehicleInfo:
    """Create a test vehicle with default values."""
    defaults = {
        "vin": "1HGCM82633A004352",
        "year": 2020,
        "make": "Toyota",
        "model": "Camry",
        "trim": "LE",
        "body_style": "Sedan",
        "vehicle_type": VehicleType.PRIVATE_PASSENGER,
        "engine_size": "2.5L",
        "fuel_type": "Gasoline",
        "safety_rating": 5,
        "anti_theft": True,
        "usage": "Personal",
        "annual_mileage": 12000,
        "garage_type": "Attached Garage",
        "owned": True,
        "finance_type": "Owned",
        "value": Decimal("25000.00"),
        "purchase_date": date(2020, 1, 15),
        "primary_use": "Work",
        "parking_location": "Garage",
        "anti_lock_brakes": True,
        "airbags": True,
        "daytime_running_lights": True,
        "passive_restraints": True,
        "automatic_seatbelts": False,
        "anti_theft_device": "Factory Alarm",
        "comprehensive_deductible": Decimal("500.00"),
        "collision_deductible": Decimal("500.00"),
    }
    defaults.update(kwargs)
    return VehicleInfo(**defaults)


@beartype
def create_test_coverage_selections(**kwargs: Any) -> list[CoverageSelection]:
    """Create test coverage selections with default values."""
    defaults = [
        CoverageSelection(
            coverage_type=CoverageType.BODILY_INJURY,
            limit=Decimal("100000.00"),
            deductible=Decimal("0.00"),
            selected=True,
        ),
        CoverageSelection(
            coverage_type=CoverageType.PROPERTY_DAMAGE,
            limit=Decimal("50000.00"),
            deductible=Decimal("0.00"),
            selected=True,
        ),
        CoverageSelection(
            coverage_type=CoverageType.COMPREHENSIVE,
            limit=Decimal("25000.00"),
            deductible=Decimal("500.00"),
            selected=True,
        ),
        CoverageSelection(
            coverage_type=CoverageType.COLLISION,
            limit=Decimal("25000.00"),
            deductible=Decimal("500.00"),
            selected=True,
        ),
    ]

    # Apply any overrides
    custom_coverages = kwargs.get("coverages", [])
    if custom_coverages:
        return custom_coverages

    return defaults
