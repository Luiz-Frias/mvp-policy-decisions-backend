"""Auth0 SSO implementation."""

from typing import Any
from urllib.parse import urlencode

import httpx
from beartype import beartype

from pd_prime_demo.core.result_types import Err, Ok, Result

from ..sso_base import OIDCProvider, SSOUserInfo


class Auth0SSOProvider(OIDCProvider):
    """Auth0 SSO provider with universal login support."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        auth0_domain: str,
        scopes: list[str] | None = None,
        audience: str | None = None,
    ) -> None:
        """Initialize Auth0 SSO provider.

        Args:
            client_id: Auth0 application client ID
            client_secret: Auth0 application client secret
            redirect_uri: Redirect URI registered with Auth0
            auth0_domain: Your Auth0 domain (e.g., 'dev-12345.auth0.com')
            scopes: OAuth scopes (defaults to standard Auth0 scopes)
            audience: Optional API audience for access token
        """
        # Ensure domain doesn't include protocol
        auth0_domain = auth0_domain.replace("https://", "").replace("http://", "")

        issuer = f"https://{auth0_domain}/"
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            issuer=issuer,
            scopes=scopes or ["openid", "email", "profile"],
        )
        self.auth0_domain = auth0_domain
        self.audience = audience

    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "auth0"

    @beartype
    async def get_authorization_url(
        self,
        state: str,
        nonce: str | None = None,
        **kwargs: Any,
    ) -> Result[str, str]:
        """Get Auth0 authorization URL.

        Args:
            state: State parameter for CSRF protection
            nonce: Nonce for OIDC
            **kwargs: Additional parameters like prompt, connection, organization

        Returns:
            Result containing authorization URL or error
        """
        try:
            params = {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": " ".join(self.scopes),
                "state": state,
            }

            if nonce:
                params["nonce"] = nonce

            if self.audience:
                params["audience"] = self.audience

            # Auth0-specific parameters

            # Prompt parameter
            if "prompt" in kwargs:
                params["prompt"] = kwargs["prompt"]

            # Connection parameter (for specific identity provider)
            if "connection" in kwargs:
                params["connection"] = kwargs["connection"]

            # Organization parameter (for B2B scenarios)
            if "organization" in kwargs:
                params["organization"] = kwargs["organization"]

            # Invitation parameter (for user invitations)
            if "invitation" in kwargs:
                params["invitation"] = kwargs["invitation"]

            # Screen hint (for specific screens in universal login)
            if "screen_hint" in kwargs:
                params["screen_hint"] = kwargs["screen_hint"]

            # Add any additional parameters
            for key, value in kwargs.items():
                if key not in params and value is not None:
                    params[key] = value

            auth_endpoint = f"https://{self.auth0_domain}/authorize"

            return Ok(f"{auth_endpoint}?{urlencode(params)}")

        except Exception as e:
            return Err(f"Failed to generate authorization URL: {str(e)}")

    @beartype
    async def exchange_code_for_token(
        self,
        code: str,
        state: str,
    ) -> Result[dict[str, Any], str]:  # SYSTEM_BOUNDARY - Auth0 API token response
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from Auth0
            state: State parameter for validation

        Returns:
            Result containing tokens or error
        """
        try:
            token_endpoint = f"https://{self.auth0_domain}/oauth/token"

            data = {
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "grant_type": "authorization_code",
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_endpoint,
                    json=data,  # Auth0 prefers JSON
                    headers={"Content-Type": "application/json"},
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_data = response.json()
                    error_msg = error_data.get(
                        "error_description", error_data.get("error", "Unknown error")
                    )
                    return Err(f"Token exchange failed: {error_msg}")

            tokens = response.json()  # SYSTEM_BOUNDARY - Auth0 API response parsing

            # Validate ID token if present
            if "id_token" in tokens:
                validation_result = await self.validate_id_token(tokens["id_token"])
                if isinstance(validation_result, Err):
                    return validation_result
                tokens["id_token_claims"] = validation_result.value

            return Ok(tokens)

        except httpx.TimeoutException:
            return Err("Token exchange request timed out")
        except httpx.RequestError as e:
            return Err(f"Network error during token exchange: {str(e)}")
        except Exception as e:
            return Err(f"Failed to exchange code for token: {str(e)}")

    @beartype
    async def get_user_info(
        self,
        access_token: str,
    ) -> Result[SSOUserInfo, str]:
        """Get user information from Auth0.

        Args:
            access_token: Auth0 access token

        Returns:
            Result containing user info or error
        """
        try:
            userinfo_endpoint = f"https://{self.auth0_domain}/userinfo"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    userinfo_endpoint,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )

                if response.status_code != 200:
                    return Err(
                        f"Failed to fetch user info: HTTP {response.status_code}"
                    )

            user_data = response.json()  # SYSTEM_BOUNDARY - Auth0 API response parsing

            # Extract custom claims and roles
            groups = []
            roles = []

            # Auth0 custom namespace for roles/groups
            for key, value in user_data.items():
                if key.endswith("/roles") and isinstance(value, list):
                    roles = value
                elif key.endswith("/groups") and isinstance(value, list):
                    groups = value

            # Auth0 may use different fields for email verification
            email_verified = user_data.get("email_verified", False)
            if (
                "email_verified" not in user_data
                and user_data.get("verified_email") is not None
            ):
                email_verified = user_data["verified_email"]

            return Ok(
                SSOUserInfo(
                    sub=user_data["sub"],
                    email=user_data.get("email", ""),
                    email_verified=email_verified,
                    name=user_data.get("name"),
                    given_name=user_data.get("given_name"),
                    family_name=user_data.get("family_name"),
                    picture=user_data.get("picture"),
                    provider="auth0",
                    provider_user_id=user_data["sub"],
                    groups=groups,
                    roles=roles,
                    raw_claims=user_data,
                )
            )

        except httpx.TimeoutException:
            return Err("User info request timed out")
        except httpx.RequestError as e:
            return Err(f"Network error fetching user info: {str(e)}")
        except Exception as e:
            return Err(f"Failed to get user info: {str(e)}")

    @beartype
    async def refresh_token(
        self,
        refresh_token: str,
    ) -> Result[dict[str, Any], str]:  # SYSTEM_BOUNDARY - Auth0 API token response
        """Refresh Auth0 access token.

        Args:
            refresh_token: Auth0 refresh token

        Returns:
            Result containing new tokens or error
        """
        try:
            token_endpoint = f"https://{self.auth0_domain}/oauth/token"

            data = {
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
            }

            if self.audience:
                data["audience"] = self.audience

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_endpoint,
                    json=data,
                    headers={"Content-Type": "application/json"},
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_data = response.json()
                    error_msg = error_data.get(
                        "error_description", error_data.get("error", "Unknown error")
                    )
                    return Err(f"Token refresh failed: {error_msg}")

            return Ok(response.json())  # SYSTEM_BOUNDARY - Auth0 API response parsing

        except httpx.TimeoutException:
            return Err("Token refresh request timed out")
        except httpx.RequestError as e:
            return Err(f"Network error during token refresh: {str(e)}")
        except Exception as e:
            return Err(f"Failed to refresh token: {str(e)}")

    @beartype
    async def revoke_token(
        self,
        token: str,
        token_type: str = "refresh_token",
    ) -> Result[bool, str]:
        """Revoke Auth0 token.

        Note: Auth0 only supports revoking refresh tokens.

        Args:
            token: Refresh token to revoke
            token_type: Must be 'refresh_token' for Auth0

        Returns:
            Result indicating success or error
        """
        try:
            if token_type != "refresh_token":
                return Err("Auth0 only supports revoking refresh tokens")

            revoke_endpoint = f"https://{self.auth0_domain}/oauth/revoke"

            data = {
                "token": token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    revoke_endpoint,
                    json=data,
                    headers={"Content-Type": "application/json"},
                    timeout=30.0,
                )

            return Ok(response.status_code == 200)

        except httpx.TimeoutException:
            return Err("Token revocation request timed out")
        except httpx.RequestError as e:
            return Err(f"Network error during token revocation: {str(e)}")
        except Exception as e:
            return Err(f"Failed to revoke token: {str(e)}")

    @beartype
    async def get_user_by_id(
        self,
        user_id: str,
        management_token: str,
    ) -> Result[dict[str, Any], str]:  # SYSTEM_BOUNDARY - Auth0 Management API response
        """Get user details from Auth0 Management API.

        Args:
            user_id: Auth0 user ID
            management_token: Management API access token

        Returns:
            Result containing user details or error
        """
        try:
            user_endpoint = f"https://{self.auth0_domain}/api/v2/users/{user_id}"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    user_endpoint,
                    headers={"Authorization": f"Bearer {management_token}"},
                    timeout=30.0,
                )

                if response.status_code != 200:
                    return Err(
                        f"Failed to fetch user details: HTTP {response.status_code}"
                    )

            return Ok(response.json())  # SYSTEM_BOUNDARY - Auth0 API response parsing

        except Exception as e:
            return Err(f"Failed to get user details: {str(e)}")

    @beartype
    async def link_user_accounts(
        self,
        primary_user_id: str,
        secondary_user_id: str,
        secondary_provider: str,
        management_token: str,
    ) -> Result[dict[str, Any], str]:  # SYSTEM_BOUNDARY - Auth0 Management API response
        """Link two user accounts in Auth0.

        Args:
            primary_user_id: Primary user ID to link to
            secondary_user_id: Secondary user ID to link
            secondary_provider: Provider of secondary account
            management_token: Management API access token

        Returns:
            Result indicating success or error
        """
        try:
            link_endpoint = (
                f"https://{self.auth0_domain}/api/v2/users/{primary_user_id}/identities"
            )

            data = {
                "provider": secondary_provider,
                "user_id": secondary_user_id,
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    link_endpoint,
                    json=data,
                    headers={
                        "Authorization": f"Bearer {management_token}",
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )

            return Ok(
                {
                    "success": response.status_code == 201,
                    "status_code": response.status_code,
                }
            )

        except Exception as e:
            return Err(f"Failed to link accounts: {str(e)}")
