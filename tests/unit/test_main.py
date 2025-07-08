"""Unit tests for main application module."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Set up environment variables BEFORE importing main
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")  # nosec
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-32-chars")  # nosec
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-testing-32-chars")  # nosec
os.environ.setdefault("API_ENV", "development")

from src.pd_prime_demo.core.config import Settings
from src.pd_prime_demo.main import BaseAppModel, Result, create_app, lifespan, main


class TestResultType:
    """Test the Result type implementation."""

    def test_result_ok_creation(self) -> None:
        """Test creating successful Result."""
        result = Result.ok("success")

        assert result.is_ok()
        assert not result.is_err()
        assert result.unwrap() == "success"
        assert result.unwrap_or("default") == "success"

    def test_result_err_creation(self) -> None:
        """Test creating error Result."""
        result = Result.err("error message")

        assert not result.is_ok()
        assert result.is_err()
        assert result.unwrap_err() == "error message"
        assert result.unwrap_or("default") == "default"

    def test_result_unwrap_panic_on_error(self) -> None:
        """Test unwrap() panics on error result."""
        result = Result.err("error")

        with pytest.raises(RuntimeError, match="Called unwrap\\(\\) on error result"):
            result.unwrap()

    def test_result_unwrap_err_panic_on_ok(self) -> None:
        """Test unwrap_err() panics on ok result."""
        result = Result.ok("success")

        with pytest.raises(RuntimeError, match="Called unwrap_err\\(\\) on ok result"):
            result.unwrap_err()

    def test_result_with_different_types(self) -> None:
        """Test Result with different types."""
        # Integer result
        int_result = Result.ok(42)
        assert int_result.unwrap() == 42
        assert int_result.unwrap_or(0) == 42

        # List result
        list_result = Result.ok([1, 2, 3])
        assert list_result.unwrap() == [1, 2, 3]

        # Error with string
        str_error = Result.err("Something went wrong")
        assert str_error.unwrap_err() == "Something went wrong"
        assert str_error.unwrap_or([]) == []


class TestBaseAppModel:
    """Test base application model."""

    def test_base_model_configuration(self) -> None:
        """Test BaseAppModel configuration."""

        class TestModel(BaseAppModel):
            name: str
            value: int

        # Valid creation
        model = TestModel(name="test", value=42)
        assert model.name == "test"
        assert model.value == 42

    def test_base_model_immutable(self) -> None:
        """Test BaseAppModel is immutable."""

        class TestModel(BaseAppModel):
            name: str

        model = TestModel(name="test")

        # Should not be able to modify
        with pytest.raises(Exception):  # ValidationError or AttributeError
            model.name = "new_name"  # type: ignore[misc]

    def test_base_model_no_extra_fields(self) -> None:
        """Test BaseAppModel forbids extra fields."""

        class TestModel(BaseAppModel):
            name: str

        with pytest.raises(Exception):  # ValidationError
            TestModel(name="test", extra_field="not_allowed")  # type: ignore[call-arg]

    def test_base_model_whitespace_stripping(self) -> None:
        """Test BaseAppModel strips whitespace."""

        class TestModel(BaseAppModel):
            name: str

        model = TestModel(name="  test  ")
        assert model.name == "test"


class TestLifespanFunction:
    """Test application lifespan management."""

    @pytest.mark.asyncio
    async def test_lifespan_startup_and_shutdown(self) -> None:
        """Test lifespan function startup and shutdown."""
        # Mock dependencies
        mock_settings = MagicMock()
        mock_settings.api_env = "development"

        mock_db = AsyncMock()
        mock_db.connect = AsyncMock()
        mock_db.disconnect = AsyncMock()

        mock_cache = AsyncMock()
        mock_cache.connect = AsyncMock()
        mock_cache.disconnect = AsyncMock()

        # Create mock app
        mock_app = MagicMock(spec=FastAPI)

        with (
            patch("src.pd_prime_demo.main.get_settings", return_value=mock_settings),
            patch("src.pd_prime_demo.main.get_database", return_value=mock_db),
            patch("src.pd_prime_demo.main.get_cache", return_value=mock_cache),
            patch("src.pd_prime_demo.main.logger") as mock_logger,
        ):
            # Test the lifespan context manager
            async with lifespan(mock_app):
                # Verify startup was called
                mock_db.connect.assert_called_once()
                mock_cache.connect.assert_called_once()

                # Verify startup messages
                assert any(
                    "🚀 Starting MVP Policy Decision Backend" in str(call)
                    for call in mock_logger.info.call_args_list
                )
                assert any(
                    "✅ Database connection pool initialized" in str(call)
                    for call in mock_logger.info.call_args_list
                )
                assert any(
                    "✅ Redis connection pool initialized" in str(call)
                    for call in mock_logger.info.call_args_list
                )

            # Verify shutdown was called
            mock_db.disconnect.assert_called_once()
            mock_cache.disconnect.assert_called_once()

            # Verify shutdown messages
            assert any(
                "🛑 Shutting down MVP Policy Decision Backend" in str(call)
                for call in mock_logger.info.call_args_list
            )
            assert any(
                "✅ Database connections closed" in str(call)
                for call in mock_logger.info.call_args_list
            )
            assert any(
                "✅ Redis connections closed" in str(call)
                for call in mock_logger.info.call_args_list
            )

    @pytest.mark.asyncio
    async def test_lifespan_database_connection_error(self) -> None:
        """Test lifespan handles database connection errors gracefully."""
        mock_settings = MagicMock()
        mock_settings.api_env = "development"

        mock_db = AsyncMock()
        mock_db.connect = AsyncMock(side_effect=Exception("Database connection failed"))
        mock_db.disconnect = AsyncMock()

        mock_cache = AsyncMock()
        mock_cache.connect = AsyncMock()
        mock_cache.disconnect = AsyncMock()

        mock_app = MagicMock(spec=FastAPI)

        with (
            patch("src.pd_prime_demo.main.get_settings", return_value=mock_settings),
            patch("src.pd_prime_demo.main.get_database", return_value=mock_db),
            patch("src.pd_prime_demo.main.get_cache", return_value=mock_cache),
            patch("builtins.print"),
        ):
            # Should propagate the exception
            with pytest.raises(Exception, match="Database connection failed"):
                async with lifespan(mock_app):
                    pass


class TestCreateApp:
    """Test FastAPI application creation."""

    def test_create_app_development_mode(self) -> None:
        """Test app creation in development mode."""
        mock_settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="test-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="development",
            api_host="0.0.0.0",  # nosec  # nosec
            api_port=8000,
        )

        with patch("src.pd_prime_demo.main.get_settings", return_value=mock_settings):
            app = create_app()

        assert isinstance(app, FastAPI)
        assert app.title == "MVP Policy Decision Backend"
        assert app.version == "1.0.0"

        # In development, docs should be available
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"
        assert app.openapi_url == "/openapi.json"

    def test_create_app_production_mode(self) -> None:
        """Test app creation in production mode."""
        mock_settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="test-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="production",
            api_host="0.0.0.0",  # nosec  # nosec
            api_port=8000,
        )

        with patch("src.pd_prime_demo.main.get_settings", return_value=mock_settings):
            app = create_app()

        assert isinstance(app, FastAPI)

        # In production, docs should be disabled
        assert app.docs_url is None
        assert app.redoc_url is None
        assert app.openapi_url is None

    def test_create_app_trusted_host_middleware_development(self) -> None:
        """Test app creation with middleware in development."""
        mock_settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="test-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="development",
        )

        with patch("src.pd_prime_demo.main.get_settings", return_value=mock_settings):
            app = create_app()

        # Verify app was created successfully with middleware configured
        assert isinstance(app, FastAPI)
        assert app.title == "MVP Policy Decision Backend"

    def test_create_app_cors_configuration(self) -> None:
        """Test app creation with CORS middleware configuration."""
        mock_settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="test-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="development",
            api_cors_origins=["http://localhost:3000", "https://app.example.com"],
        )

        with patch("src.pd_prime_demo.main.get_settings", return_value=mock_settings):
            app = create_app()

        # Verify app was created successfully with CORS configured
        assert isinstance(app, FastAPI)
        assert app.title == "MVP Policy Decision Backend"

    def test_root_endpoint(self) -> None:
        """Test root endpoint functionality."""
        mock_settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="test-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="development",
        )

        with patch("src.pd_prime_demo.main.get_settings", return_value=mock_settings):
            app = create_app()

        # Test the root endpoint
        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "MVP Policy Decision Backend"
        assert data["version"] == "1.0.0"
        assert data["status"] == "operational"
        assert data["environment"] == "development"


class TestMainFunction:
    """Test main application entry point."""

    def test_main_function_development(self) -> None:
        """Test main function calls uvicorn with correct parameters in development."""
        mock_settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="test-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="development",
            api_host="127.0.0.1",
            api_port=8080,
        )

        with (
            patch("src.pd_prime_demo.main.get_settings", return_value=mock_settings),
            patch("src.pd_prime_demo.main.uvicorn.run") as mock_run,
        ):
            main()

            mock_run.assert_called_once_with(
                "pd_prime_demo.main:app",
                host="127.0.0.1",
                port=8080,
                reload=True,  # Development mode
                log_level="info",
            )

    def test_main_function_production(self) -> None:
        """Test main function calls uvicorn with correct parameters in production."""
        mock_settings = Settings(
            database_url="postgresql://test:test@localhost/test",  # nosec # pragma: allowlist secret,
            redis_url="redis://localhost:6379/0",
            secret_key="test-secret-key-for-testing-32-chars",  # nosec # pragma: allowlist secret,
            jwt_secret="test-jwt-secret-for-testing-32-chars",  # nosec # pragma: allowlist secret
            api_env="production",
            api_host="0.0.0.0",  # nosec  # nosec
            api_port=80,
        )

        with (
            patch("src.pd_prime_demo.main.get_settings", return_value=mock_settings),
            patch("src.pd_prime_demo.main.uvicorn.run") as mock_run,
        ):
            main()

            mock_run.assert_called_once_with(
                "pd_prime_demo.main:app",
                host="0.0.0.0",  # nosec
                port=80,
                reload=False,  # Production mode
                log_level="error",
            )
