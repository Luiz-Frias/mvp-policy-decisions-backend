"""User auto-provisioning service for SSO integration."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from beartype import beartype
from pydantic import Field, ConfigDict

from pd_prime_demo.core.result_types import Err, Ok, Result

from ..core.auth.sso_base import SSOUserInfo
from ..core.cache import Cache
from ..core.database import Database
from ..models.base import BaseModelConfig
from ..models.user import UserBase, UserCreate, UserUpdate
from ..models.admin import AdminUser


class AdditionalAttributes(BaseModelConfig):
    """Structured additional attributes for provisioning."""
    
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    employee_id: str | None = None
    division: str | None = None
    location: str | None = None
    title: str | None = None
    phone: str | None = None
    country: str | None = None
    timezone: str | None = None
    language: str | None = None
    security_clearance: str | None = None
    contract_type: str | None = None


class ProvisioningCustomFields(BaseModelConfig):
    """Structured custom fields for provisioning conditions."""
    
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    department: str | None = None
    employee_type: str | None = None
    cost_center: str | None = None
    manager_email: str | None = None
    additional_attributes: AdditionalAttributes = Field(default_factory=AdditionalAttributes)


class ProvisioningConditions(BaseModelConfig):
    """Structured provisioning rule conditions."""
    
    email_domains: list[str] | None = None
    email_patterns: list[str] | None = None
    required_groups: list[str] | None = None
    excluded_groups: list[str] | None = None
    providers: list[str] | None = None
    email_verified: bool | None = None
    custom_fields: ProvisioningCustomFields | None = None


class ProvisioningActions(BaseModelConfig):
    """Structured provisioning rule actions."""
    
    role: str | None = None
    groups: list[str] | None = None
    auto_create: bool | None = None
    warnings: list[str] | None = None
    terminal: bool | None = None


class ProvisioningRuleUpdate(BaseModelConfig):
    """Model for updating provisioning rules."""
    
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    rule_name: str | None = None
    conditions: ProvisioningConditions | None = None
    actions: ProvisioningActions | None = None
    priority: int | None = None
    is_enabled: bool | None = None


class CustomAttributes(BaseModelConfig):
    """Structured custom attributes for SSO user info."""
    
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    preferred_username: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    middle_name: str | None = None
    nickname: str | None = None
    profile: str | None = None
    picture: str | None = None
    website: str | None = None
    gender: str | None = None
    birthdate: str | None = None
    zoneinfo: str | None = None
    locale: str | None = None
    updated_at: str | None = None
    address: str | None = None
    phone_number: str | None = None
    phone_number_verified: bool | None = None


class ProvisioningTestUserData(BaseModelConfig):
    """Model for test user data in provisioning rules."""
    
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    sub: str = "test-user-123"
    email: str = "test@example.com"
    email_verified: bool = True
    name: str = "Test User"
    groups: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    custom_attributes: CustomAttributes = Field(default_factory=CustomAttributes)


class ProvisioningTestResult(BaseModelConfig):
    """Result of provisioning rule test."""
    
    model_config = ConfigDict(frozen=True, extra="forbid")
    
    rule_name: str
    conditions_met: bool
    actions: ProvisioningActions
    test_data: ProvisioningTestUserData
    priority: int
    is_enabled: bool


class ProvisioningRule(BaseModelConfig):
    """User provisioning rule model."""

    id: UUID
    provider_id: UUID
    rule_name: str
    conditions: ProvisioningConditions
    actions: ProvisioningActions
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
    ) -> Result[ProvisioningResult, str]:
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

            rules = rules_result.unwrap()
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

                    if actions.role:
                        default_role = actions.role

                    if actions.groups:
                        assigned_groups.extend(actions.groups)

                    if actions.auto_create is not None:
                        auto_create = actions.auto_create

                    if actions.warnings:
                        warnings.extend(actions.warnings)

                    # Check if rule is terminal (stops further processing)
                    if actions.terminal:
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
        conditions: ProvisioningConditions,
        actions: ProvisioningActions,
        priority: int = 0,
        is_enabled: bool = True,
        created_by: UUID | None = None,
    ) -> Result[UUID, str]:
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
                conditions.model_dump(),
                actions.model_dump(),
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
        updates: ProvisioningRuleUpdate,
        updated_by: UUID | None = None,
    ) -> Result[bool, str]:
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
            if updates.conditions or updates.actions:
                new_conditions = updates.conditions or ProvisioningConditions(**existing["conditions"])
                new_actions = updates.actions or ProvisioningActions(**existing["actions"])

                validation_result = await self._validate_rule(
                    new_conditions, new_actions
                )
                if isinstance(validation_result, Err):
                    return validation_result

            # Build update query
            update_fields: list[str] = []
            update_values: list[str | int | bool | dict[str, Any] | UUID | datetime | None] = []

            # Map update fields from model using structured field mapping
            update_data = updates.model_dump(exclude_unset=True)
            
            for field, value in update_data.items():
                if field in ["rule_name", "conditions", "actions", "priority", "is_enabled"]:
                    update_fields.append(f"{field} = ${len(update_values) + 2}")
                    if field in ["conditions", "actions"] and value is not None:
                        update_values.append(value.model_dump() if hasattr(value, 'model_dump') else value)
                    else:
                        update_values.append(value)

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
    ) -> Result[bool, str]:
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
        test_user_data: ProvisioningTestUserData,
    ) -> Result[ProvisioningTestResult, str]:
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
                sub=test_user_data.sub,
                email=test_user_data.email,
                email_verified=test_user_data.email_verified,
                name=test_user_data.name,
                provider="test",
                provider_user_id="test-123",
                groups=test_user_data.groups,
                roles=test_user_data.roles,
                raw_claims=test_user_data.model_dump(),
            )

            # Evaluate conditions
            conditions = ProvisioningConditions(**rule_row["conditions"])
            conditions_met = await self._evaluate_conditions(
                conditions, test_sso_info, "test"
            )

            test_result = ProvisioningTestResult(
                rule_name=rule_row["rule_name"],
                conditions_met=conditions_met,
                actions=ProvisioningActions(**rule_row["actions"]) if conditions_met else ProvisioningActions(),
                test_data=test_user_data,
                priority=rule_row["priority"],
                is_enabled=rule_row["is_enabled"]
            )
            
            return Ok(test_result)

        except Exception as e:
            return Err(f"Failed to test provisioning rule: {str(e)}")

    @beartype
    async def _get_provisioning_rules(
        self,
        provider_id: UUID,
    ) -> Result[list[ProvisioningRule], str]:
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
                rules = []
                for rule_data in cached_rules:
                    rule = ProvisioningRule(
                        id=rule_data['id'],
                        provider_id=rule_data['provider_id'],
                        rule_name=rule_data['rule_name'],
                        conditions=ProvisioningConditions(**rule_data['conditions']),
                        actions=ProvisioningActions(**rule_data['actions']),
                        priority=rule_data['priority'],
                        is_enabled=rule_data['is_enabled']
                    )
                    rules.append(rule)
                return Ok(rules)

            # Fetch from database
            rules_data = await self._db.fetch(
                """
                SELECT id, provider_id, rule_name, conditions, actions, priority, is_enabled
                FROM user_provisioning_rules
                WHERE provider_id = $1 AND is_enabled = true
                ORDER BY priority DESC, created_at ASC
                """,
                provider_id,
            )

            rule_objects = []
            for rule_data in rules_data:
                rule = ProvisioningRule(
                    id=rule_data['id'],
                    provider_id=rule_data['provider_id'],
                    rule_name=rule_data['rule_name'],
                    conditions=ProvisioningConditions(**rule_data['conditions']),
                    actions=ProvisioningActions(**rule_data['actions']),
                    priority=rule_data['priority'],
                    is_enabled=rule_data['is_enabled']
                )
                rule_objects.append(rule)

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
        conditions: ProvisioningConditions,
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
            # Email domain conditions
            if conditions.email_domains:
                allowed_domains = conditions.email_domains
                user_domain = (
                    sso_info.email.split("@")[-1] if "@" in sso_info.email else ""
                )
                if user_domain not in allowed_domains:
                    return False

            # Email pattern conditions
            if conditions.email_patterns:
                import re
                patterns = conditions.email_patterns
                if not any(re.match(pattern, sso_info.email) for pattern in patterns):
                    return False

            # Group membership conditions
            if conditions.required_groups:
                required = set(conditions.required_groups)
                user_groups = set(sso_info.groups)
                if not required.issubset(user_groups):
                    return False

            # Group exclusion conditions
            if conditions.excluded_groups:
                excluded = set(conditions.excluded_groups)
                user_groups = set(sso_info.groups)
                if excluded.intersection(user_groups):
                    return False

            # Provider conditions
            if conditions.providers:
                allowed_providers = conditions.providers
                if provider_name not in allowed_providers:
                    return False

            # Email verification condition
            if conditions.email_verified is not None:
                if sso_info.email_verified != conditions.email_verified:
                    return False

            # Custom field conditions
            if conditions.custom_fields:
                custom_fields_data = conditions.custom_fields.model_dump(exclude_unset=True)
                for field, expected_value in custom_fields_data.items():
                    if field == "additional_attributes":
                        # Handle additional attributes structured model
                        if isinstance(expected_value, dict):
                            for attr_key, attr_value in expected_value.items():
                                if attr_value is not None:  # Only check non-None values
                                    actual_value = sso_info.raw_claims.get(attr_key)
                                    if actual_value != attr_value:
                                        return False
                    else:
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
        conditions: ProvisioningConditions,
        actions: ProvisioningActions,
    ) -> Result[bool, str]:
        """Validate rule conditions and actions.

        Args:
            conditions: Rule conditions
            actions: Rule actions

        Returns:
            Result indicating valid or error with details
        """
        # Validate role if specified
        if actions.role:
            valid_roles = ["agent", "underwriter", "admin", "system"]
            if actions.role not in valid_roles:
                return Err(
                    f"Invalid role: {actions.role}. Valid roles: {valid_roles}"
                )

        # Validate groups if specified (groups is already typed as list[str] | None)
        # Type checking ensures groups is a list when not None
        
        return Ok(True)
