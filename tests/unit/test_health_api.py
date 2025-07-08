"""Unit tests for health API endpoints."""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from pydantic import ValidationError

from src.pd_prime_demo.api.v1.health import (
    ComponentHealthMap,
    HealthResponse,
    HealthStatus,
    detailed_health_check,
    health_check,
    liveness_check,
    readiness_check,
)
from src.pd_prime_demo.core.config import Settings


def create_mock_request() -> Request:
    """Create a mock Request object for testing."""
    mock_request = MagicMock(spec=Request)
    mock_request.method = "GET"
    mock_request.url = MagicMock()
    mock_request.url.path = "/health"
    mock_request.headers = {}
    mock_request.query_params = {}
    mock_request.client = MagicMock()
    mock_request.client.host = "127.0.0.1"
    mock_request.client.port = 8000
    return mock_request


class TestHealthStatus:
    """Test HealthStatus model validation."""

    def test_valid_health_status_creation(self) -> None:
        """Test creating valid HealthStatus."""
        status = HealthStatus(
            status="healthy",
            response_time_ms=10.5,
            message="All systems operational",
            details=None,
        )

        assert status.status == "healthy"
        assert status.response_time_ms == 10.5
        assert status.message == "All systems operational"
        assert status.details is None

    def test_health_status_required_fields(self) -> None:
        """Test HealthStatus with only required field."""
        status = HealthStatus(status="degraded")

        assert status.status == "degraded"
        assert status.response_time_ms is None
        assert status.message is None
        assert status.details is None

    def test_health_status_invalid_status(self) -> None:
        """Test HealthStatus validation fails for invalid status."""
        with pytest.raises(ValidationError) as exc_info:
            HealthStatus(status="invalid_status")

        error = exc_info.value
        assert "string_pattern_mismatch" in str(error)

    def test_health_status_negative_response_time(self) -> None:
        """Test HealthStatus validation fails for negative response time."""
        with pytest.raises(ValidationError) as exc_info:
            HealthStatus(status="healthy", response_time_ms=-1.0)

        error = exc_info.value
        assert "greater_than_equal" in str(error)


class TestComponentHealthMap:
    """Test ComponentHealthMap model validation."""

    def test_valid_component_health_map(self) -> None:
        """Test creating valid ComponentHealthMap."""
        api_status = HealthStatus(status="healthy", response_time_ms=1.0)
        db_status = HealthStatus(status="degraded", response_time_ms=50.0)

        health_map = ComponentHealthMap(
            api=api_status,
            database=db_status,
        )

        assert health_map.api == api_status
        assert health_map.database == db_status

    def test_component_health_map_validation_error(self) -> None:
        """Test ComponentHealthMap validates all values are HealthStatus."""
        with pytest.raises(ValueError) as exc_info:
            ComponentHealthMap(
                api=HealthStatus(status="healthy"),
                database="invalid_value",  # type: ignore[arg-type]
            )

        assert "must be a HealthStatus instance" in str(exc_info.value)


class TestHealthResponse:
    """Test HealthResponse model validation."""

    def test_valid_health_response(self) -> None:
        """Test creating valid HealthResponse."""
        timestamp = datetime.now(timezone.utc)
        components = ComponentHealthMap(
            api=HealthStatus(status="healthy", response_time_ms=1.0)
        )

        response = HealthResponse(
            status="healthy",
            timestamp=timestamp,
            version="1.0.0",
            environment="development",
            components=components,
            uptime_seconds=3600.0,
            total_response_time_ms=10.5,
        )

        assert response.status == "healthy"
        assert response.timestamp == timestamp
        assert response.version == "1.0.0"
        assert response.environment == "development"
        assert response.uptime_seconds == 3600.0
        assert response.total_response_time_ms == 10.5

    def test_health_response_negative_uptime(self) -> None:
        """Test HealthResponse validation fails for negative uptime."""
        components = ComponentHealthMap(api=HealthStatus(status="healthy"))

        with pytest.raises(ValidationError) as exc_info:
            HealthResponse(
                status="healthy",
                timestamp=datetime.now(timezone.utc),
                version="1.0.0",
                environment="development",
                components=components,
                uptime_seconds=-1.0,
                total_response_time_ms=10.0,
            )

        error = exc_info.value
        assert "greater_than_equal" in str(error)


