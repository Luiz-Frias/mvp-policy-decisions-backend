"""Common schemas used across the API."""

from pydantic import BaseModel, ConfigDict, Field


class APIInfo(BaseModel):
    """API information response."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    name: str = Field(..., description="API name")
    version: str = Field(..., description="API version")
    status: str = Field(..., description="API status")
    environment: str = Field(..., description="Environment name")


class PolicySummary(BaseModel):
    """Summary information for a policy."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    id: str = Field(..., description="Policy ID")
    policy_number: str = Field(..., description="Policy number")
    policy_type: str = Field(..., description="Policy type")
    status: str = Field(..., description="Policy status")
    effective_date: str = Field(..., description="Effective date ISO string")
    expiration_date: str = Field(..., description="Expiration date ISO string")


class HealthDetail(BaseModel):
    """Health check detail information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    status: str = Field(..., description="Component status")
    latency_ms: float | None = Field(None, description="Latency in milliseconds")
    error: str | None = Field(None, description="Error message if any")


class HealthMetadata(BaseModel):
    """Health check metadata."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    cpu_percent: float | None = Field(None, description="CPU usage percentage")
    memory_mb: float | None = Field(None, description="Memory usage in MB")
    uptime_seconds: float | None = Field(None, description="Uptime in seconds")
    connections: int | None = Field(None, description="Active connections")
