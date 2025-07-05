# Agent 09: SSO Integration Specialist

## YOUR MISSION

Implement enterprise-grade Single Sign-On (SSO) with multiple providers (Google, Azure AD, Okta, Auth0), including SAML and OIDC support.

## CRITICAL: NO SILENT FALLBACKS PRINCIPLE

### SSO Security Requirements (NON-NEGOTIABLE)

1. **EXPLICIT PROVIDER CONFIGURATION**:
   - NO default SSO provider if none configured
   - NO fallback authentication methods without explicit approval
   - NO assumed group mappings between providers
   - ALL provider configurations MUST be explicitly validated

2. **FAIL FAST ON AUTH FAILURES**:

   ```python
   # ❌ FORBIDDEN - Silent fallback to local auth
   async def authenticate_user(provider: str, token: str):
       try:
           return await sso_provider.validate(token)
       except:
           return await local_auth.authenticate()  # Silent fallback

   # ✅ REQUIRED - Explicit authentication validation
   async def authenticate_user(provider: str, token: str) -> Result[UserInfo, str]:
       if provider not in configured_providers:
           return Err(
               f"SSO provider '{provider}' is not configured. "
               f"Available providers: {list(configured_providers.keys())}. "
               f"Required action: Configure provider in Admin > SSO Settings."
           )
   ```

3. **PROVIDER CONFIGURATION VALIDATION**:

   ```python
   # ❌ FORBIDDEN - Assume provider settings
   client_secret = config.get("client_secret", "")  # Dangerous

   # ✅ REQUIRED - Explicit provider validation
   if "client_secret" not in config or not config["client_secret"]:
       return Err(
           "SSO Configuration error: client_secret is required. "
           "Required action: Add client_secret in Admin > SSO > Provider Config."
       )
   ```

4. **GROUP MAPPING FAILURES**: Never assign default groups when mapping fails

## MANDATORY PRE-WORK

1. Read ALL documents listed in AGENT_TEMPLATE.md FIRST
2. Specifically study:
   - OAuth2/OIDC specifications (30-second search if unfamiliar)
   - SAML basics (30-second search if unfamiliar)
   - Existing security setup in `src/pd_prime_demo/core/security.py`

## SPECIFIC TASKS

### 1. Create SSO Provider Base (`src/pd_prime_demo/core/auth/sso_base.py`)

