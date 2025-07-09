"""MFA Manager to orchestrate all MFA methods."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from beartype import beartype

from pd_prime_demo.core.result_types import Err, Ok, Result

from ....core.cache import Cache
from ....core.config import Settings
from ....core.database import Database
from .biometric import BiometricProvider
from .models import (
    DeviceTrust,
    MFAChallenge,
    MFAConfig,
    MFAMethod,
    MFAStatus,
    MFAVerificationRequest,
    MFAVerificationResult,
    RiskAssessment,
    TOTPSetupData,
)
from .risk_engine import RiskEngine
from .sms import SMSProvider
from .totp import TOTPProvider
from .webauthn import WebAuthnProvider


class MFAManager:
    """Central manager for all MFA operations."""

    def __init__(self, db: Database, cache: Cache, settings: Settings) -> None:
        """Initialize MFA manager with all providers."""
        self._db = db
        self._cache = cache
        self._settings = settings

        # Initialize providers
        self._totp_provider = TOTPProvider(settings)
        self._webauthn_provider = WebAuthnProvider(settings)
        self._sms_provider = SMSProvider(settings, cache)
        self._biometric_provider = BiometricProvider(settings, cache)
        self._risk_engine = RiskEngine(db, cache, settings)

        # MFA configuration
        self._challenge_expiry = timedelta(minutes=5)
        self._recovery_code_length = 8
        self._recovery_codes_count = 10
        self._device_trust_duration = timedelta(days=30)

    @beartype
    async def get_user_mfa_config(self, user_id: UUID) -> Result[MFAConfig, str]:
        """Get user's MFA configuration.

        Args:
            user_id: User's ID

        Returns:
            Result containing MFA configuration or error
        """
        try:
            # Query from database
            row = await self._db.fetchrow(
                """
                SELECT user_id, totp_enabled, totp_secret_encrypted,
                       webauthn_enabled, webauthn_credentials,
                       sms_enabled, sms_phone_encrypted,
                       recovery_codes_encrypted, created_at, updated_at
                FROM user_mfa_settings
                WHERE user_id = $1
                """,
                user_id,
            )

            if not row:
                # Create default config
                return await self._create_default_mfa_config(user_id)

            # Determine preferred method
            preferred_method = None
            if row["webauthn_enabled"]:
                preferred_method = MFAMethod.WEBAUTHN
            elif row["totp_enabled"]:
                preferred_method = MFAMethod.TOTP
            elif row["sms_enabled"]:
                preferred_method = MFAMethod.SMS

            return Ok(
                MFAConfig(
                    user_id=row["user_id"],
                    totp_enabled=row["totp_enabled"],
                    totp_secret_encrypted=row["totp_secret_encrypted"],
                    webauthn_enabled=row["webauthn_enabled"],
                    webauthn_credentials=row["webauthn_credentials"] or [],
                    sms_enabled=row["sms_enabled"],
                    sms_phone_encrypted=row["sms_phone_encrypted"],
                    recovery_codes_encrypted=row["recovery_codes_encrypted"] or [],
                    preferred_method=preferred_method,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            )

        except Exception as e:
            return Err(f"Failed to get MFA configuration: {str(e)}")

    @beartype
    async def setup_totp(self, user_id: UUID, user_email: str) -> Result[TOTPSetupData, str]:
        """Setup TOTP for user.

        Args:
            user_id: User's ID
            user_email: User's email

        Returns:
            Result containing TOTP setup data or error
        """
        try:
            # Generate TOTP setup
            setup_result = self._totp_provider.generate_setup(user_email, str(user_id))
            if isinstance(setup_result, Err):
                return setup_result

            setup_data = setup_result.value

            # Encrypt secret for storage
            encrypt_result = self._totp_provider.encrypt_secret(setup_data.secret)
            if isinstance(encrypt_result, Err):
                return encrypt_result

            encrypted_secret = encrypt_result.value

            # Store encrypted secret temporarily (user must verify to activate)
            await self._cache.set(
                f"totp_setup:{user_id}",
                {
                    "secret_encrypted": encrypted_secret,
                    "backup_codes": setup_data.backup_codes,
                },
                ttl=1800,  # 30 minutes to complete setup
            )

            return Ok(setup_data)

        except Exception as e:
            return Err(f"Failed to setup TOTP: {str(e)}")

    @beartype
    async def verify_totp_setup(self, user_id: UUID, code: str) -> Result[None, str]:
        """Verify TOTP setup and activate.

        Args:
            user_id: User's ID
            code: TOTP code to verify

        Returns:
            Result indicating success or error
        """
        try:
            # Get setup data
            setup_data = await self._cache.get(f"totp_setup:{user_id}")
            if not setup_data:
                return Err("TOTP setup not found or expired")

            # Verify code
            verify_result = self._totp_provider.verify_code(
                setup_data["secret_encrypted"], code
            )
            if isinstance(verify_result, Err):
                return verify_result

            if not verify_result.value:
                return Err("Invalid TOTP code")

            # Encrypt recovery codes
            encrypted_codes = [
                self._encrypt_recovery_code(code) for code in setup_data["backup_codes"]
            ]

            # Update database
            await self._db.execute(
                """
                INSERT INTO user_mfa_settings (
                    user_id, totp_enabled, totp_secret_encrypted,
                    recovery_codes_encrypted, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (user_id) DO UPDATE SET
                    totp_enabled = EXCLUDED.totp_enabled,
                    totp_secret_encrypted = EXCLUDED.totp_secret_encrypted,
                    recovery_codes_encrypted = EXCLUDED.recovery_codes_encrypted,
                    updated_at = EXCLUDED.updated_at
                """,
                user_id,
                True,
                setup_data["secret_encrypted"],
                encrypted_codes,
                datetime.now(timezone.utc),
                datetime.now(timezone.utc),
            )

            # Clear setup data
            await self._cache.delete(f"totp_setup:{user_id}")

            return Ok(None)

        except Exception as e:
            return Err(f"Failed to verify TOTP setup: {str(e)}")

    @beartype
    async def create_mfa_challenge(
        self,
        user_id: UUID,
        risk_assessment: RiskAssessment | None = None,
        preferred_method: MFAMethod | None = None,
    ) -> Result[MFAChallenge, str]:
        """Create MFA challenge for authentication.

        Args:
            user_id: User's ID
            risk_assessment: Optional risk assessment result
            preferred_method: Optional preferred MFA method

        Returns:
            Result containing MFA challenge or error
        """
        try:
            # Get user's MFA config
            config_result = await self.get_user_mfa_config(user_id)
            if isinstance(config_result, Err):
                return config_result

            config = config_result.value

            # Determine which method to use
            method = self._select_mfa_method(config, risk_assessment, preferred_method)

            if not method:
                return Err("No MFA method available for user")

            # Create challenge
            challenge = MFAChallenge(
                challenge_id=uuid4(),
                user_id=user_id,
                method=method,
                status=MFAStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + self._challenge_expiry,
                attempts=0,
                max_attempts=3,
                metadata={},
            )

            # Method-specific setup
            if method == MFAMethod.SMS:
                # Check if phone is configured
                if not config.sms_phone_encrypted:
                    return Err("SMS phone number not configured")
                
                # Send SMS code
                sms_result = await self._sms_provider.send_verification_code(
                    str(user_id), config.sms_phone_encrypted, purpose="mfa"
                )
                if isinstance(sms_result, Err):
                    return sms_result

                challenge.metadata["sms_verification"] = sms_result.value

            elif method == MFAMethod.WEBAUTHN:
                # Get user's credentials
                webauthn_creds = await self._get_webauthn_credentials(user_id)

                # Generate authentication options
                auth_options = self._webauthn_provider.generate_authentication_options(
                    user_id, webauthn_creds
                )
                if isinstance(auth_options, Err):
                    return auth_options

                challenge.metadata["webauthn_options"] = auth_options.value

            # Store challenge
            await self._cache.set(
                f"mfa_challenge:{challenge.challenge_id}",
                challenge.model_dump(),
                ttl=int(self._challenge_expiry.total_seconds()),
            )

            return Ok(challenge)

        except Exception as e:
            return Err(f"Failed to create MFA challenge: {str(e)}")

    @beartype
    async def verify_mfa_challenge(self, request: MFAVerificationRequest) -> Result[MFAVerificationResult, str]:
        """Verify MFA challenge response.

        Args:
            request: MFA verification request

        Returns:
            Result containing verification result or error
        """
        try:
            # Get challenge
            challenge_data = await self._cache.get(
                f"mfa_challenge:{request.challenge_id}"
            )
            if not challenge_data:
                return Err("Challenge not found or expired")

            # Reconstruct challenge object
            challenge = MFAChallenge(**challenge_data)

            # Check status
            if challenge.status != MFAStatus.PENDING:
                return Err("Challenge already completed")

            # Check attempts
            if challenge.attempts >= challenge.max_attempts:
                await self._mark_challenge_failed(challenge)
                return Ok(
                    MFAVerificationResult(
                        success=False,
                        challenge_id=challenge.challenge_id,
                        method=challenge.method,
                        error_message="Maximum attempts exceeded",
                        remaining_attempts=0,
                    )
                )

            # Verify based on method
            verification_success = False
            error_message = None

            if challenge.method == MFAMethod.TOTP and request.code:
                # Get user's TOTP secret
                config_result = await self.get_user_mfa_config(challenge.user_id)
                if isinstance(config_result, Ok):
                    config = config_result.value
                    if config.totp_secret_encrypted:
                        verify_result = self._totp_provider.verify_code(
                            config.totp_secret_encrypted, request.code
                        )
                        if isinstance(verify_result, Ok):
                            verification_success = verify_result.value
                        else:
                            error_message = verify_result.error

            elif challenge.method == MFAMethod.SMS and request.code:
                # Verify SMS code
                # Implementation would verify against stored SMS challenge
                verification_success = True  # Mock for now

            elif challenge.method == MFAMethod.WEBAUTHN and request.credential_response:
                # Verify WebAuthn response
                # Implementation would verify credential
                verification_success = True  # Mock for now

            elif challenge.method == MFAMethod.RECOVERY_CODE and request.code:
                # Verify recovery code
                verify_result = await self._verify_recovery_code(
                    challenge.user_id, request.code
                )
                if isinstance(verify_result, Ok):
                    verification_success = verify_result.value
                else:
                    error_message = verify_result.error

            # Update challenge
            if verification_success:
                challenge.status = MFAStatus.VERIFIED
                challenge.verified_at = datetime.now(timezone.utc)
            else:
                challenge.attempts += 1

            # Store updated challenge
            await self._cache.set(
                f"mfa_challenge:{challenge.challenge_id}",
                challenge.model_dump(),
                ttl=60,  # Keep for 1 minute after completion
            )

            return Ok(
                MFAVerificationResult(
                    success=verification_success,
                    challenge_id=challenge.challenge_id,
                    method=challenge.method,
                    verified_at=challenge.verified_at if verification_success else None,
                    error_message=error_message,
                    remaining_attempts=challenge.max_attempts - challenge.attempts,
                )
            )

        except Exception as e:
            return Err(f"Failed to verify MFA challenge: {str(e)}")

    @beartype
    async def trust_device(
        self,
        user_id: UUID,
        device_fingerprint: str,
        device_name: str,
        ip_address: str,
        user_agent: str,
    ) -> Result[DeviceTrust, str]:
        """Mark device as trusted for future logins.

        Args:
            user_id: User's ID
            device_fingerprint: Unique device identifier
            device_name: Human-readable device name
            ip_address: Device IP address
            user_agent: Device user agent

        Returns:
            Result containing device trust record or error
        """
        try:
            device_trust = DeviceTrust(
                device_id=uuid4(),
                user_id=user_id,
                device_fingerprint=device_fingerprint,
                device_name=device_name,
                trusted_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + self._device_trust_duration,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            # Store in cache (in production, use database)
            await self._cache.set(
                f"trusted_device:{user_id}:{device_fingerprint}",
                device_trust.model_dump(),
                ttl=int(self._device_trust_duration.total_seconds()),
            )

            return Ok(device_trust)

        except Exception as e:
            return Err(f"Failed to trust device: {str(e)}")

    @beartype
    async def is_device_trusted(self, user_id: UUID, device_fingerprint: str) -> bool:
        """Check if device is trusted.

        Args:
            user_id: User's ID
            device_fingerprint: Device identifier

        Returns:
            True if device is trusted, False otherwise
        """
        try:
            device_data = await self._cache.get(
                f"trusted_device:{user_id}:{device_fingerprint}"
            )

            if not device_data:
                return False

            # Check expiry
            device_trust = DeviceTrust(**device_data)
            return device_trust.expires_at > datetime.now(timezone.utc)

        except Exception:
            return False

    @beartype
    async def generate_recovery_codes(self, user_id: UUID) -> Result[list[str], str]:
        """Generate new recovery codes for user.

        Args:
            user_id: User's ID

        Returns:
            Result containing recovery codes or error
        """
        try:
            # Generate codes
            codes = [
                f"{secrets.randbelow(10**self._recovery_code_length):0{self._recovery_code_length}d}"
                for _ in range(self._recovery_codes_count)
            ]

            # Encrypt codes for storage
            encrypted_codes = [self._encrypt_recovery_code(code) for code in codes]

            # Update database
            await self._db.execute(
                """
                UPDATE user_mfa_settings
                SET recovery_codes_encrypted = $2, updated_at = $3
                WHERE user_id = $1
                """,
                user_id,
                encrypted_codes,
                datetime.now(timezone.utc),
            )

            return Ok(codes)

        except Exception as e:
            return Err(f"Failed to generate recovery codes: {str(e)}")

    # Helper methods

    @beartype
    def _select_mfa_method(
        self,
        config: MFAConfig,
        risk_assessment: RiskAssessment | None,
        preferred_method: MFAMethod | None,
    ) -> MFAMethod | None:
        """Select appropriate MFA method based on config and risk."""
        available_methods = []

        if config.totp_enabled:
            available_methods.append(MFAMethod.TOTP)
        if config.webauthn_enabled and config.webauthn_credentials:
            available_methods.append(MFAMethod.WEBAUTHN)
        if config.sms_enabled and config.sms_phone_encrypted:
            available_methods.append(MFAMethod.SMS)
        if config.recovery_codes_encrypted:
            available_methods.append(MFAMethod.RECOVERY_CODE)

        if not available_methods:
            return None

        # If risk assessment provided, filter by recommended methods
        if risk_assessment and risk_assessment.recommended_methods:
            recommended = set(risk_assessment.recommended_methods)
            available_methods = [m for m in available_methods if m in recommended]

        # Use preferred method if available
        if preferred_method and preferred_method in available_methods:
            return preferred_method

        # Use user's preferred method
        if config.preferred_method and config.preferred_method in available_methods:
            return config.preferred_method

        # Default priority: WebAuthn > TOTP > SMS > Recovery
        priority = [
            MFAMethod.WEBAUTHN,
            MFAMethod.TOTP,
            MFAMethod.SMS,
            MFAMethod.RECOVERY_CODE,
        ]

        for method in priority:
            if method in available_methods:
                return method

        return available_methods[0] if available_methods else None

    @beartype
    async def _create_default_mfa_config(self, user_id: UUID) -> Result[MFAConfig, str]:
        """Create default MFA configuration for new user."""
        try:
            now = datetime.now(timezone.utc)

            await self._db.execute(
                """
                INSERT INTO user_mfa_settings (
                    user_id, totp_enabled, webauthn_enabled,
                    sms_enabled, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                user_id,
                False,
                False,
                False,
                now,
                now,
            )

            return Ok(
                MFAConfig(
                    user_id=user_id,
                    totp_enabled=False,
                    totp_secret_encrypted=None,
                    webauthn_enabled=False,
                    webauthn_credentials=[],
                    sms_enabled=False,
                    sms_phone_encrypted=None,
                    recovery_codes_encrypted=[],
                    preferred_method=None,
                    created_at=now,
                    updated_at=now,
                )
            )

        except Exception as e:
            return Err(f"Failed to create default MFA config: {str(e)}")

    @beartype
    async def _get_webauthn_credentials(self, user_id: UUID) -> list[Any]:
        """Get user's WebAuthn credentials."""
        # Mock implementation - in production, query from database
        return []

    @beartype
    def _encrypt_recovery_code(self, code: str) -> str:
        """Encrypt recovery code for storage."""
        # Use same encryption as TOTP secrets
        import base64

        from cryptography.fernet import Fernet

        key_material = self._settings.secret_key.encode()
        if len(key_material) < 32:
            key_material = key_material + b"0" * (32 - len(key_material))
        else:
            key_material = key_material[:32]

        key = base64.urlsafe_b64encode(key_material)
        fernet = Fernet(key)

        return fernet.encrypt(code.encode()).decode()

    @beartype
    async def _verify_recovery_code(self, user_id: UUID, code: str) -> Result[bool, str]:
        """Verify and consume recovery code."""
        try:
            # Get user's recovery codes
            config_result = await self.get_user_mfa_config(user_id)
            if isinstance(config_result, Err):
                return config_result

            config = config_result.value
            if not config.recovery_codes_encrypted:
                return Err("No recovery codes available")

            # Check each encrypted code
            code_index = -1
            for i, encrypted_code in enumerate(config.recovery_codes_encrypted):
                decrypted = self._decrypt_recovery_code(encrypted_code)
                if decrypted == code:
                    code_index = i
                    break

            if code_index == -1:
                return Err("Invalid recovery code")

            # Remove used code
            remaining_codes = [
                c
                for i, c in enumerate(config.recovery_codes_encrypted)
                if i != code_index
            ]

            # Update database
            await self._db.execute(
                """
                UPDATE user_mfa_settings
                SET recovery_codes_encrypted = $2, updated_at = $3
                WHERE user_id = $1
                """,
                user_id,
                remaining_codes,
                datetime.now(timezone.utc),
            )

            return Ok(True)

        except Exception as e:
            return Err(f"Failed to verify recovery code: {str(e)}")

    @beartype
    def _decrypt_recovery_code(self, encrypted_code: str) -> str:
        """Decrypt recovery code."""
        import base64

        from cryptography.fernet import Fernet

        key_material = self._settings.secret_key.encode()
        if len(key_material) < 32:
            key_material = key_material + b"0" * (32 - len(key_material))
        else:
            key_material = key_material[:32]

        key = base64.urlsafe_b64encode(key_material)
        fernet = Fernet(key)

        return fernet.decrypt(encrypted_code.encode()).decode()

    @beartype
    async def _mark_challenge_failed(self, challenge: MFAChallenge) -> None:
        """Mark challenge as failed."""
        challenge.status = MFAStatus.FAILED
        await self._cache.set(
            f"mfa_challenge:{challenge.challenge_id}",
            challenge.model_dump(),
            ttl=300,  # Keep for 5 minutes for audit
        )
