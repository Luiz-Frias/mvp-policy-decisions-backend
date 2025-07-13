# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""TOTP (Time-based One-Time Password) provider implementation."""

import base64
import io
import secrets
from datetime import datetime, timezone

import pyotp
import qrcode  # type: ignore[import-untyped]
from beartype import beartype
from cryptography.fernet import Fernet

from policy_core.core.config import Settings
from policy_core.core.result_types import Err, Ok, Result

from .models import TOTPSetupData


class TOTPProvider:
    """TOTP provider for Google Authenticator compatible 2FA."""

    def __init__(self, settings: Settings) -> None:
        """Initialize TOTP provider."""
        self._settings = settings
        self._issuer_name = settings.app_name
        self._encryption_key = self._get_or_create_encryption_key()
        self._fernet = Fernet(self._encryption_key)

        # TOTP configuration
        self._digits = 6
        self._interval = 30  # seconds
        self._window = 1  # Allow 1 interval before/after for clock drift

    @beartype
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for TOTP secrets."""
        # In production, this should come from a secure key management service
        # For now, derive from secret key
        key_material = self._settings.secret_key.encode()
        # Ensure it's exactly 32 bytes for Fernet
        if len(key_material) < 32:
            key_material = key_material + b"0" * (32 - len(key_material))
        else:
            key_material = key_material[:32]
        return base64.urlsafe_b64encode(key_material)

    @beartype
    def generate_setup(
        self, user_email: str, user_id: str
    ) -> Result[TOTPSetupData, str]:
        """Generate TOTP setup data for user enrollment.

        Args:
            user_email: User's email address
            user_id: User's ID

        Returns:
            Result containing setup data or error
        """
        try:
            # Generate random secret
            secret = pyotp.random_base32()

            # Create TOTP URI for QR code
            totp = pyotp.TOTP(secret, digits=self._digits, interval=self._interval)
            totp_uri = totp.provisioning_uri(
                name=user_email, issuer_name=self._issuer_name
            )

            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=5,
            )
            qr.add_data(totp_uri)
            qr.make(fit=True)

            # Create QR code image
            img = qr.make_image(fill_color="black", back_color="white")

            # Convert to base64 data URL
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            qr_code_url = f"data:image/png;base64,{img_str}"

            # Generate backup codes
            backup_codes = [f"{secrets.randbelow(1000000):06d}" for _ in range(10)]

            return Ok(
                TOTPSetupData(
                    secret=secret,
                    qr_code=qr_code_url,
                    manual_entry_key=self._format_secret_for_display(secret),
                    backup_codes=backup_codes,
                )
            )

        except Exception as e:
            return Err(f"Failed to generate TOTP setup: {str(e)}")

    @beartype
    def _format_secret_for_display(self, secret: str) -> str:
        """Format secret for manual entry (groups of 4 characters)."""
        return " ".join(secret[i : i + 4] for i in range(0, len(secret), 4))

    @beartype
    def encrypt_secret(self, secret: str) -> Result[str, str]:
        """Encrypt TOTP secret for storage.

        Args:
            secret: Plain text TOTP secret

        Returns:
            Result containing encrypted secret or error
        """
        try:
            encrypted = self._fernet.encrypt(secret.encode())
            return Ok(encrypted.decode())
        except Exception as e:
            return Err(f"Failed to encrypt TOTP secret: {str(e)}")

    @beartype
    def decrypt_secret(self, encrypted_secret: str) -> Result[str, str]:
        """Decrypt TOTP secret from storage.

        Args:
            encrypted_secret: Encrypted TOTP secret

        Returns:
            Result containing decrypted secret or error
        """
        try:
            decrypted = self._fernet.decrypt(encrypted_secret.encode())
            return Ok(decrypted.decode())
        except Exception as e:
            return Err(f"Failed to decrypt TOTP secret: {str(e)}")

    @beartype
    def verify_code(self, encrypted_secret: str, code: str) -> Result[bool, str]:
        """Verify TOTP code.

        Args:
            encrypted_secret: Encrypted TOTP secret
            code: User provided code

        Returns:
            Result containing verification status or error
        """
        try:
            # Decrypt secret
            secret_result = self.decrypt_secret(encrypted_secret)
            if isinstance(secret_result, Err):
                return secret_result

            secret = secret_result.value

            # Create TOTP instance
            totp = pyotp.TOTP(secret, digits=self._digits, interval=self._interval)

            # Verify with time window for clock drift
            is_valid = totp.verify(
                code, valid_window=self._window, for_time=datetime.now(timezone.utc)
            )

            return Ok(is_valid)

        except Exception as e:
            return Err(f"Failed to verify TOTP code: {str(e)}")

    @beartype
    def generate_current_code(self, encrypted_secret: str) -> Result[str, str]:
        """Generate current TOTP code (for testing/debugging only).

        Args:
            encrypted_secret: Encrypted TOTP secret

        Returns:
            Result containing current code or error
        """
        try:
            # Decrypt secret
            secret_result = self.decrypt_secret(encrypted_secret)
            if isinstance(secret_result, Err):
                return secret_result

            secret = secret_result.value

            # Generate current code
            totp = pyotp.TOTP(secret, digits=self._digits, interval=self._interval)

            code = totp.now()
            return Ok(code)

        except Exception as e:
            return Err(f"Failed to generate TOTP code: {str(e)}")

    @beartype
    def get_time_remaining(self) -> int:
        """Get seconds remaining in current TOTP interval.

        Returns:
            Seconds until next code
        """
        current_time = int(datetime.now(timezone.utc).timestamp())
        return self._interval - (current_time % self._interval)

    @beartype
    def validate_secret(self, secret: str) -> bool:
        """Validate TOTP secret format.

        Args:
            secret: Base32 encoded secret

        Returns:
            True if valid, False otherwise
        """
        try:
            # Check if it's valid base32
            base64.b32decode(secret, casefold=True)
            # Check minimum length (80 bits = 16 base32 chars)
            return len(secret) >= 16
        except Exception:
            return False
