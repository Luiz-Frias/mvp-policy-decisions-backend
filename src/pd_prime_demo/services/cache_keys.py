"""Centralized cache key management for consistency and type safety.

This module provides a single source of truth for cache key patterns
across all services, ensuring consistency and preventing key collisions.
"""

from uuid import UUID

from beartype import beartype
from pydantic import EmailStr


class CacheKeys:
    """Centralized cache key management."""

    # Cache key prefixes
    CUSTOMER_PREFIX = "customer"
    POLICY_PREFIX = "policy"
    CLAIM_PREFIX = "claim"
    QUOTE_PREFIX = "quote"
    RATE_PREFIX = "rate"
    ADMIN_PREFIX = "admin"
    SETTINGS_PREFIX = "settings"

    # Customer cache keys
    @staticmethod
    @beartype
    def customer_by_id(customer_id: UUID) -> str:
        """Cache key for customer by ID."""
        return f"{CacheKeys.CUSTOMER_PREFIX}:id:{customer_id}"

    @staticmethod
    @beartype
    def customer_by_email(email: str | EmailStr) -> str:
        """Cache key for customer by email."""
        return f"{CacheKeys.CUSTOMER_PREFIX}:email:{str(email).lower()}"

    @staticmethod
    @beartype
    def customer_by_number(customer_number: str) -> str:
        """Cache key for customer by customer number."""
        return f"{CacheKeys.CUSTOMER_PREFIX}:number:{customer_number}"

    @staticmethod
    @beartype
    def customer_policies(customer_id: UUID) -> str:
        """Cache key for customer's policies list."""
        return f"{CacheKeys.CUSTOMER_PREFIX}:{customer_id}:policies"

    @staticmethod
    @beartype
    def customer_claims(customer_id: UUID) -> str:
        """Cache key for customer's claims list."""
        return f"{CacheKeys.CUSTOMER_PREFIX}:{customer_id}:claims"

    # Policy cache keys
    @staticmethod
    @beartype
    def policy_by_id(policy_id: UUID) -> str:
        """Cache key for policy by ID."""
        return f"{CacheKeys.POLICY_PREFIX}:id:{policy_id}"

    @staticmethod
    @beartype
    def policy_by_number(policy_number: str) -> str:
        """Cache key for policy by policy number."""
        return f"{CacheKeys.POLICY_PREFIX}:number:{policy_number}"

    @staticmethod
    @beartype
    def policies_by_customer(customer_id: UUID) -> str:
        """Cache key for policies by customer."""
        return f"{CacheKeys.POLICY_PREFIX}:customer:{customer_id}"

    @staticmethod
    @beartype
    def policy_claims(policy_id: UUID) -> str:
        """Cache key for policy's claims list."""
        return f"{CacheKeys.POLICY_PREFIX}:{policy_id}:claims"

    # Claim cache keys
    @staticmethod
    @beartype
    def claim_by_id(claim_id: UUID) -> str:
        """Cache key for claim by ID."""
        return f"{CacheKeys.CLAIM_PREFIX}:id:{claim_id}"

    @staticmethod
    @beartype
    def claim_by_number(claim_number: str) -> str:
        """Cache key for claim by claim number."""
        return f"{CacheKeys.CLAIM_PREFIX}:number:{claim_number}"

    @staticmethod
    @beartype
    def claims_by_policy(policy_id: UUID) -> str:
        """Cache key for claims by policy."""
        return f"{CacheKeys.CLAIM_PREFIX}:policy:{policy_id}"

    @staticmethod
    @beartype
    def claims_by_customer(customer_id: UUID) -> str:
        """Cache key for claims by customer."""
        return f"{CacheKeys.CLAIM_PREFIX}:customer:{customer_id}"

    @staticmethod
    @beartype
    def claim_status_history(claim_id: UUID) -> str:
        """Cache key for claim status history."""
        return f"{CacheKeys.CLAIM_PREFIX}:{claim_id}:status_history"

    # Quote cache keys
    @staticmethod
    @beartype
    def quote_by_id(quote_id: UUID) -> str:
        """Cache key for quote by ID."""
        return f"{CacheKeys.QUOTE_PREFIX}:id:{quote_id}"

    @staticmethod
    @beartype
    def quote_by_number(quote_number: str) -> str:
        """Cache key for quote by quote number."""
        return f"{CacheKeys.QUOTE_PREFIX}:number:{quote_number}"

    @staticmethod
    @beartype
    def quotes_by_customer(customer_id: UUID) -> str:
        """Cache key for quotes by customer."""
        return f"{CacheKeys.QUOTE_PREFIX}:customer:{customer_id}"

    @staticmethod
    @beartype
    def quote_calculation(quote_id: UUID) -> str:
        """Cache key for quote calculation results."""
        return f"{CacheKeys.QUOTE_PREFIX}:{quote_id}:calculation"

    # Rating cache keys
    @staticmethod
    @beartype
    def rate_table(state: str, product: str, version: str) -> str:
        """Cache key for rate table."""
        return f"{CacheKeys.RATE_PREFIX}:table:{state}:{product}:{version}"

    @staticmethod
    @beartype
    def rate_factor(factor_type: str, value: str) -> str:
        """Cache key for rating factor."""
        return f"{CacheKeys.RATE_PREFIX}:factor:{factor_type}:{value}"

    @staticmethod
    @beartype
    def discount_rules(state: str, product: str) -> str:
        """Cache key for discount rules."""
        return f"{CacheKeys.RATE_PREFIX}:discount:{state}:{product}"

    # Admin cache keys
    @staticmethod
    @beartype
    def admin_user_by_id(admin_id: UUID) -> str:
        """Cache key for admin user by ID."""
        return f"{CacheKeys.ADMIN_PREFIX}:user:id:{admin_id}"

    @staticmethod
    @beartype
    def admin_user_by_email(email: str | EmailStr) -> str:
        """Cache key for admin user by email."""
        return f"{CacheKeys.ADMIN_PREFIX}:user:email:{str(email).lower()}"

    @staticmethod
    @beartype
    def admin_permissions(admin_id: UUID) -> str:
        """Cache key for admin permissions."""
        return f"{CacheKeys.ADMIN_PREFIX}:{admin_id}:permissions"

    @staticmethod
    @beartype
    def admin_role(role_id: UUID) -> str:
        """Cache key for admin role definition."""
        return f"{CacheKeys.ADMIN_PREFIX}:role:{role_id}"

    # System settings cache keys
    @staticmethod
    @beartype
    def system_setting(category: str, key: str) -> str:
        """Cache key for system setting."""
        return f"{CacheKeys.SETTINGS_PREFIX}:{category}:{key}"

    @staticmethod
    @beartype
    def system_category_settings(category: str) -> str:
        """Cache key for all settings in a category."""
        return f"{CacheKeys.SETTINGS_PREFIX}:{category}:all"

    # List/search result cache keys with filters
    @staticmethod
    @beartype
    def list_cache_key(
        entity_type: str,
        skip: int,
        limit: int,
        filter_hash: int,
    ) -> str:
        """Generic list cache key with pagination and filters."""
        return f"{entity_type}:list:{skip}:{limit}:{filter_hash}"

    # Pattern helpers for bulk operations
    @staticmethod
    @beartype
    def customer_pattern() -> str:
        """Pattern to match all customer cache keys."""
        return f"{CacheKeys.CUSTOMER_PREFIX}:*"

    @staticmethod
    @beartype
    def policy_pattern() -> str:
        """Pattern to match all policy cache keys."""
        return f"{CacheKeys.POLICY_PREFIX}:*"

    @staticmethod
    @beartype
    def claim_pattern() -> str:
        """Pattern to match all claim cache keys."""
        return f"{CacheKeys.CLAIM_PREFIX}:*"

    @staticmethod
    @beartype
    def list_pattern(entity_type: str) -> str:
        """Pattern to match all list cache keys for an entity type."""
        return f"{entity_type}:list:*"
