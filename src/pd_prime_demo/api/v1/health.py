"""Health check endpoints for monitoring system status.

This module provides health check endpoints that verify the status
of all system components including database, Redis, and external services.
"""

from datetime import datetime

import asyncpg
from beartype import beartype
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from redis.asyncio import Redis

from ...core.config import Settings, get_settings
from ...schemas.health_details import (
    CPUHealthDetails,
    DatabaseHealthDetails,
    HealthDetails,
    MemoryHealthDetails,
    RedisHealthDetails,
)
from ..dependencies import get_db, get_redis

router = APIRouter()


class HealthStatus(BaseModel):
    """Individual component health status."""

    model_config = ConfigDict(frozen=True)

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

    model_config = ConfigDict(frozen=True, extra="allow")

    # We use extra="allow" to support dynamic component names
    # but all values must be HealthStatus instances

    def __init__(self, **data: HealthStatus) -> None:
        """Initialize with validation that all values are HealthStatus instances."""
        for key, value in data.items():
            if not isinstance(value, HealthStatus):
                raise ValueError(f"Component '{key}' must be a HealthStatus instance")
        super().__init__(**data)


class HealthResponse(BaseModel):
    """Overall system health response."""

    model_config = ConfigDict(frozen=True)

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


@router.get("/health", response_model=HealthResponse)
@beartype
async def health_check(
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Perform basic health check endpoint.

    Returns:
        HealthResponse: System health status
    """
    uptime = (datetime.utcnow() - APP_START_TIME).total_seconds()

    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0",  # TODO: Get from package version
        environment=settings.api_env,
        components=ComponentHealthMap(
            api=HealthStatus(
                status="healthy", response_time_ms=0.1, message="API operational"
            )
        ),
        uptime_seconds=uptime,
        total_response_time_ms=0.1,
    )


@router.get("/health/live", response_model=HealthStatus)
@beartype
async def liveness_check() -> HealthStatus:
    """Kubernetes liveness probe endpoint.

    Returns:
        HealthStatus: Simple liveness status
    """
    return HealthStatus(
        status="healthy", message="Application is running", response_time_ms=None
    )


@router.get("/health/ready", response_model=HealthResponse)
@beartype
async def readiness_check(
    db: asyncpg.Connection = Depends(get_db),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Kubernetes readiness probe endpoint with dependency checks.

    Args:
        db: Database session
        redis: Redis client
        settings: Application settings

    Returns:
        HealthResponse: Detailed system health with all components
    """
    component_statuses = {}
    total_response_time = 0.0
    overall_status = "healthy"

    # Check database health
    db_start = datetime.utcnow()
    try:
        await db.fetchval("SELECT 1")
        db_response_time = (datetime.utcnow() - db_start).total_seconds() * 1000

        component_statuses["database"] = HealthStatus(
            status="healthy",
            response_time_ms=db_response_time,
            message="PostgreSQL connection successful",
            details=None,
        )
        total_response_time += db_response_time

    except Exception as e:
        db_response_time = (datetime.utcnow() - db_start).total_seconds() * 1000
        component_statuses["database"] = HealthStatus(
            status="unhealthy",
            response_time_ms=db_response_time,
            message=f"Database connection failed: {str(e)}",
            details=None,
        )
        overall_status = "unhealthy"
        total_response_time += db_response_time

    # Check Redis health
    redis_start = datetime.utcnow()
    try:
        await redis.ping()
        redis_info = await redis.info()
        redis_response_time = (datetime.utcnow() - redis_start).total_seconds() * 1000

        # Extract Redis info with type safety
        redis_version = redis_info.get("redis_version")
        redis_memory = redis_info.get("used_memory_human")

        component_statuses["redis"] = HealthStatus(
            status="healthy",
            response_time_ms=redis_response_time,
            message="Redis connection successful",
            details=RedisHealthDetails(
                version=redis_version if isinstance(redis_version, str) else "unknown",
                uptime_days=redis_info.get("uptime_in_days"),
                connected_clients=redis_info.get("connected_clients", 0),
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
        redis_response_time = (datetime.utcnow() - redis_start).total_seconds() * 1000
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
        # TODO: Implement OpenAI health check
        component_statuses["openai"] = HealthStatus(
            status="healthy", message="OpenAI API key configured", response_time_ms=None
        )

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

    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version="1.0.0",  # TODO: Get from package version
        environment=settings.api_env,
        components=ComponentHealthMap(**component_statuses),
        uptime_seconds=uptime,
        total_response_time_ms=total_response_time,
    )


@router.get("/health/detailed", response_model=HealthResponse)
@beartype
async def detailed_health_check(
    db: asyncpg.Connection = Depends(get_db),
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
        # Test query
        db_version = await db.fetchval("SELECT version()")

        # Get pool stats from connection
        pool_stats = None  # Pool stats structure varies by DB implementation
        # asyncpg connections don't directly expose pool stats
        # This would need to be implemented at the Database class level

        db_response_time = (datetime.utcnow() - db_start).total_seconds() * 1000

        component_statuses["database"] = HealthStatus(
            status="healthy",
            response_time_ms=db_response_time,
            message="PostgreSQL operational",
            details=DatabaseHealthDetails(version=db_version, pool_stats=pool_stats),
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

        # Check Redis memory usage
        used_memory_percent = 0.0
        if "used_memory" in redis_info and "maxmemory" in redis_info:
            if redis_info["maxmemory"] > 0:
                used_memory_percent = (
                    redis_info["used_memory"] / redis_info["maxmemory"]
                ) * 100

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
                version=redis_info.get("redis_version", "unknown"),
                uptime_days=redis_info.get("uptime_in_days", 0),
                connected_clients=redis_info.get("connected_clients", 0),
                used_memory_human=redis_info.get("used_memory_human", "unknown"),
                used_memory_percent=round(used_memory_percent, 2),
                total_commands_processed=redis_stats.get("total_commands_processed", 0),
                instantaneous_ops_per_sec=redis_stats.get(
                    "instantaneous_ops_per_sec", 0
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

    # Memory usage check
    import psutil

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
            count=psutil.cpu_count() or 1,  # Ensure we have a valid count
            percent=cpu_percent,
        ),
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
        version="1.0.0",  # TODO: Get from package version
        environment=settings.api_env,
        components=ComponentHealthMap(**component_statuses),
        uptime_seconds=uptime,
        total_response_time_ms=total_response_time,
    )
