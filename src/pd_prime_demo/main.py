"""MVP Policy Decision Backend - Main Application Module."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Generic, TypeVar

import uvicorn
from attrs import define, field
from beartype import beartype
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ConfigDict

from .api.v1 import router as v1_router
from .core.cache import get_cache
from .core.config import get_settings
from .core.database import get_database
from .schemas.common import APIInfo

# Rust-like Result type for defensive programming
T = TypeVar("T")
E = TypeVar("E")


@define(frozen=True, slots=True)
class Result(Generic[T, E]):
    """Rust-like Result type for error handling without exceptions."""

    _value: T | None = field(default=None, init=False)
    _error: E | None = field(default=None, init=False)

    @classmethod
    def ok(cls, value: T) -> "Result[T, E]":
        """Create a successful result."""
        result = cls()
        object.__setattr__(result, "_value", value)
        return result

    @classmethod
    def err(cls, error: E) -> "Result[T, E]":
        """Create an error result."""
        result = cls()
        object.__setattr__(result, "_error", error)
        return result

    def is_ok(self) -> bool:
        """Check if result is successful."""
        return self._value is not None

    def is_err(self) -> bool:
        """Check if result is an error."""
        return self._error is not None

    def unwrap(self) -> T:
        """Unwrap value or raise exception."""
        if self._value is not None:
            return self._value
        raise RuntimeError("Called unwrap() on error result")

    def unwrap_err(self) -> E:
        """Extract the error value or panic."""
        if self._error is not None:
            return self._error
        raise RuntimeError("Called unwrap_err() on ok result")

    def unwrap_or(self, default: T) -> T:
        """Unwrap value or return default."""
        return self._value if self._value is not None else default


# Base configuration for all Pydantic models in the application
class BaseAppModel(BaseModel):
    """
    Base model for all application data structures.

    Enforces Master Ruleset compliance:
    - frozen=True: IMMUTABLE BY DEFAULT
    - Strict validation: FAIL-FAST VALIDATION
    - No extra fields: EXPLICIT ERROR HANDLING
    """

    model_config = ConfigDict(
        frozen=True,
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
        use_enum_values=True,
        validate_default=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle - startup and shutdown."""
    # Startup
    settings = get_settings()
    print(f"🚀 Starting MVP Policy Decision Backend in {settings.api_env} mode...")

    # Initialize database pool
    db = get_database()
    await db.connect()
    print("✅ Database connection pool initialized")

    # Initialize Redis pool
    cache = get_cache()
    await cache.connect()
    print("✅ Redis connection pool initialized")

    yield

    # Shutdown
    print("🛑 Shutting down MVP Policy Decision Backend...")

    # Close database connections
    await db.disconnect()
    print("✅ Database connections closed")

    # Close Redis connections
    await cache.disconnect()
    print("✅ Redis connections closed")


@beartype
def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured application instance
    """
    settings = get_settings()

    app = FastAPI(
        title="MVP Policy Decision Backend",
        description="High-performance policy management system with enterprise-grade standards",
        version="1.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # Security middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"] if settings.is_development else ["api.example.com"],
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(v1_router)

    # Root endpoint
    @app.get("/")
    async def root() -> APIInfo:
        """Root endpoint returning API information."""
        return APIInfo(
            name="MVP Policy Decision Backend",
            version="1.0.0",
            status="operational",
            environment=settings.api_env,
        )

    return app


# Create the application instance
app = create_app()


@beartype
def main() -> None:
    """Run the main application entry point."""
    settings = get_settings()

    uvicorn.run(
        "pd_prime_demo.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
        log_level="info" if not settings.is_production else "error",
    )


if __name__ == "__main__":
    main()
