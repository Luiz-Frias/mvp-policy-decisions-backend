"""User domain models for authentication and authorization.

This module defines user-related models for the application including
regular users, admin users, and authentication/authorization patterns.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from beartype import beartype
from pydantic import EmailStr, Field, field_validator

from .base import BaseModelConfig, IdentifiableModel


class UserRole(str, Enum):
    """Enumeration of user roles."""

    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"
    UNDERWRITER = "UNDERWRITER"
    ADJUSTER = "ADJUSTER"
    ADMIN = "ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"


class UserStatus(str, Enum):
    """Enumeration of user account states."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    LOCKED = "LOCKED"


@beartype
class UserBase(BaseModelConfig):
    """Base user attributes shared across all user operations."""

    email: EmailStr = Field(..., description="User's email address")

    first_name: str = Field(
        ..., min_length=1, max_length=100, description="User's first name"
    )

    last_name: str = Field(
        ..., min_length=1, max_length=100, description="User's last name"
    )

    role: UserRole = Field(..., description="User's role in the system")

    status: UserStatus = Field(
        default=UserStatus.PENDING_VERIFICATION,
        description="Current status of the user account",
    )

    phone_number: str | None = Field(
        default=None,
        pattern=r"^\+?[1-9]\d{1,14}$",
        description="User's phone number in E.164 format",
    )

    is_email_verified: bool = Field(
        default=False, description="Whether the user's email has been verified"
    )

    is_phone_verified: bool = Field(
        default=False, description="Whether the user's phone has been verified"
    )

    last_login_at: datetime | None = Field(
        default=None, description="Timestamp of last login"
    )

    failed_login_attempts: int = Field(
        default=0, ge=0, description="Number of consecutive failed login attempts"
    )

    locked_until: datetime | None = Field(
        default=None, description="Timestamp until which the account is locked"
    )

    @field_validator("email")
    @classmethod
    def validate_email_domain(cls, v: str) -> str:
        """Validate email domain if needed."""
        # Basic email validation - Pydantic EmailStr already handles most validation
        email_str = str(v).lower()

        # Could add domain whitelist/blacklist validation here
        # For now, just return the normalized email
        return email_str

    @field_validator("phone_number")
    @classmethod
    def validate_phone_format(cls, v: str | None) -> str | None:
        """Validate and normalize phone number format."""
        if v is None:
            return v

        # Remove all non-digit characters except +
        cleaned = "".join(c for c in v if c.isdigit() or c == "+")

        # Ensure it starts with + if it doesn't already
        if not cleaned.startswith("+"):
            # Assume US number if no country code
            cleaned = "+1" + cleaned

        return cleaned


@beartype
class UserCreate(UserBase):
    """Model for creating a new user."""

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User's password (will be hashed)",
    )

    confirm_password: str = Field(
        ..., min_length=8, max_length=128, description="Password confirmation"
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password meets security requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")

        # Check for at least one uppercase, lowercase, digit, and special character
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v)

        if not all([has_upper, has_lower, has_digit, has_special]):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one lowercase letter, one digit, and one special character"
            )

        return v

    def model_post_init(self, __context: Any) -> None:
        """Validate password confirmation after model creation."""
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")


@beartype
class UserUpdate(BaseModelConfig):
    """Model for updating user information."""

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone_number: str | None = Field(default=None)
    status: UserStatus | None = Field(default=None)
    is_email_verified: bool | None = Field(default=None)
    is_phone_verified: bool | None = Field(default=None)


@beartype
class UserPasswordUpdate(BaseModelConfig):
    """Model for updating user password."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password"
    )
    confirm_new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password confirmation"
    )

    def model_post_init(self, __context: Any) -> None:
        """Validate new password confirmation."""
        if self.new_password != self.confirm_new_password:
            raise ValueError("New passwords do not match")


@beartype
class User(UserBase, IdentifiableModel):
    """Complete user model with all attributes."""

    # Password hash is stored separately and not exposed in API responses
    password_hash: str | None = Field(
        default=None,
        exclude=True,  # Never include in serialization
        description="Hashed password (internal use only)",
    )

    email_verification_token: str | None = Field(
        default=None,
        exclude=True,  # Never include in serialization
        description="Email verification token",
    )

    password_reset_token: str | None = Field(
        default=None,
        exclude=True,  # Never include in serialization
        description="Password reset token",
    )

    password_reset_expires: datetime | None = Field(
        default=None,
        exclude=True,  # Never include in serialization
        description="Password reset token expiration",
    )


@beartype
class UserLogin(BaseModelConfig):
    """Model for user login request."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")
    remember_me: bool = Field(
        default=False, description="Whether to create a long-lasting session"
    )


@beartype
class UserLoginResponse(BaseModelConfig):
    """Model for user login response."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user: User = Field(..., description="User information")


@beartype
class UserRefreshRequest(BaseModelConfig):
    """Model for token refresh request."""

    refresh_token: str = Field(..., description="Valid refresh token")


@beartype
class PasswordResetRequest(BaseModelConfig):
    """Model for password reset request."""

    email: EmailStr = Field(..., description="User's email address")


@beartype
class PasswordResetConfirm(BaseModelConfig):
    """Model for password reset confirmation."""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password"
    )
    confirm_password: str = Field(
        ..., min_length=8, max_length=128, description="Password confirmation"
    )

    def model_post_init(self, __context: Any) -> None:
        """Validate password confirmation."""
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")


@beartype
class EmailVerificationRequest(BaseModelConfig):
    """Model for email verification request."""

    token: str = Field(..., description="Email verification token")
