# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Elite API response patterns following Result[T,E] + HTTP semantics."""

from typing import Generic, TypeVar, Union, cast

from beartype import beartype
from fastapi import Response
from pydantic import BaseModel, ConfigDict, Field

from policy_core.core.result_types import Result
from policy_core.models.base import BaseModelConfig

# Auto-generated models


@beartype
class FieldErrorsMapping(BaseModelConfig):
    """Structured model replacing dict[str, str] usage."""

    key: str = Field(..., min_length=1, description="Mapping key")
    value: str = Field(..., min_length=1, description="Mapping value")


T = TypeVar("T")


@beartype
class ErrorDetails(BaseModel):
    """Structured error details to replace dict[str, Any] usage."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    error_code: str | None = Field(
        default=None, description="Machine-readable error code"
    )
    field_errors: FieldErrorsMapping | None = Field(
        default=None, description="Field-specific validation errors"
    )
    validation_errors: list[str] | None = Field(
        default=None, description="General validation error messages"
    )
    context: dict[str, str | int | bool | float | None] | None = Field(
        default=None, description="Additional error context"
    )
    request_id: str | None = Field(default=None, description="Request ID for debugging")
    timestamp: str | None = Field(default=None, description="Error timestamp")
    suggestion: str | None = Field(
        default=None, description="Suggested fix for the error"
    )


@beartype
class ValidationErrorDetails(BaseModel):
    """Structured validation error details for form/request validation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    field: str = Field(..., description="Field name that failed validation")
    message: str = Field(..., description="Human-readable error message")
    rejected_value: str | int | float | bool | None = Field(
        default=None, description="The value that was rejected"
    )
    constraint: str | None = Field(
        default=None, description="Constraint that was violated"
    )
    location: list[str] | None = Field(
        default=None, description="Path to the field in nested objects"
    )


@beartype
class StatusDetails(BaseModel):
    """Structured status details for status operations."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    status_code: str | None = Field(
        default=None, description="Machine-readable status code"
    )
    substatus: str | None = Field(
        default=None, description="Detailed substatus information"
    )
    progress: int | None = Field(
        default=None, description="Progress percentage (0-100)"
    )
    completion_time: str | None = Field(
        default=None, description="Estimated completion time"
    )
    affected_resources: list[str] | None = Field(
        default=None, description="List of affected resource IDs"
    )
    metrics: dict[str, str | int | bool | float | None] | None = Field(
        default=None, description="Status metrics"
    )
    warnings: list[str] | None = Field(
        default=None, description="Non-critical warnings"
    )
    next_action: str | None = Field(default=None, description="Suggested next action")


@beartype
class HealthMetrics(BaseModel):
    """Structured health metrics for health check operations."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    cpu_usage_percent: float | None = Field(
        default=None, description="CPU usage percentage"
    )
    memory_usage_mb: int | None = Field(default=None, description="Memory usage in MB")
    disk_usage_percent: float | None = Field(
        default=None, description="Disk usage percentage"
    )
    connection_count: int | None = Field(
        default=None, description="Active connection count"
    )
    request_count: int | None = Field(default=None, description="Request count")
    error_count: int | None = Field(default=None, description="Error count")
    uptime_seconds: float | None = Field(
        default=None, description="Component uptime in seconds"
    )
    version: str | None = Field(default=None, description="Component version")
    custom_metrics: dict[str, str | int | bool | float | None] | None = Field(
        default=None, description="Custom component metrics"
    )


@beartype
class ErrorResponse(BaseModel):
    """Standardized error response for business logic failures."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    success: bool = Field(default=False, description="Always false for error responses")
    error: str = Field(..., description="Human-readable error message")
    error_code: str | None = Field(
        default=None, description="Machine-readable error code"
    )
    details: ErrorDetails | None = Field(
        default=None, description="Structured error details"
    )


@beartype
class SuccessResponse(BaseModel, Generic[T]):
    """Standardized success response wrapper."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    success: bool = Field(default=True, description="Always true for success responses")
    data: T = Field(..., description="Response payload")


