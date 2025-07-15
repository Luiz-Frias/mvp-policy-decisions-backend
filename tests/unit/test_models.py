"""Unit tests for Pydantic models with MASTER RULESET compliance.

Tests verify:
- Model immutability (frozen=True)
- Strict validation (extra="forbid")
- Type safety and beartype decorators
- Field constraints and validators
- Edge cases and error handling
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from beartype import beartype
from pydantic import ValidationError

from policy_core.core.result_types import Err, Ok, Result
from policy_core.models.base import (
    BaseModelConfig,
    IdentifiableModel,
    TimestampedModel,
)
from tests.fixtures.test_data import (
    VALID_POLICY_DATA,
    DecisionFactorModel,
    PolicyDecisionModel,
    PolicyTestModel,
    TestDataFactory,
)


class TestBaseModelConfig:
    """Test base model configuration and MASTER RULESET compliance."""

    def test_model_is_frozen(self) -> None:
        """Test that models are immutable (frozen=True)."""

        @beartype
        class TestModel(BaseModelConfig):
            value: str

        instance = TestModel(value="test")

        # Verify model is frozen
        with pytest.raises(ValidationError) as exc_info:
            instance.value = "new_value"

        assert "frozen" in str(exc_info.value).lower()

    def test_no_extra_fields_allowed(self) -> None:
        """Test that extra fields are forbidden (extra="forbid")."""

        @beartype
        class TestModel(BaseModelConfig):
            allowed_field: str

        # Try to create with extra field
        with pytest.raises(ValidationError) as exc_info:
            TestModel(allowed_field="value", extra_field="not_allowed")  # type: ignore

        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_whitespace_stripping(self) -> None:
        """Test automatic whitespace stripping."""

        @beartype
        class TestModel(BaseModelConfig):
            text: str

        instance = TestModel(text="  test value  ")
        assert instance.text == "test value"

    def test_validate_assignment_enabled(self) -> None:
        """Test that validate_assignment is properly configured."""
        config = BaseModelConfig.model_config
        assert config.get("validate_assignment") is True

    def test_datetime_json_encoding(self) -> None:
        """Test datetime fields are properly encoded to ISO format."""

        @beartype
        class TestModel(BaseModelConfig):
            timestamp: datetime

        now = datetime.now(timezone.utc)
        instance = TestModel(timestamp=now)

        json_data = instance.model_dump_json()
        # Check that either format is acceptable (Z or +00:00)
        assert (
            now.isoformat() in json_data
            or now.isoformat().replace("+00:00", "Z") in json_data
        )


class TestTimestampedModel:
    """Test TimestampedModel functionality."""

    def test_timestamp_fields_required(self) -> None:
        """Test that timestamp fields are required."""

        @beartype
        class TestModel(TimestampedModel):
            name: str

        # Missing timestamps should fail
        with pytest.raises(ValidationError) as exc_info:
            TestModel(name="test")  # type: ignore[call-arg]

        error_str = str(exc_info.value)
        assert "created_at" in error_str
        assert "updated_at" in error_str

    def test_valid_timestamp_creation(self) -> None:
        """Test creating model with valid timestamps."""

        @beartype
        class TestModel(TimestampedModel):
            name: str

        now = datetime.now(timezone.utc)
        instance = TestModel(name="test", created_at=now, updated_at=now)

        assert instance.created_at == now
        assert instance.updated_at == now
        assert instance.name == "test"


class TestIdentifiableModel:
    """Test IdentifiableModel with UUID and timestamps."""

    def test_uuid_field_required(self) -> None:
        """Test that UUID field is required."""

        @beartype
        class TestModel(IdentifiableModel):
            name: str

        now = datetime.now(timezone.utc)

        # Missing ID should fail
        with pytest.raises(ValidationError) as exc_info:
            TestModel(name="test", created_at=now, updated_at=now)  # type: ignore[call-arg]

        assert "id" in str(exc_info.value)

    def test_valid_identifiable_creation(self) -> None:
        """Test creating model with all required fields."""

        @beartype
        class TestModel(IdentifiableModel):
            name: str

        test_id = uuid4()
        now = datetime.now(timezone.utc)

        instance = TestModel(id=test_id, name="test", created_at=now, updated_at=now)

        assert instance.id == test_id
        assert instance.name == "test"
        assert instance.created_at == now
        assert instance.updated_at == now


class TestPolicyModel:
    """Test PolicyTestModel validation and behavior."""

    def test_valid_policy_creation(self) -> None:
        """Test creating a valid policy."""
        policy = TestDataFactory.create_policy()

        assert policy.policy_id.startswith("POL-")
        assert policy.premium > 0
        assert policy.coverage_amount > 0
        assert policy.is_active

    def test_policy_validation_errors(self) -> None:
        """Test policy validation with invalid data."""
        invalid_data_sets = TestDataFactory.create_invalid_policy_data()

        for i, invalid_data in enumerate(invalid_data_sets):
            try:
                now = datetime.now(timezone.utc)
                PolicyTestModel(
                    id=uuid4(), created_at=now, updated_at=now, **invalid_data
                )
                # If we get here, the validation didn't fail
                pytest.fail(f"Expected ValidationError for dataset {i}: {invalid_data}")
            except ValidationError:
                # This is expected
                pass

    def test_policy_decimal_precision(self) -> None:
        """Test decimal field precision validation."""
        # Test that more than 2 decimal places raises validation error
        with pytest.raises(ValidationError) as exc_info:
            TestDataFactory.create_policy(
                premium=Decimal("1234.567"),  # More than 2 decimal places
                coverage_amount=Decimal("99999.999"),
            )

        errors = exc_info.value.errors()
        assert any(e["type"] == "decimal_max_places" for e in errors)

        # Test that exactly 2 decimal places works
        policy = TestDataFactory.create_policy(
            premium=Decimal("1234.56"),
            coverage_amount=Decimal("99999.99"),
        )
        assert policy.premium == Decimal("1234.56")
        assert policy.coverage_amount == Decimal("99999.99")

    def test_policy_status_validation(self) -> None:
        """Test policy status field validation."""
        valid_statuses = ["active", "inactive", "pending", "cancelled"]

        for status in valid_statuses:
            policy = TestDataFactory.create_policy(status=status)
            assert policy.status == status

        # Test invalid status
        with pytest.raises(ValidationError) as exc_info:
            TestDataFactory.create_policy(status="invalid_status")

        assert "String should match pattern" in str(exc_info.value)

    def test_policy_is_active_property(self) -> None:
        """Test is_active property logic."""
        now = datetime.now(timezone.utc)

        # Active policy
        active_policy = TestDataFactory.create_policy(
            status="active",
            start_date=now - timedelta(days=1),
            end_date=now + timedelta(days=1),
        )
        assert active_policy.is_active

        # Inactive status
        inactive_policy = TestDataFactory.create_policy(status="inactive")
        assert not inactive_policy.is_active

        # Expired policy
        expired_policy = TestDataFactory.create_policy(
            status="active",
            start_date=now - timedelta(days=10),
            end_date=now - timedelta(days=1),
        )
        assert not expired_policy.is_active


class TestDecisionModel:
    """Test PolicyDecisionModel validation and behavior."""

    def test_valid_decision_creation(self) -> None:
        """Test creating a valid decision."""
        decision = TestDataFactory.create_decision()

        assert decision.decision_type == "approval"
        assert 0 <= decision.confidence_score <= 1
        assert len(decision.factors) > 0
        assert decision.is_approved

    def test_decision_type_validation(self) -> None:
        """Test decision type field validation."""
        valid_types = ["approval", "rejection", "review"]

        for decision_type in valid_types:
            decision = TestDataFactory.create_decision(decision_type=decision_type)
            assert decision.decision_type == decision_type

        # Test invalid type
        with pytest.raises(ValidationError):
            TestDataFactory.create_decision(decision_type="invalid_type")

    def test_confidence_score_bounds(self) -> None:
        """Test confidence score must be between 0 and 1."""
        # Valid scores
        for score in [0.0, 0.5, 1.0]:
            decision = TestDataFactory.create_decision(confidence_score=score)
            assert decision.confidence_score == score

        # Invalid scores
        for score in [-0.1, 1.1, 2.0]:
            with pytest.raises(ValidationError):
                TestDataFactory.create_decision(confidence_score=score)

    def test_decision_factors_validation(self) -> None:
        """Test decision factors validation."""
        # Empty factors list should fail
        with pytest.raises(ValidationError):
            TestDataFactory.create_decision(factors=[])

        # Invalid factor values
        with pytest.raises(ValidationError):
            TestDataFactory.create_decision(
                factors=[
                    DecisionFactorModel(
                        name="test", value=1.5, weight=0.5, description=None
                    )  # Invalid value > 1.0
                ]
            )

    def test_is_approved_property(self) -> None:
        """Test is_approved property logic."""
        approval = TestDataFactory.create_decision(decision_type="approval")
        assert approval.is_approved

        rejection = TestDataFactory.create_decision(decision_type="rejection")
        assert not rejection.is_approved

        review = TestDataFactory.create_decision(decision_type="review")
        assert not review.is_approved


class TestModelImmutability:
    """Test that all models enforce immutability."""

    def test_policy_immutability(self) -> None:
        """Test that policy models cannot be modified."""
        policy = TestDataFactory.create_policy()

        with pytest.raises((AttributeError, ValidationError)):
            policy.premium = Decimal("2000.00")

        with pytest.raises((AttributeError, ValidationError)):
            policy.status = "cancelled"

    def test_decision_immutability(self) -> None:
        """Test that decision models cannot be modified."""
        decision = TestDataFactory.create_decision()

        with pytest.raises((AttributeError, ValidationError)):
            decision.confidence_score = 0.5

        with pytest.raises((AttributeError, ValidationError)):
            decision.factors = []


class TestModelSerialization:
    """Test model serialization and deserialization."""

    def test_policy_json_serialization(self) -> None:
        """Test policy model JSON serialization."""
        policy = TestDataFactory.create_policy()

        # Serialize to JSON
        json_str = policy.model_dump_json()
        assert isinstance(json_str, str)

        # Deserialize back
        policy_dict = policy.model_dump()
        reconstructed = PolicyTestModel(**policy_dict)

        assert reconstructed.policy_id == policy.policy_id
        assert reconstructed.premium == policy.premium

    def test_decision_json_serialization(self) -> None:
        """Test decision model JSON serialization."""
        decision = TestDataFactory.create_decision()

        # Serialize to dict
        decision_dict = decision.model_dump()

        # Verify nested factors are properly serialized
        assert "factors" in decision_dict
        assert len(decision_dict["factors"]) == len(decision.factors)

        # Reconstruct
        reconstructed = PolicyDecisionModel(**decision_dict)
        assert reconstructed.confidence_score == decision.confidence_score


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_maximum_field_lengths(self) -> None:
        """Test maximum allowed field lengths."""
        # Max length policy ID (50 chars)
        long_policy_id = "P" * 50
        policy = TestDataFactory.create_policy(policy_id=long_policy_id)
        assert len(policy.policy_id) == 50

        # Too long should fail
        with pytest.raises(ValidationError):
            TestDataFactory.create_policy(policy_id="P" * 51)

    def test_unicode_handling(self) -> None:
        """Test Unicode character handling in string fields."""
        unicode_name = "测试用户 🚀 Tëst Üsër"
        policy = TestDataFactory.create_policy(policy_holder=unicode_name)
        assert policy.policy_holder == unicode_name

    def test_decimal_edge_cases(self) -> None:
        """Test decimal field edge cases."""
        # Very large values
        large_amount = Decimal("999999999999.99")
        policy = TestDataFactory.create_policy(coverage_amount=large_amount)
        assert policy.coverage_amount == large_amount

        # Very small but valid values
        small_premium = Decimal("0.01")
        policy = TestDataFactory.create_policy(premium=small_premium)
        assert policy.premium == small_premium

        # Zero should be valid
        zero_premium = Decimal("0.00")
        policy = TestDataFactory.create_policy(premium=zero_premium)
        assert policy.premium == zero_premium


class TestResultType:
    """Test Result type for error handling."""

    def test_result_ok_creation(self) -> None:
        """Test creating successful Result."""
        result: Result[str, str] = Ok("success")

        assert result.is_ok()
        assert not result.is_err()
        assert result.unwrap() == "success"

    def test_result_err_creation(self) -> None:
        """Test creating error Result."""
        result: Result[str, str] = Err("error message")

        assert result.is_err()
        assert not result.is_ok()
        assert result.unwrap_err() == "error message"

    def test_result_unwrap_panic(self) -> None:
        """Test unwrap on error Result raises exception."""
        result: Result[str, str] = Err("error")

        with pytest.raises(ValueError) as exc_info:
            result.unwrap()

        assert "Called unwrap on Err value" in str(exc_info.value)

    def test_result_with_models(self) -> None:
        """Test Result type with Pydantic models."""

        def create_policy_safe(data: dict[str, Any]) -> Result[PolicyTestModel, str]:
            """Create policy with Result type error handling."""
            try:
                now = datetime.now(timezone.utc)
                policy = PolicyTestModel(
                    id=uuid4(), created_at=now, updated_at=now, **data
                )
                return Ok(policy)
            except ValidationError as e:
                return Err(str(e))

        # Test successful creation
        result = create_policy_safe(VALID_POLICY_DATA)
        assert result.is_ok()
        policy = result.unwrap()
        assert isinstance(policy, PolicyTestModel)

        # Test failed creation
        result = create_policy_safe({"invalid": "data"})
        assert result.is_err()
        error = result.unwrap_err()
        assert "validation error" in error.lower()


# Benchmark tests would go here but are omitted for brevity
# They would test performance requirements like:
# - Model creation < 1ms
# - Serialization < 1ms
# - No memory leaks in repeated operations
