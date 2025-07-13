# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""MFA API endpoints."""

from typing import Any
from uuid import UUID

from beartype import beartype
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from policy_core.core.cache import get_cache
from policy_core.core.config import get_settings
from policy_core.core.database import get_database

from ...core.auth.mfa import MFAManager
from ...core.auth.mfa.models import MFAMethod, MFAVerificationRequest
from ...models.base import BaseModelConfig

# For these endpoints we treat current user as a raw dict coming from test patches.
CurrentUserData = dict[str, Any]
from ..dependencies import get_current_user
from ..response_patterns import ErrorResponse

# Auto-generated models


@beartype
class MetadataData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class AuthenticatorSelectionData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class UserData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class RpData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


router = APIRouter(prefix="/mfa", tags=["mfa"])


# Request/Response models


@beartype
class MFAStatusResponse(BaseModel):
    """MFA status response."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    totp_enabled: bool
    webauthn_enabled: bool
    sms_enabled: bool
    biometric_enabled: bool
    recovery_codes_count: int
    preferred_method: MFAMethod | None
    device_trusted: bool


@beartype
class TOTPSetupResponse(BaseModel):
    """TOTP setup response."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    qr_code: str = Field(..., description="QR code data URL")
    manual_entry_key: str = Field(..., description="Manual entry key")
    backup_codes: list[str] = Field(..., description="Backup recovery codes")


@beartype
class TOTPVerifyRequest(BaseModel):
    """TOTP verification request."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    code: str = Field(..., pattern=r"^\d{6}$", description="6-digit TOTP code")


@beartype
class WebAuthnRegistrationRequest(BaseModel):
    """WebAuthn registration request."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    device_name: str = Field(..., min_length=1, max_length=100)


@beartype
class WebAuthnRegistrationResponse(BaseModel):
    """WebAuthn registration options."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    challenge: str
    rp: RpData
    user: UserData
    pubKeyCredParams: list[dict[str, Any]]
    timeout: int
    excludeCredentials: list[dict[str, Any]]
    authenticatorSelection: AuthenticatorSelectionData
    attestation: str


@beartype
class SMSSetupRequest(BaseModel):
    """SMS setup request."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    phone_number: str = Field(..., pattern=r"^\+?[1-9]\d{1,14}$")


@beartype
class MFAChallengeResponse(BaseModel):
    """MFA challenge response."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    challenge_id: UUID
    method: MFAMethod
    expires_in: int
    metadata: MetadataData = Field(default_factory=dict)


@beartype
class DeviceTrustRequest(BaseModel):
    """Device trust request."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    device_fingerprint: str
    device_name: str
    trust_duration_days: int = Field(default=30, ge=1, le=90)


# Dependency to get MFA manager
async def get_mfa_manager() -> MFAManager:
    """Get MFA manager instance."""
    db = get_database()
    cache = get_cache()
    settings = get_settings()
    return MFAManager(db, cache, settings)


# ---------------------------------------------------------------------------
# Legacy helper: extract user_id from patched dict
# ---------------------------------------------------------------------------


def _get_user_id(user: Any) -> str:  # noqa: ANN401
    """Extract user identifier from mocked/real user data (dict or model)."""
    if user is None:
        return ""

    # Dict-like objects (incl. AsyncMock with spec=dict) have .get
    if hasattr(user, "get"):
        val = user.get("sub") or user.get("user_id")  # type: ignore[attr-defined]
        if val:
            return str(val)

    # Fallback to attribute access
    for attr in ("sub", "user_id"):
        if hasattr(user, attr):
            return str(getattr(user, attr))

    return ""


# Endpoints