class TestHealthCheckEndpoint:
    """Test basic health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        """Test successful health check."""
        settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="test-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="development",
        )

        response = await health_check(request=create_mock_request(), settings=settings)

        assert response.status == "healthy"
        assert response.environment == "development"
        assert response.version == "1.0.0"
        assert response.uptime_seconds >= 0
        assert response.total_response_time_ms >= 0
        assert isinstance(response.timestamp, datetime)

        # Check API component
        assert response.components.api.status == "healthy"
        assert response.components.api.message == "API operational"
        assert response.components.api.response_time_ms == 0.1

    @pytest.mark.asyncio
    async def test_health_check_production_environment(self) -> None:
        """Test health check in production environment."""
        settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="production-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="production-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="production",
        )

        response = await health_check(request=create_mock_request(), settings=settings)

        assert response.environment == "production"
        assert response.status == "healthy"


class TestLivenessCheckEndpoint:
    """Test liveness check endpoint."""

    @pytest.mark.asyncio
    async def test_liveness_check_success(self) -> None:
        """Test successful liveness check."""
        response = await liveness_check(request=create_mock_request())

        assert response.status == "healthy"
        assert response.message == "Application is running"
        assert response.response_time_ms is None
        assert response.details is None


class TestReadinessCheckEndpoint:
    """Test readiness check endpoint with dependency checks."""

    async def mock_db_connection(self) -> AsyncGenerator[Any, None]:
        """Mock database connection."""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        yield mock_conn

    async def mock_db_connection_error(self) -> AsyncGenerator[Any, None]:
        """Mock database connection that raises an error."""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(
            side_effect=Exception("Database connection failed")
        )
        yield mock_conn

    @pytest.mark.asyncio
    async def test_readiness_check_all_healthy(self) -> None:
        """Test readiness check with all services healthy."""
        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=b"PONG")
        mock_redis.info = AsyncMock(
            return_value={
                "redis_version": "7.0.0",
                "uptime_in_days": 5,
                "connected_clients": 2,
                "used_memory_human": "1.2M",
            }
        )

        # Mock settings
        settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="test-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="development",
        )

        response = await readiness_check(
            request=create_mock_request(),
            db=self.mock_db_connection(),
            redis=mock_redis,
            settings=settings,
        )

        assert response.status == "healthy"
        assert response.environment == "development"

        # Check database component
        assert response.components.database.status == "healthy"
        assert (
            "PostgreSQL connection successful" in response.components.database.message
        )
        assert response.components.database.response_time_ms > 0

        # Check Redis component
        assert response.components.redis.status == "healthy"
        assert "Redis connection successful" in response.components.redis.message
        assert response.components.redis.response_time_ms > 0
        assert response.components.redis.details.version == "7.0.0"

        # Check API component
        assert response.components.api.status == "healthy"

    @pytest.mark.asyncio
    async def test_readiness_check_database_failure(self) -> None:
        """Test readiness check with database failure."""
        # Mock Redis (healthy)
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=b"PONG")
        mock_redis.info = AsyncMock(
            return_value={
                "redis_version": "7.0.0",
                "uptime_in_days": 5,
                "connected_clients": 2,
                "used_memory_human": "1.2M",
            }
        )

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="test-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="development",
        )

        response = await readiness_check(
            request=create_mock_request(),
            db=self.mock_db_connection_error(),
            redis=mock_redis,
            settings=settings,
        )

        assert response.status == "unhealthy"

        # Check database component is unhealthy
        assert response.components.database.status == "unhealthy"
        assert "Database connection failed" in response.components.database.message

        # Check Redis component is still healthy
        assert response.components.redis.status == "healthy"

    @pytest.mark.asyncio
    async def test_readiness_check_redis_failure(self) -> None:
        """Test readiness check with Redis failure."""
        # Mock Redis (failure)
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(side_effect=Exception("Redis connection failed"))

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="test-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="development",
        )

        response = await readiness_check(
            request=create_mock_request(),
            db=self.mock_db_connection(),
            redis=mock_redis,
            settings=settings,
        )

        assert response.status == "unhealthy"

        # Check database component is healthy
        assert response.components.database.status == "healthy"

        # Check Redis component is unhealthy
        assert response.components.redis.status == "unhealthy"
        assert "Redis connection failed" in response.components.redis.message

    @pytest.mark.asyncio
    async def test_readiness_check_with_openai_key(self) -> None:
        """Test readiness check with OpenAI API key configured."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=b"PONG")
        mock_redis.info = AsyncMock(
            return_value={
                "redis_version": "7.0.0",
            }
        )

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="test-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="development",
            openai_api_key="sk-test-key-12345",  # nosec # pragma: allowlist secret,
        )

        response = await readiness_check(
            request=create_mock_request(),
            db=self.mock_db_connection(),
            redis=mock_redis,
            settings=settings,
        )

        assert response.status == "healthy"

        # Check OpenAI component is included
        assert hasattr(response.components, "openai")
        # OpenAI should be degraded when package is not available
        assert response.components.openai.status == "degraded"
        assert "OpenAI package not installed" in response.components.openai.message


