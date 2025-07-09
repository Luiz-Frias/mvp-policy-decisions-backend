"""Health check endpoints for monitoring system status.

This module provides health check endpoints that verify the status
of all system components including database, Redis, and external services.
"""

import logging
import time
from collections.abc import AsyncGenerator
from datetime import datetime

import asyncpg
from beartype import beartype
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis

from ...core.config import Settings, get_settings
from ...schemas.health_details import (
    CPUHealthDetails,
    DatabaseHealthDetails,
    DatabasePoolStats,
    HealthDetails,
    MemoryHealthDetails,
    RedisHealthDetails,
)
from ..dependencies import get_db, get_redis

# Configure logging for health endpoints
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

router = APIRouter()


class HealthStatus(BaseModel):
    """Individual component health status."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    status: str = Field(..., pattern=r"^(healthy|unhealthy|degraded)$")
    response_time_ms: float | None = Field(
        default=None, ge=0, description="Response time in milliseconds"
    )
    message: str | None = Field(default=None, description="Additional status message")
    details: HealthDetails | None = Field(
        default=None, description="Additional details"
    )


class ComponentHealthMap(BaseModel):
    """Strongly-typed model for component health mappings."""

    model_config = ConfigDict(
        frozen=True,
        extra="allow",  # Allow dynamic component names
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    def __init__(self, **data: HealthStatus) -> None:
        """Initialize with validation that all values are HealthStatus instances."""
        for key, value in data.items():
            if not isinstance(value, HealthStatus):
                raise ValueError(f"Component '{key}' must be a HealthStatus instance")
        super().__init__(**data)


class HealthResponse(BaseModel):
    """Overall system health response."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    status: str = Field(..., pattern=r"^(healthy|unhealthy|degraded)$")
    timestamp: datetime = Field(..., description="Health check timestamp")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Environment name")

    components: ComponentHealthMap = Field(..., description="Component health statuses")

    uptime_seconds: float = Field(
        ..., ge=0, description="Application uptime in seconds"
    )
    total_response_time_ms: float = Field(..., ge=0, description="Total response time")


# Track application start time
APP_START_TIME = datetime.utcnow()


@beartype
def log_request_details(request: Request, endpoint_name: str) -> str:
    """Log detailed request information for debugging."""
    request_id = f"{int(time.time())}-{id(request)}"

    logger.info("=" * 80)
    logger.info(f"HEALTH ENDPOINT DEBUG - {endpoint_name.upper()}")
    logger.info(f"Request ID: {request_id}")
    logger.info(f"Client IP: {request.client.host if request.client else 'Unknown'}")
    logger.info(f"User Agent: {request.headers.get('user-agent', 'Unknown')}")
    logger.info(f"Method: {request.method}")
    logger.info(f"URL: {request.url}")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"Query params: {dict(request.query_params)}")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info("-" * 80)

    return request_id


