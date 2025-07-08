"""MFA domain models."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field


class MFAMethod(str, Enum):
    """Available MFA methods."""

    TOTP = "totp"
    WEBAUTHN = "webauthn"
    SMS = "sms"
    BIOMETRIC = "biometric"
    RECOVERY_CODE = "recovery_code"


class MFAStatus(str, Enum):
    """MFA verification status."""

    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"


class RiskLevel(str, Enum):
    """Risk assessment levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@beartype
class MFAConfig(BaseModel):
    """MFA configuration for a user."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    user_id: UUID
    totp_enabled: bool = False
    totp_secret_encrypted: str | None = None
    webauthn_enabled: bool = False
    webauthn_credentials: list[dict[str, Any]] = Field(default_factory=list)
    sms_enabled: bool = False
    sms_phone_encrypted: str | None = None
    recovery_codes_encrypted: list[str] = Field(default_factory=list)
    preferred_method: MFAMethod | None = None
    created_at: datetime
    updated_at: datetime


@beartype
class TOTPSetupData(BaseModel):
    """TOTP setup information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    secret: str = Field(..., description="Base32 encoded secret")
    qr_code: str = Field(..., description="QR code data URL")
    manual_entry_key: str = Field(..., description="Key for manual entry")
    backup_codes: list[str] = Field(..., description="One-time backup codes")


@beartype
class WebAuthnCredential(BaseModel):
    """WebAuthn credential information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    credential_id: str
    public_key: str
    counter: int
    device_name: str
    created_at: datetime
    last_used_at: datetime | None = None
    aaguid: str | None = None  # Authenticator attestation GUID


@beartype
class WebAuthnChallenge(BaseModel):
    """WebAuthn challenge for registration/authentication."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    challenge: str
    user_id: str
    user_name: str
    user_display_name: str
    rp_id: str  # Relying party ID
    rp_name: str  # Relying party name
    timeout: int = 60000  # milliseconds
    authenticator_selection: dict[str, Any] = Field(default_factory=dict)
    attestation: str = "none"
    extensions: dict[str, Any] = Field(default_factory=dict)


@beartype
class MFAChallenge(BaseModel):
    """MFA challenge for verification."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    challenge_id: UUID
    user_id: UUID
    method: MFAMethod
    status: MFAStatus
    created_at: datetime
    expires_at: datetime
    attempts: int = 0
    max_attempts: int = 3
    metadata: dict[str, Any] = Field(default_factory=dict)


@beartype
class RiskAssessment(BaseModel):
    """Risk assessment result."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    risk_level: RiskLevel
    risk_score: float = Field(..., ge=0.0, le=1.0)
    factors: dict[str, float] = Field(default_factory=dict)
    require_mfa: bool
    recommended_methods: list[MFAMethod]
    reason: str


@beartype
class MFAVerificationRequest(BaseModel):
    """Request to verify MFA code."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    challenge_id: UUID
    code: str | None = None  # For TOTP/SMS
    credential_response: dict[str, Any] | None = None  # For WebAuthn
    biometric_data: dict[str, Any] | None = None  # For biometric


@beartype
class MFAVerificationResult(BaseModel):
    """Result of MFA verification."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    success: bool
    challenge_id: UUID
    method: MFAMethod
    verified_at: datetime | None = None
    error_message: str | None = None
    remaining_attempts: int | None = None


@beartype
class DeviceTrust(BaseModel):
    """Trusted device information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    device_id: UUID
    user_id: UUID
    device_fingerprint: str
    device_name: str
    trusted_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    ip_address: str
    user_agent: str


@beartype
class SMSVerification(BaseModel):
    """SMS verification details."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    phone_number: str
    verification_code: str
    sent_at: datetime
    expires_at: datetime
    verified: bool = False
    sim_swap_check_passed: bool | None = None
    carrier_verified: bool | None = None
