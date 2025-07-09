"""API key management for simplified authentication."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from beartype import beartype

from pd_prime_demo.core.result_types import Err, Ok, Result

from ....core.cache import Cache
from ....core.database import Database


class APIKeyManager:
    """Manage API keys for partner integrations."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize API key manager.

        Args:
            db: Database connection
            cache: Cache instance
        """
        self._db = db
        self._cache = cache
        self._cache_prefix = "api_key:"

    @beartype
    async def create_api_key(
        self,
        name: str,
        client_id: str,
        scopes: list[str],
        expires_in_days: int | None = None,
        rate_limit_per_minute: int = 60,
        allowed_ips: list[str] | None = None,
    ) -> Result[dict[str, Any], str]:
        """Create a new API key.

        Args:
            name: Descriptive name for the API key
            client_id: Associated OAuth2 client ID
            scopes: List of allowed scopes
            expires_in_days: Optional expiration in days
            rate_limit_per_minute: Rate limit for this key
            allowed_ips: Optional list of allowed IP addresses

        Returns:
            Result containing API key details or error message
        """
        try:
            # Validate scopes
            from .scopes import ScopeValidator

            is_valid, _, error = ScopeValidator.validate_scopes(scopes)
            if not is_valid:
                return Err(f"Invalid scopes: {error}")

            # Generate key
            key_prefix = "pd_"  # Prefix for easy identification
            key_secret = secrets.token_urlsafe(32)
            api_key = f"{key_prefix}{key_secret}"

            # Hash for storage
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            # Calculate expiration
            expires_at = None
            if expires_in_days:
                expires_at = datetime.now(timezone.utc) + timedelta(
                    days=expires_in_days
                )

            # Store in database
            key_id = await self._db.fetchval(
                """
                INSERT INTO api_keys (
                    key_hash, name, client_id, scopes,
                    rate_limit_per_minute, allowed_ips,
                    expires_at, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                key_hash,
                name,
                client_id,
                scopes,
                rate_limit_per_minute,
                allowed_ips,
                expires_at,
                datetime.now(timezone.utc),
            )

            # Cache key info for fast lookup
            cache_data = {
                "id": str(key_id),
                "client_id": client_id,
                "scopes": scopes,
                "rate_limit": rate_limit_per_minute,
                "allowed_ips": allowed_ips,
            }

            cache_ttl = 3600  # 1 hour default
            if expires_at:
                # Cache until expiration
                cache_ttl = int(
                    (expires_at - datetime.now(timezone.utc)).total_seconds()
                )

            await self._cache.set(
                f"{self._cache_prefix}{key_hash}",
                cache_data,
                min(cache_ttl, 86400),  # Max 1 day cache
            )

            return Ok(
                {
                    "id": key_id,
                    "api_key": api_key,
                    "name": name,
                    "scopes": scopes,
                    "expires_at": expires_at.isoformat() if expires_at else None,
                    "rate_limit_per_minute": rate_limit_per_minute,
                    "note": "Store this API key securely. It cannot be retrieved later.",
                }
            )

        except Exception as e:
            return Err(f"Failed to create API key: {str(e)}")

    @beartype
    async def validate_api_key(
        self,
        api_key: str,
        required_scope: str | None = None,
        request_ip: str | None = None,
    ) -> Result[dict[str, Any], str]:
        """Validate API key and check permissions.

        Args:
            api_key: API key to validate
            required_scope: Optional required scope
            request_ip: Optional request IP for validation

        Returns:
            Result containing key info or error message
        """
        try:
            # Hash the key
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            # Check cache first
            cache_key = f"{self._cache_prefix}{key_hash}"
            cached = await self._cache.get(cache_key)

            if cached:
                key_info = cached
            else:
                # Load from database
                row = await self._db.fetchrow(
                    """
                    SELECT id, client_id, scopes, rate_limit_per_minute,
                           allowed_ips, expires_at, active
                    FROM api_keys
                    WHERE key_hash = $1
                    """,
                    key_hash,
                )

                if not row:
                    return Err("Invalid API key")

                if not row["active"]:
                    return Err("API key is disabled")

                if row["expires_at"] and row["expires_at"] < datetime.now(timezone.utc):
                    return Err("API key has expired")

                key_info = {
                    "id": str(row["id"]),
                    "client_id": row["client_id"],
                    "scopes": row["scopes"],
                    "rate_limit": row["rate_limit_per_minute"],
                    "allowed_ips": row["allowed_ips"],
                }

                # Cache for future lookups
                await self._cache.set(cache_key, key_info, 3600)

            # Check IP allowlist
            if key_info.get("allowed_ips") and request_ip:
                if request_ip not in key_info["allowed_ips"]:
                    return Err(f"IP {request_ip} not allowed for this API key")

            # Check scope
            if required_scope:
                from .scopes import ScopeValidator

                if not ScopeValidator.check_scope_permission(
                    key_info["scopes"], required_scope
                ):
                    return Err(f"API key lacks required scope: {required_scope}")

            # Check rate limit
            rate_limit_ok = await self._check_rate_limit(
                key_info["id"], key_info["rate_limit"]
            )

            if not rate_limit_ok:
                return Err("Rate limit exceeded")

            # Update last used
            await self._update_last_used(key_info["id"])

            return Ok(key_info)

        except Exception as e:
            return Err(f"Failed to validate API key: {str(e)}")

    @beartype
    async def revoke_api_key(
        self,
        key_id: UUID,
        reason: str | None = None,
    ) -> Result[bool, str]:
        """Revoke an API key.

        Args:
            key_id: ID of the key to revoke
            reason: Optional reason for revocation

        Returns:
            Result indicating success or error
        """
        try:
            # Get key hash for cache invalidation
            key_hash = await self._db.fetchval(
                "SELECT key_hash FROM api_keys WHERE id = $1", key_id
            )

            if not key_hash:
                return Err("API key not found")

            # Update database
            await self._db.execute(
                """
                UPDATE api_keys
                SET active = false,
                    revoked_at = $2,
                    revocation_reason = $3
                WHERE id = $1
                """,
                key_id,
                datetime.now(timezone.utc),
                reason,
            )

            # Invalidate cache
            await self._cache.delete(f"{self._cache_prefix}{key_hash}")

            return Ok(True)

        except Exception as e:
            return Err(f"Failed to revoke API key: {str(e)}")

    @beartype
    async def rotate_api_key(
        self,
        key_id: UUID,
    ) -> Result[dict[str, Any], str]:
        """Rotate an API key (revoke old, create new).

        Args:
            key_id: ID of the key to rotate

        Returns:
            Result containing new API key details or error
        """
        try:
            # Get existing key details
            row = await self._db.fetchrow(
                """
                SELECT name, client_id, scopes, rate_limit_per_minute,
                       allowed_ips, expires_at
                FROM api_keys
                WHERE id = $1 AND active = true
                """,
                key_id,
            )

            if not row:
                return Err("API key not found or already revoked")

            # Calculate remaining expiration
            expires_in_days = None
            if row["expires_at"]:
                remaining = row["expires_at"] - datetime.now(timezone.utc)
                expires_in_days = max(1, int(remaining.total_seconds() / 86400))

            # Create new key with same settings
            new_key_result = await self.create_api_key(
                name=f"{row['name']} (rotated)",
                client_id=row["client_id"],
                scopes=row["scopes"],
                expires_in_days=expires_in_days,
                rate_limit_per_minute=row["rate_limit_per_minute"],
                allowed_ips=row["allowed_ips"],
            )

            if new_key_result.is_err():
                return new_key_result

            # Revoke old key
            await self.revoke_api_key(key_id, "Key rotation")

            return new_key_result

        except Exception as e:
            return Err(f"Failed to rotate API key: {str(e)}")

    @beartype
    async def list_api_keys(
        self,
        client_id: str | None = None,
        active_only: bool = True,
    ) -> Result[list[dict[str, Any]], str]:
        """List API keys.

        Args:
            client_id: Optional filter by client ID
            active_only: Whether to show only active keys

        Returns:
            Result containing list of API keys or error
        """
        try:
            query = """
                SELECT id, name, client_id, scopes, rate_limit_per_minute,
                       allowed_ips, expires_at, created_at, last_used_at,
                       active, revoked_at
                FROM api_keys
                WHERE 1=1
            """
            params = []

            if client_id:
                params.append(client_id)
                query += f" AND client_id = ${len(params)}"

            if active_only:
                query += " AND active = true"

            query += " ORDER BY created_at DESC"

            rows = await self._db.fetch(query, *params)

            keys = []
            for row in rows:
                key_data = dict(row)
                # Don't expose the hash
                key_data.pop("key_hash", None)
                keys.append(key_data)

            return Ok(keys)

        except Exception as e:
            return Err(f"Failed to list API keys: {str(e)}")

    @beartype
    async def _check_rate_limit(
        self,
        key_id: str,
        limit_per_minute: int,
    ) -> bool:
        """Check if API key is within rate limit.

        Args:
            key_id: API key ID
            limit_per_minute: Rate limit

        Returns:
            True if within limit
        """
        now = datetime.now(timezone.utc)
        minute_key = now.strftime("%Y%m%d%H%M")

        rate_limit_key = f"rate_limit:{key_id}:{minute_key}"

        # Increment counter
        count = await self._cache.incr(rate_limit_key)

        # Set expiration on first increment
        if count == 1:
            await self._cache.expire(rate_limit_key, 60)

        return count <= limit_per_minute

    @beartype
    async def _update_last_used(self, key_id: str) -> None:
        """Update last used timestamp for API key.

        Args:
            key_id: API key ID
        """
        try:
            await self._db.execute(
                """
                UPDATE api_keys
                SET last_used_at = $2, use_count = use_count + 1
                WHERE id = $1
                """,
                UUID(key_id),
                datetime.now(timezone.utc),
            )
        except Exception:
            # Don't fail the request if we can't update last used
            pass

    @beartype
    async def get_usage_statistics(
        self,
        key_id: UUID,
        days: int = 7,
    ) -> Result[dict[str, Any], str]:
        """Get usage statistics for an API key.

        Args:
            key_id: API key ID
            days: Number of days to look back

        Returns:
            Result containing usage statistics or error
        """
        try:
            # Get basic key info
            key_info = await self._db.fetchrow(
                """
                SELECT name, client_id, created_at, last_used_at, use_count
                FROM api_keys
                WHERE id = $1
                """,
                key_id,
            )

            if not key_info:
                return Err("API key not found")

            # Calculate usage over time (this would require a separate usage log table)
            # For now, return basic stats
            stats = {
                "key_id": str(key_id),
                "name": key_info["name"],
                "client_id": key_info["client_id"],
                "created_at": key_info["created_at"],
                "last_used_at": key_info["last_used_at"],
                "total_requests": key_info["use_count"],
                "period_days": days,
            }

            return Ok(stats)

        except Exception as e:
            return Err(f"Failed to get usage statistics: {str(e)}")

    @beartype
    async def bulk_revoke_keys(
        self,
        client_id: str,
        reason: str,
    ) -> Result[int, str]:
        """Bulk revoke all API keys for a client.

        Args:
            client_id: Client ID to revoke keys for
            reason: Reason for revocation

        Returns:
            Result containing number of revoked keys or error
        """
        try:
            # Count keys to be revoked
            count = await self._db.fetchval(
                """
                SELECT COUNT(*) FROM api_keys
                WHERE client_id = $1 AND active = true
                """,
                client_id,
            )

            # Revoke all active keys for the client
            await self._db.execute(
                """
                UPDATE api_keys
                SET active = false,
                    revoked_at = $2,
                    revocation_reason = $3
                WHERE client_id = $1 AND active = true
                """,
                client_id,
                datetime.now(timezone.utc),
                reason,
            )

            # Clear cache for all affected keys
            await self._cache.clear_pattern(f"{self._cache_prefix}*")

            return Ok(count or 0)

        except Exception as e:
            return Err(f"Failed to bulk revoke API keys: {str(e)}")

    @beartype
    async def validate_key_permissions(
        self,
        api_key: str,
        required_permissions: list[str],
        request_context: dict[str, Any] | None = None,
    ) -> Result[dict[str, Any], str]:
        """Advanced API key validation with context-aware permissions.

        Args:
            api_key: API key to validate
            required_permissions: List of required permissions
            request_context: Additional context for validation

        Returns:
            Result containing validation details or error
        """
        try:
            # Basic key validation
            validation_result = await self.validate_api_key(api_key)
            if validation_result.is_err():
                return validation_result

            key_info = validation_result.ok_value
            if key_info is None:
                return Err("API key validation returned None")

            # Check each required permission
            from .scopes import ScopeValidator

            missing_permissions = []
            for permission in required_permissions:
                if not ScopeValidator.check_scope_permission(
                    key_info["scopes"], permission
                ):
                    missing_permissions.append(permission)

            if missing_permissions:
                return Err(
                    f"Missing required permissions: {', '.join(missing_permissions)}"
                )

            # Context-aware validation
            if request_context:
                # Example: Time-based restrictions
                if "time_restrictions" in request_context:
                    current_hour = datetime.now(timezone.utc).hour
                    allowed_hours = request_context["time_restrictions"]
                    if current_hour not in allowed_hours:
                        return Err("API key not allowed during current time window")

                # Example: Resource-specific restrictions
                if "resource_id" in request_context:
                    request_context["resource_id"]
                    # In a real implementation, check if key has access to specific resource
                    pass

            return Ok(
                {
                    **key_info,
                    "permissions_validated": required_permissions,
                    "validation_context": request_context,
                }
            )

        except Exception as e:
            return Err(f"Failed to validate key permissions: {str(e)}")

    @beartype
    async def get_key_security_events(
        self,
        key_id: UUID,
        limit: int = 100,
    ) -> Result[dict[str, Any], str]:
        """Get security events for an API key.

        Args:
            key_id: API key ID
            limit: Maximum number of events to return

        Returns:
            Result containing security events or error
        """
        try:
            # This would integrate with a security event logging system
            # For now, return basic validation events from cache/logs

            events = []

            # Check for recent rate limit violations
            key_hash = await self._db.fetchval(
                "SELECT key_hash FROM api_keys WHERE id = $1", key_id
            )

            if key_hash:
                # Look for rate limit events in cache
                rate_limit_keys = await self._cache.keys(f"rate_limit:{key_id}:*")

                for key in rate_limit_keys:
                    count = await self._cache.get(key)
                    if count and int(count) > 50:  # Threshold for suspicious activity
                        events.append(
                            {
                                "event_type": "rate_limit_warning",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "details": {"request_count": int(count)},
                            }
                        )

            return Ok({"events": events[:limit]})

        except Exception as e:
            return Err(f"Failed to get security events: {str(e)}")

    @beartype
    async def verify_key_ownership(
        self,
        key_id: UUID,
        client_id: str,
    ) -> Result[bool, str]:
        """Verify that an API key belongs to the specified client.

        Args:
            key_id: API key ID to verify
            client_id: Client ID to check ownership against

        Returns:
            Result indicating ownership status or error
        """
        try:
            key_client_id = await self._db.fetchval(
                "SELECT client_id FROM api_keys WHERE id = $1", key_id
            )

            if not key_client_id:
                return Err("API key not found")

            if key_client_id != client_id:
                return Err("API key does not belong to this client")

            return Ok(True)

        except Exception as e:
            return Err(f"Failed to verify key ownership: {str(e)}")

    @beartype
    async def create_scoped_api_key(
        self,
        parent_key_id: UUID,
        name: str,
        scopes: list[str],
        expires_in_hours: int = 24,
    ) -> Result[dict[str, Any], str]:
        """Create a temporary, scoped API key from a parent key.

        This allows creating short-lived keys with subset permissions.

        Args:
            parent_key_id: Parent API key ID
            name: Name for the new scoped key
            scopes: Scopes for the new key (must be subset of parent)
            expires_in_hours: Expiration in hours

        Returns:
            Result containing new API key or error
        """
        try:
            # Get parent key info
            parent_key = await self._db.fetchrow(
                """
                SELECT client_id, scopes FROM api_keys
                WHERE id = $1 AND active = true
                """,
                parent_key_id,
            )

            if not parent_key:
                return Err("Parent API key not found or inactive")

            # Validate that requested scopes are subset of parent scopes
            parent_scopes = set(parent_key["scopes"])
            requested_scopes = set(scopes)

            if not requested_scopes.issubset(parent_scopes):
                invalid_scopes = requested_scopes - parent_scopes
                return Err(
                    f"Scopes not allowed by parent key: {', '.join(invalid_scopes)}"
                )

            # Create scoped key with shorter expiration
            return await self.create_api_key(
                name=f"{name} (scoped)",
                client_id=parent_key["client_id"],
                scopes=scopes,
                expires_in_days=max(1, expires_in_hours // 24),
                rate_limit_per_minute=30,  # Lower rate limit for scoped keys
            )

        except Exception as e:
            return Err(f"Failed to create scoped API key: {str(e)}")
