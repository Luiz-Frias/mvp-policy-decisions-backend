"""Models for handling update data structures.

This module provides strongly-typed Pydantic models that replace generic
dictionary usage in the codebase.

The goal is to enforce type safety and runtime validation at every layer.
"""

from collections.abc import Mapping
from typing import Any  # SYSTEM_BOUNDARY: PostgreSQL JSONB interface

from beartype import beartype
from pydantic import Field, model_validator

from .base import BaseModelConfig


@beartype
# Inherits frozen=True from BaseModelConfig
class CustomerUpdateData(BaseModelConfig):
    """Strongly-typed model for customer update data used in JSONB operations.

    This model represents the data structure that will be merged into the
    customer JSONB column during update operations. All fields are optional
    to support partial updates.
    """

    email: str | None = Field(None, description="Updated email address")
    phone_number: str | None = Field(None, description="Updated phone number")
    address_line1: str | None = Field(
        None,
        description="Updated primary address line",
    )
    address_line2: str | None = Field(
        None, description="Updated secondary address line"
    )
    city: str | None = Field(None, description="Updated city name")
    state_province: str | None = Field(
        None,
        description="Updated state or province",
    )
    postal_code: str | None = Field(
        None,
        description="Updated postal or ZIP code",
    )
    marketing_consent: bool | None = Field(
        None, description="Updated marketing consent"
    )

    @model_validator(mode="after")
    @beartype
    def validate_not_empty(self) -> "CustomerUpdateData":
        """Ensure at least one field is provided for update."""
        if not any(getattr(self, field) is not None for field in self.model_fields):
            raise ValueError("At least one field must be provided for update")
        return self

    @beartype
    def to_jsonb_update(self) -> "CustomerUpdateData":
        """Return a new instance with only non-None values for JSONB update.

        Returns:
            CustomerUpdateData instance containing only the fields to be updated
        """
        # Create a new instance with only non-None values
        non_none_data = {k: v for k, v in self.model_dump().items() if v is not None}
        return CustomerUpdateData(**non_none_data)

    def model_dump_non_none(
        self,
    ) -> Mapping[str, Any]:
        # SYSTEM_BOUNDARY: PostgreSQL JSONB (read-only mapping)
        """Get model data excluding None values for JSONB operations.

        This method is used internally for database operations where we need
        the raw dictionary representation without ``None`` values.

        Note: This returns a ``Mapping[str, Any]`` at the system boundary for
        database JSONB operations. This is the only acceptable use of a raw
        key/value mapping.

        It interfaces directly with the PostgreSQL driver's expectations.
        """
        # System boundary: PostgreSQL JSONB expects dict format
        return {k: v for k, v in self.model_dump().items() if v is not None}