```python
"""Base classes for SSO provider integration."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from beartype import beartype

from ...models.base import BaseModelConfig


class SSOUserInfo(BaseModelConfig):
    """Standardized user info from SSO providers."""

    # Required fields
    sub: str  # Subject/unique identifier from provider
    email: str
    email_verified: bool = False

    # Common fields
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    picture: Optional[str] = None

    # Provider specific
    provider: str
    provider_user_id: str

    # Additional claims
    groups: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)

    # Metadata
    last_login: datetime = Field(default_factory=datetime.now)
    raw_claims: Dict[str, Any] = Field(default_factory=dict)


class SSOProvider(ABC):
    """Base class for SSO providers."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: List[str],
    ) -> None:
        """Initialize SSO provider."""
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get provider name."""
        pass

    @abstractmethod
    async def get_authorization_url(
        self,
        state: str,
        nonce: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Get authorization URL for user redirect."""
        pass

    @abstractmethod
    async def exchange_code_for_token(
        self,
        code: str,
        state: str,
    ) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        pass

    @abstractmethod
    async def get_user_info(
        self,
        access_token: str,
    ) -> SSOUserInfo:
        """Get user information from provider."""
        pass

    @abstractmethod
    async def refresh_token(
        self,
        refresh_token: str,
    ) -> Dict[str, Any]:
        """Refresh access token."""
        pass

    @abstractmethod
    async def revoke_token(
        self,
        token: str,
        token_type: str = "access_token",
    ) -> bool:
        """Revoke a token."""
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
        scopes: Optional[List[str]] = None,
    ) -> None:
        """Initialize OIDC provider."""
        default_scopes = ["openid", "email", "profile"]
        super().__init__(
            client_id,
            client_secret,
            redirect_uri,
            scopes or default_scopes,
        )
        self.issuer = issuer
        self._discovery_document: Optional[Dict[str, Any]] = None

    async def discover(self) -> Dict[str, Any]:
        """Get OIDC discovery document."""
        if self._discovery_document:
            return self._discovery_document

        # Fetch discovery document
        discovery_url = f"{self.issuer}/.well-known/openid-configuration"
        # Implementation would use httpx or aiohttp

        return self._discovery_document

    @beartype
    async def validate_id_token(
        self,
        id_token: str,
        nonce: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate and decode ID token."""
        # Get JWKS
        discovery = await self.discover()
        jwks_uri = discovery["jwks_uri"]

        # Fetch JWKS and validate token
        # Implementation would use python-jose or PyJWT

        # Validate claims
        claims = {}  # Decoded claims

        # Standard validations
        if claims.get("iss") != self.issuer:
            raise ValueError("Invalid issuer")

        if self.client_id not in claims.get("aud", []):
            raise ValueError("Invalid audience")

        if nonce and claims.get("nonce") != nonce:
            raise ValueError("Invalid nonce")

        # Check expiration
        exp = claims.get("exp", 0)
        if datetime.fromtimestamp(exp) < datetime.now():
            raise ValueError("Token expired")

        return claims


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
        scopes: Optional[List[str]] = None,
    ) -> None:
        """Initialize SAML provider."""
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
        relay_state: Optional[str] = None,
    ) -> str:
        """Create SAML authentication request."""
        # Implementation would use python3-saml
        pass

    @beartype
    async def process_saml_response(
        self,
        saml_response: str,
        relay_state: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process SAML response and extract attributes."""
        # Implementation would validate and parse SAML response
        pass
```

### 2. Implement Google SSO (`src/pd_prime_demo/core/auth/providers/google.py`)

```python
"""Google Workspace SSO implementation."""

import httpx
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode

from beartype import beartype

from ..sso_base import OIDCProvider, SSOUserInfo


class GoogleSSOProvider(OIDCProvider):
    """Google Workspace SSO provider."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        hosted_domain: Optional[str] = None,
        scopes: Optional[List[str]] = None,
    ) -> None:
        """Initialize Google SSO provider."""
        super().__init__(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            issuer="https://accounts.google.com",
            scopes=scopes,
        )
        self.hosted_domain = hosted_domain  # For Google Workspace domains

    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "google"

    @beartype
    async def get_authorization_url(
        self,
        state: str,
        nonce: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Get Google authorization URL."""
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
        params.update(kwargs)

        discovery = await self.discover()
        auth_endpoint = discovery["authorization_endpoint"]

        return f"{auth_endpoint}?{urlencode(params)}"

    @beartype
    async def exchange_code_for_token(
        self,
        code: str,
        state: str,
    ) -> Dict[str, Any]:
        """Exchange authorization code for tokens."""
        discovery = await self.discover()
        token_endpoint = discovery["token_endpoint"]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_endpoint,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                }
            )
            response.raise_for_status()

        tokens = response.json()

        # Validate ID token if present
        if "id_token" in tokens:
            claims = await self.validate_id_token(tokens["id_token"])
            tokens["id_token_claims"] = claims

        return tokens

    @beartype
    async def get_user_info(
        self,
        access_token: str,
    ) -> SSOUserInfo:
        """Get user information from Google."""
        discovery = await self.discover()
        userinfo_endpoint = discovery["userinfo_endpoint"]

        async with httpx.AsyncClient() as client:
            response = await client.get(
                userinfo_endpoint,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()

        user_data = response.json()

        # Check domain restriction
        if self.hosted_domain:
            email_domain = user_data.get("email", "").split("@")[-1]
            if email_domain != self.hosted_domain:
                raise ValueError(f"User not from allowed domain: {self.hosted_domain}")

        # Get Google Workspace groups if available
        groups = []
        if "groups" in self.scopes:
            groups = await self._get_user_groups(access_token, user_data["sub"])

        return SSOUserInfo(
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

    @beartype
    async def refresh_token(
        self,
        refresh_token: str,
    ) -> Dict[str, Any]:
        """Refresh Google access token."""
        discovery = await self.discover()
        token_endpoint = discovery["token_endpoint"]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_endpoint,
                data={
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "refresh_token",
                }
            )
            response.raise_for_status()

        return response.json()

    @beartype
    async def revoke_token(
        self,
        token: str,
        token_type: str = "access_token",
    ) -> bool:
        """Revoke Google token."""
        revoke_url = "https://oauth2.googleapis.com/revoke"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                revoke_url,
                data={"token": token}
            )

        return response.status_code == 200

    async def _get_user_groups(
        self,
        access_token: str,
        user_id: str,
    ) -> List[str]:
        """Get user's Google Workspace groups."""
        # Requires Google Workspace Admin SDK access
        # Implementation depends on domain admin setup
        return []
```

