"""Base classes for SSO provider integration."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import uuid4

from beartype import beartype
from pydantic import ConfigDict, Field

from ...core.result_types import Err, Ok, Result

from ...models.base import BaseModelConfig


class SSOUserInfo(BaseModelConfig):
    """Standardized user info from SSO providers."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Required fields
    sub: str = Field(..., description="Subject/unique identifier from provider")
    email: str = Field(..., description="User email address")
    email_verified: bool = Field(False, description="Whether email is verified")

    # Common fields
    name: str | None = Field(None, description="Full name")
    given_name: str | None = Field(None, description="First name")
    family_name: str | None = Field(None, description="Last name")
    picture: str | None = Field(None, description="Profile picture URL")

    # Provider specific
    provider: str = Field(..., description="SSO provider name")
    provider_user_id: str = Field(..., description="User ID from provider")

    # Additional claims
    groups: list[str] = Field(
        default_factory=list, description="User groups from provider"
    )
    roles: list[str] = Field(
        default_factory=list, description="User roles from provider"
    )

    # Metadata
    last_login: datetime = Field(
        default_factory=datetime.now, description="Last login time"
    )
    raw_claims: dict[str, Any] = Field(
        default_factory=dict, description="Raw claims from provider"
    )


class SSOProvider(ABC):
    """Base class for SSO providers."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: list[str],
    ) -> None:
        """Initialize SSO provider.

        Args:
            client_id: OAuth/OIDC client ID
            client_secret: OAuth/OIDC client secret
            redirect_uri: Redirect URI for OAuth flow
            scopes: List of scopes to request
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get provider name."""
        pass

    @beartype
    @abstractmethod
    async def get_authorization_url(
        self,
        state: str,
        nonce: str | None = None,
        **kwargs: Any,
    ) -> Result[str, str]:
        """Get authorization URL for user redirect.

        Args:
            state: State parameter for CSRF protection
            nonce: Nonce for OIDC (optional)
            **kwargs: Additional provider-specific parameters

        Returns:
            Result containing authorization URL or error
        """
        pass

    @beartype
    @abstractmethod
    async def exchange_code_for_token(
        self,
        code: str,
        state: str,
    ) -> Result[dict[str, Any], str]:
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from callback
            state: State parameter for validation

        Returns:
            Result containing tokens or error
        """
        pass

    @beartype
    @abstractmethod
    async def get_user_info(
        self,
        access_token: str,
    ) -> Result[SSOUserInfo, str]:
        """Get user information from provider.

        Args:
            access_token: Access token from provider

        Returns:
            Result containing user info or error
        """
        pass

    @beartype
    @abstractmethod
    async def refresh_token(
        self,
        refresh_token: str,
    ) -> Result[dict[str, Any], str]:
        """Refresh access token.

        Args:
            refresh_token: Refresh token from provider

        Returns:
            Result containing new tokens or error
        """
        pass

    @beartype
    @abstractmethod
    async def revoke_token(
        self,
        token: str,
        token_type: str = "access_token",
    ) -> Result[bool, str]:
        """Revoke a token.

        Args:
            token: Token to revoke
            token_type: Type of token (access_token or refresh_token)

        Returns:
            Result indicating success or error
        """
        pass

    @beartype
    def validate_state(
        self,
        state: str,
        expected_state: str,
    ) -> bool:
        """Validate state parameter for CSRF protection."""
        return state == expected_state

    @beartype
    def generate_state(self) -> str:
        """Generate secure state parameter."""
        return uuid4().hex

    @beartype
    def generate_nonce(self) -> str:
        """Generate nonce for OIDC."""
        return uuid4().hex


