# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Internal schemas for system boundaries where dict is allowed."""

from pydantic import BaseModel, ConfigDict, Field


class JWTDecodeResult(BaseModel):
    """JWT decode result at system boundary."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    sub: str = Field(..., description="Subject")
    exp: int = Field(..., description="Expiration timestamp")
    iat: int = Field(..., description="Issued at timestamp")
    jti: str = Field(..., description="JWT ID")
    type: str = Field(default="access", description="Token type")
    scopes: list[str] = Field(default_factory=list, description="Scopes")