### 3. Implement Azure AD SSO (`src/pd_prime_demo/core/auth/providers/azure.py`)

```python
"""Microsoft Azure AD SSO implementation."""

import httpx
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode

from beartype import beartype

from ..sso_base import OIDCProvider, SSOUserInfo


class AzureADSSOProvider(OIDCProvider):
    """Azure Active Directory SSO provider."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        tenant_id: str,
        scopes: Optional[List[str]] = None,
    ) -> None:
        """Initialize Azure AD SSO provider."""
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
        nonce: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Get Azure AD authorization URL."""
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

        if "domain_hint" in kwargs:
            params["domain_hint"] = kwargs["domain_hint"]

        params.update(kwargs)

        auth_endpoint = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize"

        return f"{auth_endpoint}?{urlencode(params)}"

    @beartype
    async def get_user_info(
        self,
        access_token: str,
    ) -> SSOUserInfo:
        """Get user information from Azure AD."""
        # Microsoft Graph API endpoint
        graph_url = "https://graph.microsoft.com/v1.0/me"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                graph_url,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            response.raise_for_status()

        user_data = response.json()

        # Get user groups if permission granted
        groups = []
        if "Group.Read.All" in self.scopes:
            groups = await self._get_user_groups(access_token)

        return SSOUserInfo(
            sub=user_data["id"],
            email=user_data.get("mail") or user_data.get("userPrincipalName", ""),
            email_verified=True,  # Azure AD emails are verified
            name=user_data.get("displayName"),
            given_name=user_data.get("givenName"),
            family_name=user_data.get("surname"),
            provider="azure",
            provider_user_id=user_data["id"],
            groups=groups,
            raw_claims=user_data,
        )

    async def _get_user_groups(
        self,
        access_token: str,
    ) -> List[str]:
        """Get user's Azure AD groups."""
        groups_url = "https://graph.microsoft.com/v1.0/me/memberOf"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                groups_url,
                headers={"Authorization": f"Bearer {access_token}"}
            )

            if response.status_code == 200:
                data = response.json()
                return [g["displayName"] for g in data.get("value", [])]

        return []
```

### 4. Create SSO Manager (`src/pd_prime_demo/core/auth/sso_manager.py`)

