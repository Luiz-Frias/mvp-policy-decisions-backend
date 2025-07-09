"""Common response schemas for API endpoints."""

from typing import Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from beartype import beartype

from pd_prime_demo.api.response_patterns import ErrorResponse, SuccessResponse


@beartype
class CreatedResponse(BaseModel):
    """Standard response for resource creation."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    id: UUID = Field(..., description="ID of created resource")
    created_at: datetime = Field(..., description="Creation timestamp")
    message: str = Field(default="Resource created successfully")


@beartype  
class UpdatedResponse(BaseModel):
    """Standard response for resource updates."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    id: UUID = Field(..., description="ID of updated resource")
    updated_at: datetime = Field(..., description="Update timestamp")
    message: str = Field(default="Resource updated successfully")


@beartype
class DeletedResponse(BaseModel):
    """Standard response for resource deletion."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    id: UUID = Field(..., description="ID of deleted resource")
    deleted_at: datetime = Field(..., description="Deletion timestamp")
    message: str = Field(default="Resource deleted successfully")


@beartype
class StatusResponse(BaseModel):
    """Standard response for status operations."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    status: str = Field(..., description="Current status")
    message: str = Field(..., description="Status description")
    details: dict[str, str | int | bool | float | list[str] | None] | None = Field(default=None, description="Additional status details")


@beartype
class ListResponse(BaseModel):
    """Standard response for list operations with pagination."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    items: list[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(default=1, description="Current page number")
    limit: int = Field(default=50, description="Items per page")
    has_more: bool = Field(..., description="Whether more items are available")


# Type aliases for common response patterns
CreatedResult = CreatedResponse | ErrorResponse
UpdatedResult = UpdatedResponse | ErrorResponse  
DeletedResult = DeletedResponse | ErrorResponse
StatusResult = StatusResponse | ErrorResponse
ListResult = ListResponse | ErrorResponse