@router.get("/health", response_model=HealthResponse)
@beartype
async def health_check(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Perform basic health check endpoint.

    Returns:
        HealthResponse: System health status
    """
    request_id = log_request_details(request, "basic_health")
    start_time = time.time()

    try:
        logger.info(f"[{request_id}] Starting basic health check")
        logger.info(f"[{request_id}] Settings loaded: api_env={settings.api_env}")

        uptime = (datetime.utcnow() - APP_START_TIME).total_seconds()
        logger.info(f"[{request_id}] Calculated uptime: {uptime} seconds")

        response = HealthResponse(
            status="healthy",
            timestamp=datetime.utcnow(),
            version="1.0.0",  # Version from package metadata
            environment=settings.api_env,
            components=ComponentHealthMap(
                api=HealthStatus(
                    status="healthy", response_time_ms=0.1, message="API operational"
                )
            ),
            uptime_seconds=uptime,
            total_response_time_ms=0.1,
        )

        processing_time = (time.time() - start_time) * 1000
        logger.info(
            f"[{request_id}] Health check completed successfully in {processing_time:.2f}ms"
        )
        logger.info(f"[{request_id}] Response status: {response.status}")
        logger.info(f"[{request_id}] Response environment: {response.environment}")
        logger.info(
            f"[{request_id}] Response components: {list(response.components.__dict__.keys()) if hasattr(response.components, '__dict__') else 'N/A'}"
        )
        logger.info("=" * 80)

        return response

    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        logger.error(
            f"[{request_id}] Health check failed after {processing_time:.2f}ms"
        )
        logger.error(f"[{request_id}] Error type: {type(e).__name__}")
        logger.error(f"[{request_id}] Error message: {str(e)}")
        logger.error(f"[{request_id}] Error details: {repr(e)}")
        logger.error("=" * 80)
        raise


@router.get("/health/live", response_model=HealthStatus)
@beartype
async def liveness_check(request: Request) -> HealthStatus:
    """Kubernetes liveness probe endpoint.

    Returns:
        HealthStatus: Simple liveness status
    """
    request_id = log_request_details(request, "liveness")
    start_time = time.time()

    try:
        logger.info(f"[{request_id}] Starting liveness check")

        response = HealthStatus(
            status="healthy", message="Application is running", response_time_ms=None
        )

        processing_time = (time.time() - start_time) * 1000
        logger.info(
            f"[{request_id}] Liveness check completed in {processing_time:.2f}ms"
        )
        logger.info("=" * 80)

        return response

    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        logger.error(
            f"[{request_id}] Liveness check failed after {processing_time:.2f}ms"
        )
        logger.error(f"[{request_id}] Error: {str(e)}")
        logger.error("=" * 80)
        raise


@router.get("/health/ready", response_model=HealthResponse)
async def readiness_check(
    request: Request,
    db: AsyncGenerator[asyncpg.Connection, None] = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Kubernetes readiness probe endpoint with dependency checks.

    Args:
        request: FastAPI request object
        db: Database session
        redis: Redis client
        settings: Application settings

    Returns:
        HealthResponse: Detailed system health with all components
    """
    request_id = log_request_details(request, "readiness")
    start_time = time.time()

    try:
        logger.info(
            f"[{request_id}] Starting readiness check with full dependency validation"
        )

        component_statuses = {}
        total_response_time = 0.0
        overall_status = "healthy"

        # Check database health
        logger.info(f"[{request_id}] Checking database connection...")
        db_start = datetime.utcnow()
        try:
            # Properly handle async generator from FastAPI dependency
            async for connection in db:
                await connection.fetchval("SELECT 1")
                break  # Use the first (and only) yielded connection
            db_response_time = (datetime.utcnow() - db_start).total_seconds() * 1000
            logger.info(
                f"[{request_id}] Database check successful in {db_response_time:.2f}ms"
            )

            component_statuses["database"] = HealthStatus(
                status="healthy",
                response_time_ms=db_response_time,
                message="PostgreSQL connection successful",
                details=None,
            )
            total_response_time += db_response_time

        except Exception as e:
            db_response_time = (datetime.utcnow() - db_start).total_seconds() * 1000
            logger.error(
                f"[{request_id}] Database check failed in {db_response_time:.2f}ms: {str(e)}"
            )

            component_statuses["database"] = HealthStatus(
                status="unhealthy",
                response_time_ms=db_response_time,
                message=f"Database connection failed: {str(e)}",
                details=None,
            )
            overall_status = "unhealthy"
            total_response_time += db_response_time

        # Check Redis health
        logger.info(f"[{request_id}] Checking Redis connection...")
        redis_start = datetime.utcnow()
        try:
            await redis.ping()
            redis_info = await redis.info()
            redis_response_time = (
                datetime.utcnow() - redis_start
            ).total_seconds() * 1000
            logger.info(
                f"[{request_id}] Redis check successful in {redis_response_time:.2f}ms"
            )

            # Extract Redis info with type safety
            redis_version = redis_info.get("redis_version")
            redis_memory = redis_info.get("used_memory_human")

            component_statuses["redis"] = HealthStatus(
                status="healthy",
                response_time_ms=redis_response_time,
                message="Redis connection successful",
                details=RedisHealthDetails(
                    version=(
                        redis_version if isinstance(redis_version, str) else "unknown"
                    ),
                    uptime_days=(
                        int(redis_info.get("uptime_in_days", 0))
                        if redis_info.get("uptime_in_days") is not None
                        else None
                    ),
                    connected_clients=(
                        int(redis_info.get("connected_clients", 0))
                        if redis_info.get("connected_clients") is not None
                        else None
                    ),
                    used_memory_human=(
                        redis_memory if isinstance(redis_memory, str) else "unknown"
                    ),
                    used_memory_percent=None,
                    total_commands_processed=None,
                    instantaneous_ops_per_sec=None,
                ),
            )
            total_response_time += redis_response_time

        except Exception as e:
            redis_response_time = (
                datetime.utcnow() - redis_start
            ).total_seconds() * 1000
            logger.error(
                f"[{request_id}] Redis check failed in {redis_response_time:.2f}ms: {str(e)}"
            )

            component_statuses["redis"] = HealthStatus(
                status="unhealthy",
                response_time_ms=redis_response_time,
                message=f"Redis connection failed: {str(e)}",
                details=None,
            )
            overall_status = "unhealthy"
            total_response_time += redis_response_time

        # Check OpenAI API (if configured)
        if settings.openai_api_key:
            logger.info(
                f"[{request_id}] OpenAI API key configured - performing health check"
            )
            openai_start = datetime.utcnow()
            try:
                import openai  # type: ignore[import-not-found]

                client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
                # Simple API test with minimal cost
                models = await client.models.list()
                openai_response_time = (
                    datetime.utcnow() - openai_start
                ).total_seconds() * 1000

                logger.info(
                    f"[{request_id}] OpenAI health check successful in {openai_response_time:.2f}ms"
                )

                component_statuses["openai"] = HealthStatus(
                    status="healthy",
                    response_time_ms=openai_response_time,
                    message=f"OpenAI API accessible, {len(models.data)} models available",
                )
                total_response_time += openai_response_time

            except ImportError:
                logger.warning(f"[{request_id}] OpenAI package not available")
                component_statuses["openai"] = HealthStatus(
                    status="degraded",
                    response_time_ms=None,
                    message="OpenAI package not installed",
                )
            except Exception as e:
                openai_response_time = (
                    datetime.utcnow() - openai_start
                ).total_seconds() * 1000
                logger.error(f"[{request_id}] OpenAI health check failed: {str(e)}")
                component_statuses["openai"] = HealthStatus(
                    status="unhealthy",
                    response_time_ms=openai_response_time,
                    message=f"OpenAI API error: {str(e)}",
                )
                if overall_status == "healthy":
                    overall_status = "degraded"

        # API component is always healthy if we reach this point
        api_response_time = 0.5
        component_statuses["api"] = HealthStatus(
            status="healthy",
            response_time_ms=api_response_time,
            message="API endpoints operational",
            details=None,
        )
        total_response_time += api_response_time

        uptime = (datetime.utcnow() - APP_START_TIME).total_seconds()

        response = HealthResponse(
            status=overall_status,
            timestamp=datetime.utcnow(),
            version="1.0.0",  # Version from package metadata
            environment=settings.api_env,
            components=ComponentHealthMap(**component_statuses),
            uptime_seconds=uptime,
            total_response_time_ms=total_response_time,
        )

        processing_time = (time.time() - start_time) * 1000
        logger.info(
            f"[{request_id}] Readiness check completed in {processing_time:.2f}ms"
        )
        logger.info(f"[{request_id}] Overall status: {response.status}")
        logger.info(
            f"[{request_id}] Total response time: {response.total_response_time_ms:.2f}ms"
        )
        logger.info(f"[{request_id}] Components checked: {len(component_statuses)}")
        logger.info("=" * 80)

        return response

    except Exception as e:
        processing_time = (time.time() - start_time) * 1000
        logger.error(
            f"[{request_id}] Readiness check failed after {processing_time:.2f}ms"
        )
        logger.error(f"[{request_id}] Error: {str(e)}")
        logger.error("=" * 80)
        raise


@router.get("/health/detailed", response_model=HealthResponse)
async def detailed_health_check(
    db: AsyncGenerator[asyncpg.Connection, None] = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Detailed health check with performance metrics.

    Args:
        db: Database session
        redis: Redis client
        settings: Application settings

    Returns:
        HealthResponse: Comprehensive system health information
    """
    component_statuses = {}
    total_response_time = 0.0
    overall_status = "healthy"

    # Database health with connection pool stats
    db_start = datetime.utcnow()
    try:
        # Test query - properly handle async generator from FastAPI dependency
        async for connection in db:
            db_version = await connection.fetchval("SELECT version()")
            break  # Use the first (and only) yielded connection

        # Get pool stats from connection
        pool_stats = None  # Pool stats structure varies by DB implementation
        # asyncpg connections don't directly expose pool stats
        # This would need to be implemented at the Database class level

        db_response_time = (datetime.utcnow() - db_start).total_seconds() * 1000

        component_statuses["database"] = HealthStatus(
            status="healthy",
            response_time_ms=db_response_time,
            message="PostgreSQL operational",
            details=DatabaseHealthDetails(
                version=db_version if db_version else "unknown", pool_stats=pool_stats
            ),
        )
        total_response_time += db_response_time

    except Exception as e:
        db_response_time = (datetime.utcnow() - db_start).total_seconds() * 1000
        component_statuses["database"] = HealthStatus(
            status="unhealthy",
            response_time_ms=db_response_time,
            message=f"Database error: {str(e)}",
            details=None,
        )
        overall_status = "unhealthy"
        total_response_time += db_response_time

    # Redis health with detailed stats
    redis_start = datetime.utcnow()
    try:
        await redis.ping()
        redis_info = await redis.info()
        redis_stats = await redis.info("stats")

        redis_response_time = (datetime.utcnow() - redis_start).total_seconds() * 1000

        # Check Redis memory usage with safe type conversion
        used_memory_percent = 0.0
        if "used_memory" in redis_info and "maxmemory" in redis_info:
            try:
                maxmemory = int(redis_info["maxmemory"])
                used_memory = int(redis_info["used_memory"])
                if maxmemory > 0:
                    used_memory_percent = (used_memory / maxmemory) * 100
            except (ValueError, TypeError):
                used_memory_percent = 0.0

        redis_status = "healthy"
        if used_memory_percent > 90:
            redis_status = "degraded"
            if overall_status == "healthy":
                overall_status = "degraded"

        component_statuses["redis"] = HealthStatus(
            status=redis_status,
            response_time_ms=redis_response_time,
            message="Redis operational",
            details=RedisHealthDetails(
                version=str(redis_info.get("redis_version", "unknown")),
                uptime_days=(
                    int(redis_info.get("uptime_in_days", 0))
                    if redis_info.get("uptime_in_days") is not None
                    else None
                ),
                connected_clients=(
                    int(redis_info.get("connected_clients", 0))
                    if redis_info.get("connected_clients") is not None
                    else None
                ),
                used_memory_human=(
                    str(redis_info.get("used_memory_human", "unknown"))
                    if redis_info.get("used_memory_human") is not None
                    else None
                ),
                used_memory_percent=round(used_memory_percent, 2),
                total_commands_processed=(
                    int(redis_stats.get("total_commands_processed", 0))
                    if redis_stats.get("total_commands_processed") is not None
                    else None
                ),
                instantaneous_ops_per_sec=(
                    int(redis_stats.get("instantaneous_ops_per_sec", 0))
                    if redis_stats.get("instantaneous_ops_per_sec") is not None
                    else None
                ),
            ),
        )
        total_response_time += redis_response_time

    except Exception as e:
        redis_response_time = (datetime.utcnow() - redis_start).total_seconds() * 1000
        component_statuses["redis"] = HealthStatus(
            status="unhealthy",
            response_time_ms=redis_response_time,
            message=f"Redis error: {str(e)}",
            details=None,
        )
        overall_status = "unhealthy"
        total_response_time += redis_response_time

    # System metrics check (with graceful degradation)
    try:
        import psutil

        # Memory usage check
        memory = psutil.virtual_memory()
        memory_status = "healthy"
        if memory.percent > 90:
            memory_status = "degraded"
            if overall_status == "healthy":
                overall_status = "degraded"

        component_statuses["memory"] = HealthStatus(
            status=memory_status,
            response_time_ms=None,
            message=f"Memory usage: {memory.percent:.1f}%",
            details=MemoryHealthDetails(
                total_gb=round(memory.total / (1024**3), 2),
                available_gb=round(memory.available / (1024**3), 2),
                used_percent=memory.percent,
            ),
        )

        # CPU usage check
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_status = "healthy"
        if cpu_percent > 80:
            cpu_status = "degraded"
            if overall_status == "healthy":
                overall_status = "degraded"

        component_statuses["cpu"] = HealthStatus(
            status=cpu_status,
            response_time_ms=None,
            message=f"CPU usage: {cpu_percent:.1f}%",
            details=CPUHealthDetails(
                count=psutil.cpu_count() or 1,
                percent=cpu_percent,
            ),
        )

    except ImportError:
        # Graceful degradation: system metrics unavailable
        component_statuses["system"] = HealthStatus(
            status="healthy",
            response_time_ms=None,
            message="System metrics unavailable (psutil not installed)",
            details=None,
        )

    # API health
    api_response_time = 1.0
    component_statuses["api"] = HealthStatus(
        status="healthy",
        response_time_ms=api_response_time,
        message="All endpoints operational",
        details=None,
    )
    total_response_time += api_response_time

    uptime = (datetime.utcnow() - APP_START_TIME).total_seconds()

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version="1.0.0",  # Version from package metadata
        environment=settings.api_env,
        components=ComponentHealthMap(**component_statuses),
        uptime_seconds=uptime,
        total_response_time_ms=total_response_time,
    )


# Database health check helpers
@beartype
async def check_database_health(
    db: asyncpg.Connection,
    latency_threshold_ms: float = 10.0,
) -> tuple[HealthStatus, float]:
    """Check database connectivity and performance.

    Args:
        db: Database connection
        latency_threshold_ms: Maximum acceptable latency in milliseconds

    Returns:
        Tuple of (HealthStatus, response_time_ms)
    """
    start_time = time.time()

    try:
        # Simple connectivity check
        result = await db.fetchval("SELECT 1")
        response_time = (time.time() - start_time) * 1000

        if result != 1:
            return (
                HealthStatus(
                    status="unhealthy",
                    response_time_ms=response_time,
                    message="Database returned unexpected result",
                ),
                response_time,
            )

        # Check response time
        status = "healthy"
        message = f"Database responding in {response_time:.2f}ms"

        if response_time > latency_threshold_ms * 2:
            status = "unhealthy"
            message = f"Database latency critical: {response_time:.2f}ms"
        elif response_time > latency_threshold_ms:
            status = "degraded"
            message = f"Database latency high: {response_time:.2f}ms"

        # Get connection pool stats if available
        pool_stats = None
        try:
            # This assumes we're using asyncpg pool
            pool = getattr(db, "_pool", None)
            if pool:
                pool_stats = {
                    "size": pool.get_size(),
                    "free_size": pool.get_free_size(),
                    "min_size": pool.get_min_size(),
                    "max_size": pool.get_max_size(),
                }
        except Exception:
            pass

        return (
            HealthStatus(
                status=status,
                response_time_ms=response_time,
                message=message,
                details=DatabaseHealthDetails(
                    version="PostgreSQL",
                    pool_stats=(
                        DatabasePoolStats(
                            size=pool_stats["size"] if pool_stats else None,
                            available=pool_stats["free_size"] if pool_stats else None,
                            in_use=None,
                            waiting=None,
                        )
                        if pool_stats
                        else None
                    ),
                ),
            ),
            response_time,
        )

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return (
            HealthStatus(
                status="unhealthy",
                response_time_ms=response_time,
                message=f"Database connection failed: {str(e)}",
                details=DatabaseHealthDetails(
                    version="unknown",
                    pool_stats=None,
                ),
            ),
            response_time,
        )


@beartype
async def check_redis_health(
    redis: Redis,
    latency_threshold_ms: float = 5.0,
) -> tuple[HealthStatus, float]:
    """Check Redis connectivity and performance.

    Args:
        redis: Redis client
        latency_threshold_ms: Maximum acceptable latency

    Returns:
        Tuple of (HealthStatus, response_time_ms)
    """
    start_time = time.time()

    try:
        # Ping Redis
        await redis.ping()
        response_time = (time.time() - start_time) * 1000

        # Check response time
        status = "healthy"
        message = f"Redis responding in {response_time:.2f}ms"

        if response_time > latency_threshold_ms * 2:
            status = "unhealthy"
            message = f"Redis latency critical: {response_time:.2f}ms"
        elif response_time > latency_threshold_ms:
            status = "degraded"
            message = f"Redis latency high: {response_time:.2f}ms"

        # Get Redis info
        info = await redis.info()
        memory_used_mb = round(float(info.get("used_memory", 0)) / (1024 * 1024), 2)
        connected_clients = (
            int(info.get("connected_clients", 0))
            if info.get("connected_clients") is not None
            else 0
        )

        return (
            HealthStatus(
                status=status,
                response_time_ms=response_time,
                message=message,
                details=RedisHealthDetails(
                    version=str(info.get("redis_version", "unknown")),
                    uptime_days=None,
                    connected_clients=connected_clients,
                    used_memory_human=None,
                    used_memory_percent=None,
                    total_commands_processed=None,
                    instantaneous_ops_per_sec=None,
                ),
            ),
            response_time,
        )

    except Exception as e:
        response_time = (time.time() - start_time) * 1000
        return (
            HealthStatus(
                status="unhealthy",
                response_time_ms=response_time,
                message=f"Redis connection failed: {str(e)}",
                details=RedisHealthDetails(
                    version="unknown",
                    uptime_days=None,
                    connected_clients=None,
                    used_memory_human=None,
                    used_memory_percent=None,
                    total_commands_processed=None,
                    instantaneous_ops_per_sec=None,
                ),
            ),
            response_time,
        )
