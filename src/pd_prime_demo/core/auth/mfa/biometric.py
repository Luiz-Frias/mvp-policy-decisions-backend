"""Biometric authentication provider."""

import base64
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from beartype import beartype
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from pd_prime_demo.core.result_types import Err, Ok, Result

from ....core.cache import Cache
from ....core.config import Settings


class BiometricProvider:
    """Biometric authentication provider for fingerprint and face recognition."""

    def __init__(self, settings: Settings, cache: Cache) -> None:
        """Initialize biometric provider."""
        self._settings = settings
        self._cache = cache

        # Biometric configuration
        self._challenge_expiry = 300  # 5 minutes
        self._max_templates = 5  # Max biometric templates per user
        self._similarity_threshold = 0.95  # For biometric matching

        # Supported biometric types
        self._supported_types = ["fingerprint", "face", "voice"]

    @beartype
    async def enroll_biometric(
        self,
        user_id: UUID,
        biometric_type: str,
        template_data: str,
        device_info: dict[str, Any],
    ) -> Result[dict[str, Any], str]:
        """Enroll new biometric template.

        Args:
            user_id: User's ID
            biometric_type: Type of biometric (fingerprint, face, voice)
            template_data: Base64 encoded biometric template
            device_info: Information about the capturing device

        Returns:
            Result containing enrollment details or error
        """
        try:
            # Validate biometric type
            if biometric_type not in self._supported_types:
                return Err(f"Unsupported biometric type: {biometric_type}")

            # Validate template data
            if not self._validate_template(template_data, biometric_type):
                return Err("Invalid biometric template data")

            # Generate template ID
            template_id = str(uuid4())

            # Create template hash for matching
            template_hash = self._hash_template(template_data)

            # Store template metadata (not the actual biometric data)
            template_metadata = {
                "template_id": template_id,
                "user_id": str(user_id),
                "type": biometric_type,
                "template_hash": template_hash,
                "device_info": device_info,
                "enrolled_at": datetime.now(timezone.utc).isoformat(),
                "last_used_at": None,
                "use_count": 0,
            }

            # Store in cache (in production, use secure database)
            cache_key = f"biometric:{user_id}:{template_id}"
            await self._cache.set(
                cache_key, template_metadata, ttl=86400 * 365  # 1 year
            )

            # Update user's biometric list
            await self._update_user_biometrics(user_id, template_id, biometric_type)

            return Ok(
                {
                    "template_id": template_id,
                    "type": biometric_type,
                    "enrolled_at": template_metadata["enrolled_at"],
                    "device_name": device_info.get("name", "Unknown Device"),
                }
            )

        except Exception as e:
            return Err(f"Failed to enroll biometric: {str(e)}")

    @beartype
    async def create_authentication_challenge(
        self, user_id: UUID, biometric_type: str
    ) -> Result[dict[str, Any], str]:
        """Create biometric authentication challenge.

        Args:
            user_id: User's ID
            biometric_type: Type of biometric to use

        Returns:
            Result containing challenge data or error
        """
        try:
            # Check if user has enrolled biometrics
            user_biometrics = await self._get_user_biometrics(user_id)
            if not user_biometrics:
                return Err("No biometric data enrolled for user")

            # Filter by requested type
            type_biometrics = [
                b for b in user_biometrics if b.get("type") == biometric_type
            ]

            if not type_biometrics:
                return Err(f"No {biometric_type} biometric enrolled")

            # Create challenge
            challenge_id = str(uuid4())
            challenge_data = {
                "challenge_id": challenge_id,
                "user_id": str(user_id),
                "biometric_type": biometric_type,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "valid_templates": [b["template_id"] for b in type_biometrics],
                "status": "pending",
            }

            # Store challenge
            await self._cache.set(
                f"biometric_challenge:{challenge_id}",
                challenge_data,
                ttl=self._challenge_expiry,
            )

            # Return challenge info
            return Ok(
                {
                    "challenge_id": challenge_id,
                    "type": biometric_type,
                    "expires_in": self._challenge_expiry,
                    "capture_settings": self._get_capture_settings(biometric_type),
                }
            )

        except Exception as e:
            return Err(f"Failed to create biometric challenge: {str(e)}")

    @beartype
    async def verify_biometric(
        self,
        challenge_id: str,
        biometric_data: str,
        liveness_data: dict[str, Any] | None = None,
    ):
        """Verify biometric authentication.

        Args:
            challenge_id: Challenge ID
            biometric_data: Base64 encoded biometric data
            liveness_data: Optional liveness detection data

        Returns:
            Result containing verification status or error
        """
        try:
            # Get challenge
            challenge_key = f"biometric_challenge:{challenge_id}"
            challenge = await self._cache.get(challenge_key)

            if not challenge:
                return Err("Challenge not found or expired")

            # Check challenge status
            if challenge["status"] != "pending":
                return Err("Challenge already used")

            # Perform liveness check if provided
            if liveness_data:
                liveness_result = await self._check_liveness(
                    challenge["biometric_type"], liveness_data
                )
                if isinstance(liveness_result, Err):
                    return liveness_result
                if not liveness_result.value:
                    return Err("Liveness check failed")

            # Match biometric against enrolled templates
            match_found = False
            matched_template = None

            for template_id in challenge["valid_templates"]:
                template_key = f"biometric:{challenge['user_id']}:{template_id}"
                template_metadata = await self._cache.get(template_key)

                if template_metadata:
                    # Perform biometric matching (mock implementation)
                    similarity = self._match_biometric(
                        biometric_data,
                        template_metadata["template_hash"],
                        challenge["biometric_type"],
                    )

                    if similarity >= self._similarity_threshold:
                        match_found = True
                        matched_template = template_id
                        break

            # Update challenge status
            challenge["status"] = "verified" if match_found else "failed"
            await self._cache.set(
                challenge_key, challenge, ttl=60  # Keep for 1 minute for audit
            )

            if match_found:
                # Update template usage stats
                await self._update_template_usage(
                    challenge["user_id"], matched_template
                )

                return Ok(True)
            else:
                return Err("Biometric verification failed")

        except Exception as e:
            return Err(f"Failed to verify biometric: {str(e)}")

    @beartype
    async def remove_biometric(self, user_id: UUID, template_id: str):
        """Remove biometric template.

        Args:
            user_id: User's ID
            template_id: Template ID to remove

        Returns:
            Result indicating success or error
        """
        try:
            # Remove template
            cache_key = f"biometric:{user_id}:{template_id}"
            await self._cache.delete(cache_key)

            # Update user's biometric list
            user_biometrics = await self._get_user_biometrics(user_id)
            updated_biometrics = [
                b for b in user_biometrics if b.get("template_id") != template_id
            ]

            await self._cache.set(
                f"user_biometrics:{user_id}", updated_biometrics, ttl=86400 * 365
            )

            return Ok(True)

        except Exception as e:
            return Err(f"Failed to remove biometric: {str(e)}")

    @beartype
    def _validate_template(self, template_data: str, biometric_type: str) -> bool:
        """Validate biometric template format and content."""
        try:
            # Decode base64
            decoded = base64.b64decode(template_data)

            # Check minimum size based on type
            min_sizes = {
                "fingerprint": 512,  # Minimum fingerprint template size
                "face": 1024,  # Minimum face template size
                "voice": 2048,  # Minimum voice template size
            }

            min_size = min_sizes.get(biometric_type, 512)
            if len(decoded) < min_size:
                return False

            # Additional validation could check format headers, etc.
            return True

        except Exception:
            return False

    @beartype
    def _hash_template(self, template_data: str) -> str:
        """Create secure hash of biometric template."""
        # Use PBKDF2 for additional security
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._settings.secret_key.encode()[:16],
            iterations=100000,
        )

        key = kdf.derive(template_data.encode())
        return base64.b64encode(key).decode()

    @beartype
    async def _get_user_biometrics(self, user_id: UUID) -> list[dict[str, Any]]:
        """Get user's enrolled biometric templates."""
        user_biometrics = await self._cache.get(f"user_biometrics:{user_id}")
        return user_biometrics or []

    @beartype
    async def _update_user_biometrics(
        self, user_id: UUID, template_id: str, biometric_type: str
    ) -> None:
        """Update user's biometric list."""
        user_biometrics = await self._get_user_biometrics(user_id)

        # Check max templates limit
        if len(user_biometrics) >= self._max_templates:
            # Remove oldest template
            user_biometrics.sort(key=lambda x: x.get("enrolled_at", ""))
            oldest = user_biometrics[0]
            await self._cache.delete(f"biometric:{user_id}:{oldest['template_id']}")
            user_biometrics = user_biometrics[1:]

        # Add new template
        user_biometrics.append(
            {
                "template_id": template_id,
                "type": biometric_type,
                "enrolled_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        await self._cache.set(
            f"user_biometrics:{user_id}", user_biometrics, ttl=86400 * 365
        )

    @beartype
    def _get_capture_settings(self, biometric_type: str) -> dict[str, Any]:
        """Get recommended capture settings for biometric type."""
        settings = {
            "fingerprint": {
                "min_quality": 80,
                "capture_timeout": 30,
                "finger_detect": True,
                "anti_spoofing": True,
            },
            "face": {
                "min_quality": 85,
                "capture_timeout": 20,
                "face_detect": True,
                "liveness_required": True,
                "pose_variation": False,
            },
            "voice": {
                "min_duration": 3,
                "max_duration": 10,
                "sample_rate": 16000,
                "noise_reduction": True,
            },
        }

        return settings.get(biometric_type, {})

    @beartype
    async def _check_liveness(self, biometric_type: str, liveness_data: dict[str, Any]):
        """Check liveness to prevent spoofing attacks."""
        try:
            # Mock liveness detection
            # In production, use specialized liveness detection libraries

            if biometric_type == "face":
                # Check for blink detection, head movement, etc.
                has_blink = liveness_data.get("blink_detected", False)
                has_movement = liveness_data.get("head_movement", False)

                if not (has_blink or has_movement):
                    return Ok(False)

            elif biometric_type == "fingerprint":
                # Check for pulse detection, temperature, etc.
                has_pulse = liveness_data.get("pulse_detected", False)
                temperature_ok = liveness_data.get("temperature_range", False)

                if not (has_pulse and temperature_ok):
                    return Ok(False)

            return Ok(True)

        except Exception as e:
            return Err(f"Liveness check error: {str(e)}")

    @beartype
    def _match_biometric(
        self, biometric_data: str, template_hash: str, biometric_type: str
    ) -> float:
        """Match biometric data against template.

        This is a mock implementation. In production, use specialized
        biometric matching libraries for each type.
        """
        # Create hash of provided biometric
        provided_hash = self._hash_template(biometric_data)

        # In real implementation, this would use sophisticated matching algorithms
        # For now, simple hash comparison
        if provided_hash == template_hash:
            return 1.0
        else:
            # Calculate similarity (mock)
            return 0.8  # Mock similarity score

    @beartype
    async def _update_template_usage(self, user_id: str, template_id: str) -> None:
        """Update template usage statistics."""
        cache_key = f"biometric:{user_id}:{template_id}"
        template_metadata = await self._cache.get(cache_key)

        if template_metadata:
            template_metadata["last_used_at"] = datetime.now(timezone.utc).isoformat()
            template_metadata["use_count"] = template_metadata.get("use_count", 0) + 1

            await self._cache.set(cache_key, template_metadata, ttl=86400 * 365)
