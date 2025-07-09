"""Security utilities for JWT, password hashing, and authentication."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from attrs import field, frozen
from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

from ..models.base import BaseModelConfig
from ..schemas.internal import JWTDecodeResult
from .config import get_settings

# Auto-generated models


@beartype
class PayloadData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@frozen
class TokenPayload:
    """Immutable JWT token payload."""

    sub: str = field()  # Subject (user ID)
    exp: datetime = field()  # Expiration time
    iat: datetime = field()  # Issued at time
    jti: str = field()  # JWT ID for token revocation
    type: str = field(default="access")  # Token type
    scopes: list[str] = field(factory=list)  # Permission scopes


class TokenData(BaseModel):
    """Token data for API responses."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration


class Security:
    """Security utilities for authentication and authorization."""

    def __init__(self) -> None:
        """Initialize security utilities."""
        settings = get_settings()
        self._secret_key = settings.secret_key
        self._jwt_secret = settings.jwt_secret
        self._jwt_algorithm = settings.jwt_algorithm
        self._jwt_expiration_minutes = settings.jwt_expiration_minutes
        self._bcrypt_rounds = 12

    @beartype
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")

        password_bytes = password.encode("utf-8")
        salt = bcrypt.gensalt(rounds=self._bcrypt_rounds)
        hashed = bcrypt.hashpw(password_bytes, salt)
        # Type cast to handle bcrypt returning Any due to missing type stubs
        return str(hashed.decode("utf-8"))

    @beartype
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        try:
            password_bytes = password.encode("utf-8")
            hashed_bytes = hashed_password.encode("utf-8")
            # Type cast to handle bcrypt returning Any due to missing type stubs
            return bool(bcrypt.checkpw(password_bytes, hashed_bytes))
        except Exception:
            return False

    @beartype
    def create_access_token(
        self,
        subject: str,
        scopes: list[str] | None = None,
        expires_delta: timedelta | None = None,
    ) -> TokenData:
        """Create JWT access token."""
        now = datetime.now(timezone.utc)

        if expires_delta is None:
            expires_delta = timedelta(minutes=self._jwt_expiration_minutes)

        expire = now + expires_delta

        payload = {
            "sub": subject,
            "exp": expire,
            "iat": now,
            "jti": self._generate_jti(),
            "type": "access",
            "scopes": scopes or [],
        }

        token = jwt.encode(
            payload,
            self._jwt_secret,
            algorithm=self._jwt_algorithm,
        )

        return TokenData(
            access_token=token,
            expires_in=int(expires_delta.total_seconds()),
        )

    @beartype
    def decode_token(self, token: str) -> TokenPayload | None:
        """Decode and validate JWT token."""
        try:
            payload = jwt.decode(
                token,
                self._jwt_secret,
                algorithms=[self._jwt_algorithm],
            )

            return TokenPayload(
                sub=payload["sub"],
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
                jti=payload["jti"],
                type=payload.get("type", "access"),
                scopes=payload.get("scopes", []),
            )
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception:
            return None

    @beartype
    def _generate_jti(self) -> str:
        """Generate unique JWT ID."""
        import uuid

        return str(uuid.uuid4())

    @beartype
    def has_scope(self, token_payload: TokenPayload, required_scope: str) -> bool:
        """Check if token has required scope."""
        return required_scope in token_payload.scopes

    @beartype
    def has_any_scope(
        self,
        token_payload: TokenPayload,
        required_scopes: list[str],
    ) -> bool:
        """Check if token has any of the required scopes."""
        return any(scope in token_payload.scopes for scope in required_scopes)

    @beartype
    def has_all_scopes(
        self,
        token_payload: TokenPayload,
        required_scopes: list[str],
    ) -> bool:
        """Check if token has all required scopes."""
        return all(scope in token_payload.scopes for scope in required_scopes)

    @beartype
    def generate_api_key(self) -> str:
        """Generate secure API key."""
        import secrets

        return secrets.token_urlsafe(32)

    @beartype
    def constant_time_compare(self, a: str, b: str) -> bool:
        """Compare two strings in constant time to prevent timing attacks."""
        import hmac

        return hmac.compare_digest(a.encode(), b.encode())


# Global security instance
_security: Security | None = None


@beartype
def get_security() -> Security:
    """Get global security instance."""
    global _security
    if _security is None:
        _security = Security()
    return _security


@beartype
async def verify_jwt_token(token: str, secret: str) -> JWTDecodeResult:
    """Verify JWT token and return payload.

    Args:
        token: JWT token to verify
        secret: JWT secret (unused, uses settings)

    Returns:
        dict: Token payload

    Raises:
        Exception: If token is invalid or expired
    """
    security = get_security()
    token_payload = security.decode_token(token)

    if token_payload is None:
        raise ValueError("Invalid or expired token")

    # Convert TokenPayload to JWTDecodeResult for type safety
    return JWTDecodeResult(
        sub=token_payload.sub,
        exp=int(token_payload.exp.timestamp()),
        iat=int(token_payload.iat.timestamp()),
        jti=token_payload.jti,
        type=token_payload.type,
        scopes=token_payload.scopes,
    )


@beartype
async def create_jwt_token(payload: PayloadData, secret: str) -> str:
    """Create JWT token from payload.

    Args:
        payload: Token payload data
        secret: JWT secret (unused, uses settings)

    Returns:
        str: Encoded JWT token
    """
    security = get_security()

    # Extract required fields
    subject = payload.get("sub", "")
    scopes = payload.get("scopes", [])

    # Use the security instance to create token
    token_data = security.create_access_token(
        subject=subject,
        scopes=scopes,
    )

    return token_data.access_token
