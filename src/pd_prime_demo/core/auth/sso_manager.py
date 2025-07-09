"""SSO provider management and user provisioning."""

from typing import Any
from uuid import UUID, uuid4

from beartype import beartype
from pydantic import ConfigDict

from pd_prime_demo.core.result_types import Err, Ok, Result

from ...core.cache import Cache
from ...core.database import Database
from ...models.base import BaseModelConfig
from .providers.auth0 import Auth0SSOProvider
from .providers.azure import AzureADSSOProvider
from .providers.google import GoogleSSOProvider
from .providers.okta import OktaSSOProvider
from .sso_base import SSOProvider, SSOUserInfo


class User(BaseModelConfig):
    """User model for SSO integration."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    id: UUID
    email: str
    first_name: str
    last_name: str
    role: str
    is_active: bool = True


class SSOManager:
    """Manage SSO providers and user provisioning."""

    def __init__(
        self,
        db: Database,
        cache: Cache,
    ) -> None:
        """Initialize SSO manager.

        Args:
            db: Database instance
            cache: Cache instance
        """
        self._db = db
        self._cache = cache
        self._providers: dict[str, SSOProvider] = {}
        self._provider_configs: dict[str, dict[str, Any]] = {}

    @beartype
    async def initialize(self) -> Result[None, str]:
        """Load SSO provider configurations from database.

        Returns:
            Result indicating success or error
        """
        try:
            # Check cache first
            cached_configs = await self._cache.get("sso:provider_configs")
            if cached_configs:
                await self._load_providers_from_configs(cached_configs)
                return Ok(None)

            # Load from database - use correct table name
            rows = await self._db.fetch(
                """
                SELECT id, provider_name, provider_type, configuration, is_enabled
                FROM sso_provider_configs
                WHERE is_enabled = true
                """
            )

            configs = {}
            for row in rows:
                provider_name = row["provider_name"]
                provider_type = row["provider_type"]

                # Get configuration data (already contains client_id and client_secret)
                config = row["configuration"] or {}
                config["provider_type"] = provider_type
                config["provider_id"] = str(row["id"])

                # Create provider instance based on type
                provider_result = await self._create_provider(
                    provider_name, provider_type, config
                )

                if isinstance(provider_result, Err):
                    # Log error but continue loading other providers
                    continue

                self._providers[provider_name] = provider_result.value
                self._provider_configs[provider_name] = config
                configs[provider_name] = config

            # Cache configurations
            await self._cache.set("sso:provider_configs", configs, ttl=3600)

            return Ok(None)

        except Exception as e:
            return Err(f"Failed to initialize SSO providers: {str(e)}")

    @beartype
    async def _create_provider(
        self,
        provider_name: str,
        provider_type: str,
        config: dict[str, Any],
    ) -> Result[SSOProvider, str]:
        """Create SSO provider instance.

        Args:
            provider_name: Name of the provider
            provider_type: Type of provider (google, azure, okta, auth0)
            config: Provider configuration

        Returns:
            Result containing provider instance or error
        """
        try:
            redirect_uri = config.get("redirect_uri", "")
            if not redirect_uri:
                return Err(f"Missing redirect_uri for provider {provider_name}")

            if provider_type == "google":
                if not all(k in config for k in ["client_id", "client_secret"]):
                    return Err(f"Missing required Google config for {provider_name}")

                return Ok(
                    GoogleSSOProvider(
                        client_id=config["client_id"],
                        client_secret=config["client_secret"],
                        redirect_uri=redirect_uri,
                        hosted_domain=config.get("hosted_domain"),
                    )
                )

            elif provider_type == "azure":
                if not all(
                    k in config for k in ["client_id", "client_secret", "tenant_id"]
                ):
                    return Err(f"Missing required Azure AD config for {provider_name}")

                return Ok(
                    AzureADSSOProvider(
                        client_id=config["client_id"],
                        client_secret=config["client_secret"],
                        redirect_uri=redirect_uri,
                        tenant_id=config["tenant_id"],
                    )
                )

            elif provider_type == "okta":
                if not all(
                    k in config for k in ["client_id", "client_secret", "okta_domain"]
                ):
                    return Err(f"Missing required Okta config for {provider_name}")

                return Ok(
                    OktaSSOProvider(
                        client_id=config["client_id"],
                        client_secret=config["client_secret"],
                        redirect_uri=redirect_uri,
                        okta_domain=config["okta_domain"],
                        authorization_server_id=config.get(
                            "authorization_server_id", "default"
                        ),
                    )
                )

            elif provider_type == "auth0":
                if not all(
                    k in config for k in ["client_id", "client_secret", "auth0_domain"]
                ):
                    return Err(f"Missing required Auth0 config for {provider_name}")

                return Ok(
                    Auth0SSOProvider(
                        client_id=config["client_id"],
                        client_secret=config["client_secret"],
                        redirect_uri=redirect_uri,
                        auth0_domain=config["auth0_domain"],
                        audience=config.get("audience"),
                    )
                )

            else:
                return Err(f"Unsupported provider type: {provider_type}")

        except Exception as e:
            return Err(f"Failed to create provider {provider_name}: {str(e)}")

    @beartype
    def get_provider(self, provider_name: str) -> SSOProvider | None:
        """Get SSO provider by name.

        Args:
            provider_name: Name of the provider

        Returns:
            SSO provider instance or None if not found
        """
        return self._providers.get(provider_name)

    @beartype
    def list_providers(self) -> list[str]:
        """List all configured SSO providers.

        Returns:
            List of provider names
        """
        return list(self._providers.keys())

    @beartype
    async def create_or_update_user(
        self,
        sso_info: SSOUserInfo,
        provider_name: str,
    ) -> Result[User, str]:
        """Create or update user from SSO information.

        Args:
            sso_info: SSO user information
            provider_name: Name of the SSO provider

        Returns:
            Result containing user or error
        """
        if provider_name not in self._providers:
            return Err(
                f"SSO provider '{provider_name}' is not configured. "
                f"Available providers: {list(self._providers.keys())}. "
                f"Required action: Configure provider in Admin > SSO Settings."
            )

        try:
            async with self._db.transaction():
                # Check if user exists by SSO link
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
                        UUID(existing["id"]), sso_info
                    )
                else:
                    # Check if email already exists
                    email_user = await self._db.fetchrow(
                        "SELECT * FROM users WHERE email = $1", sso_info.email
                    )

                    if email_user:
                        # Link existing user to SSO
                        user = await self._link_user_to_sso(
                            UUID(email_user["id"]), provider_name, sso_info
                        )
                    else:
                        # Check if auto-provisioning is allowed
                        config = self._provider_configs.get(provider_name, {})
                        auto_create = await self._check_auto_provisioning(
                            provider_name, sso_info, config
                        )

                        if isinstance(auto_create, Err):
                            return auto_create

                        # Create new user
                        user = await self._create_user_from_sso(sso_info, provider_name)

                # Update groups/roles
                await self._sync_user_groups(user.id, provider_name, sso_info.groups)

                # Log successful authentication
                await self._log_auth_event(
                    user.id, "sso", provider_name, "success", None
                )

                return Ok(user)

        except Exception as e:
            # Log failed authentication
            await self._log_auth_event(None, "sso", provider_name, "failed", str(e))
            return Err(f"Failed to create/update user: {str(e)}")

    @beartype
    async def _check_auto_provisioning(
        self,
        provider_name: str,
        sso_info: SSOUserInfo,
        config: dict[str, Any],
    ) -> Result[bool, str]:
        """Check if user auto-provisioning is allowed.

        Args:
            provider_name: Name of the SSO provider
            sso_info: SSO user information
            config: Provider configuration

        Returns:
            Result indicating if provisioning is allowed or error
        """
        # Check if auto-create is enabled
        provider_row = await self._db.fetchrow(
            "SELECT auto_create_users, allowed_domains, default_role FROM sso_provider_configs WHERE provider_name = $1",
            provider_name,
        )

        if not provider_row or not provider_row["auto_create_users"]:
            return Err(
                f"User provisioning not allowed for provider '{provider_name}'. "
                f"User email: {sso_info.email}. "
                f"Required action: Enable auto-provisioning in Admin > SSO > {provider_name} Settings "
                f"or manually create user account first."
            )

        # Check domain restrictions
        allowed_domains = provider_row.get("allowed_domains", [])
        if allowed_domains:
            email_domain = (
                sso_info.email.split("@")[-1] if "@" in sso_info.email else ""
            )
            if email_domain not in allowed_domains:
                return Err(
                    f"Email domain '{email_domain}' not allowed for {provider_name}. "
                    f"Allowed domains: {', '.join(allowed_domains)}. "
                    f"Required action: Use email from allowed domain or update domain restrictions."
                )

        return Ok(True)

    @beartype
    async def _create_user_from_sso(
        self,
        sso_info: SSOUserInfo,
        provider_name: str,
    ) -> User:
        """Create new user from SSO information.

        Args:
            sso_info: SSO user information
            provider_name: Name of the SSO provider

        Returns:
            Created user
        """
        # Extract name parts
        first_name = sso_info.given_name or ""
        last_name = sso_info.family_name or ""

        if not first_name and not last_name and sso_info.name:
            # Split full name
            name_parts = sso_info.name.split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

        if not first_name:
            # Use email username as fallback
            first_name = sso_info.email.split("@")[0]

        # Create user with random password (won't be used with SSO)
        import secrets

        random_password = secrets.token_urlsafe(32)

        user_id = await self._db.fetchval(
            """
            INSERT INTO users (email, password_hash, first_name, last_name, role, is_active)
            VALUES ($1, $2, $3, $4, $5, true)
            RETURNING id
            """,
            sso_info.email,
            f"sso:{random_password}",  # Prefix to indicate SSO user
            first_name,
            last_name,
            "agent",  # Default role
        )

        # Create SSO link
        await self._db.execute(
            """
            INSERT INTO user_sso_links
            (user_id, provider, provider_user_id, profile_data, last_login_at)
            VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
            """,
            user_id,
            provider_name,
            sso_info.provider_user_id,
            sso_info.raw_claims,
        )

        # Get full user record
        row = await self._db.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        
        if not row:
            raise ValueError(f"User {user_id} not found after creation")

        return User(
            id=user_id,
            email=row["email"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            role=row["role"],
            is_active=row["is_active"],
        )

    @beartype
    async def _update_user_from_sso(
        self,
        user_id: UUID,
        sso_info: SSOUserInfo,
    ) -> User:
        """Update existing user from SSO information.

        Args:
            user_id: User ID
            sso_info: SSO user information

        Returns:
            Updated user
        """
        # Update SSO link
        await self._db.execute(
            """
            UPDATE user_sso_links
            SET profile_data = $1, last_login_at = CURRENT_TIMESTAMP
            WHERE user_id = $2 AND provider = $3
            """,
            sso_info.raw_claims,
            user_id,
            sso_info.provider,
        )

        # Update user last login
        await self._db.execute(
            "UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = $1", user_id
        )

        # Get updated user
        row = await self._db.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        
        if not row:
            raise ValueError(f"User {user_id} not found after update")

        return User(
            id=user_id,
            email=row["email"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            role=row["role"],
            is_active=row["is_active"],
        )

    @beartype
    async def _link_user_to_sso(
        self,
        user_id: UUID,
        provider_name: str,
        sso_info: SSOUserInfo,
    ) -> User:
        """Link existing user to SSO provider.

        Args:
            user_id: User ID
            provider_name: Name of the SSO provider
            sso_info: SSO user information

        Returns:
            Linked user
        """
        # Create SSO link
        await self._db.execute(
            """
            INSERT INTO user_sso_links
            (user_id, provider, provider_user_id, profile_data, last_login_at)
            VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
            ON CONFLICT (provider, provider_user_id) DO UPDATE
            SET profile_data = EXCLUDED.profile_data,
                last_login_at = EXCLUDED.last_login_at
            """,
            user_id,
            provider_name,
            sso_info.provider_user_id,
            sso_info.raw_claims,
        )

        return await self._update_user_from_sso(user_id, sso_info)

    @beartype
    async def _sync_user_groups(
        self,
        user_id: UUID,
        provider_name: str,
        sso_groups: list[str],
    ) -> None:
        """Synchronize user groups from SSO provider.

        Args:
            user_id: User ID
            provider_name: Name of the SSO provider
            sso_groups: List of groups from SSO provider
        """
        try:
            # Get provider ID
            provider_id = await self._db.fetchval(
                "SELECT id FROM sso_provider_configs WHERE provider_name = $1",
                provider_name,
            )

            if not provider_id:
                return

            # Get group mappings
            mappings = await self._db.fetch(
                """
                SELECT sso_group_name, internal_role
                FROM sso_group_mappings
                WHERE provider_id = $1 AND auto_assign = true
                """,
                provider_id,
            )

            # Map SSO groups to internal roles
            mapped_roles = []
            for mapping in mappings:
                if mapping["sso_group_name"] in sso_groups:
                    mapped_roles.append(mapping["internal_role"])

            # Update user role if mappings found
            if mapped_roles:
                # Use highest privilege role
                role_priority = {"system": 4, "admin": 3, "underwriter": 2, "agent": 1}
                highest_role = max(mapped_roles, key=lambda r: role_priority.get(r, 0))

                await self._db.execute(
                    "UPDATE users SET role = $1 WHERE id = $2", highest_role, user_id
                )

            # Log group sync
            await self._db.execute(
                """
                INSERT INTO sso_group_sync_logs
                (provider_id, user_id, sync_type, groups_added, status, last_sync)
                VALUES ($1, $2, 'full', $3, 'success', CURRENT_TIMESTAMP)
                """,
                provider_id,
                user_id,
                sso_groups,
            )

        except Exception as e:
            # Log sync failure
            await self._db.execute(
                """
                INSERT INTO sso_group_sync_logs
                (provider_id, user_id, sync_type, status, error_message, last_sync)
                VALUES ($1, $2, 'full', 'failed', $3, CURRENT_TIMESTAMP)
                """,
                provider_id or uuid4(),
                user_id,
                str(e),
            )

    @beartype
    async def _log_auth_event(
        self,
        user_id: UUID | None,
        auth_method: str,
        provider: str | None,
        status: str,
        error_message: str | None,
    ) -> None:
        """Log authentication event.

        Args:
            user_id: User ID (None if auth failed)
            auth_method: Authentication method (password, sso, api_key)
            provider: SSO provider name (if applicable)
            status: Authentication status (success, failed, blocked)
            error_message: Error message (if failed)
        """
        try:
            await self._db.execute(
                """
                INSERT INTO auth_logs
                (user_id, auth_method, provider, status, error_message, created_at)
                VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
                """,
                user_id,
                auth_method,
                provider,
                status,
                error_message,
            )
        except Exception:
            # Don't fail auth due to logging error
            pass

    @beartype
    async def _decrypt_secret(self, encrypted_secret: str) -> str:
        """Decrypt client secret.

        In production, this would use KMS or similar service.

        Args:
            encrypted_secret: Encrypted secret

        Returns:
            Decrypted secret
        """
        # TODO: Implement proper encryption/decryption with KMS
        # For now, return as-is (assuming it's not actually encrypted)
        return encrypted_secret

    @beartype
    async def _load_providers_from_configs(
        self,
        configs: dict[str, dict[str, Any]],
    ) -> None:
        """Load providers from cached configurations.

        Args:
            configs: Provider configurations
        """
        for provider_name, config in configs.items():
            provider_type = config.get("provider_type", "oidc")
            provider_result = await self._create_provider(
                provider_name, provider_type, config
            )

            if isinstance(provider_result, Ok):
                self._providers[provider_name] = provider_result.value
                self._provider_configs[provider_name] = config
