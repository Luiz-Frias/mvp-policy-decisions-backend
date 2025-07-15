# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""MVP Policy Decision Backend - Main Application Module."""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Generic, TypeVar

import uvicorn
from attrs import define, field
from beartype import beartype
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ConfigDict
from starlette.middleware.base import BaseHTTPMiddleware

from .api.middleware.security_headers import SecurityHeadersMiddleware
from .api.v1 import router as v1_router
from .core.cache import get_cache
from .core.config import get_settings
from .core.database import get_database
from .core.performance_monitor import PerformanceMonitoringMiddleware
from .core.rate_limiter import RateLimitConfig, RateLimitingMiddleware
from .schemas.common import APIInfo
from .websocket.app import websocket_app

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Install uvloop for performance if available
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logger.info("✅ uvloop installed - 2-4x performance boost enabled")
except ImportError:
    logger.warning("⚠️ uvloop not available - using default asyncio")

# Rust-like Result type for defensive programming
T = TypeVar("T")
E = TypeVar("E")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Comprehensive request logging middleware for debugging."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Log all request and response details."""
        start_time = time.time()
        request_id = f"{int(start_time)}-{id(request)}"

        # Log incoming request
        logger.info("=" * 120)
        logger.info(f"INCOMING REQUEST - ID: {request_id}")
        logger.info(f"Method: {request.method}")
        logger.info(f"URL: {request.url}")
        logger.info(f"Path: {request.url.path}")
        logger.info(f"Query params: {dict(request.query_params)}")
        logger.info(
            f"Client: {request.client.host if request.client else 'Unknown'}:{request.client.port if request.client else 'Unknown'}"
        )
        logger.info(f"User-Agent: {request.headers.get('user-agent', 'Unknown')}")
        logger.info(f"Content-Type: {request.headers.get('content-type', 'None')}")
        logger.info(
            f"Content-Length: {request.headers.get('content-length', 'Unknown')}"
        )
        logger.info(f"Accept: {request.headers.get('accept', 'Unknown')}")
        logger.info(
            f"Authorization: {'Present' if request.headers.get('authorization') else 'None'}"
        )
        logger.info(f"Origin: {request.headers.get('origin', 'None')}")
        logger.info(f"Referer: {request.headers.get('referer', 'None')}")

        # Log all headers for debugging
        logger.info("Headers:")
        for name, value in request.headers.items():
            # Don't log sensitive headers in full
            if name.lower() in ["authorization", "cookie", "x-api-key"]:
                logger.info(f"  {name}: [REDACTED]")
            else:
                logger.info(f"  {name}: {value}")

        # Try to read and log request body for non-GET requests
        if request.method != "GET":
            try:
                body = await request.body()
                if body:
                    try:
                        # Try to parse as JSON
                        body_json = json.loads(body.decode())
                        logger.info(f"Request body (JSON): {body_json}")
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        logger.info(
                            f"Request body (raw): {body[:500]!r}..."
                        )  # First 500 chars
                else:
                    logger.info("Request body: Empty")
            except Exception as e:
                logger.error(f"Error reading request body: {e}")

        logger.info(
            f"Request processing started at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}"
        )
        logger.info("-" * 120)

        # Process the request
        try:
            response = await call_next(request)
            processing_time = (time.time() - start_time) * 1000

            # Log response
            logger.info(f"RESPONSE - ID: {request_id}")
            logger.info(f"Status: {response.status_code}")
            logger.info(f"Processing time: {processing_time:.2f}ms")
            logger.info("Response headers:")
            for name, value in response.headers.items():
                logger.info(f"  {name}: {value}")

            # Try to read response body for debugging (only for small responses)
            if hasattr(response, "body"):
                try:
                    # This is tricky because we can't easily read the response body without consuming it
                    logger.info(
                        "Response body: [Available but not logged to preserve stream]"
                    )
                except Exception as e:
                    logger.info(f"Could not read response body: {e}")

            if response.status_code >= 400:
                logger.error(
                    f"ERROR RESPONSE - ID: {request_id} - Status: {response.status_code}"
                )
            else:
                logger.info(
                    f"SUCCESS RESPONSE - ID: {request_id} - Status: {response.status_code}"
                )

        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            logger.error(f"REQUEST FAILED - ID: {request_id}")
            logger.error(f"Error: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Processing time: {processing_time:.2f}ms")
            raise

        logger.info("=" * 120)
        return response


