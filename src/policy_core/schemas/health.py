# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

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
