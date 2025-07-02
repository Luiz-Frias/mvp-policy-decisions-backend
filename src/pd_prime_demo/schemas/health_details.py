"""Health check detail schemas for component-specific information."""

from typing import Union

from pydantic import BaseModel, ConfigDict, Field


class DatabasePoolStats(BaseModel):
    """Database connection pool statistics."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    size: int | None = Field(
        None, ge=0, description="Total size of the connection pool"
    )
    available: int | None = Field(
        None, ge=0, description="Number of available connections in the pool"
    )
    in_use: int | None = Field(
        None, ge=0, description="Number of connections currently in use"
    )
    waiting: int | None = Field(
        None, ge=0, description="Number of requests waiting for a connection"
    )


class DatabaseHealthDetails(BaseModel):
    """Detailed health information for database component."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    version: str = Field(..., description="Database version string")
    pool_stats: DatabasePoolStats | None = Field(
        None, description="Connection pool statistics"
    )


class RedisHealthDetails(BaseModel):
    """Detailed health information for Redis component."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    version: str = Field(..., description="Redis version")
    uptime_days: int | None = Field(
        None, ge=0, description="Redis server uptime in days"
    )
    connected_clients: int | None = Field(
        None, ge=0, description="Number of connected clients"
    )
    used_memory_human: str | None = Field(
        None, description="Human-readable memory usage"
    )
    used_memory_percent: float | None = Field(
        None, ge=0, le=100, description="Memory usage percentage"
    )
    total_commands_processed: int | None = Field(
        None, ge=0, description="Total number of commands processed"
    )
    instantaneous_ops_per_sec: int | None = Field(
        None, ge=0, description="Current operations per second"
    )


class SystemResourceDetails(BaseModel):
    """System resource health details."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    total_gb: float | None = Field(
        None, ge=0, description="Total resource in GB (memory/disk)"
    )
    available_gb: float | None = Field(
        None, ge=0, description="Available resource in GB"
    )
    used_percent: float | None = Field(
        None, ge=0, le=100, description="Usage percentage"
    )


class CPUHealthDetails(BaseModel):
    """CPU health details."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    count: int | None = Field(None, ge=1, description="Number of CPU cores")
    percent: float | None = Field(
        None, ge=0, le=100, description="CPU usage percentage"
    )


class MemoryHealthDetails(BaseModel):
    """Memory health details."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    total_gb: float = Field(..., ge=0, description="Total memory in GB")
    available_gb: float = Field(..., ge=0, description="Available memory in GB")
    used_percent: float = Field(
        ..., ge=0, le=100, description="Memory usage percentage"
    )


# Union type for all possible health details
HealthDetails = Union[
    RedisHealthDetails,
    DatabaseHealthDetails,
    MemoryHealthDetails,
    CPUHealthDetails,
    SystemResourceDetails,
]
