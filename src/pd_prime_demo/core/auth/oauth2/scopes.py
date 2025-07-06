"""OAuth2 scope definitions and validation."""

from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from beartype import beartype


class ScopeCategory(str, Enum):
    """Scope categories."""

    USER = "user"
    QUOTE = "quote"
    POLICY = "policy"
    CLAIM = "claim"
    ADMIN = "admin"
    ANALYTICS = "analytics"


class Scope:
    """OAuth2 scope definition."""

    def __init__(
        self,
        name: str,
        description: str,
        category: ScopeCategory,
        includes: Optional[List[str]] = None,
        requires_user: bool = True,
    ) -> None:
        """Initialize scope.
        
        Args:
            name: Scope identifier
            description: Human-readable description
            category: Scope category
            includes: List of scopes this scope includes
            requires_user: Whether this scope requires user context
        """
        self.name = name
        self.description = description
        self.category = category
        self.includes = includes or []
        self.requires_user = requires_user


# Define all available scopes
SCOPES: Dict[str, Scope] = {
    # User scopes
    "user:read": Scope(
        "user:read",
        "Read user profile information",
        ScopeCategory.USER,
    ),
    "user:write": Scope(
        "user:write",
        "Update user profile information",
        ScopeCategory.USER,
        includes=["user:read"],
    ),
    
    # Quote scopes
    "quote:read": Scope(
        "quote:read",
        "Read quote information",
        ScopeCategory.QUOTE,
    ),
    "quote:write": Scope(
        "quote:write",
        "Create and update quotes",
        ScopeCategory.QUOTE,
        includes=["quote:read"],
    ),
    "quote:calculate": Scope(
        "quote:calculate",
        "Calculate quote pricing",
        ScopeCategory.QUOTE,
        includes=["quote:read"],
    ),
    "quote:convert": Scope(
        "quote:convert",
        "Convert quotes to policies",
        ScopeCategory.QUOTE,
        includes=["quote:read", "policy:write"],
    ),
    
    # Policy scopes
    "policy:read": Scope(
        "policy:read",
        "Read policy information",
        ScopeCategory.POLICY,
    ),
    "policy:write": Scope(
        "policy:write",
        "Create and update policies",
        ScopeCategory.POLICY,
        includes=["policy:read"],
    ),
    "policy:cancel": Scope(
        "policy:cancel",
        "Cancel policies",
        ScopeCategory.POLICY,
        includes=["policy:read", "policy:write"],
    ),
    
    # Claim scopes
    "claim:read": Scope(
        "claim:read",
        "Read claim information",
        ScopeCategory.CLAIM,
    ),
    "claim:write": Scope(
        "claim:write",
        "Create and update claims",
        ScopeCategory.CLAIM,
        includes=["claim:read"],
    ),
    "claim:approve": Scope(
        "claim:approve",
        "Approve or deny claims",
        ScopeCategory.CLAIM,
        includes=["claim:read", "claim:write"],
    ),
    
    # Analytics scopes
    "analytics:read": Scope(
        "analytics:read",
        "Read analytics data",
        ScopeCategory.ANALYTICS,
        requires_user=False,
    ),
    "analytics:export": Scope(
        "analytics:export",
        "Export analytics data",
        ScopeCategory.ANALYTICS,
        includes=["analytics:read"],
        requires_user=False,
    ),
    
    # Admin scopes
    "admin:users": Scope(
        "admin:users",
        "Manage users",
        ScopeCategory.ADMIN,
    ),
    "admin:clients": Scope(
        "admin:clients",
        "Manage OAuth2 clients",
        ScopeCategory.ADMIN,
    ),
    "admin:system": Scope(
        "admin:system",
        "System administration",
        ScopeCategory.ADMIN,
        includes=["admin:users", "admin:clients"],
    ),
}


