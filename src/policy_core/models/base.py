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
from typing import Any
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

    # ------------------------------------------------------------------
    # Legacy compatibility helpers – treat *any* domain model as a mapping.
    # This allows the existing (v1) test-suite – which still expects plain
    # ``dict`` objects – to interact with Pydantic models transparently while
    # we finish migrating the codebase.  The helpers delegate to
    # ``self.model_dump()`` so the behaviour always reflects the frozen field
    # values without exposing internal implementation details.
    # ------------------------------------------------------------------

    # NOTE: We cannot inherit from ``collections.abc.Mapping`` here because
    # Pydantic’s BaseModel already implements its own ``__iter__`` semantics.
    # Implementing the minimal set of dunder methods is sufficient for most
    # dict-like use cases found in the tests (len(), iteration, membership,
    # bracket access, .items(), .keys(), .values(), .get()).

    def _as_dict(self) -> dict[str, Any]:  # pragma: no cover – helper
        """Return a plain-Python dict of the model fields.

        Separate helper keeps the dict-like wrappers concise and sidesteps
        Pydantic’s internal mapping implementation.  We avoid memoisation
        here to prevent potential edge-cases with recursive models and keep
        the implementation straightforward.
        """
        return self.model_dump()

    # Mapping dunder helpers -------------------------------------------------

    def __getitem__(self, item: str):  # type: ignore[override]
        return self._as_dict()[item]

    def __iter__(self):  # type: ignore[override]
        return iter(self._as_dict())

    def __len__(self):  # type: ignore[override]
        return len(self._as_dict())

    # Convenience accessors --------------------------------------------------

    def items(self):  # type: ignore[override]
        return self._as_dict().items()

    def keys(self):  # type: ignore[override]
        return self._as_dict().keys()

    def values(self):  # type: ignore[override]
        return self._as_dict().values()

    def get(self, key: str, default=None):  # type: ignore[override]
        return self._as_dict().get(key, default)

    def __contains__(self, item: object) -> bool:  # type: ignore[override]
        return item in self._as_dict()

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