class OIDCProvider(SSOProvider):
    """Base class for OpenID Connect providers."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        issuer: str,
        scopes: list[str] | None = None,
    ) -> None:
        """Initialize OIDC provider.

        Args:
            client_id: OIDC client ID
            client_secret: OIDC client secret
            redirect_uri: Redirect URI for OAuth flow
            issuer: OIDC issuer URL
            scopes: List of scopes (defaults to standard OIDC scopes)
        """
        default_scopes = ["openid", "email", "profile"]
        super().__init__(
            client_id,
            client_secret,
            redirect_uri,
            scopes or default_scopes,
        )
        self.issuer = issuer
        self._discovery_document: dict[str, Any] | None = None

    @beartype
    async def discover(self) -> Result[dict[str, Any], str]:
        """Get OIDC discovery document.

        Returns:
            Result containing discovery document or error
        """
        if self._discovery_document:
            return Ok(self._discovery_document)

        # Fetch discovery document
        discovery_url = f"{self.issuer}/.well-known/openid-configuration"

        try:
            import httpx

            async with httpx.AsyncClient() as client:
                response = await client.get(discovery_url)
                response.raise_for_status()
                self._discovery_document = response.json()
                return Ok(self._discovery_document)
        except Exception as e:
            return Err(f"Failed to fetch discovery document: {str(e)}")

    @beartype
    async def validate_id_token(
        self,
        id_token: str,
        nonce: str | None = None,
    ) -> Result[dict[str, Any], str]:
        """Validate and decode ID token.

        Args:
            id_token: ID token to validate
            nonce: Nonce to verify (if provided)

        Returns:
            Result containing decoded claims or error
        """
        try:
            # Get JWKS
            discovery_result = await self.discover()
            if isinstance(discovery_result, Err):
                return discovery_result

            discovery = discovery_result.value
            jwks_uri = discovery.get("jwks_uri")
            if not jwks_uri:
                return Err("JWKS URI not found in discovery document")

            # Import JWT library
            import jwt
            from jwt import PyJWKClient

            # Fetch JWKS and validate token
            jwks_client = PyJWKClient(jwks_uri)
            signing_key = jwks_client.get_signing_key_from_jwt(id_token)

            # Decode and validate token
            claims = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=self.issuer,
            )

            # Additional validations
            if nonce and claims.get("nonce") != nonce:
                return Err("Invalid nonce")

            return Ok(claims)

        except jwt.ExpiredSignatureError:
            return Err("ID token has expired")
        except jwt.InvalidTokenError as e:
            return Err(f"Invalid ID token: {str(e)}")
        except Exception as e:
            return Err(f"Failed to validate ID token: {str(e)}")


class SAMLProvider(SSOProvider):
    """Base class for SAML providers."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        entity_id: str,
        sso_url: str,
        x509_cert: str,
        scopes: list[str] | None = None,
    ) -> None:
        """Initialize SAML provider.

        Args:
            client_id: Service provider entity ID
            client_secret: Not used for SAML, kept for interface compatibility
            redirect_uri: Assertion Consumer Service URL
            entity_id: Identity provider entity ID
            sso_url: SAML SSO URL
            x509_cert: X.509 certificate for signature verification
            scopes: Not used for SAML
        """
        super().__init__(
            client_id,
            client_secret,
            redirect_uri,
            scopes or [],
        )
        self.entity_id = entity_id
        self.sso_url = sso_url
        self.x509_cert = x509_cert

    @beartype
    def create_saml_request(
        self,
        relay_state: str | None = None,
    ) -> Result[str, str]:
        """Create SAML authentication request.

        Args:
            relay_state: Optional relay state parameter

        Returns:
            Result containing SAML request URL or error
        """
        # This would use python3-saml or similar library
        # For now, return a placeholder
        return Err("SAML implementation requires python3-saml library")

    @beartype
    async def process_saml_response(
        self,
        saml_response: str,
        relay_state: str | None = None,
    ) -> Result[dict[str, Any], str]:
        """Process SAML response and extract attributes.

        Args:
            saml_response: Base64 encoded SAML response
            relay_state: Optional relay state for validation

        Returns:
            Result containing user attributes or error
        """
        # This would validate and parse SAML response
        # For now, return a placeholder
        return Err("SAML implementation requires python3-saml library")
