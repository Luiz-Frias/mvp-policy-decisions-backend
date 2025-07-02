"""Configuration management using Pydantic Settings with Doppler integration."""

from functools import lru_cache

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
        ...,
        description="PostgreSQL connection URL",
        min_length=1,
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

    # Redis
    redis_url: str = Field(
        ...,
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

    # Security
    secret_key: str = Field(
        ...,
        min_length=32,
        description="Application secret key",
    )
    jwt_secret: str = Field(
        ...,
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

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.api_env == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.api_env == "development"


@lru_cache
@beartype
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
