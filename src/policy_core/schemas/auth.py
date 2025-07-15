# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Authentication schemas."""

from pydantic import BaseModel, ConfigDict, Field


class CurrentUser(BaseModel):
    """Current authenticated user information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    user_id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="User email")
    client_id: str | None = Field(default=None, description="OAuth2 client identifier")
    scopes: list[str] = Field(default_factory=list, description="User permissions")

    # ------------------------------------------------------------------
    # Legacy dict-style access shim ------------------------------------------------
    # Several older API handlers still expect `current_user["sub"]` or similar.
    # Pydantic models are not subscriptable by default, so we provide a minimal
    # mapping interface that forwards to attribute access.  This should be
    # removed once all handlers are updated to dot-notation.
    # ------------------------------------------------------------------

    def __getitem__(self, item: str):  # type: ignore[override]
        """Allow legacy dict-style key access.

        Keys like "sub" map to ``user_id`` for backward compatibility.
        """
        mapping = {
            "sub": "user_id",
            "user_id": "user_id",
            "username": "username",
            "email": "email",
            "client_id": "client_id",
            "scopes": "scopes",
        }
        attr = mapping.get(item, item)
        if not hasattr(self, attr):
            raise KeyError(item)
        return getattr(self, attr)

    def get(self, item: str, default=None):  # noqa: D401
        """Dict-like ``get`` helper for legacy code."""
        try:
            return self[item]
        except KeyError:
            return default


class JWTPayload(BaseModel):
    """JWT token payload."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    sub: str = Field(..., description="Subject (user ID)")
    exp: int = Field(..., description="Expiration timestamp")
    iat: int = Field(..., description="Issued at timestamp")
    jti: str = Field(..., description="JWT ID")
    client_id: str = Field(..., description="OAuth2 client identifier")
    type: str = Field(default="access", description="Token type")
    scopes: list[str] = Field(default_factory=list, description="Permission scopes")
