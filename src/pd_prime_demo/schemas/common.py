"""Common schemas used across the API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# Additional models to replace dict usage


class ErrorContext(BaseModel):
    """Additional error context information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    request_id: str | None = Field(None, description="Request ID for correlation")
    user_id: str | None = Field(None, description="User ID associated with error")
    operation: str | None = Field(None, description="Operation being performed")
    resource_id: str | None = Field(None, description="Resource identifier")
    additional_info: dict[str, str] = Field(
        default_factory=dict, description="Additional context info"
    )


class ResponseData(BaseModel):
    """Generic response data structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    result: Any = Field(None, description="Primary result data")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Response metadata"
    )
    links: dict[str, str] = Field(
        default_factory=dict, description="Related resource links"
    )
    pagination: dict[str, Any] | None = Field(
        None, description="Pagination information"
    )


class OperationMetadata(BaseModel):
    """Operation metadata information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    operation_id: str | None = Field(None, description="Unique operation identifier")
    request_id: str | None = Field(None, description="Request tracking ID")
    execution_time_ms: float | None = Field(
        None, ge=0, description="Operation execution time"
    )
    cached: bool = Field(default=False, description="Whether result was cached")
    warnings: list[str] = Field(default_factory=list, description="Operation warnings")
    additional_data: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


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


class ErrorDetail(BaseModel):
    """Individual error detail."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    field: str | None = Field(None, description="Field that caused the error")
    context: ErrorContext | None = Field(None, description="Additional error context")


class ErrorResponse(BaseModel):
    """Standardized error response model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    error: bool = Field(True, description="Indicates this is an error response")
    status_code: int = Field(..., description="HTTP status code")
    message: str = Field(..., description="Primary error message")
    details: list[ErrorDetail] | None = Field(
        None, description="Detailed error information"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Error timestamp"
    )
    request_id: str | None = Field(None, description="Request ID for tracking")


class SuccessResponse(BaseModel):
    """Standardized success response wrapper."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    success: bool = Field(True, description="Indicates successful operation")
    message: str = Field(..., description="Success message")
    data: ResponseData | None = Field(None, description="Response data")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )


class PaginatedResponse(BaseModel):
    """Standardized paginated response wrapper."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    items: list[Any] = Field(..., description="List of items")
    total: int = Field(..., ge=0, description="Total number of items")
    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, description="Items per page")
    pages: int = Field(..., ge=1, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")


class ApiOperation(BaseModel):
    """Standard API operation result."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    operation_id: str = Field(..., description="Unique operation identifier")
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Operation message")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Operation timestamp"
    )
    resource_id: str | None = Field(None, description="Created/modified resource ID")
    resource_type: str | None = Field(None, description="Resource type")
    metadata: OperationMetadata | None = Field(
        None, description="Additional operation metadata"
    )
