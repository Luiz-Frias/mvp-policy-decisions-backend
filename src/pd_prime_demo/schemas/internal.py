"""Internal schemas for system boundaries where dict is allowed."""

from typing import List

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