```python
"""SSO provider management and user provisioning."""

from typing import Dict, Any, Optional, List
from uuid import UUID

from beartype import beartype

from ...core.database import Database
from ...core.cache import Cache
from ...models.user import User, UserCreate
from ...services.result import Result, Ok, Err
from .sso_base import SSOProvider, SSOUserInfo
from .providers.google import GoogleSSOProvider
from .providers.azure import AzureADSSOProvider


class SSOManager:
    """Manage SSO providers and user provisioning."""

    def __init__(
        self,
        db: Database,
        cache: Cache,
    ) -> None:
        """Initialize SSO manager."""
        self._db = db
        self._cache = cache
        self._providers: Dict[str, SSOProvider] = {}
        self._provider_configs: Dict[str, Dict[str, Any]] = {}

    @beartype
    async def initialize(self) -> None:
        """Load SSO provider configurations."""
        # Load from database
        rows = await self._db.fetch(
            """
            SELECT provider_name, provider_type, client_id,
                   client_secret_encrypted, config
            FROM sso_providers
            WHERE enabled = true
            """
        )

        for row in rows:
            provider_name = row["provider_name"]
            provider_type = row["provider_type"]

            # Decrypt client secret
            client_secret = await self._decrypt_secret(
                row["client_secret_encrypted"]
            )

            config = row["config"] or {}

            # Create provider instance
            if provider_type == "google":
                provider = GoogleSSOProvider(
                    client_id=row["client_id"],
                    client_secret=client_secret,
                    redirect_uri=config.get("redirect_uri"),
                    hosted_domain=config.get("hosted_domain"),
                )
            elif provider_type == "azure":
                provider = AzureADSSOProvider(
                    client_id=row["client_id"],
                    client_secret=client_secret,
                    redirect_uri=config.get("redirect_uri"),
                    tenant_id=config["tenant_id"],
                )
            # Add other providers...

            self._providers[provider_name] = provider
            self._provider_configs[provider_name] = config

    @beartype
    def get_provider(self, provider_name: str) -> Optional[SSOProvider]:
        """Get SSO provider by name."""
        return self._providers.get(provider_name)

    @beartype
    async def create_or_update_user(
        self,
        sso_info: SSOUserInfo,
        provider_name: str,
    ) -> Result[User, str]:
        """Create or update user from SSO information."""
        try:
            # Check if user exists
            existing = await self._db.fetchrow(
                """
                SELECT u.* FROM users u
                JOIN user_sso_links l ON u.id = l.user_id
                WHERE l.provider = $1 AND l.provider_user_id = $2
                """,
                provider_name,
                sso_info.provider_user_id,
            )

            if existing:
                # Update user info
                user = await self._update_user_from_sso(
                    UUID(existing["id"]),
                    sso_info
                )
            else:
                # Check if email already exists
                email_user = await self._db.fetchrow(
                    "SELECT * FROM users WHERE email = $1",
                    sso_info.email
                )

                if email_user:
                    # Link existing user to SSO
                    user = await self._link_user_to_sso(
                        UUID(email_user["id"]),
                        provider_name,
                        sso_info
                    )
                else:
                    # Create new user
                    config = self._provider_configs.get(provider_name, {})
                    if not config.get("auto_create_users", True):
                        return Err("User provisioning not allowed for this provider")

                    user = await self._create_user_from_sso(
                        sso_info,
                        provider_name
                    )

            # Update groups/roles
            await self._sync_user_groups(user.id, sso_info.groups)

            return Ok(user)

        except Exception as e:
            return Err(f"Failed to create/update user: {str(e)}")

    @beartype
    async def _create_user_from_sso(
        self,
        sso_info: SSOUserInfo,
        provider_name: str,
    ) -> User:
        """Create new user from SSO information."""
        async with self._db.transaction():
            # Create user
            user_id = await self._db.fetchval(
                """
                INSERT INTO users (email, name, email_verified, active)
                VALUES ($1, $2, $3, true)
                RETURNING id
                """,
                sso_info.email,
                sso_info.name or sso_info.email.split("@")[0],
                sso_info.email_verified,
            )

            # Create SSO link
            await self._db.execute(
                """
                INSERT INTO user_sso_links
                (user_id, provider, provider_user_id, profile_data)
                VALUES ($1, $2, $3, $4)
                """,
                user_id,
                provider_name,
                sso_info.provider_user_id,
                sso_info.raw_claims,
            )

            # Get full user record
            row = await self._db.fetchrow(
                "SELECT * FROM users WHERE id = $1",
                user_id
            )

            return User(**row)

    # Additional helper methods...
```

## SEARCH TRIGGERS (30-second timeout)

If confidence < 95% on:

- OAuth2/OIDC flow → Search: "oauth2 authorization code flow"
- SAML implementation → Search: "python saml integration"
- JWT validation → Search: "python jwt token validation"

## DELIVERABLES

