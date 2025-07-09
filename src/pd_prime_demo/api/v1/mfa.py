"""MFA API endpoints."""

from typing import Any
from uuid import UUID

from beartype import beartype
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from ...core.auth.mfa import MFAManager
from ...core.auth.mfa.models import (
    MFAMethod,
    MFAVerificationRequest,
)
from ...core.cache import get_cache
from ...core.config import get_settings
from ...core.database import get_database
from ..dependencies import get_current_user

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
    rp: dict[str, Any]
    user: dict[str, Any]
    pubKeyCredParams: list[dict[str, Any]]
    timeout: int
    excludeCredentials: list[dict[str, Any]]
    authenticatorSelection: dict[str, Any]
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
    metadata: dict[str, Any] = Field(default_factory=dict)


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


# Endpoints


@router.get("/status", response_model=MFAStatusResponse)
async def get_mfa_status(
    current_user: dict[str, Any] = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> MFAStatusResponse:
    """Get user's MFA status."""
    user_id = UUID(current_user["sub"])

    # Get MFA configuration
    config_result = await mfa_manager.get_user_mfa_config(user_id)
    if config_result.is_err():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve MFA configuration",
        )

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
    current_user: dict[str, Any] = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> TOTPSetupResponse:
    """Start TOTP setup process."""
    user_id = UUID(current_user["sub"])
    user_email = current_user.get("email", "user@example.com")

    # Check if TOTP already enabled
    config_result = await mfa_manager.get_user_mfa_config(user_id)
    if config_result.is_ok() and config_result.ok_value is not None and config_result.ok_value.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TOTP already enabled for this account",
        )

    # Generate TOTP setup
    setup_result = await mfa_manager.setup_totp(user_id, user_email)
    if setup_result.is_err():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=setup_result.err_value
        )

    setup_data = setup_result.ok_value
    
    # Type narrowing - setup_data should not be None if is_ok() is True
    if setup_data is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error: setup data is None"
        )

    return TOTPSetupResponse(
        qr_code=setup_data.qr_code,
        manual_entry_key=setup_data.manual_entry_key,
        backup_codes=setup_data.backup_codes,
    )


@router.post("/totp/verify-setup")
async def verify_totp_setup(
    request: TOTPVerifyRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> dict[str, str]:
    """Verify TOTP setup and activate."""
    user_id = UUID(current_user["sub"])

    # Verify and activate TOTP
    verify_result = await mfa_manager.verify_totp_setup(user_id, request.code)
    if verify_result.is_err():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=verify_result.err_value
        )

    return {"message": "TOTP successfully enabled"}


@router.delete("/totp")
async def disable_totp(
    current_user: dict[str, Any] = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> dict[str, str]:
    """Disable TOTP authentication."""
    user_id = UUID(current_user["sub"])

    # Check if user has other MFA methods enabled
    config_result = await mfa_manager.get_user_mfa_config(user_id)
    if config_result.is_err():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve MFA configuration",
        )

    config = config_result.ok_value
    if not config or not config.totp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="TOTP not enabled"
        )

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
    current_user: dict[str, Any] = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> WebAuthnRegistrationResponse:
    """Begin WebAuthn registration."""
    user_id = UUID(current_user["sub"])
    user_email = current_user.get("email", "user@example.com")
    user_name = current_user.get("name", user_email)

    # Get existing credentials
    config_result = await mfa_manager.get_user_mfa_config(user_id)
    existing_creds: list[Any] = []
    if config_result.is_ok() and config_result.ok_value:
        existing_creds = config_result.ok_value.webauthn_credentials

    # Generate registration options
    options_result = await mfa_manager._webauthn_provider.generate_registration_options(
        user_id, user_email, user_name, existing_creds
    )

    if options_result.is_err():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=options_result.err_value,
        )

    options = options_result.ok_value
    return WebAuthnRegistrationResponse(**options)


