"""Admin SSO configuration management service."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from beartype import beartype

from pd_prime_demo.core.result_types import Err, Ok, Result

from ...core.cache import Cache
from ...core.database import Database


class SSOAdminService:
    """Service for admin SSO configuration and management."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize SSO admin service.

        Args:
            db: Database instance
            cache: Cache instance
        """
        self._db = db
        self._cache = cache
        self._config_cache_prefix = "sso_config:"

    @beartype
    async def create_sso_provider_config(
        self,
        admin_user_id: UUID,
        provider_name: str,
        provider_type: str,  # 'oidc', 'saml', 'oauth2'
        configuration: dict[str, Any],
        is_enabled: bool = False,
    ) -> Result[UUID, str]:
        """Create new SSO provider configuration.

        Args:
            admin_user_id: ID of admin user creating the config
            provider_name: Unique name for the provider
            provider_type: Type of provider (oidc, saml, oauth2)
            configuration: Provider configuration
            is_enabled: Whether to enable immediately

        Returns:
            Result containing provider ID or error
        """
        try:
            # Validate configuration based on provider type
            validation = await self._validate_provider_config(
                provider_type, configuration
            )
            if isinstance(validation, Err):
                return validation

            # Check if provider name already exists
            existing = await self._db.fetchval(
                "SELECT id FROM sso_provider_configs WHERE provider_name = $1",
                provider_name,
            )
            if existing:
                return Err(
                    f"Provider name '{provider_name}' already exists. "
                    f"Required action: Choose a different provider name."
                )

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
                provider_id,
                provider_name,
                provider_type,
                encrypted_config,
                is_enabled,
                admin_user_id,
                datetime.utcnow(),
            )

            # Clear configuration cache
            await self._cache.clear_pattern(f"{self._config_cache_prefix}*")
            await self._cache.delete("sso:provider_configs")

            # Log configuration creation
            await self._log_sso_activity(
                admin_user_id,
                "create_provider",
                provider_id,
                {"provider_name": provider_name, "provider_type": provider_type},
            )

            return Ok(provider_id)

        except Exception as e:
            return Err(f"Provider configuration failed: {str(e)}")

    @beartype
    async def update_provider_config(
        self,
        provider_id: UUID,
        admin_user_id: UUID,
        updates: dict[str, Any],
    ) -> Result[bool, str]:
        """Update SSO provider configuration.

        Args:
            provider_id: Provider ID to update
            admin_user_id: ID of admin user making the update
            updates: Dictionary of updates to apply

        Returns:
            Result indicating success or error
        """
        try:
            # Get existing configuration
            existing = await self._db.fetchrow(
                "SELECT * FROM sso_provider_configs WHERE id = $1", provider_id
            )
            if not existing:
                return Err("Provider configuration not found")

            # Check if trying to change provider name to existing one
            if (
                "provider_name" in updates
                and updates["provider_name"] != existing["provider_name"]
            ):
                name_exists = await self._db.fetchval(
                    "SELECT id FROM sso_provider_configs WHERE provider_name = $1 AND id != $2",
                    updates["provider_name"],
                    provider_id,
                )
                if name_exists:
                    return Err(
                        f"Provider name '{updates['provider_name']}' already exists. "
                        f"Required action: Choose a different provider name."
                    )

            # Merge updates with existing config
            current_config = existing["configuration"]
            if "configuration" in updates:
                updated_config = {**current_config, **updates["configuration"]}
            else:
                updated_config = current_config

            # Validate updated configuration
            validation = await self._validate_provider_config(
                existing["provider_type"], updated_config
            )
            if isinstance(validation, Err):
                return validation

            # Encrypt updated configuration
            encrypted_config = await self._encrypt_sensitive_config(updated_config)

            # Build update query dynamically
            update_fields = []
            update_values = []

            if "provider_name" in updates:
                update_fields.append("provider_name = $%d")
                update_values.append(updates["provider_name"])

            if "configuration" in updates:
                update_fields.append("configuration = $%d")
                update_values.append(encrypted_config)

            if "is_enabled" in updates:
                update_fields.append("is_enabled = $%d")
                update_values.append(updates["is_enabled"])

            update_fields.append("updated_by = $%d")
            update_values.append(admin_user_id)

            update_fields.append("updated_at = $%d")
            update_values.append(datetime.utcnow())

            # Format placeholders
            formatted_fields = []
            for i, field in enumerate(update_fields, 2):
                formatted_fields.append(field % (i))

            # Update database
            query = f"""
                UPDATE sso_provider_configs
                SET {', '.join(formatted_fields)}
                WHERE id = $1
            """

            await self._db.execute(query, provider_id, *update_values)

            # Clear cache
            await self._cache.clear_pattern(f"{self._config_cache_prefix}*")
            await self._cache.delete("sso:provider_configs")

            # Log update
            await self._log_sso_activity(
                admin_user_id,
                "update_provider",
                provider_id,
                {"updates": list(updates.keys())},
            )

            return Ok(True)

        except Exception as e:
            return Err(f"Update failed: {str(e)}")

    @beartype
    async def test_provider_connection(
        self,
        provider_id: UUID,
        admin_user_id: UUID,
    ) -> Result[dict[str, Any], str]:
        """Test SSO provider connection and configuration.

        Args:
            provider_id: Provider ID to test
            admin_user_id: ID of admin user running the test

        Returns:
            Result containing test results or error
        """
        try:
            # Get provider configuration
            provider = await self._db.fetchrow(
                "SELECT * FROM sso_provider_configs WHERE id = $1", provider_id
            )
            if not provider:
                return Err("Provider not found")

            if not provider["is_enabled"]:
                return Err(
                    "Provider is not enabled. "
                    "Required action: Enable the provider before testing."
                )

            # Decrypt configuration
            config = await self._decrypt_config(provider["configuration"])

            # Test connection based on provider type
            if provider["provider_type"] == "oidc":
                test_result = await self._test_oidc_connection(config)
            elif provider["provider_type"] == "saml":
                test_result = await self._test_saml_connection(config)
            else:
                return Err(f"Unsupported provider type: {provider['provider_type']}")

            # Log test attempt
            await self._log_sso_activity(
                admin_user_id,
                "test_connection",
                provider_id,
                {"success": test_result.get("success", False)},
            )

            return Ok(test_result)

        except Exception as e:
            return Err(f"Connection test failed: {str(e)}")

    @beartype
    async def get_user_provisioning_rules(
        self,
        provider_id: UUID,
    ) -> Result[list[dict[str, Any]], str]:
        """Get user provisioning rules for a provider.

        Args:
            provider_id: Provider ID

        Returns:
            Result containing list of rules or error
        """
        try:
            rules = await self._db.fetch(
                """
                SELECT
                    id, rule_name, conditions, actions,
                    is_enabled, priority, created_at
                FROM user_provisioning_rules
                WHERE provider_id = $1
                ORDER BY priority DESC, created_at ASC
                """,
                provider_id,
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
        """Create SSO group to internal role mapping.

        Args:
            provider_id: Provider ID
            admin_user_id: ID of admin user creating the mapping
            sso_group: SSO group name
            internal_role: Internal role to map to
            auto_assign: Whether to auto-assign on login

        Returns:
            Result containing mapping ID or error
        """
        try:
            # Validate internal role
            valid_roles = ["agent", "underwriter", "admin", "system"]
            if internal_role not in valid_roles:
                return Err(
                    f"Invalid internal role '{internal_role}'. "
                    f"Valid roles: {', '.join(valid_roles)}."
                )

            # Check if mapping already exists
            existing = await self._db.fetchval(
                """
                SELECT id FROM sso_group_mappings
                WHERE provider_id = $1 AND sso_group_name = $2
                """,
                provider_id,
                sso_group,
            )
            if existing:
                return Err(
                    f"Mapping for group '{sso_group}' already exists. "
                    f"Required action: Update existing mapping or choose different group."
                )

            mapping_id = uuid4()

            await self._db.execute(
                """
                INSERT INTO sso_group_mappings (
                    id, provider_id, sso_group_name, internal_role,
                    auto_assign, created_by, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                mapping_id,
                provider_id,
                sso_group,
                internal_role,
                auto_assign,
                admin_user_id,
                datetime.utcnow(),
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
    ) -> Result[dict[str, Any], str]:
        """Get SSO usage analytics for admin dashboards.

        Args:
            date_from: Start date for analytics
            date_to: End date for analytics

        Returns:
            Result containing analytics data or error
        """
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
                    AND al.provider = usl.provider
                GROUP BY usl.provider
                ORDER BY total_logins DESC
                """,
                date_from,
                date_to,
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
                date_from,
                date_to,
            )

            # Group sync statistics
            sync_stats = await self._db.fetchrow(
                """
                SELECT
                    COUNT(*) as total_syncs,
                    COUNT(*) FILTER (WHERE status = 'success') as successful_syncs,
                    MAX(last_sync) as last_sync_time
                FROM sso_group_sync_logs
                WHERE last_sync BETWEEN $1 AND $2
                """,
                date_from,
                date_to,
            )

            # Provider configuration stats
            provider_stats = await self._db.fetch(
                """
                SELECT
                    provider_type,
                    COUNT(*) as total_providers,
                    COUNT(*) FILTER (WHERE is_enabled = true) as enabled_providers
                FROM sso_provider_configs
                GROUP BY provider_type
                """
            )

            return Ok(
                {
                    "login_statistics": [dict(row) for row in login_stats],
                    "provisioning_statistics": [
                        dict(row) for row in provisioning_stats
                    ],
                    "sync_statistics": dict(sync_stats) if sync_stats else {},
                    "provider_statistics": [dict(row) for row in provider_stats],
                    "period": {
                        "from": date_from.isoformat(),
                        "to": date_to.isoformat(),
                    },
                }
            )

        except Exception as e:
            return Err(f"Analytics failed: {str(e)}")

    @beartype
    async def _validate_provider_config(
        self,
        provider_type: str,
        config: dict[str, Any],
    ) -> Result[bool, str]:
        """Validate provider configuration.

        Args:
            provider_type: Type of provider
            config: Configuration to validate

        Returns:
            Result indicating valid or error with details
        """
        if provider_type == "oidc":
            required = ["client_id", "client_secret", "redirect_uri"]
            missing = [f for f in required if not config.get(f)]
            if missing:
                return Err(
                    f"Missing required OIDC configuration: {', '.join(missing)}. "
                    f"Required action: Provide all required fields."
                )

            # Additional OIDC validations
            if provider_type == "google" and "hosted_domain" in config:
                if not config["hosted_domain"].strip():
                    return Err("Google hosted_domain cannot be empty if provided")

            elif provider_type == "azure" and "tenant_id" not in config:
                return Err(
                    "Azure AD requires tenant_id. "
                    "Required action: Add tenant_id to configuration."
                )

            elif provider_type == "okta" and "okta_domain" not in config:
                return Err(
                    "Okta requires okta_domain. "
                    "Required action: Add okta_domain to configuration."
                )

        elif provider_type == "saml":
            required = ["entity_id", "sso_url", "x509_cert", "redirect_uri"]
            missing = [f for f in required if not config.get(f)]
            if missing:
                return Err(
                    f"Missing required SAML configuration: {', '.join(missing)}. "
                    f"Required action: Provide all required fields."
                )

        return Ok(True)

    @beartype
    async def _test_oidc_connection(
        self,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Test OIDC provider connection.

        Args:
            config: Provider configuration

        Returns:
            Test results
        """
        try:
            import httpx

            # Try to fetch discovery document
            issuer = config.get("issuer_url", "")
            if not issuer:
                return {"success": False, "error": "Missing issuer URL", "details": {}}

            discovery_url = f"{issuer}/.well-known/openid-configuration"

            async with httpx.AsyncClient() as client:
                response = await client.get(discovery_url, timeout=10.0)

                if response.status_code == 200:
                    discovery = response.json()
                    return {
                        "success": True,
                        "details": {
                            "issuer": discovery.get("issuer"),
                            "authorization_endpoint": discovery.get(
                                "authorization_endpoint"
                            ),
                            "token_endpoint": discovery.get("token_endpoint"),
                            "userinfo_endpoint": discovery.get("userinfo_endpoint"),
                            "jwks_uri": discovery.get("jwks_uri"),
                            "scopes_supported": discovery.get("scopes_supported", []),
                        },
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to fetch discovery document: HTTP {response.status_code}",
                        "details": {},
                    }

        except Exception as e:
            return {"success": False, "error": str(e), "details": {}}

    @beartype
    async def _test_saml_connection(
        self,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Test SAML provider connection.

        Args:
            config: Provider configuration

        Returns:
            Test results
        """
        # Basic validation for SAML
        return {
            "success": True,
            "details": {
                "entity_id": config.get("entity_id"),
                "sso_url": config.get("sso_url"),
                "has_certificate": bool(config.get("x509_cert")),
            },
            "note": "SAML connections require user-initiated testing",
        }

    @beartype
    async def _encrypt_sensitive_config(
        self,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Encrypt sensitive configuration fields.

        Args:
            config: Configuration to encrypt

        Returns:
            Configuration with encrypted fields
        """
        # Implement basic encryption for sensitive fields
        # In production, this would use AWS KMS or similar
        encrypted = config.copy()
        sensitive_fields = ["client_secret", "x509_cert", "private_key"]

        for field in sensitive_fields:
            if field in encrypted and encrypted[field]:
                # Use basic base64 encoding as placeholder for KMS encryption
                import base64

                encoded_value = base64.b64encode(encrypted[field].encode()).decode()
                encrypted[field] = f"encrypted:{encoded_value}"

        return encrypted

    @beartype
    async def _decrypt_config(
        self,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Decrypt configuration.

        Args:
            config: Encrypted configuration

        Returns:
            Decrypted configuration
        """
        # Basic decryption for demo purposes - production would use KMS
        decrypted = config.copy()

        for key, value in decrypted.items():
            if isinstance(value, str) and value.startswith("encrypted:"):
                # Basic base64 decoding for demo - production would use KMS
                import base64
                try:
                    encrypted_value = value.replace("encrypted:", "")
                    decoded_value = base64.b64decode(encrypted_value).decode()
                    decrypted[key] = decoded_value
                except Exception:
                    # If decoding fails, return as-is
                    decrypted[key] = value

        return decrypted

    @beartype
    async def list_sso_providers(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Result[dict[str, Any], str]:
        """List SSO provider configurations.

        Args:
            limit: Maximum number of providers to return
            offset: Number of providers to skip

        Returns:
            Result containing list of providers and metadata
        """
        try:
            # Get total count
            total = await self._db.fetchval("SELECT COUNT(*) FROM sso_provider_configs")

            # Get providers with pagination
            providers = await self._db.fetch(
                """
                SELECT
                    id, provider_name, provider_type, is_enabled,
                    created_at, updated_at
                FROM sso_provider_configs
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )

            return Ok(
                {
                    "providers": [dict(row) for row in providers],
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                }
            )

        except Exception as e:
            return Err(f"Failed to list providers: {str(e)}")

    @beartype
    async def get_sso_provider(
        self,
        provider_id: UUID,
    ) -> Result[dict[str, Any], str]:
        """Get SSO provider configuration details.

        Args:
            provider_id: Provider ID

        Returns:
            Result containing provider details or error
        """
        try:
            provider = await self._db.fetchrow(
                """
                SELECT
                    id, provider_name, provider_type, configuration,
                    is_enabled, created_by, updated_by, created_at, updated_at
                FROM sso_provider_configs
                WHERE id = $1
                """,
                provider_id,
            )

            if not provider:
                return Err("Provider not found")

            # Decrypt configuration for display (mask sensitive fields)
            config = await self._decrypt_config(provider["configuration"])
            masked_config = self._mask_sensitive_config(config)

            provider_data = dict(provider)
            provider_data["configuration"] = masked_config

            return Ok(provider_data)

        except Exception as e:
            return Err(f"Failed to get provider: {str(e)}")

    @beartype
    async def delete_sso_provider(
        self,
        provider_id: UUID,
        admin_user_id: UUID,
    ) -> Result[bool, str]:
        """Delete SSO provider configuration.

        Args:
            provider_id: Provider ID to delete
            admin_user_id: ID of admin user performing deletion

        Returns:
            Result indicating success or error
        """
        try:
            # Check if provider exists
            provider = await self._db.fetchrow(
                "SELECT provider_name FROM sso_provider_configs WHERE id = $1",
                provider_id,
            )

            if not provider:
                return Err("Provider not found")

            # Check if provider has active users
            active_users = await self._db.fetchval(
                """
                SELECT COUNT(*) FROM user_sso_links usl
                JOIN sso_provider_configs spc ON usl.provider = spc.provider_name
                WHERE spc.id = $1
                """,
                provider_id,
            )

            if active_users > 0:
                return Err(
                    f"Cannot delete provider with {active_users} active users. "
                    f"Required action: Migrate users to another provider first."
                )

            # Delete provider (cascades to related tables)
            await self._db.execute(
                "DELETE FROM sso_provider_configs WHERE id = $1", provider_id
            )

            # Clear cache
            await self._cache.clear_pattern(f"{self._config_cache_prefix}*")
            await self._cache.delete("sso:provider_configs")

            # Log deletion
            await self._log_sso_activity(
                admin_user_id,
                "delete_provider",
                provider_id,
                {"provider_name": provider["provider_name"]},
            )

            return Ok(True)

        except Exception as e:
            return Err(f"Failed to delete provider: {str(e)}")

    @beartype
    async def list_group_mappings(
        self,
        provider_id: UUID,
    ) -> Result[list[dict[str, Any]], str]:
        """List group mappings for a provider.

        Args:
            provider_id: Provider ID

        Returns:
            Result containing list of mappings or error
        """
        try:
            mappings = await self._db.fetch(
                """
                SELECT
                    id, sso_group_name, internal_role, auto_assign,
                    created_by, created_at
                FROM sso_group_mappings
                WHERE provider_id = $1
                ORDER BY sso_group_name
                """,
                provider_id,
            )

            return Ok([dict(row) for row in mappings])

        except Exception as e:
            return Err(f"Failed to list group mappings: {str(e)}")

    @beartype
    async def get_activity_logs(
        self,
        limit: int = 50,
        offset: int = 0,
        provider_id: UUID | None = None,
    ) -> Result[dict[str, Any], str]:
        """Get SSO administrative activity logs.

        Args:
            limit: Maximum number of logs to return
            offset: Number of logs to skip
            provider_id: Optional provider filter

        Returns:
            Result containing activity logs or error
        """
        try:
            # Build query with optional provider filter
            where_clause = "WHERE 1=1"
            params: list[UUID | int] = []

            if provider_id:
                where_clause += " AND provider_id = $1"
                params.append(provider_id)

            # Get total count
            count_query = f"SELECT COUNT(*) FROM sso_activity_logs {where_clause}"
            total = await self._db.fetchval(count_query, *params)

            # Get logs with pagination
            params.extend([limit, offset])
            limit_offset = f"LIMIT ${len(params)-1} OFFSET ${len(params)}"

            # Safe query construction - where_clause and limit_offset are built from parameterized conditions
            logs_query = (
                """
                SELECT
                    sal.id, sal.action, sal.provider_id, sal.details, sal.created_at,
                    u.email as admin_email,
                    spc.provider_name
                FROM sso_activity_logs sal
                LEFT JOIN users u ON sal.admin_user_id = u.id
                LEFT JOIN sso_provider_configs spc ON sal.provider_id = spc.id
                """
                + where_clause
                + """
                ORDER BY sal.created_at DESC
                """
                + limit_offset
            )

            logs = await self._db.fetch(logs_query, *params)

            return Ok(
                {
                    "activities": [dict(row) for row in logs],
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                }
            )

        except Exception as e:
            return Err(f"Failed to get activity logs: {str(e)}")

    @beartype
    def _mask_sensitive_config(
        self,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Mask sensitive configuration fields for display.

        Args:
            config: Configuration to mask

        Returns:
            Configuration with masked sensitive fields
        """
        masked = config.copy()
        sensitive_fields = ["client_secret", "x509_cert", "private_key"]

        for field in sensitive_fields:
            if field in masked and masked[field]:
                value = str(masked[field])
                if len(value) > 8:
                    masked[field] = f"{value[:4]}...{value[-4:]}"
                else:
                    masked[field] = "***"

        return masked

    @beartype
    async def _log_sso_activity(
        self,
        admin_user_id: UUID,
        action: str,
        provider_id: UUID | None,
        details: dict[str, Any],
    ) -> None:
        """Log SSO administrative activity.

        Args:
            admin_user_id: Admin user performing the action
            action: Action performed
            provider_id: Related provider ID (if applicable)
            details: Additional details about the action
        """
        try:
            await self._db.execute(
                """
                INSERT INTO sso_activity_logs
                (admin_user_id, action, provider_id, details, created_at)
                VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
                """,
                admin_user_id,
                action,
                provider_id,
                details,
            )
        except Exception:
            # Don't fail operations due to logging errors
            pass
