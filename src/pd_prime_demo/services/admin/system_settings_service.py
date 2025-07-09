"""System configuration management service."""

import json
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from beartype import beartype
from cryptography.fernet import Fernet

from pd_prime_demo.core.result_types import Err, Ok, Result

from ...core.cache import Cache
from ...core.database import Database
from ..cache_keys import CacheKeys


class SettingType(str, Enum):
    """Types of system settings."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    JSON = "json"
    ENCRYPTED = "encrypted"


class SystemSettingsService:
    """Service for system configuration management."""

    def __init__(
        self, db: Database, cache: Cache, encryption_key: str | None = None
    ) -> None:
        """Initialize settings service with dependency validation."""
        if not db or not hasattr(db, "execute"):
            raise ValueError("Database connection required and must be active")
        if not cache or not hasattr(cache, "get"):
            raise ValueError("Cache connection required and must be available")

        self._db = db
        self._cache = cache
        self._cache_ttl = 3600  # 1 hour

        # Initialize encryption for sensitive settings
        if encryption_key:
            self._fernet = Fernet(
                encryption_key.encode()
                if isinstance(encryption_key, str)
                else encryption_key
            )
        else:
            self._fernet = None

    @beartype
    async def get_setting(
        self,
        category: str,
        key: str,
    ) -> Result[Any, str]:
        """Get system setting value.

        Args:
            category: Setting category (e.g., 'email', 'security', 'features')
            key: Setting key within category

        Returns:
            Result with setting value (typed based on setting type) or error
        """
        # Check cache first
        cache_key = CacheKeys.system_setting(category, key)
        cached = await self._cache.get(cache_key)

        if cached is not None:
            return Ok(cached)

        # Load from database
        query = """
            SELECT value, value_type, is_sensitive, is_public
            FROM system_settings
            WHERE category = $1 AND key = $2 AND is_active = true
        """

        row = await self._db.fetchrow(query, category, key)
        if not row:
            return Err(f"Setting {category}.{key} not found")

        # Parse value based on type
        value = row["value"]
        value_type = SettingType(row["value_type"])
        is_sensitive = row["is_sensitive"]

        try:
            # Decrypt if sensitive
            if is_sensitive and self._fernet and value_type == SettingType.ENCRYPTED:
                decrypted = self._fernet.decrypt(value.encode()).decode()
                parsed_value = self._parse_value(decrypted, SettingType.STRING)
            else:
                parsed_value = self._parse_value(value, value_type)

            # Cache non-sensitive values only
            if not is_sensitive:
                await self._cache.set(cache_key, parsed_value, self._cache_ttl)

            return Ok(parsed_value)

        except Exception as e:
            return Err(f"Failed to parse setting value: {str(e)}")

    @beartype
    async def update_setting(
        self,
        category: str,
        key: str,
        value: Any,
        updated_by: UUID,
    ) -> Result[bool, str]:
        """Update system setting.

        Args:
            category: Setting category
            key: Setting key
            value: New value (will be validated against rules)
            updated_by: Admin user making the update

        Returns:
            Result with success boolean or error
        """
        # Get current setting with validation rules
        query = """
            SELECT id, value, value_type, is_sensitive, validation_rules,
                   requires_restart, description
            FROM system_settings
            WHERE category = $1 AND key = $2 AND is_active = true
        """

        row = await self._db.fetchrow(query, category, key)
        if not row:
            return Err(f"Setting {category}.{key} not found")

        setting_id = row["id"]
        old_value = row["value"]
        value_type = SettingType(row["value_type"])
        is_sensitive = row["is_sensitive"]
        validation_rules = row["validation_rules"] or {}

        # Validate new value against rules
        validation_result = self._validate_value(value, value_type, validation_rules)
        if isinstance(validation_result, Err):
            return validation_result

        # Serialize value
        try:
            if is_sensitive and self._fernet and value_type == SettingType.ENCRYPTED:
                # Encrypt sensitive values
                serialized = self._fernet.encrypt(str(value).encode()).decode()
            else:
                serialized = self._serialize_value(value, value_type)
        except Exception as e:
            return Err(f"Failed to serialize value: {str(e)}")

        # Update database
        update_query = """
            UPDATE system_settings
            SET value = $1, updated_at = NOW(), updated_by = $2
            WHERE id = $3
        """

        try:
            await self._db.execute(update_query, serialized, updated_by, setting_id)

            # Log change
            await self._log_setting_change(
                setting_id,
                category,
                key,
                old_value,
                serialized,
                updated_by,
                row["requires_restart"],
            )

            # Invalidate cache
            cache_key = CacheKeys.system_setting(category, key)
            await self._cache.delete(cache_key)

            # Also invalidate category cache
            category_cache_key = CacheKeys.system_category_settings(category)
            await self._cache.delete(category_cache_key)

            return Ok(True)

        except Exception as e:
            return Err(f"Failed to update setting: {str(e)}")

    @beartype
    async def get_category_settings(
        self,
        category: str,
        include_sensitive: bool = False,
    ) -> Result[dict[str, Any], str]:
        """Get all settings in a category.

        Args:
            category: Setting category
            include_sensitive: Whether to include sensitive settings

        Returns:
            Result with dictionary of key-value pairs or error
        """
        # Check cache for non-sensitive settings
        if not include_sensitive:
            cache_key = CacheKeys.system_category_settings(category)
            cached = await self._cache.get(cache_key)

            if cached:
                return Ok(cached)

        # Query database
        query = """
            SELECT key, value, value_type, is_sensitive, is_public
            FROM system_settings
            WHERE category = $1 AND is_active = true
        """

        if not include_sensitive:
            query += " AND is_sensitive = false"

        query += " ORDER BY key"

        rows = await self._db.fetch(query, category)

        settings = {}
        for row in rows:
            try:
                value_type = SettingType(row["value_type"])

                if (
                    row["is_sensitive"]
                    and self._fernet
                    and value_type == SettingType.ENCRYPTED
                ):
                    decrypted = self._fernet.decrypt(row["value"].encode()).decode()
                    settings[row["key"]] = self._parse_value(
                        decrypted, SettingType.STRING
                    )
                else:
                    settings[row["key"]] = self._parse_value(row["value"], value_type)
            except Exception:
                # Skip settings that fail to parse
                continue

        # Cache non-sensitive results
        if not include_sensitive and settings:
            await self._cache.set(cache_key, settings, self._cache_ttl)

        return Ok(settings)

    @beartype
    async def get_public_settings(self) -> Result[dict[str, dict[str, Any]], str]:
        """Get all public settings (safe for client exposure).

        Returns:
            Result with nested dict of category -> settings
        """
        query = """
            SELECT category, key, value, value_type
            FROM system_settings
            WHERE is_public = true AND is_active = true
            ORDER BY category, key
        """

        rows = await self._db.fetch(query)

        settings: dict[str, dict[str, Any]] = {}

        for row in rows:
            category = row["category"]
            if category not in settings:
                settings[category] = {}

            try:
                value_type = SettingType(row["value_type"])
                settings[category][row["key"]] = self._parse_value(
                    row["value"], value_type
                )
            except Exception:
                continue

        return Ok(settings)

    @beartype
    def _parse_value(self, value: str, value_type: SettingType) -> Any:
        """Parse string value based on type."""
        if value_type == SettingType.STRING or value_type == SettingType.ENCRYPTED:
            return value
        elif value_type == SettingType.INTEGER:
            return int(value)
        elif value_type == SettingType.FLOAT:
            return float(value)
        elif value_type == SettingType.BOOLEAN:
            return value.lower() in ("true", "1", "yes", "on")
        elif value_type == SettingType.JSON:
            return json.loads(value)
        # This should never happen as all enum values are covered
        return value

    @beartype
    def _serialize_value(self, value: Any, value_type: SettingType) -> str:
        """Serialize value to string for storage."""
        if value_type == SettingType.JSON:
            return json.dumps(value)
        elif value_type == SettingType.BOOLEAN:
            return "true" if value else "false"
        else:
            return str(value)

    @beartype
    def _validate_value(
        self,
        value: Any,
        value_type: SettingType,
        rules: dict[str, Any],
    ) -> Result[bool, str]:
        """Validate value against type and rules."""
        # Type validation
        if value_type == SettingType.INTEGER:
            if not isinstance(value, int):
                return Err("Value must be an integer")

            if "min" in rules and value < rules["min"]:
                return Err(f"Value must be >= {rules['min']}")
            if "max" in rules and value > rules["max"]:
                return Err(f"Value must be <= {rules['max']}")

        elif value_type == SettingType.FLOAT:
            if not isinstance(value, (int, float)):
                return Err("Value must be a number")

            if "min" in rules and value < rules["min"]:
                return Err(f"Value must be >= {rules['min']}")
            if "max" in rules and value > rules["max"]:
                return Err(f"Value must be <= {rules['max']}")

        elif value_type == SettingType.BOOLEAN:
            if not isinstance(value, bool):
                return Err("Value must be a boolean")

        elif value_type == SettingType.STRING or value_type == SettingType.ENCRYPTED:
            if not isinstance(value, str):
                return Err("Value must be a string")

            if "min_length" in rules and len(value) < rules["min_length"]:
                return Err(f"Value must be at least {rules['min_length']} characters")
            if "max_length" in rules and len(value) > rules["max_length"]:
                return Err(f"Value must be at most {rules['max_length']} characters")
            if "pattern" in rules:
                import re

                if not re.match(rules["pattern"], value):
                    return Err(f"Value must match pattern: {rules['pattern']}")
            if "allowed_values" in rules and value not in rules["allowed_values"]:
                return Err(
                    f"Value must be one of: {', '.join(rules['allowed_values'])}"
                )

        return Ok(True)

    @beartype
    async def _log_setting_change(
        self,
        setting_id: UUID,
        category: str,
        key: str,
        old_value: str,
        new_value: str,
        updated_by: UUID,
        requires_restart: bool,
    ) -> None:
        """Log setting change for audit trail."""
        try:
            await self._db.execute(
                """
                INSERT INTO system_settings_history (
                    setting_id, category, key, old_value, new_value,
                    updated_by, requires_restart, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                setting_id,
                category,
                key,
                old_value,
                new_value,
                updated_by,
                requires_restart,
                datetime.utcnow(),
            )
        except Exception:
            # Don't fail the update if logging fails
            pass