@router.post("/sms/setup")
async def setup_sms(
    request: SMSSetupRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> dict[str, str]:
    """Setup SMS authentication."""
    user_id = UUID(current_user["sub"])

    # Encrypt phone number
    encrypt_result = await mfa_manager._sms_provider.encrypt_phone_number(
        request.phone_number
    )
    if encrypt_result.is_err():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=encrypt_result.err_value
        )

    encrypted_phone = encrypt_result.ok_value

    # Send verification code
    send_result = await mfa_manager._sms_provider.send_verification_code(
        str(user_id), encrypted_phone, purpose="setup"
    )
    if send_result.is_err():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=send_result.err_value
        )

    return {"message": "Verification code sent", "expires_in": 600}  # 10 minutes


@router.post("/challenge", response_model=MFAChallengeResponse)
async def create_mfa_challenge(
    preferred_method: MFAMethod | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> MFAChallengeResponse:
    """Create MFA challenge for authentication."""
    user_id = UUID(current_user["sub"])

    # In production, would include risk assessment
    challenge_result = await mfa_manager.create_mfa_challenge(
        user_id, risk_assessment=None, preferred_method=preferred_method
    )

    if challenge_result.is_err():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=challenge_result.err_value
        )

    challenge = challenge_result.ok_value
    
    # Type narrowing - challenge should not be None if is_ok() is True
    if challenge is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error: challenge is None"
        )

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
    current_user: dict[str, Any] = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> dict[str, Any]:
    """Verify MFA challenge."""
    # Ensure challenge ID matches request
    if request.challenge_id != challenge_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Challenge ID mismatch"
        )

    # Verify challenge
    verify_result = await mfa_manager.verify_mfa_challenge(request)
    if verify_result.is_err():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=verify_result.err_value,
        )

    result = verify_result.ok_value
    
    # Type narrowing - result should not be None if is_ok() is True
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error: verification result is None"
        )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": result.error_message or "Verification failed",
                "remaining_attempts": result.remaining_attempts,
            },
        )

    return {
        "success": True,
        "verified_at": result.verified_at.isoformat() if result.verified_at else None,
    }


@router.post("/recovery-codes/generate")
async def generate_recovery_codes(
    current_user: dict[str, Any] = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> dict[str, Any]:
    """Generate new recovery codes."""
    user_id = UUID(current_user["sub"])

    # Generate new codes
    codes_result = await mfa_manager.generate_recovery_codes(user_id)
    if codes_result.is_err():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=codes_result.err_value
        )

    codes = codes_result.ok_value

    return {
        "recovery_codes": codes,
        "warning": "Store these codes securely. Each code can only be used once.",
    }


@router.post("/device/trust")
async def trust_device(
    request: DeviceTrustRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> dict[str, Any]:
    """Mark device as trusted."""
    user_id = UUID(current_user["sub"])

    # Get request metadata (in production, extract from request)
    ip_address = "127.0.0.1"  # Mock
    user_agent = "Mozilla/5.0"  # Mock

    # Trust device
    trust_result = await mfa_manager.trust_device(
        user_id, request.device_fingerprint, request.device_name, ip_address, user_agent
    )

    if trust_result.is_err():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=trust_result.err_value
        )

    device_trust = trust_result.ok_value
    
    # Type narrowing - device_trust should not be None if is_ok() is True
    if device_trust is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error: device trust is None"
        )

    return {
        "device_id": str(device_trust.device_id),
        "trusted_until": device_trust.expires_at.isoformat(),
    }


@router.get("/risk-assessment")
async def get_risk_assessment(
    current_user: dict[str, Any] = Depends(get_current_user),
    mfa_manager: MFAManager = Depends(get_mfa_manager),
) -> dict[str, Any]:
    """Get current authentication risk assessment."""
    user_id = str(current_user["sub"])

    # Get request metadata (in production, extract from request)
    ip_address = "127.0.0.1"  # Mock
    user_agent = "Mozilla/5.0"  # Mock
    device_fingerprint = None  # Mock

    # Assess risk
    risk_result = await mfa_manager._risk_engine.assess_risk(
        user_id, ip_address, user_agent, device_fingerprint
    )

    if risk_result.is_err():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=risk_result.error
        )

    assessment = risk_result.value

    return {
        "risk_level": assessment.risk_level.value,
        "risk_score": assessment.risk_score,
        "require_mfa": assessment.require_mfa,
        "recommended_methods": [m.value for m in assessment.recommended_methods],
        "reason": assessment.reason,
    }