class APIResponseHandler:
    """Elite API response handler implementing Result[T,E] + HTTP semantics pattern."""

    @staticmethod
    @beartype
    def map_error_to_status(error: str) -> int:
        """Map business logic errors to appropriate HTTP status codes.

        Args:
            error: Business logic error message

        Returns:
            HTTP status code following RESTful conventions
        """
        error_lower = error.lower()

        # Resource not found
        if any(
            phrase in error_lower
            for phrase in ["not found", "does not exist", "missing"]
        ):
            return 404

        # Authorization failures
        if any(
            phrase in error_lower
            for phrase in ["unauthorized", "not authorized", "access denied"]
        ):
            return 401

        # Permission failures
        if any(
            phrase in error_lower
            for phrase in ["forbidden", "insufficient permissions", "not allowed"]
        ):
            return 403

        # Validation failures
        if any(
            phrase in error_lower
            for phrase in [
                "validation",
                "invalid",
                "malformed",
                "bad request",
                "required field",
            ]
        ):
            return 400

        # Conflict states
        if any(
            phrase in error_lower
            for phrase in [
                "already exists",
                "conflict",
                "duplicate",
                "concurrent modification",
            ]
        ):
            return 409

        # Rate limiting
        if any(
            phrase in error_lower
            for phrase in ["rate limit", "too many requests", "throttled"]
        ):
            return 429

        # Default to 422 for business logic errors
        return 422

    @staticmethod
    @beartype
    def from_result(
        result: Result[T, str], response: Response, success_status: int = 200
    ) -> T | ErrorResponse:
        """Convert Result[T,E] to HTTP response with proper status codes.

        Args:
            result: Service layer Result
            response: FastAPI Response object to set status code
            success_status: HTTP status for successful operations (default 200)

        Returns:
            Either the unwrapped success value or ErrorResponse
        """
        if result.is_err():
            error_msg = result.unwrap_err()
            response.status_code = APIResponseHandler.map_error_to_status(error_msg)
            return ErrorResponse(error=error_msg)

        response.status_code = success_status
        return result.unwrap()

    @staticmethod
    @beartype
    def from_result_wrapped(
        result: Result[T, str], response: Response, success_status: int = 200
    ) -> SuccessResponse[T] | ErrorResponse:
        """Convert Result[T,E] to wrapped response format.

        Args:
            result: Service layer Result
            response: FastAPI Response object to set status code
            success_status: HTTP status for successful operations

        Returns:
            Either SuccessResponse[T] or ErrorResponse
        """
        if result.is_err():
            error_msg = result.unwrap_err()
            response.status_code = APIResponseHandler.map_error_to_status(error_msg)
            return ErrorResponse(error=error_msg)

        response.status_code = success_status
        return SuccessResponse(data=result.unwrap())


# Convenience type aliases for common response patterns
# These are generic aliases that need to be parameterized when used


@beartype
class PaginationInfo(BaseModel):
    """Structured pagination information for list responses."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total number of items")
    has_more: bool = Field(..., description="Whether more items are available")
    total_pages: int = Field(..., description="Total number of pages")
    first_page: int = Field(default=1, description="First page number")
    last_page: int = Field(..., description="Last page number")
    prev_page: int | None = Field(default=None, description="Previous page number")
    next_page: int | None = Field(default=None, description="Next page number")


@beartype
class ApiMetadata(BaseModel):
    """Structured metadata for API responses."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    request_id: str | None = Field(default=None, description="Request ID for tracing")
    timestamp: str | None = Field(default=None, description="Response timestamp")
    api_version: str | None = Field(default=None, description="API version")
    response_time_ms: float | None = Field(
        default=None, description="Response time in milliseconds"
    )
    rate_limit_remaining: int | None = Field(
        default=None, description="Remaining rate limit"
    )
    rate_limit_reset: str | None = Field(
        default=None, description="Rate limit reset time"
    )
    warnings: list[str] | None = Field(
        default=None, description="Non-critical warnings"
    )
    cache_status: str | None = Field(default=None, description="Cache hit/miss status")


