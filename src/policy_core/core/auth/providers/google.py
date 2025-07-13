# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.
# SPDX-License-Identifier: AGPL-3.0-or-later OR Commercial
"""Google Workspace SSO implementation."""

from typing import Any
from urllib.parse import urlencode

import httpx
from beartype import beartype

from policy_core.core.result_types import Err, Ok, Result

from ..sso_base import OIDCProvider, SSOUserInfo


class GoogleSSOProvider(OIDCProvider):
    """Google Workspace SSO provider."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        hosted_domain: str | None = None,
        scopes: list[str] | None = None,
    ) -> None:
        """Initialize Google SSO provider.

        Args:
            client_id: Google OAuth2 client ID
            client_secret: Google OAuth2 client secret
            redirect_uri: Redirect URI registered with Google
            hosted_domain: Optional Google Workspace domain restriction
            scopes: OAuth scopes (defaults to standard Google scopes)
        """
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            issuer="https://accounts.google.com",
            scopes=scopes,
        )
        self.hosted_domain = hosted_domain  # For Google Workspace domains

    @property
    @beartype
    def provider_name(self) -> str:
        """Get provider name."""
        return "google"

    @beartype
    async def get_authorization_url(
        self,
        state: str,
        nonce: str | None = None,
        **kwargs: Any,
    ) -> Result[str, str]:
        """Get Google authorization URL.

        Args:
            state: State parameter for CSRF protection
            nonce: Nonce for OIDC
            **kwargs: Additional parameters like prompt, login_hint

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
                "access_type": "offline",  # Request refresh token
                "prompt": kwargs.get("prompt", "select_account"),
            }

            if nonce:
                params["nonce"] = nonce

            if self.hosted_domain:
                params["hd"] = self.hosted_domain

            # Add any additional parameters
            for key, value in kwargs.items():
                if key not in params and value is not None:
                    params[key] = value

            discovery_result = await self.discover()
            if isinstance(discovery_result, Err):
                return discovery_result

            discovery = discovery_result.value
            auth_endpoint = discovery.get("authorization_endpoint")
            if not auth_endpoint:
                return Err("Authorization endpoint not found in discovery document")

            return Ok(f"{auth_endpoint}?{urlencode(params)}")

        except Exception as e:
            return Err(f"Failed to generate authorization URL: {str(e)}")

    @beartype
    async def exchange_code_for_token(
        self,
        code: str,
        state: str,
    ) -> Result[
        dict[str, Any], str
    ]:  # SYSTEM_BOUNDARY - Google OAuth2 API token response
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from Google
            state: State parameter for validation

        Returns:
            Result containing tokens or error
        """
        try:
            discovery_result = await self.discover()
            if isinstance(discovery_result, Err):
                return discovery_result

            discovery = discovery_result.value
            token_endpoint = discovery.get("token_endpoint")
            if not token_endpoint:
                return Err("Token endpoint not found in discovery document")

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
                    error_data = response.json()
                    error_msg = error_data.get(
                        "error_description", error_data.get("error", "Unknown error")
                    )
                    return Err(f"Token exchange failed: {error_msg}")

            tokens = (
                response.json()
            )  # SYSTEM_BOUNDARY - Google OAuth2 API response parsing

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
        """Get user information from Google.

        Args:
            access_token: Google access token

        Returns:
            Result containing user info or error
        """
        try:
            discovery_result = await self.discover()
            if isinstance(discovery_result, Err):
                return discovery_result

            discovery = discovery_result.value
            userinfo_endpoint = discovery.get("userinfo_endpoint")
            if not userinfo_endpoint:
                return Err("UserInfo endpoint not found in discovery document")

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

            user_data = (
                response.json()
            )  # SYSTEM_BOUNDARY - Google OAuth2 API response parsing

            # Check domain restriction
            if self.hosted_domain:
                email = user_data.get("email", "")
                email_domain = email.split("@")[-1] if "@" in email else ""
                if email_domain != self.hosted_domain:
                    return Err(
                        f"User not from allowed domain '{self.hosted_domain}'. "
                        f"User domain: '{email_domain}'. "
                        f"Required action: Use an email from {self.hosted_domain} domain."
                    )

            # Get Google Workspace groups if available
            groups: list[str] = []
            if (
                "https://www.googleapis.com/auth/admin.directory.group.readonly"
                in self.scopes
            ):
                groups_result = await self._get_user_groups(
                    access_token, user_data["sub"]
                )
                if isinstance(groups_result, Ok):
                    groups = groups_result.value

            return Ok(
                SSOUserInfo(
                    sub=user_data["sub"],
                    email=user_data["email"],
                    email_verified=user_data.get("email_verified", False),
                    name=user_data.get("name"),
                    given_name=user_data.get("given_name"),
                    family_name=user_data.get("family_name"),
                    picture=user_data.get("picture"),
                    provider="google",
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
    ) -> Result[
        dict[str, Any], str
    ]:  # SYSTEM_BOUNDARY - Google OAuth2 API token response
        """Refresh Google access token.

        Args:
            refresh_token: Google refresh token

        Returns:
            Result containing new tokens or error
        """
        try:
            discovery_result = await self.discover()
            if isinstance(discovery_result, Err):
                return discovery_result

            discovery = discovery_result.value
            token_endpoint = discovery.get("token_endpoint")
            if not token_endpoint:
                return Err("Token endpoint not found in discovery document")

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
                    error_data = response.json()
                    error_msg = error_data.get(
                        "error_description", error_data.get("error", "Unknown error")
                    )
                    return Err(f"Token refresh failed: {error_msg}")

            return Ok(
                response.json()
            )  # SYSTEM_BOUNDARY - Google OAuth2 API response parsing

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
        """Revoke Google token.

        Args:
            token: Token to revoke
            token_type: Type of token (ignored, Google revokes all tokens)

        Returns:
            Result indicating success or error
        """
        try:
            revoke_url = "https://oauth2.googleapis.com/revoke"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    revoke_url,
                    data={"token": token},
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
    async def _get_user_groups(
        self,
        access_token: str,
        user_id: str,
    ) -> Result[list[str], str]:
        """Get user's Google Workspace groups.

        Args:
            access_token: Google access token with admin directory scope
            user_id: Google user ID

        Returns:
            Result containing list of group names or error
        """
        # This requires Google Workspace Admin SDK access
        # and the domain admin must grant directory access
        try:
            groups_url = "https://admin.googleapis.com/admin/directory/v1/groups"
            params = {"userKey": user_id}

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    groups_url,
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )

                if response.status_code == 403:
                    # Common case - no admin access
                    return Ok([])

                if response.status_code != 200:
                    return Err(f"Failed to fetch groups: HTTP {response.status_code}")

            data = (
                response.json()
            )  # SYSTEM_BOUNDARY - Google Admin API response parsing
            groups = [group["name"] for group in data.get("groups", [])]
            return Ok(groups)

        except Exception:
            # Groups are optional, don't fail the entire auth
            return Ok([])
