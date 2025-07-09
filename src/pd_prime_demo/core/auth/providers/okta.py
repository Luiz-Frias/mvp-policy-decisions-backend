"""Okta SSO implementation supporting both OIDC and SAML."""

from typing import Any
from urllib.parse import urlencode

import httpx
from beartype import beartype

from pd_prime_demo.core.result_types import Err, Ok, Result

from ..sso_base import OIDCProvider, SSOUserInfo


class OktaSSOProvider(OIDCProvider):
    """Okta SSO provider with OIDC support."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        okta_domain: str,
        authorization_server_id: str = "default",
        scopes: list[str] | None = None,
    ) -> None:
        """Initialize Okta SSO provider.

        Args:
            client_id: Okta application client ID
            client_secret: Okta application client secret
            redirect_uri: Redirect URI registered with Okta
            okta_domain: Your Okta domain (e.g., 'dev-12345.okta.com')
            authorization_server_id: Okta authorization server ID (default: 'default')
            scopes: OAuth scopes (defaults to standard Okta scopes)
        """
        # Ensure domain doesn't include protocol
        okta_domain = okta_domain.replace("https://", "").replace("http://", "")

        issuer = f"https://{okta_domain}/oauth2/{authorization_server_id}"
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            issuer=issuer,
            scopes=scopes or ["openid", "email", "profile", "groups"],
        )
        self.okta_domain = okta_domain
        self.authorization_server_id = authorization_server_id

    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "okta"

    @beartype
    async def get_authorization_url(
        self,
        state: str,
        nonce: str | None = None,
        **kwargs: Any,
    ) -> Result[str, str]:
        """Get Okta authorization URL.

        Args:
            state: State parameter for CSRF protection
            nonce: Nonce for OIDC
            **kwargs: Additional parameters like prompt, idp

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

            # Okta-specific parameters
            if "prompt" in kwargs:
                params["prompt"] = kwargs["prompt"]

            # Identity provider hint (for social login)
            if "idp" in kwargs:
                params["idp"] = kwargs["idp"]

            # Session token for seamless SSO
            if "sessionToken" in kwargs:
                params["sessionToken"] = kwargs["sessionToken"]

            # Add any additional parameters
            for key, value in kwargs.items():
                if key not in params and value is not None:
                    params[key] = value

            auth_endpoint = f"https://{self.okta_domain}/oauth2/{self.authorization_server_id}/v1/authorize"

            return Ok(f"{auth_endpoint}?{urlencode(params)}")

        except Exception as e:
            return Err(f"Failed to generate authorization URL: {str(e)}")

    @beartype
    async def exchange_code_for_token(
        self,
        code: str,
        state: str,
    ) -> Result[dict[str, Any], str]:  # SYSTEM_BOUNDARY - Okta API token response
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from Okta
            state: State parameter for validation

        Returns:
            Result containing tokens or error
        """
        try:
            token_endpoint = f"https://{self.okta_domain}/oauth2/{self.authorization_server_id}/v1/token"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_endpoint,
                    data={
                        "code": code,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uri": self.redirect_uri,
                        "grant_type": "authorization_code",
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_data = (
                        response.json()
                    )  # SYSTEM_BOUNDARY - Okta API error response parsing
                    error_msg = error_data.get(
                        "error_description", error_data.get("error", "Unknown error")
                    )
                    return Err(f"Token exchange failed: {error_msg}")

            tokens = response.json()  # SYSTEM_BOUNDARY - Okta API response parsing

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
        """Get user information from Okta.

        Args:
            access_token: Okta access token

        Returns:
            Result containing user info or error
        """
        try:
            userinfo_endpoint = f"https://{self.okta_domain}/oauth2/{self.authorization_server_id}/v1/userinfo"

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

            user_data = response.json()  # SYSTEM_BOUNDARY - Okta API response parsing

            # Extract groups from Okta claims
            groups = []
            if "groups" in user_data:
                groups = (
                    user_data["groups"] if isinstance(user_data["groups"], list) else []
                )

            # Okta may use 'preferred_username' instead of 'email'
            email = user_data.get("email") or user_data.get("preferred_username", "")

            return Ok(
                SSOUserInfo(
                    sub=user_data["sub"],
                    email=email,
                    email_verified=user_data.get("email_verified", True),
                    name=user_data.get("name"),
                    given_name=user_data.get("given_name"),
                    family_name=user_data.get("family_name"),
                    picture=user_data.get("picture"),
                    provider="okta",
                    provider_user_id=user_data["sub"],
                    groups=groups,
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
    ) -> Result[dict[str, Any], str]:  # SYSTEM_BOUNDARY - Okta API token response
        """Refresh Okta access token.

        Args:
            refresh_token: Okta refresh token

        Returns:
            Result containing new tokens or error
        """
        try:
            token_endpoint = f"https://{self.okta_domain}/oauth2/{self.authorization_server_id}/v1/token"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_endpoint,
                    data={
                        "refresh_token": refresh_token,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "refresh_token",
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_data = (
                        response.json()
                    )  # SYSTEM_BOUNDARY - Okta API error response parsing
                    error_msg = error_data.get(
                        "error_description", error_data.get("error", "Unknown error")
                    )
                    return Err(f"Token refresh failed: {error_msg}")

            return Ok(response.json())  # SYSTEM_BOUNDARY - Okta API response parsing

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
        token_type: str = "access_token",
    ) -> Result[bool, str]:
        """Revoke Okta token.

        Args:
            token: Token to revoke
            token_type: Type of token (access_token or refresh_token)

        Returns:
            Result indicating success or error
        """
        try:
            revoke_endpoint = f"https://{self.okta_domain}/oauth2/{self.authorization_server_id}/v1/revoke"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    revoke_endpoint,
                    data={
                        "token": token,
                        "token_type_hint": token_type,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    timeout=30.0,
                )

            # Okta returns 200 even if token was already revoked
            return Ok(response.status_code == 200)

        except httpx.TimeoutException:
            return Err("Token revocation request timed out")
        except httpx.RequestError as e:
            return Err(f"Network error during token revocation: {str(e)}")
        except Exception as e:
            return Err(f"Failed to revoke token: {str(e)}")

    @beartype
    async def introspect_token(
        self,
        token: str,
        token_type: str = "access_token",
    ) -> Result[
        dict[str, Any], str
    ]:  # SYSTEM_BOUNDARY - Okta API introspection response
        """Introspect Okta token to check its validity and metadata.

        Args:
            token: Token to introspect
            token_type: Type of token (access_token or refresh_token)

        Returns:
            Result containing token metadata or error
        """
        try:
            introspect_endpoint = f"https://{self.okta_domain}/oauth2/{self.authorization_server_id}/v1/introspect"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    introspect_endpoint,
                    data={
                        "token": token,
                        "token_type_hint": token_type,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    return Err(
                        f"Token introspection failed: HTTP {response.status_code}"
                    )

            introspection_data = (
                response.json()
            )  # SYSTEM_BOUNDARY - Okta API response parsing

            if not introspection_data.get("active", False):
                return Err("Token is not active")

            return Ok(introspection_data)

        except httpx.TimeoutException:
            return Err("Token introspection request timed out")
        except httpx.RequestError as e:
            return Err(f"Network error during token introspection: {str(e)}")
        except Exception as e:
            return Err(f"Failed to introspect token: {str(e)}")

    @beartype
    async def get_user_groups_detailed(
        self,
        access_token: str,
        user_id: str,
    ) -> Result[list[dict[str, Any]], str]:
        """Get detailed group information for a user from Okta.

        Args:
            access_token: Okta access token with appropriate permissions
            user_id: Okta user ID

        Returns:
            Result containing list of group objects or error
        """
        try:
            # This requires Okta API access token, not just OAuth token
            groups_endpoint = (
                f"https://{self.okta_domain}/api/v1/users/{user_id}/groups"
            )

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    groups_endpoint,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )

                if response.status_code == 403:
                    # No permission to read groups via API
                    return Ok([])

                if response.status_code != 200:
                    return Err(
                        f"Failed to fetch user groups: HTTP {response.status_code}"
                    )

            groups = response.json()  # SYSTEM_BOUNDARY - Okta API response parsing
            return Ok(groups)

        except Exception:
            # Groups are optional, don't fail the entire auth
            return Ok([])
