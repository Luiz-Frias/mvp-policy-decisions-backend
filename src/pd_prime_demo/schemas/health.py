"""Health check schemas."""

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    pass


class ComponentStatus(BaseModel):
    """Individual component health status."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    status: str = Field(..., pattern=r"^(healthy|unhealthy|degraded)$")
    latency_ms: float = Field(..., ge=0, description="Response latency in milliseconds")
    message: str = Field(default="", description="Status message")


class HealthComponents(BaseModel):
    """Health status for all system components."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    database: ComponentStatus = Field(..., description="Database health")
    redis: ComponentStatus = Field(..., description="Redis health")
    api: ComponentStatus = Field(..., description="API health")
