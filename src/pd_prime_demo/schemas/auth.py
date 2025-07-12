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
    client_id: str = Field(..., description="OAuth2 client identifier")
    scopes: list[str] = Field(default_factory=list, description="User permissions")


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
