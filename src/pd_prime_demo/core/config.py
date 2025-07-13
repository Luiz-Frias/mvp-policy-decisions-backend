# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Configuration management using Pydantic Settings with Doppler integration."""

from beartype import beartype
from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with immutable configuration."""

    model_config = SettingsConfigDict(
        env_file=None,  # We use Doppler, not .env files
        env_file_encoding="utf-8",
        frozen=True,  # Immutable settings
        validate_default=True,
        extra="forbid",
    )

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///:memory:",
        description="PostgreSQL connection URL",
        min_length=1,
    )
    database_public_url: str | None = Field(
        default=None,
        description="PostgreSQL public URL (for external access)",
    )
    database_read_url: str | None = Field(
        default=None,
        description="PostgreSQL read replica URL (optional)",
    )
    database_pool_min: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Minimum database pool size",
    )
    database_pool_max: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Maximum database pool size",
    )
    database_pool_timeout: float = Field(
        default=10.0,
        ge=1.0,
        le=60.0,
        description="Connection acquisition timeout in seconds",
    )
    database_command_timeout: float = Field(
        default=30.0,
        ge=5.0,
        le=300.0,
        description="Query execution timeout in seconds",
    )
    database_max_inactive_connection_lifetime: float = Field(
        default=600.0,
        ge=60.0,
        le=3600.0,
        description="Maximum connection lifetime in seconds",
    )
    database_max_connections: int = Field(
        default=100,
        ge=50,
        le=500,
        description="Maximum database connections (for capacity planning)",
    )
    database_admin_pool_enabled: bool = Field(
        default=True,
        description="Enable dedicated admin connection pool",
    )

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
        min_length=1,
    )
    redis_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Default Redis TTL in seconds",
    )

    # API Configuration
    app_name: str = Field(
        default="PD Prime Demo",
        description="Application name",
        min_length=1,
    )
    api_host: str = Field(
        default="0.0.0.0",  # nosec B104 - Binding to all interfaces is needed for containerized deployment
        description="API host to bind to",
    )
    api_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="API port to bind to",
    )
    api_env: str = Field(
        default="development",
        pattern="^(development|staging|production)$",
        description="API environment",
    )
    api_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        description="Allowed CORS origins",
    )
    api_url: str = Field(
        default="http://localhost:8000",
        description="API base URL",
        min_length=1,
    )

    # Security
    secret_key: str = Field(
        default="test-secret-key-for-testing-only-never-use-in-production-32-chars",
        min_length=32,
        description="Application secret key",
    )
    jwt_secret: str = Field(
        default="test-jwt-secret-for-testing-only-never-use-in-production-32-chars",
        min_length=32,
        description="JWT signing secret",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT algorithm",
    )
    jwt_expiration_minutes: int = Field(
        default=60,
        ge=5,
        le=1440,  # Max 24 hours
        description="JWT token expiration in minutes",
    )

    # OpenAI (Optional)
    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key for AI features",
    )

    # External APIs
    vin_api_key: str | None = Field(
        default=None,
        description="VIN decoder API key",
    )
    vin_api_endpoint: str | None = Field(
        default=None,
        description="VIN decoder API endpoint URL",
    )

    # SSO Configuration
    google_oauth_client_id: str | None = Field(
        default=None,
        description="Google OAuth2 client ID",
    )
    azure_ad_client_id: str | None = Field(
        default=None,
        description="Azure AD client ID",
    )
    okta_domain: str | None = Field(
        default=None,
        description="Okta domain for SSO",
    )

    # Feature Flags
    enable_metrics: bool = Field(
        default=True,
        description="Enable metrics collection",
    )
    enable_profiling: bool = Field(
        default=False,
        description="Enable performance profiling",
    )

    # Performance
    max_request_size_mb: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum request size in MB",
    )
    request_timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Request timeout in seconds",
    )

    @field_validator("database_pool_max")
    @classmethod
    def validate_pool_sizes(cls: type["Settings"], v: int, info: ValidationInfo) -> int:
        """Ensure pool max is greater than pool min."""
        if "database_pool_min" in info.data:
            min_size = info.data["database_pool_min"]
            if v < min_size:
                raise ValueError(
                    f"database_pool_max ({v}) must be >= database_pool_min ({min_size})"
                )
        return v

    @field_validator("api_cors_origins")
    @classmethod
    def validate_cors_origins(cls: type["Settings"], v: list[str]) -> list[str]:
        """Validate CORS origins are proper URLs."""
        for origin in v:
            if not origin.startswith(("http://", "https://")):
                raise ValueError(f"Invalid CORS origin: {origin}")
        return v

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls: type["Settings"], v: str, info: ValidationInfo) -> str:
        """Ensure test secrets are not used in production."""
        if "api_env" in info.data and info.data["api_env"] == "production":
            if v.startswith("test-"):
                raise ValueError(
                    "Test secret key cannot be used in production. "
                    "Set SECRET_KEY environment variable."
                )
        return v

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls: type["Settings"], v: str, info: ValidationInfo) -> str:
        """Ensure test JWT secrets are not used in production."""
        if "api_env" in info.data and info.data["api_env"] == "production":
            if v.startswith("test-"):
                raise ValueError(
                    "Test JWT secret cannot be used in production. "
                    "Set JWT_SECRET environment variable."
                )
        return v

    @property
    @beartype
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.api_env == "production"

    @property
    @beartype
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.api_env == "development"

    @property
    @beartype
    def effective_database_url(self) -> str:
        """Get the effective database URL, preferring public URL when available."""
        # If public URL is available and we're not in Railway environment, use public
        if self.database_public_url:
            # Check if we're running outside Railway (by testing if internal URL works)
            if "railway.internal" in self.database_url:
                # We have an internal URL, so prefer public for external access
                return self.database_public_url

        # Fall back to regular database_url
        return self.database_url


_settings: Settings | None = None


@beartype
def get_settings() -> Settings:
    """Get cached settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


@beartype
def clear_settings_cache() -> None:
    """Clear settings cache (for testing)."""
    global _settings
    _settings = None