1. **SSO Base Classes**: Provider abstraction layer
2. **Provider Implementations**: Google, Azure, Okta, Auth0
3. **SSO Manager**: User provisioning and management
4. **Configuration UI**: Admin interface for SSO setup
5. **Integration Tests**: Full SSO flow tests

## SUCCESS CRITERIA

1. All providers working with test accounts
2. User auto-provisioning works correctly
3. Group/role synchronization functions
4. Token refresh handles gracefully
5. Security best practices followed

## PARALLEL COORDINATION

- Agent 01 creates SSO provider tables
- Agent 10 will add OAuth2 server
- Agent 11 adds MFA on top of SSO
- Agent 12 ensures SOC 2 compliance

Document all provider-specific quirks!

## ADDITIONAL REQUIREMENT: Admin SSO Configuration Interface

**IMPORTANT**: You must ALSO read `.sage/wave_contexts/wave_2/AGENT_DEPLOYMENT_SUMMARY.md` to understand the full system context.

### 4. Create Admin SSO Configuration Service (`src/pd_prime_demo/services/admin/sso_admin_service.py`)

You must also implement comprehensive admin SSO configuration management:

```python
"""Admin SSO configuration management service."""

from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from beartype import beartype

from ...core.cache import Cache
from ...core.database import Database
from ..result import Result, Ok, Err

class SSOAdminService:
    """Service for admin SSO configuration and management."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize SSO admin service."""
        self._db = db
        self._cache = cache
        self._config_cache_prefix = "sso_config:"

    @beartype
    async def create_sso_provider_config(
        self,
        admin_user_id: UUID,
        provider_name: str,
        provider_type: str,  # 'oidc', 'saml', 'oauth2'
        configuration: Dict[str, Any],
        is_enabled: bool = False,
    ) -> Result[UUID, str]:
        """Create new SSO provider configuration."""
        try:
            # Validate configuration based on provider type
            validation = await self._validate_provider_config(provider_type, configuration)
            if isinstance(validation, Err):
                return validation

            # Encrypt sensitive configuration data
            encrypted_config = await self._encrypt_sensitive_config(configuration)

            provider_id = uuid4()

            await self._db.execute(
                """
                INSERT INTO sso_provider_configs (
                    id, provider_name, provider_type, configuration,
                    is_enabled, created_by, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                provider_id, provider_name, provider_type, encrypted_config,
                is_enabled, admin_user_id, datetime.utcnow()
            )

            # Clear configuration cache
            await self._cache.delete_pattern(f"{self._config_cache_prefix}*")

            # Log configuration creation
            await self._log_sso_activity(
                admin_user_id, "create_provider", provider_id,
                {"provider_name": provider_name, "provider_type": provider_type}
            )

            return Ok(provider_id)

        except Exception as e:
            return Err(f"Provider configuration failed: {str(e)}")

    @beartype
    async def update_provider_config(
        self,
        provider_id: UUID,
        admin_user_id: UUID,
        updates: Dict[str, Any],
    ) -> Result[bool, str]:
        """Update SSO provider configuration."""
        try:
            # Get existing configuration
            existing = await self._db.fetchrow(
                "SELECT * FROM sso_provider_configs WHERE id = $1",
                provider_id
            )
            if not existing:
                return Err("Provider configuration not found")

            # Merge updates with existing config
            current_config = existing['configuration']
            updated_config = {**current_config, **updates.get('configuration', {})}

            # Validate updated configuration
            validation = await self._validate_provider_config(
                existing['provider_type'], updated_config
            )
            if isinstance(validation, Err):
                return validation

            # Encrypt updated configuration
            encrypted_config = await self._encrypt_sensitive_config(updated_config)

            # Update database
            await self._db.execute(
                """
                UPDATE sso_provider_configs
                SET configuration = $2, is_enabled = $3, updated_by = $4,
                    updated_at = $5
                WHERE id = $1
                """,
                provider_id, encrypted_config,
                updates.get('is_enabled', existing['is_enabled']),
                admin_user_id, datetime.utcnow()
            )

            # Clear cache
            await self._cache.delete_pattern(f"{self._config_cache_prefix}*")

            # Log update
            await self._log_sso_activity(
                admin_user_id, "update_provider", provider_id,
                {"updates": list(updates.keys())}
            )

            return Ok(True)

        except Exception as e:
            return Err(f"Update failed: {str(e)}")

    @beartype
    async def test_provider_connection(
        self,
        provider_id: UUID,
        admin_user_id: UUID,
    ) -> Result[Dict[str, Any], str]:
        """Test SSO provider connection and configuration."""
        try:
            # Get provider configuration
            provider = await self._db.fetchrow(
                "SELECT * FROM sso_provider_configs WHERE id = $1",
                provider_id
            )
            if not provider:
                return Err("Provider not found")

            # Decrypt configuration
            config = await self._decrypt_config(provider['configuration'])

            # Test connection based on provider type
            if provider['provider_type'] == 'oidc':
                test_result = await self._test_oidc_connection(config)
            elif provider['provider_type'] == 'saml':
                test_result = await self._test_saml_connection(config)
            else:
                return Err(f"Unsupported provider type: {provider['provider_type']}")

            # Log test attempt
            await self._log_sso_activity(
                admin_user_id, "test_connection", provider_id,
                {"success": test_result.get('success', False)}
            )

            return Ok(test_result)

        except Exception as e:
            return Err(f"Connection test failed: {str(e)}")

    @beartype
    async def get_user_provisioning_rules(
        self,
        provider_id: UUID,
    ) -> Result[List[Dict[str, Any]], str]:
        """Get user provisioning rules for a provider."""
        try:
            rules = await self._db.fetch(
                """
                SELECT
                    id, rule_name, conditions, actions,
                    is_enabled, created_at
                FROM user_provisioning_rules
                WHERE provider_id = $1
                ORDER BY created_at DESC
                """,
                provider_id
            )

            return Ok([dict(row) for row in rules])

        except Exception as e:
            return Err(f"Failed to get rules: {str(e)}")

    @beartype
    async def create_group_mapping(
        self,
        provider_id: UUID,
        admin_user_id: UUID,
        sso_group: str,
        internal_role: str,
        auto_assign: bool = True,
    ) -> Result[UUID, str]:
        """Create SSO group to internal role mapping."""
        try:
            mapping_id = uuid4()

            await self._db.execute(
                """
                INSERT INTO sso_group_mappings (
                    id, provider_id, sso_group_name, internal_role,
                    auto_assign, created_by, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                mapping_id, provider_id, sso_group, internal_role,
                auto_assign, admin_user_id, datetime.utcnow()
            )

            # Clear group mapping cache
            await self._cache.delete(f"sso_mappings:{provider_id}")

            return Ok(mapping_id)

        except Exception as e:
            return Err(f"Group mapping failed: {str(e)}")

    @beartype
    async def get_sso_analytics(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> Result[Dict[str, Any], str]:
        """Get SSO usage analytics for admin dashboards."""
        try:
            # Login statistics by provider
            login_stats = await self._db.fetch(
                """
                SELECT
                    usl.provider,
                    COUNT(*) as total_logins,
                    COUNT(DISTINCT usl.user_id) as unique_users,
                    COUNT(*) FILTER (WHERE al.status = 'success') as successful_logins,
                    COUNT(*) FILTER (WHERE al.status = 'failed') as failed_logins
                FROM user_sso_links usl
                LEFT JOIN auth_logs al ON al.user_id = usl.user_id
                WHERE al.created_at BETWEEN $1 AND $2
                    AND al.auth_method = 'sso'
                GROUP BY usl.provider
                ORDER BY total_logins DESC
                """,
                date_from, date_to
            )

            # User provisioning statistics
            provisioning_stats = await self._db.fetch(
                """
                SELECT
                    provider,
                    COUNT(*) as users_provisioned,
                    COUNT(*) FILTER (WHERE created_at BETWEEN $1 AND $2) as recent_provisions
                FROM user_sso_links
                GROUP BY provider
                """,
                date_from, date_to
            )

            # Group sync statistics
            sync_stats = await self._db.fetch(
                """
                SELECT
                    COUNT(*) as total_syncs,
                    COUNT(*) FILTER (WHERE status = 'success') as successful_syncs,
                    MAX(last_sync) as last_sync_time
                FROM sso_group_sync_logs
                WHERE last_sync BETWEEN $1 AND $2
                """,
                date_from, date_to
            )

            return Ok({
                "login_statistics": [dict(row) for row in login_stats],
                "provisioning_statistics": [dict(row) for row in provisioning_stats],
                "sync_statistics": dict(sync_stats[0]) if sync_stats else {},
                "period": {"from": date_from, "to": date_to}
            })

        except Exception as e:
            return Err(f"Analytics failed: {str(e)}")
```