class TestDetailedHealthCheckEndpoint:
    """Test detailed health check endpoint."""

    async def mock_db_connection_detailed(self) -> AsyncGenerator[Any, None]:
        """Mock database connection for detailed checks."""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(
            return_value="PostgreSQL 15.0 on x86_64-pc-linux-gnu"
        )
        yield mock_conn

    @pytest.mark.asyncio
    async def test_detailed_health_check_success(self) -> None:
        """Test detailed health check with all components healthy."""
        # Mock Redis with detailed stats
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=b"PONG")
        mock_redis.info = AsyncMock(
            side_effect=[
                # First call for general info
                {
                    "redis_version": "7.0.0",
                    "uptime_in_days": 10,
                    "connected_clients": 5,
                    "used_memory_human": "2.5M",
                    "used_memory": 2621440,  # 2.5MB
                    "maxmemory": 134217728,  # 128MB
                },
                # Second call for stats
                {
                    "total_commands_processed": 1000000,
                    "instantaneous_ops_per_sec": 50,
                },
            ]
        )

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="test-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="development",
        )

        # Mock psutil for system metrics
        with (
            patch("psutil.virtual_memory") as mock_memory_func,
            patch("psutil.cpu_percent") as mock_cpu_func,
            patch("psutil.cpu_count") as mock_cpu_count_func,
        ):
            # Configure memory mock
            mock_memory = MagicMock()
            mock_memory.total = 8589934592  # 8GB
            mock_memory.available = 4294967296  # 4GB
            mock_memory.percent = 50.0
            mock_memory_func.return_value = mock_memory

            # Configure CPU mocks
            mock_cpu_func.return_value = 25.0
            mock_cpu_count_func.return_value = 4

            response = await detailed_health_check(
                db=self.mock_db_connection_detailed(),
                redis=mock_redis,
                settings=settings,
            )

        assert response.status == "healthy"

        # Check database component with details
        assert response.components.database.status == "healthy"
        assert (
            response.components.database.details.version
            == "PostgreSQL 15.0 on x86_64-pc-linux-gnu"
        )

        # Check Redis component with detailed stats
        assert response.components.redis.status == "healthy"
        redis_details = response.components.redis.details
        assert redis_details.version == "7.0.0"
        assert redis_details.uptime_days == 10
        assert redis_details.connected_clients == 5
        assert redis_details.used_memory_percent == 1.95  # ~2%
        assert redis_details.total_commands_processed == 1000000

        # Check system metrics
        assert response.components.memory.status == "healthy"
        memory_details = response.components.memory.details
        assert memory_details.total_gb == 8.0
        assert memory_details.available_gb == 4.0
        assert memory_details.used_percent == 50.0

        assert response.components.cpu.status == "healthy"
        cpu_details = response.components.cpu.details
        assert cpu_details.count == 4
        assert cpu_details.percent == 25.0

    @pytest.mark.asyncio
    async def test_detailed_health_check_degraded_memory(self) -> None:
        """Test detailed health check with high memory usage."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=b"PONG")
        mock_redis.info = AsyncMock(
            side_effect=[
                {"redis_version": "7.0.0", "used_memory": 1000, "maxmemory": 0},
                {"total_commands_processed": 1000},
            ]
        )

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="test-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="development",
        )

        # Mock psutil with high memory usage
        with (
            patch("psutil.virtual_memory") as mock_memory_func,
            patch("psutil.cpu_percent") as mock_cpu_func,
            patch("psutil.cpu_count") as mock_cpu_count_func,
        ):
            # Configure memory mock for high usage
            mock_memory = MagicMock()
            mock_memory.total = 8589934592
            mock_memory.available = 429496729  # Low available memory
            mock_memory.percent = 95.0  # High usage
            mock_memory_func.return_value = mock_memory

            # Configure CPU mocks
            mock_cpu_func.return_value = 15.0
            mock_cpu_count_func.return_value = 4

            response = await detailed_health_check(
                db=self.mock_db_connection_detailed(),
                redis=mock_redis,
                settings=settings,
            )

        # Overall status should be degraded due to high memory usage
        assert response.status == "degraded"
        assert response.components.memory.status == "degraded"

    @pytest.mark.asyncio
    async def test_detailed_health_check_no_psutil(self) -> None:
        """Test detailed health check without psutil installed."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=b"PONG")
        mock_redis.info = AsyncMock(
            side_effect=[
                {"redis_version": "7.0.0", "used_memory": 1000, "maxmemory": 0},
                {"total_commands_processed": 1000},
            ]
        )

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="test-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="development",
        )

        # Mock ImportError for psutil by intercepting the import
        def mock_import(name, *args, **kwargs):
            if name == "psutil":
                raise ImportError("No module named 'psutil'")
            return __import__(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            response = await detailed_health_check(
                db=self.mock_db_connection_detailed(),
                redis=mock_redis,
                settings=settings,
            )

        assert response.status == "healthy"
        # Should have system component with graceful degradation message
        assert response.components.system.status == "healthy"
        assert "System metrics unavailable" in response.components.system.message

    @pytest.mark.asyncio
    async def test_detailed_health_check_redis_high_memory(self) -> None:
        """Test detailed health check with Redis in degraded state."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=b"PONG")
        mock_redis.info = AsyncMock(
            side_effect=[
                {
                    "redis_version": "7.0.0",
                    "used_memory": 96636764,  # ~92MB
                    "maxmemory": 104857600,  # 100MB (>90% usage)
                    "uptime_in_days": 5,
                    "connected_clients": 10,
                    "used_memory_human": "92M",
                },
                {"total_commands_processed": 5000000, "instantaneous_ops_per_sec": 100},
            ]
        )

        settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="test-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="development",
        )

        with (
            patch("psutil.virtual_memory") as mock_memory_func,
            patch("psutil.cpu_percent") as mock_cpu_func,
            patch("psutil.cpu_count") as mock_cpu_count_func,
        ):
            # Configure memory mock
            mock_memory = MagicMock()
            mock_memory.total = 8589934592
            mock_memory.available = 4294967296
            mock_memory.percent = 50.0
            mock_memory_func.return_value = mock_memory

            # Configure CPU mocks
            mock_cpu_func.return_value = 25.0
            mock_cpu_count_func.return_value = 4

            response = await detailed_health_check(
                db=self.mock_db_connection_detailed(),
                redis=mock_redis,
                settings=settings,
            )

        # Overall status should be degraded due to Redis memory usage
        assert response.status == "degraded"
        assert response.components.redis.status == "degraded"
        assert response.components.redis.details.used_memory_percent == 92.16