@define(frozen=True, slots=True)
class Result(Generic[T, E]):
    """Rust-like Result type for error handling without exceptions."""

    _value: T | None = field(default=None, init=False)
    _error: E | None = field(default=None, init=False)

    @classmethod
    @beartype
    def ok(cls, value: T) -> "Result[T, E]":
        """Create a successful result."""
        result = cls()
        object.__setattr__(result, "_value", value)
        return result

    @classmethod
    @beartype
    def err(cls, error: E) -> "Result[T, E]":
        """Create an error result."""
        result = cls()
        object.__setattr__(result, "_error", error)
        return result

    @beartype
    def is_ok(self) -> bool:
        """Check if result is successful."""
        return self._value is not None

    @beartype
    def is_err(self) -> bool:
        """Check if result is an error."""
        return self._error is not None

    @beartype
    def unwrap(self) -> T:
        """Unwrap value or raise exception."""
        if self._value is not None:
            return self._value
        raise RuntimeError("Called unwrap() on error result")

    @beartype
    def unwrap_err(self) -> E:
        """Extract the error value or panic."""
        if self._error is not None:
            return self._error
        raise RuntimeError("Called unwrap_err() on ok result")

    @beartype
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
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle - startup and shutdown."""
    # Startup
    settings = get_settings()
    logger.info(
        f"🚀 Starting MVP Policy Decision Backend in {settings.api_env} mode..."
    )
    logger.info(f"API Host: {settings.api_host}")
    logger.info(f"API Port: {settings.api_port}")
    logger.info(
        f"Database URL: {settings.database_url[:20]}..."
    )  # Only show first 20 chars
    logger.info(f"Redis URL: {settings.redis_url[:20]}...")  # Only show first 20 chars
    logger.info(f"CORS Origins: {settings.api_cors_origins}")

    # Initialize database pool
    db = get_database()
    await db.connect()
    logger.info("✅ Database connection pool initialized")

    # Initialize Redis pool
    cache = get_cache()
    await cache.connect()
    logger.info("✅ Redis connection pool initialized")

    # Initialize WebSocket manager
    from .websocket.app import get_manager

    websocket_manager = get_manager()
    await websocket_manager.start()
    logger.info("✅ WebSocket manager started with monitoring")

    # Warm performance caches for optimal response times
    from .core.performance_cache import warm_all_caches

    cache_results = await warm_all_caches()
    logger.info(
        f"✅ Performance caches warmed: {cache_results['summary']['total_keys_warmed']} keys in {cache_results['summary']['total_warmup_time_ms']:.1f}ms"
    )

    # Ensure monitoring DB artifacts (pg_stat_statements & materialised views)
    from .bootstrap.monitoring_bootstrap import ensure_monitoring_artifacts

    await ensure_monitoring_artifacts(db)
    logger.info("✅ Monitoring artifacts ensured")

    yield

    # Shutdown
    logger.info("🛑 Shutting down MVP Policy Decision Backend...")

    # Stop WebSocket manager
    await websocket_manager.stop()
    logger.info("✅ WebSocket manager stopped")

    # Close database connections
    await db.disconnect()
    logger.info("✅ Database connections closed")

    # Close Redis connections
    await cache.disconnect()
    logger.info("✅ Redis connections closed")


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

    # Add rate limiting middleware (protect against high load)
    rate_limit_config = RateLimitConfig()
    logger.info("Adding rate limiting middleware for high load protection")
    app.add_middleware(RateLimitingMiddleware, config=rate_limit_config, enabled=True)

    # Add performance monitoring middleware (always enabled for Wave 2.5)
    logger.info(
        "Adding performance monitoring middleware for <100ms requirement tracking"
    )
    app.add_middleware(PerformanceMonitoringMiddleware, track_memory=True)

    # Add comprehensive request logging middleware (only in development)
    if settings.is_development:
        logger.info("Adding request logging middleware for debugging")
        app.add_middleware(RequestLoggingMiddleware)

    # Security middleware
    app.add_middleware(SecurityHeadersMiddleware)
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

    # Mount WebSocket app
    app.mount("/ws", websocket_app)

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

    logger.info(f"Starting server on {settings.api_host}:{settings.api_port}")
    logger.info(f"Development mode: {settings.is_development}")
    logger.info(f"Production mode: {settings.is_production}")

    uvicorn.run(
        "policy_core.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
        log_level="info" if not settings.is_production else "error",
    )


if __name__ == "__main__":
    main()

# SYSTEM_BOUNDARY: Application bootstrap requires flexible dict structures for framework integration, middleware configuration, and system lifecycle management