### 5. Create Admin SSO Configuration API (`src/pd_prime_demo/api/v1/admin/sso_management.py`)

```python
"""Admin SSO configuration endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID

from beartype import beartype

from ....services.admin.sso_admin_service import SSOAdminService
from ...dependencies import get_sso_admin_service, get_current_admin_user
from ....models.admin import AdminUser

router = APIRouter()

@router.post("/providers")
@beartype
async def create_sso_provider(
    provider_request: SSOProviderCreateRequest,
    sso_service: SSOAdminService = Depends(get_sso_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Create new SSO provider configuration."""
    if "admin:write" not in admin_user.effective_permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await sso_service.create_sso_provider_config(
        admin_user.id,
        provider_request.provider_name,
        provider_request.provider_type,
        provider_request.configuration,
        provider_request.is_enabled
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)

    return {"provider_id": result.value}

@router.post("/providers/{provider_id}/test")
@beartype
async def test_sso_provider(
    provider_id: UUID,
    sso_service: SSOAdminService = Depends(get_sso_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Test SSO provider connection."""
    result = await sso_service.test_provider_connection(
        provider_id, admin_user.id
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)

    return result.value

@router.get("/analytics")
@beartype
async def get_sso_analytics(
    date_from: datetime,
    date_to: datetime,
    sso_service: SSOAdminService = Depends(get_sso_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Get SSO usage analytics."""
    result = await sso_service.get_sso_analytics(date_from, date_to)

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)

    return result.value
```