# Convenience functions for common patterns
@beartype
def handle_result(
    result: Result[T, str], response: Response, success_status: int = 200
) -> T | ErrorResponse:
    """Convenience function for standard result handling."""
    # Type assertion to satisfy mypy - we know T won't be ErrorResponse here
    return APIResponseHandler.from_result(
        cast(Result[Union[T, ErrorResponse], str], result), response, success_status
    )


@beartype
def handle_result_wrapped(
    result: Result[T, str], response: Response, success_status: int = 200
) -> SuccessResponse[T] | ErrorResponse:
    """Convenience function for wrapped result handling."""
    return APIResponseHandler.from_result_wrapped(result, response, success_status)


@beartype
def create_error_details(
    error_code: str | None = None,
    field_errors: FieldErrorsMapping | None = None,
    validation_errors: list[str] | None = None,
    context: dict[str, str | int | bool | float | None] | None = None,
    request_id: str | None = None,
    timestamp: str | None = None,
    suggestion: str | None = None,
) -> ErrorDetails:
    """Create structured error details."""
    return ErrorDetails(
        error_code=error_code,
        field_errors=field_errors,
        validation_errors=validation_errors,
        context=context,
        request_id=request_id,
        timestamp=timestamp,
        suggestion=suggestion,
    )


@beartype
def create_status_details(
    status_code: str | None = None,
    substatus: str | None = None,
    progress: int | None = None,
    completion_time: str | None = None,
    affected_resources: list[str] | None = None,
    metrics: dict[str, str | int | bool | float | None] | None = None,
    warnings: list[str] | None = None,
    next_action: str | None = None,
) -> StatusDetails:
    """Create structured status details."""
    return StatusDetails(
        status_code=status_code,
        substatus=substatus,
        progress=progress,
        completion_time=completion_time,
        affected_resources=affected_resources,
        metrics=metrics,
        warnings=warnings,
        next_action=next_action,
    )


@beartype
def create_health_metrics(
    cpu_usage_percent: float | None = None,
    memory_usage_mb: int | None = None,
    disk_usage_percent: float | None = None,
    connection_count: int | None = None,
    request_count: int | None = None,
    error_count: int | None = None,
    uptime_seconds: float | None = None,
    version: str | None = None,
    custom_metrics: dict[str, str | int | bool | float | None] | None = None,
) -> HealthMetrics:
    """Create structured health metrics."""
    return HealthMetrics(
        cpu_usage_percent=cpu_usage_percent,
        memory_usage_mb=memory_usage_mb,
        disk_usage_percent=disk_usage_percent,
        connection_count=connection_count,
        request_count=request_count,
        error_count=error_count,
        uptime_seconds=uptime_seconds,
        version=version,
        custom_metrics=custom_metrics,
    )


@beartype
def create_pagination_info(
    page: int, limit: int, total: int, first_page: int = 1
) -> PaginationInfo:
    """Create pagination information with calculated fields."""
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    has_more = page < total_pages
    last_page = max(total_pages, 1)
    prev_page = page - 1 if page > first_page else None
    next_page = page + 1 if has_more else None

    return PaginationInfo(
        page=page,
        limit=limit,
        total=total,
        has_more=has_more,
        total_pages=total_pages,
        first_page=first_page,
        last_page=last_page,
        prev_page=prev_page,
        next_page=next_page,
    )


@beartype
def create_api_metadata(
    request_id: str | None = None,
    timestamp: str | None = None,
    api_version: str | None = None,
    response_time_ms: float | None = None,
    rate_limit_remaining: int | None = None,
    rate_limit_reset: str | None = None,
    warnings: list[str] | None = None,
    cache_status: str | None = None,
) -> ApiMetadata:
    """Create API metadata."""
    return ApiMetadata(
        request_id=request_id,
        timestamp=timestamp,
        api_version=api_version,
        response_time_ms=response_time_ms,
        rate_limit_remaining=rate_limit_remaining,
        rate_limit_reset=rate_limit_reset,
        warnings=warnings,
        cache_status=cache_status,
    )
