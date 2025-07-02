"""Base Pydantic model configuration for all domain models.

This module provides the foundation for all domain models in the system,
enforcing immutability, strict validation, and enterprise-grade standards.
"""

from datetime import datetime

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field
from pydantic.types import UUID4


@beartype
class BaseModelConfig(BaseModel):
    """Base model with strict configuration for all domain entities.

    Enforces:
    - Immutability (frozen=True)
    - No extra fields allowed (extra="forbid")
    - Validation on assignment
    - Automatic whitespace stripping
    - Timezone-aware datetime handling
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
        use_enum_values=True,
        arbitrary_types_allowed=False,
        json_encoders={
            datetime: lambda v: v.isoformat(),
        },
    )


@beartype
class TimestampedModel(BaseModelConfig):
    """Base model with automatic timestamp fields."""

    created_at: datetime = Field(
        ..., description="Timestamp when the entity was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the entity was last updated"
    )


@beartype
class IdentifiableModel(TimestampedModel):
    """Base model with UUID identifier and timestamps."""

    id: UUID4 = Field(..., description="Unique identifier for the entity")
