"""Common schemas used across the API."""

from datetime import datetime
from typing import Generic, TypeVar
from decimal import Decimal

from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Type variable for generic models
T = TypeVar("T")

# Additional models to replace dict usage


class AdditionalInfo(BaseModel):
    """Additional information key-value pairs."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    key: str = Field(..., min_length=1, max_length=100, description="Information key")
    value: str = Field(..., min_length=1, max_length=1000, description="Information value")


class ResourceLink(BaseModel):
    """Resource link information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    rel: str = Field(..., min_length=1, max_length=50, description="Link relation")
    href: str = Field(..., min_length=1, max_length=2000, description="Link URL")
    method: str = Field(default="GET", description="HTTP method for the link")
    title: str | None = Field(None, max_length=200, description="Link title")


class PaginationInfo(BaseModel):
    """Pagination information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, le=1000, description="Items per page")
    total: int = Field(..., ge=0, description="Total number of items")
    pages: int = Field(..., ge=1, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")


class MetadataItem(BaseModel):
    """Generic metadata item."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    key: str = Field(..., min_length=1, max_length=100, description="Metadata key")
    value: str | int | float | bool | None = Field(..., description="Metadata value")
    type: str = Field(default="string", description="Value type")


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
    additional_info: list[AdditionalInfo] = Field(
        default_factory=list, description="Additional context info"
    )


class ResponseData(BaseModel, Generic[T]):
    """Generic response data structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    result: T | None = Field(None, description="Primary result data")
    metadata: list[MetadataItem] = Field(
        default_factory=list, description="Response metadata"
    )
    links: list[ResourceLink] = Field(
        default_factory=list, description="Related resource links"
    )
    pagination: PaginationInfo | None = Field(
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
    additional_data: list[MetadataItem] = Field(
        default_factory=list, description="Additional metadata"
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


class SuccessResponse(BaseModel, Generic[T]):
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
    data: ResponseData[T] | None = Field(None, description="Response data")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized paginated response wrapper."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    items: list[T] = Field(..., description="List of items")
    pagination: PaginationInfo = Field(..., description="Pagination information")
    metadata: list[MetadataItem] = Field(
        default_factory=list, description="Response metadata"
    )
    links: list[ResourceLink] = Field(
        default_factory=list, description="Related resource links"
    )


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


# Common domain models for reuse across schemas


class Money(BaseModel):
    """Money value with currency."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    amount: Decimal = Field(..., decimal_places=2, description="Monetary amount")
    currency: str = Field(default="USD", min_length=3, max_length=3, description="Currency code")


class Address(BaseModel):
    """Standard address model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    street_address: str = Field(..., min_length=1, max_length=200, description="Street address")
    city: str = Field(..., min_length=1, max_length=100, description="City")
    state: str = Field(..., min_length=2, max_length=50, description="State or province")
    postal_code: str = Field(..., min_length=1, max_length=20, description="Postal code")
    country: str = Field(default="US", min_length=2, max_length=3, description="Country code")


class ContactInfo(BaseModel):
    """Contact information model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    email: str | None = Field(None, max_length=320, description="Email address")
    phone: str | None = Field(None, max_length=20, description="Phone number")
    mobile: str | None = Field(None, max_length=20, description="Mobile number")


class DateRange(BaseModel):
    """Date range model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: datetime, info: Any) -> datetime:
        """Ensure end_date is after start_date."""
        if hasattr(info, "data") and "start_date" in info.data and v <= info.data["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class Status(BaseModel):
    """Generic status model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    code: str = Field(..., min_length=1, max_length=50, description="Status code")
    name: str = Field(..., min_length=1, max_length=100, description="Status name")
    description: str | None = Field(None, max_length=500, description="Status description")
    is_active: bool = Field(default=True, description="Whether status is active")


class Audit(BaseModel):
    """Audit trail information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    created_by: str | None = Field(None, description="User who created the record")
    updated_at: datetime | None = Field(None, description="Last update timestamp")
    updated_by: str | None = Field(None, description="User who last updated the record")
    version: int = Field(default=1, ge=1, description="Record version number")


class ValidationResult(BaseModel):
    """Validation result model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    is_valid: bool = Field(..., description="Whether validation passed")
    errors: list[ErrorDetail] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")


class SearchCriteria(BaseModel):
    """Search criteria model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    query: str | None = Field(None, max_length=500, description="Search query")
    filters: list[MetadataItem] = Field(default_factory=list, description="Search filters")
    sort_by: str | None = Field(None, max_length=100, description="Sort field")
    sort_order: str = Field(default="asc", description="Sort order (asc/desc)")
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=50, ge=1, le=1000, description="Items per page")