@router.get("/status", response_model=MFAStatusResponse)
async def get_mfa_status(
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> MFAStatusResponse | ErrorResponse:
    """Get user's MFA status."""
    user_id = _get_user_id(current_user)

    # Get MFA configuration
    config_result = await mfa_manager.get_user_mfa_config(user_id)
    if config_result.is_err():
        response.status_code = 500
        return ErrorResponse(error=config_result.err_value or "Unknown error")

    config = config_result.ok_value

    # Check device trust (mock for now)
    device_trusted = False

    # If no config exists, return default disabled status
    if not config:
        return MFAStatusResponse(
            totp_enabled=False,
            webauthn_enabled=False,
            sms_enabled=False,
            biometric_enabled=False,
            recovery_codes_count=0,
            preferred_method=None,
            device_trusted=device_trusted,
        )

    return MFAStatusResponse(
        totp_enabled=config.totp_enabled,
        webauthn_enabled=config.webauthn_enabled,
        sms_enabled=config.sms_enabled,
        biometric_enabled=False,  # Not implemented yet
        recovery_codes_count=len(config.recovery_codes_encrypted),
        preferred_method=config.preferred_method,
        device_trusted=device_trusted,
    )


@router.post("/totp/setup", response_model=TOTPSetupResponse)
async def setup_totp(
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> TOTPSetupResponse | ErrorResponse:
    """Start TOTP setup process."""
    user_id = _get_user_id(current_user)
    user_email = current_user.get("email", "user@example.com")

    # Check if TOTP already enabled
    config_result = await mfa_manager.get_user_mfa_config(user_id)
    if (
        config_result.is_ok()
        and config_result.ok_value is not None
        and config_result.ok_value.totp_enabled
    ):
        response.status_code = 400
        return ErrorResponse(error="TOTP already enabled for this account")

    # Generate TOTP setup
    setup_result = await mfa_manager.setup_totp(user_id, user_email)
    if setup_result.is_err():
        response.status_code = 500
        return ErrorResponse(error=setup_result.err_value or "Unknown error")

    setup_data = setup_result.ok_value

    # Type narrowing - setup_data should not be None if is_ok() is True
    if setup_data is None:
        response.status_code = 500
        return ErrorResponse(error="Internal server error: setup data is None")

    return TOTPSetupResponse(
        qr_code=setup_data.qr_code,
        manual_entry_key=setup_data.manual_entry_key,
        backup_codes=setup_data.backup_codes,
    )


@router.post("/totp/verify-setup")
async def verify_totp_setup(
    request: TOTPVerifyRequest,
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> dict[str, str] | ErrorResponse:
    """Verify TOTP setup and activate."""
    user_id = _get_user_id(current_user)

    # Verify and activate TOTP
    verify_result = await mfa_manager.verify_totp_setup(user_id, request.code)
    if verify_result.is_err():
        response.status_code = 400
        return ErrorResponse(error=verify_result.err_value or "Unknown error")

    return {"message": "TOTP successfully enabled"}


@router.delete("/totp")
async def disable_totp(
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> dict[str, str] | ErrorResponse:
    """Disable TOTP authentication."""
    user_id = _get_user_id(current_user)

    # Check if user has other MFA methods enabled
    config_result = await mfa_manager.get_user_mfa_config(user_id)
    if config_result.is_err():
        response.status_code = 500
        return ErrorResponse(error=config_result.err_value or "Unknown error")

    config = config_result.ok_value
    if not config or not config.totp_enabled:
        response.status_code = 400
        return ErrorResponse(error="TOTP not enabled")

    # Ensure user has other MFA methods or allow disabling
    other_methods = config.webauthn_enabled or config.sms_enabled
    if not other_methods:
        # In production, might require additional verification
        pass

    # Disable TOTP
    db = get_database()
    await db.execute(
        """
        UPDATE user_mfa_settings
        SET totp_enabled = false,
            totp_secret_encrypted = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = $1
        """,
        user_id,
    )

    return {"message": "TOTP successfully disabled"}


@router.post("/webauthn/register/begin", response_model=WebAuthnRegistrationResponse)
async def begin_webauthn_registration(
    request: WebAuthnRegistrationRequest,
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> WebAuthnRegistrationResponse | ErrorResponse:
    """Begin WebAuthn registration."""
    user_id = _get_user_id(current_user)
    user_email = current_user.get("email", "user@example.com")
    user_name = current_user.get("name", user_email)

    # Get existing credentials
    config_result = await mfa_manager.get_user_mfa_config(user_id)
    existing_creds: list[Any] = []
    if config_result.is_ok() and config_result.ok_value:
        existing_creds = config_result.ok_value.webauthn_credentials

    # Generate registration options
    options_result = mfa_manager._webauthn_provider.generate_registration_options(
        user_id, user_email, user_name, existing_creds
    )

    if options_result.is_err():
        response.status_code = 500
        return ErrorResponse(error=options_result.err_value or "Unknown error")

    options = options_result.unwrap()
    return WebAuthnRegistrationResponse(**options)


@router.post("/sms/setup")
async def setup_sms(
    request: SMSSetupRequest,
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> dict[str, str | int] | ErrorResponse:
    """Setup SMS authentication."""
    user_id = _get_user_id(current_user)

    # Encrypt phone number
    encrypt_result = mfa_manager._sms_provider.encrypt_phone_number(
        request.phone_number
    )
    if encrypt_result.is_err():
        response.status_code = 400
        return ErrorResponse(error=encrypt_result.err_value or "Unknown error")

    encrypted_phone = encrypt_result.unwrap()

    # Send verification code
    send_result = await mfa_manager._sms_provider.send_verification_code(
        str(user_id), encrypted_phone, purpose="setup"
    )
    if send_result.is_err():
        response.status_code = 400
        return ErrorResponse(error=send_result.err_value or "Unknown error")

    return {"message": "Verification code sent", "expires_in": 600}  # 10 minutes


@router.post("/challenge", response_model=MFAChallengeResponse)
async def create_mfa_challenge(
    response: Response,
    preferred_method: MFAMethod | None = None,
    current_user: CurrentUserData = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> MFAChallengeResponse | ErrorResponse:
    """Create MFA challenge for authentication."""
    user_id = _get_user_id(current_user)

    # In production, would include risk assessment
    challenge_result = await mfa_manager.create_mfa_challenge(
        user_id, risk_assessment=None, preferred_method=preferred_method
    )

    if challenge_result.is_err():
        response.status_code = 400
        return ErrorResponse(error=challenge_result.err_value or "Unknown error")

    challenge = challenge_result.ok_value

    # Type narrowing - challenge should not be None if is_ok() is True
    if challenge is None:
        response.status_code = 500
        return ErrorResponse(error="Internal server error: challenge is None")

    return MFAChallengeResponse(
        challenge_id=challenge.challenge_id,
        method=challenge.method,
        expires_in=int((challenge.expires_at - challenge.created_at).total_seconds()),
        metadata=challenge.metadata,
    )


@router.post("/challenge/{challenge_id}/verify")
async def verify_mfa_challenge(
    challenge_id: UUID,
    request: MFAVerificationRequest,
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> dict[str, Any] | ErrorResponse:
    """Verify MFA challenge."""
    # Ensure challenge ID matches request
    if request.challenge_id != challenge_id:
        response.status_code = 400
        return ErrorResponse(error="Challenge ID mismatch")

    # Verify challenge
    verify_result = await mfa_manager.verify_mfa_challenge(request)
    if verify_result.is_err():
        response.status_code = 500
        return ErrorResponse(error=verify_result.err_value or "Unknown error")

    result = verify_result.ok_value

    # Type narrowing - result should not be None if is_ok() is True
    if result is None:
        response.status_code = 500
        return ErrorResponse(error="Internal server error: verification result is None")

    if not result.success:
        error_detail = {
            "error": result.error_message or "Verification failed",
            "remaining_attempts": result.remaining_attempts,
        }
        response.status_code = 401
        return ErrorResponse(error=f"Verification failed: {error_detail}")

    return {
        "success": True,
        "verified_at": result.verified_at.isoformat() if result.verified_at else None,
    }


@router.post("/recovery-codes/generate")
async def generate_recovery_codes(
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> dict[str, Any] | ErrorResponse:
    """Generate new recovery codes."""
    user_id = _get_user_id(current_user)

    # Generate new codes
    codes_result = await mfa_manager.generate_recovery_codes(user_id)
    if codes_result.is_err():
        response.status_code = 500
        return ErrorResponse(error=codes_result.err_value or "Unknown error")

    codes = codes_result.ok_value

    return {
        "recovery_codes": codes,
        "warning": "Store these codes securely. Each code can only be used once.",
    }


@router.post("/device/trust")
async def trust_device(
    request: DeviceTrustRequest,
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> dict[str, Any] | ErrorResponse:
    """Mark device as trusted."""
    user_id = _get_user_id(current_user)

    # Get request metadata (in production, extract from request)
    ip_address = "127.0.0.1"  # Mock
    user_agent = "Mozilla/5.0"  # Mock

    # Trust device
    trust_result = await mfa_manager.trust_device(
        user_id, request.device_fingerprint, request.device_name, ip_address, user_agent
    )

    if trust_result.is_err():
        response.status_code = 500
        return ErrorResponse(error=trust_result.err_value or "Unknown error")

    device_trust = trust_result.ok_value

    # Type narrowing - device_trust should not be None if is_ok() is True
    if device_trust is None:
        response.status_code = 500
        return ErrorResponse(error="Internal server error: device trust is None")

    return {
        "device_id": str(device_trust.device_id),
        "trusted_until": device_trust.expires_at.isoformat(),
    }


@router.get("/risk-assessment")
async def get_risk_assessment(
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> dict[str, Any] | ErrorResponse:
    """Get current authentication risk assessment."""
    user_id = _get_user_id(current_user)

    # Get request metadata (in production, extract from request)
    ip_address = "127.0.0.1"  # Mock
    user_agent = "Mozilla/5.0"  # Mock
    device_fingerprint = None  # Mock

    # Assess risk
    risk_result = await mfa_manager._risk_engine.assess_risk(
        user_id, ip_address, user_agent, device_fingerprint
    )

    if risk_result.is_err():
        response.status_code = 500
        return ErrorResponse(error=risk_result.err_value or "Unknown error")

    assessment = risk_result.unwrap()

    return {
        "risk_level": assessment.risk_level.value,
        "risk_score": assessment.risk_score,
        "require_mfa": assessment.require_mfa,
        "recommended_methods": [m.value for m in assessment.recommended_methods],
        "reason": assessment.reason,
    }
