"""User auto-provisioning service for SSO integration."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from beartype import beartype

from ..core.auth.sso_base import SSOUserInfo
from ..core.cache import Cache
from ..core.database import Database
from ..models.base import BaseModelConfig
from ..services.result import Err, Ok


class ProvisioningRule(BaseModelConfig):
    """User provisioning rule model."""

    id: UUID
    provider_id: UUID
    rule_name: str
    conditions: dict[str, Any]
    actions: dict[str, Any]
    priority: int
    is_enabled: bool


class ProvisioningResult(BaseModelConfig):
    """Result of user provisioning operation."""

    user_id: UUID
    action_taken: str  # created, updated, linked
    applied_rules: list[str]
    groups_assigned: list[str]
    role_assigned: str
    warnings: list[str]


class UserProvisioningService:
    """Service for automatic user provisioning via SSO."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize user provisioning service.

        Args:
            db: Database instance
            cache: Cache instance
        """
        self._db = db
        self._cache = cache
        self._rules_cache_prefix = "provisioning_rules:"

    @beartype
    async def evaluate_provisioning(
        self,
        sso_info: SSOUserInfo,
        provider_name: str,
        provider_id: UUID,
    ):
        """Evaluate provisioning rules for a user.

        Args:
            sso_info: SSO user information
            provider_name: Name of the SSO provider
            provider_id: UUID of the SSO provider

        Returns:
            Result containing provisioning decision or error
        """
        try:
            # Get applicable rules for this provider
            rules_result = await self._get_provisioning_rules(provider_id)
            if isinstance(rules_result, Err):
                return rules_result

            rules = rules_result.value
            applied_rules = []
            warnings = []

            # Default values
            default_role = "agent"
            assigned_groups = []
            auto_create = True

            # Process rules in priority order
            for rule in sorted(rules, key=lambda r: r.priority, reverse=True):
                if not rule.is_enabled:
                    continue

                # Evaluate rule conditions
                if await self._evaluate_conditions(
                    rule.conditions, sso_info, provider_name
                ):
                    applied_rules.append(rule.rule_name)

                    # Apply rule actions
                    actions = rule.actions

                    if "role" in actions:
                        default_role = actions["role"]

                    if "groups" in actions:
                        assigned_groups.extend(actions["groups"])

                    if "auto_create" in actions:
                        auto_create = actions["auto_create"]

                    if "warnings" in actions:
                        warnings.extend(actions["warnings"])

                    # Check if rule is terminal (stops further processing)
                    if actions.get("terminal", False):
                        break

            # Check auto-create permission
            if not auto_create:
                return Err(
                    f"User auto-creation denied by provisioning rules. "
                    f"Applied rules: {', '.join(applied_rules)}. "
                    f"User email: {sso_info.email}. "
                    f"Required action: Manually create user account or update provisioning rules."
                )

            # Validate role assignment
            valid_roles = ["agent", "underwriter", "admin", "system"]
            if default_role not in valid_roles:
                warnings.append(f"Invalid role '{default_role}', using 'agent' instead")
                default_role = "agent"

            # Remove duplicate groups
            assigned_groups = list(set(assigned_groups + sso_info.groups))

            return Ok(
                ProvisioningResult(
                    user_id=uuid4(),  # Placeholder, will be set by caller
                    action_taken="evaluate",
                    applied_rules=applied_rules,
                    groups_assigned=assigned_groups,
                    role_assigned=default_role,
                    warnings=warnings,
                )
            )

        except Exception as e:
            return Err(f"Provisioning evaluation failed: {str(e)}")

    @beartype
    async def create_provisioning_rule(
        self,
        provider_id: UUID,
        rule_name: str,
        conditions: dict[str, Any],
        actions: dict[str, Any],
        priority: int = 0,
        is_enabled: bool = True,
        created_by: UUID | None = None,
    ):
        """Create a new user provisioning rule.

        Args:
            provider_id: Provider ID
            rule_name: Name of the rule
            conditions: Rule conditions
            actions: Actions to perform
            priority: Rule priority (higher = first)
            is_enabled: Whether rule is enabled
            created_by: Admin user creating the rule

        Returns:
            Result containing rule ID or error
        """
        try:
            # Validate conditions and actions
            validation_result = await self._validate_rule(conditions, actions)
            if isinstance(validation_result, Err):
                return validation_result

            # Check if rule name already exists for this provider
            existing = await self._db.fetchval(
                """
                SELECT id FROM user_provisioning_rules
                WHERE provider_id = $1 AND rule_name = $2
                """,
                provider_id,
                rule_name,
            )

            if existing:
                return Err(
                    f"Provisioning rule '{rule_name}' already exists for this provider. "
                    f"Required action: Choose a different rule name or update existing rule."
                )

            rule_id = uuid4()

            await self._db.execute(
                """
                INSERT INTO user_provisioning_rules
                (id, provider_id, rule_name, conditions, actions, priority, is_enabled, created_by)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                rule_id,
                provider_id,
                rule_name,
                conditions,
                actions,
                priority,
                is_enabled,
                created_by,
            )

            # Clear rules cache
            await self._cache.delete(f"{self._rules_cache_prefix}{provider_id}")

            return Ok(rule_id)

        except Exception as e:
            return Err(f"Failed to create provisioning rule: {str(e)}")

    @beartype
    async def update_provisioning_rule(
        self,
        rule_id: UUID,
        updates: dict[str, Any],
        updated_by: UUID | None = None,
    ):
        """Update an existing provisioning rule.

        Args:
            rule_id: Rule ID to update
            updates: Dictionary of updates
            updated_by: Admin user making the update

        Returns:
            Result indicating success or error
        """
        try:
            # Get existing rule
            existing = await self._db.fetchrow(
                "SELECT * FROM user_provisioning_rules WHERE id = $1", rule_id
            )

            if not existing:
                return Err("Provisioning rule not found")

            # Validate updates if conditions or actions are being changed
            if "conditions" in updates or "actions" in updates:
                new_conditions = updates.get("conditions", existing["conditions"])
                new_actions = updates.get("actions", existing["actions"])

                validation_result = await self._validate_rule(
                    new_conditions, new_actions
                )
                if isinstance(validation_result, Err):
                    return validation_result

            # Build update query
            update_fields = []
            update_values = []

            for field in [
                "rule_name",
                "conditions",
                "actions",
                "priority",
                "is_enabled",
            ]:
                if field in updates:
                    update_fields.append(f"{field} = ${len(update_values) + 2}")
                    update_values.append(updates[field])

            if not update_fields:
                return Err("No valid fields to update")

            update_values.append(updated_by)
            update_fields.append(f"updated_by = ${len(update_values) + 1}")

            update_values.append(datetime.utcnow())
            update_fields.append(f"updated_at = ${len(update_values) + 1}")

            # Safe query construction - update_fields are built from trusted column names
            query = (
                """
                UPDATE user_provisioning_rules
                SET """
                + ", ".join(update_fields)
                + """
                WHERE id = $1
            """
            )

            await self._db.execute(query, rule_id, *update_values)

            # Clear rules cache
            await self._cache.delete(
                f"{self._rules_cache_prefix}{existing['provider_id']}"
            )

            return Ok(True)

        except Exception as e:
            return Err(f"Failed to update provisioning rule: {str(e)}")

    @beartype
    async def delete_provisioning_rule(
        self,
        rule_id: UUID,
        deleted_by: UUID | None = None,
    ):
        """Delete a provisioning rule.

        Args:
            rule_id: Rule ID to delete
            deleted_by: Admin user performing deletion

        Returns:
            Result indicating success or error
        """
        try:
            # Get rule to find provider_id for cache clearing
            rule = await self._db.fetchrow(
                "SELECT provider_id FROM user_provisioning_rules WHERE id = $1", rule_id
            )

            if not rule:
                return Err("Provisioning rule not found")

            # Delete rule
            deleted_count = await self._db.fetchval(
                "DELETE FROM user_provisioning_rules WHERE id = $1 RETURNING 1", rule_id
            )

            if not deleted_count:
                return Err("Rule not found or already deleted")

            # Clear rules cache
            await self._cache.delete(f"{self._rules_cache_prefix}{rule['provider_id']}")

            return Ok(True)

        except Exception as e:
            return Err(f"Failed to delete provisioning rule: {str(e)}")

    @beartype
    async def test_provisioning_rule(
        self,
        rule_id: UUID,
        test_user_data: dict[str, Any],
    ) -> dict:
        """Test a provisioning rule against sample user data.

        Args:
            rule_id: Rule ID to test
            test_user_data: Sample user data for testing

        Returns:
            Result containing test results or error
        """
        try:
            # Get rule
            rule_row = await self._db.fetchrow(
                "SELECT * FROM user_provisioning_rules WHERE id = $1", rule_id
            )

            if not rule_row:
                return Err("Provisioning rule not found")

            # Create test SSO user info
            test_sso_info = SSOUserInfo(
                sub=test_user_data.get("sub", "test-user-123"),
                email=test_user_data.get("email", "test@example.com"),
                email_verified=test_user_data.get("email_verified", True),
                name=test_user_data.get("name", "Test User"),
                provider="test",
                provider_user_id="test-123",
                groups=test_user_data.get("groups", []),
                roles=test_user_data.get("roles", []),
                raw_claims=test_user_data,
            )

            # Evaluate conditions
            conditions_met = await self._evaluate_conditions(
                rule_row["conditions"], test_sso_info, "test"
            )

            return Ok(
                {
                    "rule_name": rule_row["rule_name"],
                    "conditions_met": conditions_met,
                    "actions": rule_row["actions"] if conditions_met else {},
                    "test_data": test_user_data,
                    "priority": rule_row["priority"],
                    "is_enabled": rule_row["is_enabled"],
                }
            )

        except Exception as e:
            return Err(f"Failed to test provisioning rule: {str(e)}")

    @beartype
    async def _get_provisioning_rules(
        self,
        provider_id: UUID,
    ) -> dict:
        """Get provisioning rules for a provider.

        Args:
            provider_id: Provider ID

        Returns:
            Result containing list of rules or error
        """
        try:
            # Check cache first
            cache_key = f"{self._rules_cache_prefix}{provider_id}"
            cached_rules = await self._cache.get(cache_key)

            if cached_rules:
                return Ok([ProvisioningRule(**rule) for rule in cached_rules])

            # Fetch from database
            rules = await self._db.fetch(
                """
                SELECT id, provider_id, rule_name, conditions, actions, priority, is_enabled
                FROM user_provisioning_rules
                WHERE provider_id = $1 AND is_enabled = true
                ORDER BY priority DESC, created_at ASC
                """,
                provider_id,
            )

            rule_objects = [ProvisioningRule(**dict(rule)) for rule in rules]

            # Cache for 5 minutes
            await self._cache.set(
                cache_key, [rule.model_dump() for rule in rule_objects], ttl=300
            )

            return Ok(rule_objects)

        except Exception as e:
            return Err(f"Failed to get provisioning rules: {str(e)}")

    @beartype
    async def _evaluate_conditions(
        self,
        conditions: dict[str, Any],
        sso_info: SSOUserInfo,
        provider_name: str,
    ) -> bool:
        """Evaluate rule conditions against user data.

        Args:
            conditions: Rule conditions
            sso_info: SSO user information
            provider_name: Provider name

        Returns:
            True if conditions are met, False otherwise
        """
        try:
            # If no conditions, rule always applies
            if not conditions:
                return True

            # Email domain conditions
            if "email_domains" in conditions:
                allowed_domains = conditions["email_domains"]
                if isinstance(allowed_domains, str):
                    allowed_domains = [allowed_domains]

                user_domain = (
                    sso_info.email.split("@")[-1] if "@" in sso_info.email else ""
                )
                if user_domain not in allowed_domains:
                    return False

            # Email pattern conditions
            if "email_patterns" in conditions:
                import re

                patterns = conditions["email_patterns"]
                if isinstance(patterns, str):
                    patterns = [patterns]

                if not any(re.match(pattern, sso_info.email) for pattern in patterns):
                    return False

            # Group membership conditions
            if "required_groups" in conditions:
                required = set(conditions["required_groups"])
                user_groups = set(sso_info.groups)
                if not required.issubset(user_groups):
                    return False

            # Group exclusion conditions
            if "excluded_groups" in conditions:
                excluded = set(conditions["excluded_groups"])
                user_groups = set(sso_info.groups)
                if excluded.intersection(user_groups):
                    return False

            # Provider conditions
            if "providers" in conditions:
                allowed_providers = conditions["providers"]
                if isinstance(allowed_providers, str):
                    allowed_providers = [allowed_providers]

                if provider_name not in allowed_providers:
                    return False

            # Email verification condition
            if "email_verified" in conditions:
                required_verified = conditions["email_verified"]
                if sso_info.email_verified != required_verified:
                    return False

            # Custom field conditions
            if "custom_fields" in conditions:
                custom_conditions = conditions["custom_fields"]
                for field, expected_value in custom_conditions.items():
                    actual_value = sso_info.raw_claims.get(field)
                    if actual_value != expected_value:
                        return False

            return True

        except Exception:
            # If condition evaluation fails, err on the side of caution
            return False

    @beartype
    async def _validate_rule(
        self,
        conditions: dict[str, Any],
        actions: dict[str, Any],
    ):
        """Validate rule conditions and actions.

        Args:
            conditions: Rule conditions
            actions: Rule actions

        Returns:
            Result indicating valid or error with details
        """
        # Validate conditions structure
        valid_condition_keys = {
            "email_domains",
            "email_patterns",
            "required_groups",
            "excluded_groups",
            "providers",
            "email_verified",
            "custom_fields",
        }

        for key in conditions.keys():
            if key not in valid_condition_keys:
                return Err(f"Invalid condition key: {key}")

        # Validate actions structure
        valid_action_keys = {"role", "groups", "auto_create", "warnings", "terminal"}

        for key in actions.keys():
            if key not in valid_action_keys:
                return Err(f"Invalid action key: {key}")

        # Validate role if specified
        if "role" in actions:
            valid_roles = ["agent", "underwriter", "admin", "system"]
            if actions["role"] not in valid_roles:
                return Err(
                    f"Invalid role: {actions['role']}. Valid roles: {valid_roles}"
                )

        # Validate groups if specified
        if "groups" in actions:
            if not isinstance(actions["groups"], list):
                return Err("Groups must be a list")

        return Ok(True)
