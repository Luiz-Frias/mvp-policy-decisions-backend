"""MFA domain models."""

from datetime import datetime
from enum import Enum
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
    webauthn_credentials: list["WebAuthnCredential"] = Field(default_factory=list)
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
class TOTPSetupCache(BaseModel):
    """TOTP setup cache data for temporary storage."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    secret_encrypted: str = Field(..., description="Encrypted TOTP secret")
    backup_codes: list[str] = Field(..., description="One-time backup codes")


@beartype
class WebAuthnCredential(BaseModel):
    """WebAuthn credential information."""

    model_config = ConfigDict(
        frozen=True,
        frozen=False,  # Allow mutation for counter updates
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
class AuthenticatorSelection(BaseModel):
    """WebAuthn authenticator selection criteria."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    authenticator_attachment: str | None = None  # "platform" or "cross-platform"
    require_resident_key: bool = False
    user_verification: str = "preferred"  # "required", "preferred", "discouraged"


@beartype
class WebAuthnExtensions(BaseModel):
    """WebAuthn extensions configuration."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    credential_protection_policy: str | None = None
    enforce_credential_protection_policy: bool | None = None
    cred_blob: str | None = None
    min_pin_length: int | None = None


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
    authenticator_selection: AuthenticatorSelection = Field(
        default_factory=AuthenticatorSelection
    )
    attestation: str = "none"
    extensions: WebAuthnExtensions = Field(default_factory=WebAuthnExtensions)


@beartype
class MFAChallengeMetadata(BaseModel):
    """MFA challenge metadata."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    ip_address: str | None = None
    user_agent: str | None = None
    device_fingerprint: str | None = None
    risk_level: str | None = None
    sms_phone_number: str | None = None
    webauthn_challenge: str | None = None
    biometric_type: str | None = None


@beartype
class MFAChallenge(BaseModel):
    """MFA challenge for verification."""

    model_config = ConfigDict(
        frozen=True,
        frozen=False,  # Allow mutation for challenge tracking
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
    metadata: MFAChallengeMetadata = Field(default_factory=MFAChallengeMetadata)
    verified_at: datetime | None = None


@beartype
class RiskFactors(BaseModel):
    """Risk assessment factors with scores."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    location_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    device_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    behavioral_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    time_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    network_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    velocity_risk: float = Field(default=0.0, ge=0.0, le=1.0)
    credential_risk: float = Field(default=0.0, ge=0.0, le=1.0)


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
    factors: RiskFactors = Field(default_factory=RiskFactors)
    require_mfa: bool
    recommended_methods: list[MFAMethod]
    reason: str


@beartype
class WebAuthnCredentialResponse(BaseModel):
    """WebAuthn credential response."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    credential_id: str
    authenticator_data: str
    client_data_json: str
    signature: str
    user_handle: str | None = None


@beartype
class BiometricData(BaseModel):
    """Biometric verification data."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    biometric_type: str  # "fingerprint", "face", "voice", "iris"
    template_data: str  # Base64 encoded biometric template
    quality_score: float = Field(..., ge=0.0, le=1.0)
    liveness_check: bool = False
    capture_timestamp: datetime


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
    credential_response: WebAuthnCredentialResponse | None = None  # For WebAuthn
    biometric_data: BiometricData | None = None  # For biometric


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


@beartype
class BiometricCaptureSettings(BaseModel):
    """Biometric capture settings configuration."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    min_quality: int = Field(..., ge=0, le=100, description="Minimum quality score")
    capture_timeout: int = Field(
        ..., ge=1, le=120, description="Capture timeout in seconds"
    )
    # Optional features that may be enabled
    finger_detect: bool = Field(default=False, description="Enable finger detection")
    anti_spoofing: bool = Field(
        default=False, description="Enable anti-spoofing measures"
    )
    face_detect: bool = Field(default=False, description="Enable face detection")
    liveness_required: bool = Field(default=False, description="Require liveness check")
    pose_variation: bool = Field(default=False, description="Allow pose variation")
    noise_reduction: bool = Field(default=False, description="Enable noise reduction")
    # Voice-specific settings
    min_duration: int | None = Field(None, description="Minimum duration in seconds")
    max_duration: int | None = Field(None, description="Maximum duration in seconds")
    sample_rate: int | None = Field(None, description="Audio sample rate")