class ScopeValidator:
    """Validate and expand OAuth2 scopes."""

    @staticmethod
    @beartype
    def validate_scopes(
        requested_scopes: List[str],
        allowed_scopes: Optional[List[str]] = None,
    ) -> Tuple[bool, List[str], Optional[str]]:
        """Validate requested scopes.
        
        Args:
            requested_scopes: List of requested scope names
            allowed_scopes: List of scopes allowed for the client (optional)
            
        Returns:
            Tuple of (is_valid, expanded_scopes, error_message)
        """
        # Check if all requested scopes exist
        invalid_scopes = [s for s in requested_scopes if s not in SCOPES]
        if invalid_scopes:
            return False, [], f"Invalid scopes: {', '.join(invalid_scopes)}"
        
        # Check if scopes are allowed for client
        if allowed_scopes is not None:
            disallowed = set(requested_scopes) - set(allowed_scopes)
            if disallowed:
                return False, [], f"Scopes not allowed: {', '.join(disallowed)}"
        
        # Expand scopes to include dependencies
        expanded_scopes = ScopeValidator.expand_scopes(requested_scopes)
        
        return True, list(expanded_scopes), None

    @staticmethod
    @beartype
    def expand_scopes(scopes: List[str]) -> Set[str]:
        """Expand scopes to include all dependencies.
        
        Args:
            scopes: List of scope names
            
        Returns:
            Set of expanded scope names including all dependencies
        """
        expanded = set()
        
        def add_scope_with_includes(scope_name: str) -> None:
            if scope_name in expanded:
                return
            
            expanded.add(scope_name)
            
            scope = SCOPES.get(scope_name)
            if scope and scope.includes:
                for included in scope.includes:
                    add_scope_with_includes(included)
        
        for scope in scopes:
            add_scope_with_includes(scope)
        
        return expanded

    @staticmethod
    @beartype
    def check_scope_permission(
        token_scopes: List[str],
        required_scope: str,
    ) -> bool:
        """Check if token has required scope.
        
        Args:
            token_scopes: List of scopes in the token
            required_scope: Required scope to check
            
        Returns:
            True if token has the required scope (directly or through inclusion)
        """
        expanded = ScopeValidator.expand_scopes(token_scopes)
        return required_scope in expanded

    @staticmethod
    @beartype
    def get_scope_categories(scopes: List[str]) -> Set[ScopeCategory]:
        """Get categories for a list of scopes.
        
        Args:
            scopes: List of scope names
            
        Returns:
            Set of scope categories
        """
        categories = set()
        for scope_name in scopes:
            scope = SCOPES.get(scope_name)
            if scope:
                categories.add(scope.category)
        return categories

    @staticmethod
    @beartype
    def filter_scopes_by_category(
        scopes: List[str],
        category: ScopeCategory,
    ) -> List[str]:
        """Filter scopes by category.
        
        Args:
            scopes: List of scope names
            category: Category to filter by
            
        Returns:
            List of scopes in the specified category
        """
        return [
            s for s in scopes 
            if SCOPES.get(s) and SCOPES[s].category == category
        ]

    @staticmethod
    @beartype
    def validate_scope_compatibility(
        scopes: List[str],
    ) -> Tuple[bool, Optional[str]]:
        """Check if a set of scopes are compatible with each other.
        
        Some scopes might have mutual exclusions or requirements.
        
        Args:
            scopes: List of scope names
            
        Returns:
            Tuple of (is_compatible, error_message)
        """
        # Currently all scopes are compatible
        # This method is here for future scope compatibility rules
        return True, None

    @staticmethod
    @beartype
    def get_required_scopes_for_operation(
        operation: str,
    ) -> List[str]:
        """Get required scopes for a specific operation.
        
        This is used to map API operations to required scopes.
        
        Args:
            operation: Operation identifier (e.g., "create_quote", "read_policy")
            
        Returns:
            List of required scope names
        """
        # Map operations to required scopes
        operation_scopes = {
            # Quote operations
            "create_quote": ["quote:write"],
            "read_quote": ["quote:read"],
            "calculate_quote": ["quote:calculate"],
            "convert_quote_to_policy": ["quote:convert"],
            
            # Policy operations
            "create_policy": ["policy:write"],
            "read_policy": ["policy:read"],
            "update_policy": ["policy:write"],
            "cancel_policy": ["policy:cancel"],
            
            # Claim operations
            "create_claim": ["claim:write"],
            "read_claim": ["claim:read"],
            "update_claim": ["claim:write"],
            "approve_claim": ["claim:approve"],
            
            # User operations
            "read_profile": ["user:read"],
            "update_profile": ["user:write"],
            
            # Analytics operations
            "view_analytics": ["analytics:read"],
            "export_analytics": ["analytics:export"],
            
            # Admin operations
            "manage_users": ["admin:users"],
            "manage_clients": ["admin:clients"],
            "system_admin": ["admin:system"],
        }
        
        return operation_scopes.get(operation, [])