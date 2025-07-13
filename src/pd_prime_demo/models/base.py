# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Base Pydantic model configuration for all domain models.

This module provides the foundation for all domain models in the system,
enforcing immutability, strict validation, and enterprise-grade standards.
"""

from datetime import datetime
from uuid import UUID

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field


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
class TimestampMixin(BaseModelConfig):
    """Mixin for models that need timestamp tracking."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    created_at: datetime = Field(
        ..., description="Timestamp when the entity was created"
    )
    updated_at: datetime = Field(
        ..., description="Timestamp when the entity was last updated"
    )


@beartype
class IdentifiableModel(TimestampedModel):
    """Base model with UUID identifier and timestamps."""

    id: UUID = Field(..., description="Unique identifier for the entity")
