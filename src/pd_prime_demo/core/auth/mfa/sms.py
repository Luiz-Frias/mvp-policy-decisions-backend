"""SMS provider with anti-SIM swap protection."""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from beartype import beartype
from cryptography.fernet import Fernet

from pd_prime_demo.core.result_types import Err, Ok, Result

from ....core.cache import Cache
from ....core.config import Settings
from .models import SMSVerification
from pydantic import BaseModel, ConfigDict, Field
from beartype import beartype


@beartype
class SIMSwapCheckResult(BaseModel):
    """SIM swap security check result."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    sim_swap_safe: bool
    days_since_activation: int
    carrier_verified: bool
    risk_score: float = Field(..., ge=0.0, le=1.0)


@beartype
class SMSVerificationCacheData(BaseModel):
    """SMS verification cache data structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    user_id: str
    phone_hash: str
    code_hash: str
    attempts: int
    expires_at: str  # ISO format datetime
    sim_swap_check: SIMSwapCheckResult


class SMSProvider:
    """SMS provider with anti-SIM swap and carrier verification."""

    def __init__(self, settings: Settings, cache: Cache) -> None:
        """Initialize SMS provider."""
        self._settings = settings
        self._cache = cache
        self._encryption_key = self._get_encryption_key()
        self._fernet = Fernet(self._encryption_key)

        # SMS configuration
        self._code_length = 6
        self._code_expiry = timedelta(minutes=10)
        self._max_attempts = 3
        self._rate_limit_window = timedelta(minutes=60)
        self._max_sends_per_window = 3

        # Anti-SIM swap configuration
        self._sim_swap_delay = timedelta(hours=24)  # Delay after SIM change
        self._require_carrier_verification = True

    @beartype
    def _get_encryption_key(self) -> bytes:
        """Get encryption key for phone numbers."""
        import base64

        key_material = self._settings.secret_key.encode()
        if len(key_material) < 32:
            key_material = key_material + b"0" * (32 - len(key_material))
        else:
            key_material = key_material[:32]
        return base64.urlsafe_b64encode(key_material)

    @beartype
    def encrypt_phone_number(self, phone_number: str) -> Result[str, str]:
        """Encrypt phone number for storage.

        Args:
            phone_number: Phone number in E.164 format

        Returns:
            Result containing encrypted phone number or error
        """
        try:
            # Normalize phone number
            normalized = self._normalize_phone_number(phone_number)
            if not normalized:
                return Err("Invalid phone number format")

            encrypted = self._fernet.encrypt(normalized.encode())
            return Ok(encrypted.decode())
        except Exception as e:
            return Err(f"Failed to encrypt phone number: {str(e)}")

    @beartype
    def _normalize_phone_number(self, phone_number: str) -> str | None:
        """Normalize phone number to E.164 format."""
        # Remove all non-digit characters except +
        cleaned = "".join(c for c in phone_number if c.isdigit() or c == "+")

        # Ensure it starts with +
        if not cleaned.startswith("+"):
            # Assume US number if no country code
            cleaned = "+1" + cleaned

        # Basic validation (should be more comprehensive)
        if len(cleaned) < 10 or len(cleaned) > 15:
            return None

        return cleaned

    @beartype
    async def send_verification_code(
        self, user_id: str, encrypted_phone: str, purpose: str = "mfa"
    ) -> Result[SMSVerification, str]:
        """Send verification code via SMS with anti-SIM swap checks.

        Args:
            user_id: User's ID
            encrypted_phone: Encrypted phone number
            purpose: Purpose of verification (mfa, recovery, etc.)

        Returns:
            Result containing verification details or error
        """
        try:
            # Check rate limiting
            rate_limit_check = await self._check_rate_limit(user_id)
            if isinstance(rate_limit_check, Err):
                return rate_limit_check

            # Decrypt phone number
            phone_result = self._decrypt_phone_number(encrypted_phone)
            if isinstance(phone_result, Err):
                return phone_result
            phone_number = phone_result.value

            # Perform anti-SIM swap checks
            sim_swap_check = await self._check_sim_swap_risk(phone_number)
            if isinstance(sim_swap_check, Err):
                return sim_swap_check

            # Generate verification code
            code = self._generate_verification_code()

            # Store verification details
            verification_id = secrets.token_urlsafe(16)
            verification = SMSVerification(
                phone_number=phone_number,
                verification_code=code,
                sent_at=datetime.now(timezone.utc),
                expires_at=datetime.now(timezone.utc) + self._code_expiry,
                sim_swap_check_passed=sim_swap_check.value.sim_swap_safe,
                carrier_verified=sim_swap_check.value.carrier_verified,
            )

            # Create cache data structure
            cache_data = SMSVerificationCacheData(
                user_id=user_id,
                phone_hash=self._hash_phone_number(phone_number),
                code_hash=self._hash_code(code),
                attempts=0,
                expires_at=verification.expires_at.isoformat(),
                sim_swap_check=sim_swap_check.value,
            )

            # Store in cache
            await self._cache.set(
                f"sms_verification:{verification_id}",
                cache_data.model_dump(),
                int(self._code_expiry.total_seconds()),
            )

            # Send SMS (actual implementation would use Twilio/AWS SNS)
            send_result = await self._send_sms(phone_number, code, purpose)
            if isinstance(send_result, Err):
                return send_result

            # Update rate limit
            await self._update_rate_limit(user_id)

            # Return verification (without actual code for security)
            return Ok(
                SMSVerification(
                    phone_number="***" + phone_number[-4:],  # Masked
                    verification_code="",  # Don't return actual code
                    sent_at=verification.sent_at,
                    expires_at=verification.expires_at,
                    sim_swap_check_passed=verification.sim_swap_check_passed,
                    carrier_verified=verification.carrier_verified,
                )
            )

        except Exception as e:
            return Err(f"Failed to send SMS verification: {str(e)}")

    @beartype
    async def verify_code(self, verification_id: str, code: str, user_id: str) -> Result[bool, str]:
        """Verify SMS code with attempt tracking.

        Args:
            verification_id: Verification session ID
            code: User provided code
            user_id: User's ID for validation

        Returns:
            Result containing verification status or error
        """
        try:
            # Get verification details
            cache_key = f"sms_verification:{verification_id}"
            verification_data_dict = await self._cache.get(cache_key)

            if not verification_data_dict:
                return Err("Verification session not found or expired")

            # Reconstruct verification data from cache
            verification_data = SMSVerificationCacheData(**verification_data_dict)

            # Validate user
            if verification_data.user_id != user_id:
                return Err("Invalid verification session")

            # Check expiry
            expires_at = datetime.fromisoformat(verification_data.expires_at)
            if datetime.now(timezone.utc) > expires_at:
                await self._cache.delete(cache_key)
                return Err("Verification code expired")

            # Check attempts
            if verification_data.attempts >= self._max_attempts:
                await self._cache.delete(cache_key)
                return Err("Maximum verification attempts exceeded")

            # Verify code
            code_hash = self._hash_code(code)
            if not hmac.compare_digest(code_hash, verification_data.code_hash):
                # Update attempts - create new data with incremented attempts
                updated_data = SMSVerificationCacheData(
                    user_id=verification_data.user_id,
                    phone_hash=verification_data.phone_hash,
                    code_hash=verification_data.code_hash,
                    attempts=verification_data.attempts + 1,
                    expires_at=verification_data.expires_at,
                    sim_swap_check=verification_data.sim_swap_check,
                )
                await self._cache.set(
                    cache_key,
                    updated_data.model_dump(),
                    ttl=int((expires_at - datetime.now(timezone.utc)).total_seconds()),
                )

                remaining = self._max_attempts - updated_data.attempts
                return Err(f"Invalid code. {remaining} attempts remaining")

            # Success - clear verification
            await self._cache.delete(cache_key)

            # Log successful verification
            await self._log_verification_success(user_id, verification_data)

            return Ok(True)

        except Exception as e:
            return Err(f"Failed to verify SMS code: {str(e)}")

    @beartype
    def _decrypt_phone_number(self, encrypted_phone: str) -> Result[str, str]:
        """Decrypt phone number."""
        try:
            decrypted = self._fernet.decrypt(encrypted_phone.encode())
            return Ok(decrypted.decode())
        except Exception as e:
            return Err(f"Failed to decrypt phone number: {str(e)}")

    @beartype
    async def _check_sim_swap_risk(self, phone_number: str) -> Result[SIMSwapCheckResult, str]:
        """Check for SIM swap risk indicators.

        In production, this would integrate with carrier APIs.
        """
        try:
            # Mock implementation - in production, use carrier APIs
            # like Twilio Verify or similar services

            days_since_activation = 90  # Mock data
            sim_swap_safe = True
            risk_score = 0.1

            # Check if SIM was recently swapped
            if days_since_activation < 1:
                sim_swap_safe = False
                risk_score = 0.9

                # For high-risk scenarios, require additional verification
                return Err(
                    "SMS verification temporarily unavailable due to recent SIM change. "
                    "Please use an alternative authentication method."
                )

            risk_indicators = SIMSwapCheckResult(
                sim_swap_safe=sim_swap_safe,
                days_since_activation=days_since_activation,
                carrier_verified=True,
                risk_score=risk_score,
            )

            return Ok(risk_indicators)

        except Exception as e:
            # If risk check fails, err on the side of caution
            return Err(f"Unable to verify phone security: {str(e)}")

    @beartype
    async def _check_rate_limit(self, user_id: str) -> Result[None, str]:
        """Check SMS rate limiting."""
        try:
            rate_key = f"sms_rate_limit:{user_id}"
            current_count = await self._cache.get(rate_key) or 0

            if current_count >= self._max_sends_per_window:
                return Err("SMS rate limit exceeded. Please try again later.")

            return Ok(None)

        except Exception:
            return Ok(None)  # Don't block on rate limit errors

    @beartype
    async def _update_rate_limit(self, user_id: str) -> None:
        """Update SMS rate limit counter."""
        try:
            rate_key = f"sms_rate_limit:{user_id}"
            current_count = await self._cache.get(rate_key) or 0

            await self._cache.set(
                rate_key,
                current_count + 1,
                int(self._rate_limit_window.total_seconds()),
            )
        except Exception:
            pass  # Don't fail on rate limit update

    @beartype
    def _generate_verification_code(self) -> str:
        """Generate secure verification code."""
        return f"{secrets.randbelow(10**self._code_length):0{self._code_length}d}"

    @beartype
    def _hash_phone_number(self, phone_number: str) -> str:
        """Hash phone number for secure comparison."""
        return hashlib.sha256(
            (phone_number + self._settings.secret_key).encode()
        ).hexdigest()

    @beartype
    def _hash_code(self, code: str) -> str:
        """Hash verification code for secure storage."""
        return hashlib.sha256((code + self._settings.secret_key).encode()).hexdigest()

    @beartype
    async def _send_sms(self, phone_number: str, code: str, purpose: str) -> Result[str, str]:
        """Send SMS via provider (Twilio/AWS SNS).

        This is a mock implementation. In production, integrate with real SMS provider.
        """
        try:
            # In production, use Twilio or AWS SNS
            # Example with Twilio:
            # client = Client(account_sid, auth_token)
            # message = client.messages.create(
            #     body=f"Your {purpose} verification code is: {code}",
            #     from_='+1234567890',
            #     to=phone_number
            # )

            print(f"[MOCK SMS] To: {phone_number}, Code: {code}, Purpose: {purpose}")
            return Ok("SMS sent successfully")

        except Exception as e:
            return Err(f"Failed to send SMS: {str(e)}")

    @beartype
    async def _log_verification_success(
        self, user_id: str, verification_data: SMSVerificationCacheData
    ) -> None:
        """Log successful verification for audit trail."""
        # In production, log to audit system
        pass
