"""Microsoft Azure AD SSO implementation."""

from typing import Any
from urllib.parse import urlencode

import httpx
from beartype import beartype

from pd_prime_demo.core.result_types import Err, Ok, Result

from ..sso_base import OIDCProvider, SSOUserInfo


class AzureADSSOProvider(OIDCProvider):
    """Azure Active Directory SSO provider."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        tenant_id: str,
        scopes: list[str] | None = None,
    ) -> None:
        """Initialize Azure AD SSO provider.

        Args:
            client_id: Azure AD application (client) ID
            client_secret: Azure AD client secret
            redirect_uri: Redirect URI registered with Azure AD
            tenant_id: Azure AD tenant ID (or 'common' for multi-tenant)
            scopes: OAuth scopes (defaults to standard Azure AD scopes)
        """
        issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            issuer=issuer,
            scopes=scopes or ["openid", "email", "profile", "User.Read"],
        )
        self.tenant_id = tenant_id

    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "azure"

    @beartype
    async def get_authorization_url(
        self,
        state: str,
        nonce: str | None = None,
        **kwargs: Any,
    ) -> Result[str, str]:
        """Get Azure AD authorization URL.

        Args:
            state: State parameter for CSRF protection
            nonce: Nonce for OIDC
            **kwargs: Additional parameters like prompt, domain_hint

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
                "response_mode": "query",
            }

            if nonce:
                params["nonce"] = nonce

            # Azure-specific parameters
            if "prompt" in kwargs:
                params["prompt"] = kwargs["prompt"]
            else:
                params["prompt"] = "select_account"

            if "domain_hint" in kwargs:
                params["domain_hint"] = kwargs["domain_hint"]

            if "login_hint" in kwargs:
                params["login_hint"] = kwargs["login_hint"]

            # Add any additional parameters
            for key, value in kwargs.items():
                if key not in params and value is not None:
                    params[key] = value

            auth_endpoint = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize"

            return Ok(f"{auth_endpoint}?{urlencode(params)}")

        except Exception as e:
            return Err(f"Failed to generate authorization URL: {str(e)}")

    @beartype
    async def exchange_code_for_token(
        self,
        code: str,
        state: str,
    ) -> Result[dict[str, Any], str]:
        """Exchange authorization code for tokens.

        Args:
            code: Authorization code from Azure AD
            state: State parameter for validation

        Returns:
            Result containing tokens or error
        """
        try:
            token_endpoint = (
                f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
            )

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_endpoint,
                    data={
                        "code": code,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uri": self.redirect_uri,
                        "grant_type": "authorization_code",
                        "scope": " ".join(self.scopes),
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_data = response.json()
                    error_msg = error_data.get(
                        "error_description", error_data.get("error", "Unknown error")
                    )
                    return Err(f"Token exchange failed: {error_msg}")

            tokens = response.json()

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
        """Get user information from Azure AD.

        Args:
            access_token: Azure AD access token

        Returns:
            Result containing user info or error
        """
        try:
            # Microsoft Graph API endpoint
            graph_url = "https://graph.microsoft.com/v1.0/me"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    graph_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )

                if response.status_code != 200:
                    return Err(
                        f"Failed to fetch user info: HTTP {response.status_code}"
                    )

            user_data = response.json()

            # Get user groups if permission granted
            groups = []
            if "Group.Read.All" in self.scopes or "Directory.Read.All" in self.scopes:
                groups_result = await self._get_user_groups(access_token)
                if isinstance(groups_result, Ok):
                    groups = groups_result.value

            # Azure AD may return mail or userPrincipalName
            email = user_data.get("mail") or user_data.get("userPrincipalName", "")

            return Ok(
                SSOUserInfo(
                    sub=user_data["id"],
                    email=email,
                    email_verified=True,  # Azure AD emails are verified
                    name=user_data.get("displayName"),
                    given_name=user_data.get("givenName"),
                    family_name=user_data.get("surname"),
                    provider="azure",
                    provider_user_id=user_data["id"],
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
    ) -> Result[dict[str, Any], str]:
        """Refresh Azure AD access token.

        Args:
            refresh_token: Azure AD refresh token

        Returns:
            Result containing new tokens or error
        """
        try:
            token_endpoint = (
                f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
            )

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    token_endpoint,
                    data={
                        "refresh_token": refresh_token,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "refresh_token",
                        "scope": " ".join(self.scopes),
                    },
                    timeout=30.0,
                )

                if response.status_code != 200:
                    error_data = response.json()
                    error_msg = error_data.get(
                        "error_description", error_data.get("error", "Unknown error")
                    )
                    return Err(f"Token refresh failed: {error_msg}")

            return Ok(response.json())

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
        """Revoke Azure AD token.

        Note: Azure AD doesn't support token revocation via API.
        Tokens expire naturally based on their lifetime.

        Args:
            token: Token to revoke (ignored)
            token_type: Type of token (ignored)

        Returns:
            Result indicating success (always returns True for Azure AD)
        """
        # Azure AD doesn't support token revocation
        # Tokens expire based on their configured lifetime
        # Return success to maintain interface compatibility
        return Ok(True)

    @beartype
    async def _get_user_groups(
        self,
        access_token: str,
    ) -> Result[dict[str, Any], str]:
        """Get user's Azure AD groups.

        Args:
            access_token: Azure AD access token with group read permissions

        Returns:
            Result containing list of group names or error
        """
        try:
            groups_url = "https://graph.microsoft.com/v1.0/me/memberOf"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    groups_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )

                if response.status_code == 403:
                    # No permission to read groups
                    return Ok([])

                if response.status_code != 200:
                    return Err(f"Failed to fetch groups: HTTP {response.status_code}")

            data = response.json()
            groups = []

            for group in data.get("value", []):
                # Only include security groups and Microsoft 365 groups
                if group.get("@odata.type") in [
                    "#microsoft.graph.group",
                    "#microsoft.graph.directoryRole",
                ]:
                    group_name = group.get("displayName", "")
                    if group_name:
                        groups.append(group_name)

            return Ok(groups)

        except Exception:
            # Groups are optional, don't fail the entire auth
            return Ok([])

    @beartype
    async def get_tenant_info(
        self,
        access_token: str,
    ) -> Result[dict[str, Any], str]:
        """Get Azure AD tenant information.

        Args:
            access_token: Azure AD access token

        Returns:
            Result containing tenant info or error
        """
        try:
            org_url = "https://graph.microsoft.com/v1.0/organization"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    org_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )

                if response.status_code != 200:
                    return Err(
                        f"Failed to fetch tenant info: HTTP {response.status_code}"
                    )

            data = response.json()
            if data.get("value"):
                return Ok(data["value"][0])
            else:
                return Err("No tenant information found")

        except Exception as e:
            return Err(f"Failed to get tenant info: {str(e)}")
