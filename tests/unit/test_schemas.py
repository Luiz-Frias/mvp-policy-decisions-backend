"""Unit tests for Pydantic schemas."""

import pytest
from pydantic import ValidationError

from src.policy_core.schemas.health import ComponentStatus, HealthComponents


class TestComponentStatus:
    """Test ComponentStatus schema validation and behavior."""

    def test_valid_component_status_creation(self) -> None:
        """Test creating a valid ComponentStatus."""
        component = ComponentStatus(
            status="healthy",
            latency_ms=10.5,
            message="All systems operational",
        )

        assert component.status == "healthy"
        assert component.latency_ms == 10.5
        assert component.message == "All systems operational"

    def test_component_status_all_valid_statuses(self) -> None:
        """Test all valid status values."""
        valid_statuses = ["healthy", "unhealthy", "degraded"]

        for status in valid_statuses:
            component = ComponentStatus(
                status=status,
                latency_ms=5.0,
                message=f"Status: {status}",
            )
            assert component.status == status

    def test_component_status_default_message(self) -> None:
        """Test ComponentStatus with default empty message."""
        component = ComponentStatus(
            status="healthy",
            latency_ms=0.0,
        )

        assert component.message == ""

    def test_component_status_invalid_status_pattern(self) -> None:
        """Test ComponentStatus validation fails for invalid status."""
        with pytest.raises(ValidationError) as exc_info:
            ComponentStatus(
                status="invalid_status",
                latency_ms=10.0,
                message="Test message",
            )

        error = exc_info.value
        assert len(error.errors()) == 1
        assert error.errors()[0]["type"] == "string_pattern_mismatch"
        assert "status" in error.errors()[0]["loc"]

    def test_component_status_negative_latency(self) -> None:
        """Test ComponentStatus validation fails for negative latency."""
        with pytest.raises(ValidationError) as exc_info:
            ComponentStatus(
                status="healthy",
                latency_ms=-5.0,
                message="Test message",
            )

        error = exc_info.value
        assert len(error.errors()) == 1
        assert error.errors()[0]["type"] == "greater_than_equal"
        assert "latency_ms" in error.errors()[0]["loc"]

    def test_component_status_zero_latency(self) -> None:
        """Test ComponentStatus accepts zero latency."""
        component = ComponentStatus(
            status="healthy",
            latency_ms=0.0,
            message="Instant response",
        )

        assert component.latency_ms == 0.0

    def test_component_status_missing_required_fields(self) -> None:
        """Test ComponentStatus validation fails for missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            ComponentStatus()  # type: ignore[call-arg]

        error = exc_info.value
        assert len(error.errors()) == 2  # status and latency_ms are required
        field_names = {err["loc"][0] for err in error.errors()}
        assert field_names == {"status", "latency_ms"}

    def test_component_status_extra_fields_forbidden(self) -> None:
        """Test ComponentStatus rejects extra fields."""
        with pytest.raises(ValidationError) as exc_info:
            ComponentStatus(
                status="healthy",
                latency_ms=10.0,
                message="Test",
                extra_field="not_allowed",  # type: ignore[call-arg]
            )

        error = exc_info.value
        assert len(error.errors()) == 1
        assert error.errors()[0]["type"] == "extra_forbidden"

    def test_component_status_immutable(self) -> None:
        """Test ComponentStatus is immutable (frozen=True)."""
        component = ComponentStatus(
            status="healthy",
            latency_ms=10.0,
            message="Test",
        )

        with pytest.raises(ValidationError):
            component.status = "unhealthy"  # type: ignore[misc]


class TestHealthComponents:
    """Test HealthComponents schema validation and behavior."""

    def test_valid_health_components_creation(self) -> None:
        """Test creating a valid HealthComponents object."""
        database_status = ComponentStatus(
            status="healthy",
            latency_ms=5.2,
            message="Database operational",
        )
        redis_status = ComponentStatus(
            status="degraded",
            latency_ms=12.8,
            message="Redis experiencing high latency",
        )
        api_status = ComponentStatus(
            status="healthy",
            latency_ms=1.1,
            message="API responding normally",
        )

        health = HealthComponents(
            database=database_status,
            redis=redis_status,
            api=api_status,
        )

        assert health.database == database_status
        assert health.redis == redis_status
        assert health.api == api_status

    def test_health_components_missing_required_fields(self) -> None:
        """Test HealthComponents validation fails for missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            HealthComponents()  # type: ignore[call-arg]

        error = exc_info.value
        assert len(error.errors()) == 3  # database, redis, api are required
        field_names = {err["loc"][0] for err in error.errors()}
        assert field_names == {"database", "redis", "api"}

    def test_health_components_partial_data(self) -> None:
        """Test HealthComponents with only some components."""
        database_status = ComponentStatus(
            status="healthy",
            latency_ms=5.0,
            message="Database OK",
        )

        with pytest.raises(ValidationError) as exc_info:
            HealthComponents(database=database_status)  # type: ignore[call-arg]

        error = exc_info.value
        assert len(error.errors()) == 2  # redis and api missing
        field_names = {err["loc"][0] for err in error.errors()}
        assert field_names == {"redis", "api"}

    def test_health_components_invalid_nested_data(self) -> None:
        """Test HealthComponents validation fails for invalid nested ComponentStatus."""
        valid_component = ComponentStatus(
            status="healthy",
            latency_ms=5.0,
            message="OK",
        )

        with pytest.raises(ValidationError) as exc_info:
            HealthComponents(
                database=valid_component,
                redis=valid_component,
                api={"status": "invalid_status", "latency_ms": 1.0},  # type: ignore[arg-type]
            )

        error = exc_info.value
        # Should have validation error for the invalid api component
        assert any("api" in str(err["loc"]) for err in error.errors())

    def test_health_components_extra_fields_forbidden(self) -> None:
        """Test HealthComponents rejects extra fields."""
        component = ComponentStatus(
            status="healthy",
            latency_ms=1.0,
            message="OK",
        )

        with pytest.raises(ValidationError) as exc_info:
            HealthComponents(
                database=component,
                redis=component,
                api=component,
                extra_service=component,  # type: ignore[call-arg]
            )

        error = exc_info.value
        assert len(error.errors()) == 1
        assert error.errors()[0]["type"] == "extra_forbidden"

    def test_health_components_immutable(self) -> None:
        """Test HealthComponents is immutable (frozen=True)."""
        component = ComponentStatus(
            status="healthy",
            latency_ms=1.0,
            message="OK",
        )

        health = HealthComponents(
            database=component,
            redis=component,
            api=component,
        )

        with pytest.raises(ValidationError):
            health.database = component  # type: ignore[misc]

    def test_health_components_dict_serialization(self) -> None:
        """Test HealthComponents can be serialized to dict."""
        component = ComponentStatus(
            status="healthy",
            latency_ms=1.5,
            message="All good",
        )

        health = HealthComponents(
            database=component,
            redis=component,
            api=component,
        )

        health_dict = health.model_dump()

        assert isinstance(health_dict, dict)
        assert "database" in health_dict
        assert "redis" in health_dict
        assert "api" in health_dict

        # Verify nested structure
        assert health_dict["database"]["status"] == "healthy"
        assert health_dict["database"]["latency_ms"] == 1.5
        assert health_dict["database"]["message"] == "All good"

    def test_health_components_json_schema(self) -> None:
        """Test HealthComponents JSON schema generation."""
        schema = HealthComponents.model_json_schema()

        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "database" in schema["properties"]
        assert "redis" in schema["properties"]
        assert "api" in schema["properties"]

        # Verify all fields are required
        assert "required" in schema
        assert set(schema["required"]) == {"database", "redis", "api"}