### 6. Add SSO Management Tables

Tell Agent 01 to also create:

```sql
-- SSO provider configurations
CREATE TABLE sso_provider_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_name VARCHAR(100) UNIQUE NOT NULL,
    provider_type VARCHAR(20) NOT NULL, -- 'oidc', 'saml', 'oauth2'
    configuration JSONB NOT NULL, -- Encrypted sensitive config
    is_enabled BOOLEAN DEFAULT false,
    created_by UUID REFERENCES admin_users(id),
    updated_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- SSO group to role mappings
CREATE TABLE sso_group_mappings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID REFERENCES sso_provider_configs(id),
    sso_group_name VARCHAR(200) NOT NULL,
    internal_role VARCHAR(50) NOT NULL,
    auto_assign BOOLEAN DEFAULT true,
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(provider_id, sso_group_name)
);

-- User provisioning rules
CREATE TABLE user_provisioning_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID REFERENCES sso_provider_configs(id),
    rule_name VARCHAR(100) NOT NULL,
    conditions JSONB NOT NULL, -- Conditions for rule execution
    actions JSONB NOT NULL, -- Actions to perform
    is_enabled BOOLEAN DEFAULT true,
    created_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- SSO group sync logs
CREATE TABLE sso_group_sync_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID REFERENCES sso_provider_configs(id),
    user_id UUID REFERENCES customers(id),
    sync_type VARCHAR(20) NOT NULL, -- 'full', 'incremental'
    groups_added TEXT[],
    groups_removed TEXT[],
    status VARCHAR(20) NOT NULL, -- 'success', 'failed', 'partial'
    error_message TEXT,
    last_sync TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

Make sure all SSO configuration operations include proper admin authentication and audit logging!
