"""Admin OAuth2 client management service."""

import hashlib
import secrets
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from beartype import beartype

from pd_prime_demo.core.result_types import Err, Ok, Result

from ...core.cache import Cache
from ...core.database import Database


class OAuth2AdminService:
    """Service for admin OAuth2 client management."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize OAuth2 admin service.

        Args:
            db: Database connection
            cache: Cache instance
        """
        self._db = db
        self._cache = cache
        self._client_cache_prefix = "oauth2_client:"

    @beartype
    async def create_oauth2_client(
        self,
        admin_user_id: UUID,
        client_name: str,
        client_type: str,  # 'public', 'confidential'
        allowed_grant_types: list[str],
        allowed_scopes: list[str],
        redirect_uris: list[str],
        description: str | None = None,
        token_lifetime: int = 3600,  # 1 hour default
        refresh_token_lifetime: int = 86400 * 7,  # 1 week default
    ) -> Result[dict[str, Any], str]:
        """Create new OAuth2 client application.

        Args:
            admin_user_id: ID of admin creating the client
            client_name: Name of the client application
            client_type: Type of client ('public' or 'confidential')
            allowed_grant_types: List of allowed OAuth2 grant types
            allowed_scopes: List of allowed OAuth2 scopes
            redirect_uris: List of allowed redirect URIs
            description: Optional description
            token_lifetime: Access token lifetime in seconds
            refresh_token_lifetime: Refresh token lifetime in seconds

        Returns:
            Result containing client details or error message
        """
        try:
            # Generate client credentials
            client_id = f"pd_{secrets.token_urlsafe(16)}"
            client_secret = None
            client_secret_hash = None

            if client_type == "confidential":
                client_secret = secrets.token_urlsafe(32)
                client_secret_hash = hashlib.sha256(client_secret.encode()).hexdigest()

            # Validate grant types and scopes
            valid_grants = [
                "authorization_code",
                "client_credentials",
                "refresh_token",
                "password",
            ]
            invalid_grants = set(allowed_grant_types) - set(valid_grants)
            if invalid_grants:
                return Err(f"Invalid grant types: {invalid_grants}")

            # Validate scopes exist
            from ...core.auth.oauth2.scopes import SCOPES

            invalid_scopes = [s for s in allowed_scopes if s not in SCOPES]
            if invalid_scopes:
                return Err(f"Invalid scopes: {invalid_scopes}")

            # Validate required fields
            if not allowed_grant_types:
                return Err(
                    "OAuth2 error: allowed_grant_types is required. "
                    "Required action: Specify at least one grant type."
                )

            if not allowed_scopes:
                return Err(
                    "OAuth2 error: allowed_scopes is required. "
                    "Required action: Specify at least one scope."
                )

            if not redirect_uris and "authorization_code" in allowed_grant_types:
                return Err(
                    "OAuth2 error: redirect_uris is required for authorization_code grant. "
                    "Required action: Specify at least one redirect URI."
                )

            oauth2_client_id = uuid4()

            await self._db.execute(
                """
                INSERT INTO oauth2_clients (
                    id, client_id, client_secret_hash, client_name,
                    client_type, description, allowed_grant_types,
                    allowed_scopes, redirect_uris, token_lifetime,
                    refresh_token_lifetime, created_by, created_at,
                    is_active
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                oauth2_client_id,
                client_id,
                client_secret_hash,
                client_name,
                client_type,
                description,
                allowed_grant_types,
                allowed_scopes,
                redirect_uris,
                token_lifetime,
                refresh_token_lifetime,
                admin_user_id,
                datetime.utcnow(),
                True,
            )

            # Clear client cache
            await self._cache.delete_pattern(f"{self._client_cache_prefix}*")

            # Log client creation
            await self._log_oauth2_activity(
                admin_user_id,
                "create_client",
                oauth2_client_id,
                {"client_name": client_name, "client_type": client_type},
            )

            result = {
                "id": oauth2_client_id,
                "client_id": client_id,
                "client_name": client_name,
                "client_type": client_type,
                "allowed_scopes": allowed_scopes,
                "allowed_grant_types": allowed_grant_types,
                "redirect_uris": redirect_uris,
                "token_lifetime": token_lifetime,
                "refresh_token_lifetime": refresh_token_lifetime,
            }

            if client_secret:
                result["client_secret"] = client_secret
                result["note"] = (
                    "Store client_secret securely. It cannot be retrieved later."
                )

            return Ok(result)

        except Exception as e:
            return Err(f"Client creation failed: {str(e)}")

    @beartype
    async def update_client_config(
        self,
        client_id: str,
        admin_user_id: UUID,
        updates: dict[str, Any],
    ):
        """Update OAuth2 client configuration.

        Args:
            client_id: OAuth2 client ID
            admin_user_id: ID of admin making the update
            updates: Dictionary of fields to update

        Returns:
            Result indicating success or error
        """
        try:
            # Get existing client
            client = await self._db.fetchrow(
                "SELECT * FROM oauth2_clients WHERE client_id = $1", client_id
            )
            if not client:
                return Err("Client not found")

            # Build update query dynamically
            allowed_fields = [
                "client_name",
                "description",
                "allowed_scopes",
                "redirect_uris",
                "token_lifetime",
                "refresh_token_lifetime",
                "is_active",
                "allowed_grant_types",
            ]

            update_fields = []
            values = []
            param_count = 1

            for field, value in updates.items():
                if field in allowed_fields:
                    param_count += 1
                    update_fields.append(f"{field} = ${param_count}")
                    values.append(value)

            if not update_fields:
                return Err("No valid fields to update")

            # Validate updates
            if "allowed_grant_types" in updates:
                valid_grants = [
                    "authorization_code",
                    "client_credentials",
                    "refresh_token",
                    "password",
                ]
                invalid_grants = set(updates["allowed_grant_types"]) - set(valid_grants)
                if invalid_grants:
                    return Err(f"Invalid grant types: {invalid_grants}")

            if "allowed_scopes" in updates:
                from ...core.auth.oauth2.scopes import SCOPES

                invalid_scopes = [
                    s for s in updates["allowed_scopes"] if s not in SCOPES
                ]
                if invalid_scopes:
                    return Err(f"Invalid scopes: {invalid_scopes}")

            # Add updated metadata
            param_count += 1
            update_fields.append(f"updated_by = ${param_count}")
            values.append(admin_user_id)

            param_count += 1
            update_fields.append(f"updated_at = ${param_count}")
            values.append(datetime.utcnow())

            query = f"""
                UPDATE oauth2_clients
                SET {', '.join(update_fields)}
                WHERE client_id = $1
            """

            await self._db.execute(query, client_id, *values)

            # Clear cache
            await self._cache.delete_pattern(f"{self._client_cache_prefix}*")

            # Log update
            await self._log_oauth2_activity(
                admin_user_id,
                "update_client",
                client["id"],
                {"updates": list(updates.keys())},
            )

            return Ok(True)

        except Exception as e:
            return Err(f"Update failed: {str(e)}")

    @beartype
    async def regenerate_client_secret(
        self,
        client_id: str,
        admin_user_id: UUID,
    ):
        """Regenerate client secret for confidential clients.

        Args:
            client_id: OAuth2 client ID
            admin_user_id: ID of admin performing the action

        Returns:
            Result containing new secret or error
        """
        try:
            # Get client
            client = await self._db.fetchrow(
                "SELECT * FROM oauth2_clients WHERE client_id = $1", client_id
            )
            if not client:
                return Err("Client not found")

            if client["client_type"] != "confidential":
                return Err("Only confidential clients have secrets")

            # Generate new secret
            new_secret = secrets.token_urlsafe(32)
            secret_hash = hashlib.sha256(new_secret.encode()).hexdigest()

            # Update database
            await self._db.execute(
                """
                UPDATE oauth2_clients
                SET client_secret_hash = $2, updated_by = $3, updated_at = $4
                WHERE client_id = $1
                """,
                client_id,
                secret_hash,
                admin_user_id,
                datetime.utcnow(),
            )

            # Revoke all existing tokens for this client
            await self._revoke_client_tokens(client_id)

            # Clear cache
            await self._cache.delete_pattern(f"{self._client_cache_prefix}*")

            # Log secret regeneration
            await self._log_oauth2_activity(
                admin_user_id,
                "regenerate_secret",
                client["id"],
                {"client_id": client_id},
            )

            return Ok(new_secret)

        except Exception as e:
            return Err(f"Secret regeneration failed: {str(e)}")

    @beartype
    async def get_client_analytics(
        self,
        client_id: str,
        date_from: datetime,
        date_to: datetime,
    ) -> Result[dict[str, Any], str]:
        """Get OAuth2 client usage analytics.

        Args:
            client_id: OAuth2 client ID
            date_from: Start date for analytics
            date_to: End date for analytics

        Returns:
            Result containing analytics data or error
        """
        try:
            # Verify client exists
            client = await self._db.fetchrow(
                "SELECT id, client_name FROM oauth2_clients WHERE client_id = $1",
                client_id,
            )
            if not client:
                return Err("Client not found")

            # Token usage statistics
            token_stats = await self._db.fetchrow(
                """
                SELECT
                    COUNT(*) as total_tokens,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(*) FILTER (WHERE grant_type = 'authorization_code') as auth_code_grants,
                    COUNT(*) FILTER (WHERE grant_type = 'client_credentials') as client_cred_grants,
                    COUNT(*) FILTER (WHERE grant_type = 'refresh_token') as refresh_grants,
                    COUNT(*) FILTER (WHERE revoked_at IS NOT NULL) as revoked_tokens
                FROM oauth2_tokens
                WHERE client_id = $1
                    AND created_at BETWEEN $2 AND $3
                """,
                client_id,
                date_from,
                date_to,
            )

            # API usage by scope
            scope_usage = await self._db.fetch(
                """
                SELECT
                    unnest(scopes) as scope,
                    COUNT(*) as usage_count
                FROM oauth2_tokens
                WHERE client_id = $1
                    AND created_at BETWEEN $2 AND $3
                GROUP BY scope
                ORDER BY usage_count DESC
                """,
                client_id,
                date_from,
                date_to,
            )

            # Usage timeline
            usage_timeline = await self._db.fetch(
                """
                SELECT
                    date_trunc('day', created_at) as date,
                    COUNT(*) as token_count,
                    COUNT(DISTINCT user_id) as unique_users
                FROM oauth2_tokens
                WHERE client_id = $1
                    AND created_at BETWEEN $2 AND $3
                GROUP BY date
                ORDER BY date
                """,
                client_id,
                date_from,
                date_to,
            )

            # Active tokens by day
            active_tokens_timeline = await self._db.fetch(
                """
                SELECT
                    date_trunc('day', d.date) as date,
                    COUNT(DISTINCT t.id) as active_tokens
                FROM generate_series($2::date, $3::date, '1 day'::interval) d(date)
                LEFT JOIN oauth2_tokens t ON
                    t.client_id = $1
                    AND t.created_at <= d.date + interval '1 day'
                    AND t.expires_at > d.date
                    AND (t.revoked_at IS NULL OR t.revoked_at > d.date)
                GROUP BY date
                ORDER BY date
                """,
                client_id,
                date_from,
                date_to,
            )

            return Ok(
                {
                    "client_id": client_id,
                    "client_name": client["client_name"],
                    "token_statistics": dict(token_stats) if token_stats else {},
                    "scope_usage": [dict(row) for row in scope_usage],
                    "usage_timeline": [dict(row) for row in usage_timeline],
                    "active_tokens_timeline": [
                        dict(row) for row in active_tokens_timeline
                    ],
                    "period": {
                        "from": date_from.isoformat(),
                        "to": date_to.isoformat(),
                    },
                }
            )

        except Exception as e:
            return Err(f"Analytics failed: {str(e)}")

    @beartype
    async def revoke_client_access(
        self,
        client_id: str,
        admin_user_id: UUID,
        reason: str,
    ):
        """Revoke all active tokens for a client.

        Args:
            client_id: OAuth2 client ID
            admin_user_id: ID of admin performing the action
            reason: Reason for revocation

        Returns:
            Result containing number of revoked tokens or error
        """
        try:
            # Verify client exists
            client = await self._db.fetchrow(
                "SELECT id FROM oauth2_clients WHERE client_id = $1", client_id
            )
            if not client:
                return Err("Client not found")

            # Count tokens to be revoked
            token_count = await self._db.fetchval(
                """
                SELECT COUNT(*) FROM oauth2_tokens
                WHERE client_id = $1 AND revoked_at IS NULL
                """,
                client_id,
            )

            # Revoke all active tokens
            await self._db.execute(
                """
                UPDATE oauth2_tokens
                SET revoked_at = $2, revoked_by = $3, revocation_reason = $4
                WHERE client_id = $1 AND revoked_at IS NULL
                """,
                client_id,
                datetime.utcnow(),
                admin_user_id,
                reason,
            )

            # Also revoke refresh tokens
            await self._db.execute(
                """
                UPDATE oauth2_refresh_tokens
                SET revoked_at = $2, revoked_by = $3
                WHERE client_id = $1 AND revoked_at IS NULL
                """,
                client_id,
                datetime.utcnow(),
                admin_user_id,
            )

            # Clear token cache
            await self._cache.delete_pattern("oauth2_token:*")
            await self._cache.delete_pattern("revoked_token:*")

            # Log revocation
            await self._log_oauth2_activity(
                admin_user_id,
                "revoke_client_tokens",
                client["id"],
                {
                    "client_id": client_id,
                    "tokens_revoked": token_count,
                    "reason": reason,
                },
            )

            return Ok(token_count)

        except Exception as e:
            return Err(f"Token revocation failed: {str(e)}")

    @beartype
    async def list_clients(
        self,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> Result[list[dict[str, Any]], str]:
        """List OAuth2 clients.

        Args:
            active_only: Whether to show only active clients
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            Result containing list of clients or error
        """
        try:
            query = """
                SELECT
                    id, client_id, client_name, client_type, description,
                    allowed_grant_types, allowed_scopes, redirect_uris,
                    token_lifetime, refresh_token_lifetime, is_active,
                    created_at, updated_at, created_by, updated_by
                FROM oauth2_clients
                WHERE 1=1
            """

            if active_only:
                query += " AND is_active = true"

            query += " ORDER BY created_at DESC LIMIT $1 OFFSET $2"

            rows = await self._db.fetch(query, limit, offset)

            clients = []
            for row in rows:
                client_data = dict(row)
                # Don't expose the secret hash
                client_data.pop("client_secret_hash", None)
                clients.append(client_data)

            return Ok(clients)

        except Exception as e:
            return Err(f"Failed to list clients: {str(e)}")

    @beartype
    async def get_client_details(
        self,
        client_id: str,
    ) -> Result[dict[str, Any], str]:
        """Get detailed information about a client.

        Args:
            client_id: OAuth2 client ID

        Returns:
            Result containing client details or error
        """
        try:
            client = await self._db.fetchrow(
                """
                SELECT
                    id, client_id, client_name, client_type, description,
                    allowed_grant_types, allowed_scopes, redirect_uris,
                    token_lifetime, refresh_token_lifetime, is_active,
                    created_at, updated_at, created_by, updated_by
                FROM oauth2_clients
                WHERE client_id = $1
                """,
                client_id,
            )

            if not client:
                return Err("Client not found")

            client_data = dict(client)
            # Don't expose the secret hash
            client_data.pop("client_secret_hash", None)

            # Get token counts
            token_counts = await self._db.fetchrow(
                """
                SELECT
                    COUNT(*) FILTER (WHERE revoked_at IS NULL) as active_tokens,
                    COUNT(*) FILTER (WHERE revoked_at IS NOT NULL) as revoked_tokens,
                    COUNT(DISTINCT user_id) as unique_users
                FROM oauth2_tokens
                WHERE client_id = $1
                """,
                client_id,
            )

            client_data["token_statistics"] = dict(token_counts) if token_counts else {}

            return Ok(client_data)

        except Exception as e:
            return Err(f"Failed to get client details: {str(e)}")

    @beartype
    async def _revoke_client_tokens(self, client_id: str) -> None:
        """Revoke all tokens for a client (internal method).

        Args:
            client_id: OAuth2 client ID
        """
        try:
            # Mark all access tokens as revoked
            await self._db.execute(
                """
                UPDATE oauth2_tokens
                SET revoked_at = $2
                WHERE client_id = $1 AND revoked_at IS NULL
                """,
                client_id,
                datetime.utcnow(),
            )

            # Mark all refresh tokens as revoked
            await self._db.execute(
                """
                UPDATE oauth2_refresh_tokens
                SET revoked_at = $2
                WHERE client_id = $1 AND revoked_at IS NULL
                """,
                client_id,
                datetime.utcnow(),
            )

            # Clear caches
            await self._cache.delete_pattern("oauth2_token:*")
            await self._cache.delete_pattern("revoked_token:*")

        except Exception:
            # Log error but don't fail the main operation
            pass

    @beartype
    async def _log_oauth2_activity(
        self,
        admin_user_id: UUID,
        action: str,
        target_id: UUID | None,
        details: dict[str, Any],
    ) -> None:
        """Log OAuth2 administrative activity.

        Args:
            admin_user_id: ID of admin performing the action
            action: Action being performed
            target_id: ID of target entity (client, token, etc.)
            details: Additional details about the action
        """
        try:
            await self._db.execute(
                """
                INSERT INTO admin_activity_logs (
                    admin_user_id, action, target_type, target_id,
                    details, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                admin_user_id,
                action,
                "oauth2_client",
                target_id,
                details,
                datetime.utcnow(),
            )
        except Exception:
            # Don't fail the main operation if logging fails
            pass
