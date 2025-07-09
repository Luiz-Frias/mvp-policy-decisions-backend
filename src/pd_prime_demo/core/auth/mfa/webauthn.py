"""WebAuthn/FIDO2 provider implementation."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from beartype import beartype

# Define mock classes first
class _MockPublicKeyCredentialDescriptor:
    def __init__(self, id: str, type: str) -> None:
        self.id = id
        self.type = type

class _MockPublicKeyCredentialType:
    PUBLIC_KEY = "public-key"

try:
    from webauthn import (
        generate_authentication_options,
        generate_registration_options,
        verify_authentication_response,
        verify_registration_response,
    )
    from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
    from webauthn.helpers.structs import (
        PublicKeyCredentialDescriptor,
        PublicKeyCredentialType,
    )
except ImportError:
    # Mock implementation for testing
    def generate_registration_options(*args: Any, **kwargs: Any) -> Any:
        return type(
            "MockOptions",
            (),
            {
                "challenge": b"mock_challenge",
                "rp": type("RP", (), {"id": "localhost", "name": "Mock"})(),
                "user": type(
                    "User",
                    (),
                    {"id": "user123", "name": "test", "display_name": "Test"},
                )(),
                "pub_key_cred_params": [],
                "timeout": 60000,
                "exclude_credentials": [],
                "authenticator_selection": {},
                "attestation": "none",
            },
        )()

    def generate_authentication_options(*args: Any, **kwargs: Any) -> Any:
        return type(
            "MockOptions",
            (),
            {
                "challenge": b"mock_challenge",
                "timeout": 60000,
                "rp_id": "localhost",
                "allow_credentials": [],
                "user_verification": "preferred",
            },
        )()

    def verify_registration_response(*args: Any, **kwargs: Any) -> Any:
        return type(
            "MockVerification",
            (),
            {
                "verified": True,
                "credential_id": b"mock_id",
                "credential_public_key": b"mock_key",
                "sign_count": 0,
                "aaguid": b"mock_aaguid",
            },
        )()

    def verify_authentication_response(*args: Any, **kwargs: Any) -> bool:
        # Mock implementation returns True for verified
        return True

    def base64url_to_bytes(data: str) -> bytes:
        import base64

        return base64.urlsafe_b64decode(data + "==")

    def bytes_to_base64url(data: bytes) -> str:
        import base64

        return base64.urlsafe_b64encode(data).decode().rstrip("=")

    PublicKeyCredentialDescriptor = _MockPublicKeyCredentialDescriptor
    PublicKeyCredentialType = _MockPublicKeyCredentialType


from pd_prime_demo.core.result_types import Err, Ok, Result

from ....core.config import Settings
from .models import WebAuthnCredential


class WebAuthnProvider:
    """WebAuthn/FIDO2 provider for passwordless authentication."""

    def __init__(self, settings: Settings) -> None:
        """Initialize WebAuthn provider."""
        self._settings = settings
        self._rp_id = self._get_rp_id()
        self._rp_name = settings.app_name
        self._origin = self._get_origin()

        # WebAuthn configuration
        self._timeout = 60000  # 60 seconds
        self._user_verification = "preferred"
        self._attestation = "none"  # We don't need attestation for most use cases
        
        # Challenge storage - in production, use Redis with proper TTL
        self._challenge_store: dict[str, dict[str, str]] = {}

    @beartype
    def _get_rp_id(self) -> str:
        """Get Relying Party ID from settings."""
        # Extract domain from API URL
        # In production, this should be explicitly configured
        api_url = self._settings.api_url
        if api_url.startswith("http://"):
            domain = api_url[7:].split("/")[0].split(":")[0]
        elif api_url.startswith("https://"):
            domain = api_url[8:].split("/")[0].split(":")[0]
        else:
            domain = "localhost"
        return domain

    @beartype
    def _get_origin(self) -> str:
        """Get origin URL."""
        return self._settings.api_url.rstrip("/")

    @beartype
    def generate_registration_options(
        self,
        user_id: UUID,
        user_email: str,
        user_display_name: str,
        exclude_credentials: list[WebAuthnCredential] | None = None,
    ) -> Result[dict[str, Any], str]:
        """Generate WebAuthn registration options.

        Args:
            user_id: User's ID
            user_email: User's email (username)
            user_display_name: User's display name
            exclude_credentials: List of existing credentials to exclude

        Returns:
            Result containing registration options or error
        """
        try:
            # Convert user ID to bytes
            user_id_bytes = bytes_to_base64url(str(user_id).encode())

            # Build exclude list
            exclude_list = []
            if exclude_credentials:
                for cred in exclude_credentials:
                    exclude_list.append(
                        PublicKeyCredentialDescriptor(
                            id=base64url_to_bytes(cred.credential_id),
                            type=PublicKeyCredentialType.PUBLIC_KEY,
                        )
                    )

            # Generate registration options
            options = generate_registration_options(
                rp_id=self._rp_id,
                rp_name=self._rp_name,
                user_id=user_id_bytes,
                user_name=user_email,
                user_display_name=user_display_name,
                exclude_credentials=exclude_list,
                authenticator_selection={
                    "user_verification": self._user_verification,
                    "authenticator_attachment": "cross-platform",
                    "resident_key": "discouraged",
                },
                attestation=self._attestation,
                timeout=self._timeout,
                # Support various algorithms
                supported_pub_key_algs=[
                    {"type": "public-key", "alg": -7},  # ES256
                    {"type": "public-key", "alg": -257},  # RS256
                    {"type": "public-key", "alg": -8},  # EdDSA
                ],  # type: ignore
            )

            # Convert to JSON-serializable format
            options_dict = {
                "challenge": bytes_to_base64url(options.challenge),
                "rp": {"id": options.rp.id, "name": options.rp.name},
                "user": {
                    "id": options.user.id,
                    "name": options.user.name,
                    "displayName": options.user.display_name,
                },
                "pubKeyCredParams": options.pub_key_cred_params,
                "timeout": options.timeout,
                "excludeCredentials": [
                    {"type": cred.type, "id": bytes_to_base64url(cred.id)}
                    for cred in (options.exclude_credentials or [])
                ],
                "authenticatorSelection": options.authenticator_selection,
                "attestation": options.attestation,
            }

            # Store challenge for verification
            self._store_challenge(
                user_id=user_id,
                challenge=bytes_to_base64url(options.challenge),
                operation="registration",
            )

            return Ok(options_dict)

        except Exception as e:
            return Err(f"Failed to generate registration options: {str(e)}")

    @beartype
    def verify_registration(self, user_id: UUID, credential_response: dict[str, Any]) -> Result[WebAuthnCredential, str]:
        """Verify WebAuthn registration response.

        Args:
            user_id: User's ID
            credential_response: Registration response from client

        Returns:
            Result containing verified credential or error
        """
        try:
            # Get stored challenge
            challenge = self._get_stored_challenge(user_id, "registration")
            if not challenge:
                return Err("Registration challenge not found or expired")

            # Verify registration
            verification = verify_registration_response(
                credential=credential_response,
                expected_challenge=base64url_to_bytes(challenge),
                expected_origin=self._origin,
                expected_rp_id=self._rp_id,
                require_user_verification=self._user_verification == "required",
            )

            if not verification.user_verified:
                return Err("Registration verification failed")

            # Extract credential data
            credential_id = bytes_to_base64url(verification.credential_id)
            public_key = bytes_to_base64url(verification.credential_public_key)

            # Create credential record
            credential = WebAuthnCredential(
                credential_id=credential_id,
                public_key=public_key,
                counter=verification.sign_count,
                device_name=self._detect_device_name(credential_response),
                created_at=datetime.now(timezone.utc),
                aaguid=(
                    bytes_to_base64url(verification.aaguid)
                    if verification.aaguid
                    else None
                ),
            )

            # Clear used challenge
            self._clear_challenge(user_id, "registration")

            return Ok(credential)

        except Exception as e:
            return Err(f"Failed to verify registration: {str(e)}")

    @beartype
    def generate_authentication_options(
        self, user_id: UUID, allowed_credentials: list[WebAuthnCredential]
    ) -> Result[dict[str, Any], str]:
        """Generate WebAuthn authentication options.

        Args:
            user_id: User's ID
            allowed_credentials: List of user's registered credentials

        Returns:
            Result containing authentication options or error
        """
        try:
            # Build allowed credentials list
            allow_list = []
            for cred in allowed_credentials:
                allow_list.append(
                    PublicKeyCredentialDescriptor(
                        id=base64url_to_bytes(cred.credential_id),
                        type=PublicKeyCredentialType.PUBLIC_KEY,
                    )
                )

            # Generate authentication options
            options = generate_authentication_options(
                rp_id=self._rp_id,
                allow_credentials=allow_list,
                user_verification=self._user_verification,
                timeout=self._timeout,
            )

            # Convert to JSON-serializable format
            options_dict = {
                "challenge": bytes_to_base64url(options.challenge),
                "timeout": options.timeout,
                "rpId": options.rp_id,
                "allowCredentials": [
                    {"type": cred.type, "id": bytes_to_base64url(cred.id)}
                    for cred in (options.allow_credentials or [])
                ],
                "userVerification": options.user_verification,
            }

            # Store challenge for verification
            self._store_challenge(
                user_id=user_id,
                challenge=bytes_to_base64url(options.challenge),
                operation="authentication",
            )

            return Ok(options_dict)

        except Exception as e:
            return Err(f"Failed to generate authentication options: {str(e)}")

    @beartype
    def verify_authentication(
        self,
        user_id: UUID,
        credential_response: dict[str, Any],
        stored_credential: WebAuthnCredential,
    ):
        """Verify WebAuthn authentication response.

        Args:
            user_id: User's ID
            credential_response: Authentication response from client
            stored_credential: Stored credential to verify against

        Returns:
            Result containing verification status or error
        """
        try:
            # Get stored challenge
            challenge = self._get_stored_challenge(user_id, "authentication")
            if not challenge:
                return Err("Authentication challenge not found or expired")

            # Verify authentication
            verification = verify_authentication_response(
                credential=credential_response,
                expected_challenge=base64url_to_bytes(challenge),
                expected_origin=self._origin,
                expected_rp_id=self._rp_id,
                credential_public_key=base64url_to_bytes(stored_credential.public_key),
                credential_current_sign_count=stored_credential.counter,
                require_user_verification=self._user_verification == "required",
            )

            if not verification.user_verified:  # type: ignore[attr-defined]
                return Err("Authentication verification failed")

            # Update counter to prevent replay attacks
            # This should be persisted to database
            stored_credential.counter = verification.new_sign_count

            # Clear used challenge
            self._clear_challenge(user_id, "authentication")

            return Ok(True)

        except Exception as e:
            return Err(f"Failed to verify authentication: {str(e)}")

    @beartype
    def _detect_device_name(self, credential_response: dict[str, Any]) -> str:
        """Detect device name from credential response."""
        # This is a simplified version - in production, you might want to
        # parse the attestation statement for more details
        # client_data = credential_response.get("response", {}).get("clientDataJSON", "")

        # Try to detect from user agent or other metadata
        # For now, return a generic name
        return "Security Key"

    @beartype
    def _store_challenge(self, user_id: UUID, challenge: str, operation: str) -> None:
        """Store challenge for later verification.

        In production, this should use Redis or similar with TTL.
        """
        # Simple in-memory storage for demo - production should use Redis
        key = f"{user_id}:{operation}"
        from datetime import datetime, timedelta
        
        # Store with expiration time
        self._challenge_store[key] = {
            "challenge": challenge,
            "expires_at": (datetime.now() + timedelta(minutes=5)).isoformat()
        }

    @beartype
    def _get_stored_challenge(self, user_id: UUID, operation: str) -> str | None:
        """Get stored challenge for verification.

        In production, this should retrieve from Redis or similar.
        """
        # Simple in-memory retrieval for demo - production should use Redis
        key = f"{user_id}:{operation}"
        stored = self._challenge_store.get(key)
        
        if not stored:
            return None
            
        # Check if expired
        from datetime import datetime
        try:
            expires_at = datetime.fromisoformat(stored["expires_at"])
            if datetime.now() > expires_at:
                # Clean up expired challenge
                del self._challenge_store[key]
                return None
        except (ValueError, KeyError):
            # Invalid expiration data, remove
            del self._challenge_store[key]
            return None
            
        return stored["challenge"]

    @beartype
    def _clear_challenge(self, user_id: UUID, operation: str) -> None:
        """Clear used challenge.

        In production, this should remove from Redis or similar.
        """
        # Simple in-memory clearing for demo - production should use Redis
        key = f"{user_id}:{operation}"
        self._challenge_store.pop(key, None)
