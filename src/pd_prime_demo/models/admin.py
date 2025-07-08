"""Admin system models with comprehensive security and audit features."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List

from beartype import beartype
from pydantic import EmailStr, Field, computed_field, field_validator, model_validator
from pydantic.types import UUID4

from .base import BaseModelConfig, IdentifiableModel


class AdminRole(str, Enum):
    """Admin role types with hierarchical permissions."""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    SUPPORT = "support"
    VIEWER = "viewer"


class Permission(str, Enum):
    """System permissions following principle of least privilege."""

    # User management
    USER_READ = "user:read"
    USER_WRITE = "user:write"
    USER_DELETE = "user:delete"
    USER_SUSPEND = "user:suspend"
    USER_RESTORE = "user:restore"

    # Quote management
    QUOTE_READ = "quote:read"
    QUOTE_WRITE = "quote:write"
    QUOTE_APPROVE = "quote:approve"
    QUOTE_OVERRIDE = "quote:override"
    QUOTE_DELETE = "quote:delete"

    # Policy management
    POLICY_READ = "policy:read"
    POLICY_WRITE = "policy:write"
    POLICY_CANCEL = "policy:cancel"
    POLICY_REINSTATE = "policy:reinstate"
    POLICY_OVERRIDE = "policy:override"

    # Claim management
    CLAIM_READ = "claim:read"
    CLAIM_WRITE = "claim:write"
    CLAIM_APPROVE = "claim:approve"
    CLAIM_DENY = "claim:deny"
    CLAIM_INVESTIGATE = "claim:investigate"

    # Rate management
    RATE_READ = "rate:read"
    RATE_WRITE = "rate:write"
    RATE_APPROVE = "rate:approve"
    RATE_PUBLISH = "rate:publish"

    # System settings
    SETTINGS_READ = "settings:read"
    SETTINGS_WRITE = "settings:write"
    SETTINGS_SECURITY = "settings:security"

    # Admin management
    ADMIN_READ = "admin:read"
    ADMIN_WRITE = "admin:write"
    ADMIN_DELETE = "admin:delete"
    ADMIN_PERMISSION = "admin:permission"

    # Analytics
    ANALYTICS_READ = "analytics:read"
    ANALYTICS_EXPORT = "analytics:export"
    ANALYTICS_FULL = "analytics:full"

    # Audit logs
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    AUDIT_DELETE = "audit:delete"

    # Compliance
    COMPLIANCE_READ = "compliance:read"
    COMPLIANCE_WRITE = "compliance:write"
    COMPLIANCE_APPROVE = "compliance:approve"


# Default permissions per role
DEFAULT_ROLE_PERMISSIONS = {
    AdminRole.SUPER_ADMIN: list(Permission),  # All permissions
    AdminRole.ADMIN: [
        Permission.USER_READ,
        Permission.USER_WRITE,
        Permission.QUOTE_READ,
        Permission.QUOTE_WRITE,
        Permission.QUOTE_APPROVE,
        Permission.POLICY_READ,
        Permission.POLICY_WRITE,
        Permission.CLAIM_READ,
        Permission.CLAIM_WRITE,
        Permission.RATE_READ,
        Permission.SETTINGS_READ,
        Permission.ADMIN_READ,
        Permission.ANALYTICS_READ,
        Permission.ANALYTICS_EXPORT,
        Permission.AUDIT_READ,
        Permission.COMPLIANCE_READ,
    ],
    AdminRole.MANAGER: [
        Permission.USER_READ,
        Permission.QUOTE_READ,
        Permission.QUOTE_WRITE,
        Permission.POLICY_READ,
        Permission.CLAIM_READ,
        Permission.ANALYTICS_READ,
        Permission.AUDIT_READ,
    ],
    AdminRole.SUPPORT: [
        Permission.USER_READ,
        Permission.QUOTE_READ,
        Permission.POLICY_READ,
        Permission.CLAIM_READ,
        Permission.ANALYTICS_READ,
    ],
    AdminRole.VIEWER: [
        Permission.USER_READ,
        Permission.QUOTE_READ,
        Permission.POLICY_READ,
        Permission.CLAIM_READ,
        Permission.ANALYTICS_READ,
    ],
}


@beartype
class AdminRoleModel(IdentifiableModel):
    """Admin role with permissions and inheritance."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_\-]+$",
        description="Role name (alphanumeric, underscore, hyphen only)",
    )
    description: str | None = Field(
        None, max_length=200, description="Human-readable role description"
    )
    permissions: list[Permission] = Field(
        default_factory=list, description="List of granted permissions"
    )
    parent_role_id: UUID4 | None = Field(
        None, description="Parent role for permission inheritance"
    )

    # Role settings
    is_system_role: bool = Field(
        default=False, description="True for built-in roles that cannot be deleted"
    )
    max_session_duration: int = Field(
        default=28800,  # 8 hours
        ge=900,  # 15 minutes
        le=86400,  # 24 hours
        description="Maximum session duration in seconds",
    )
    require_mfa: bool = Field(
        default=False, description="Whether this role requires MFA"
    )

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: list[Permission]) -> list[Permission]:
        """Ensure unique permissions and validate combinations."""
        # Remove duplicates while preserving order
        unique_perms = []
        seen = set()
        for perm in v:
            if perm not in seen:
                seen.add(perm)
                unique_perms.append(perm)

        # Validate permission combinations
        # If you can delete, you should be able to write
        if (
            Permission.USER_DELETE in unique_perms
            and Permission.USER_WRITE not in unique_perms
        ):
            unique_perms.append(Permission.USER_WRITE)
        if (
            Permission.USER_WRITE in unique_perms
            and Permission.USER_READ not in unique_perms
        ):
            unique_perms.append(Permission.USER_READ)

        return unique_perms

    @computed_field  # type: ignore[misc]
    @property
    def permission_count(self) -> int:
        """Count of permissions for this role."""
        return len(self.permissions)


@beartype
class AdminUserBase(BaseModelConfig):
    """Base admin user model with essential fields."""

    email: EmailStr = Field(..., description="Admin user email address")
    role_id: UUID4 = Field(..., description="Assigned role ID")
    is_super_admin: bool = Field(
        default=False, description="Super admin override - grants all permissions"
    )
    two_factor_enabled: bool = Field(
        default=False, description="Whether 2FA is enabled for this user"
    )

    # Profile
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z\s\-'\.]+$",
        description="Full name of admin user",
    )
    phone: str | None = Field(
        None, pattern=r"^\+?1?\d{10,14}$", description="Contact phone number"
    )
    department: str | None = Field(
        None,
        max_length=50,
        pattern=r"^[a-zA-Z\s\-]+$",
        description="Department or team name",
    )

    # Work schedule
    timezone: str = Field(
        default="UTC",
        pattern=r"^[A-Za-z]+/[A-Za-z_]+$",
        description="User timezone (e.g., America/New_York)",
    )
    work_hours_start: int | None = Field(
        None, ge=0, le=23, description="Work hours start (0-23)"
    )
    work_hours_end: int | None = Field(
        None, ge=0, le=23, description="Work hours end (0-23)"
    )

    # Settings
    notification_preferences: dict[str, bool] = Field(
        default_factory=lambda: {
            "email_quotes": True,
            "email_claims": True,
            "email_system": True,
            "sms_urgent": False,
            "push_notifications": True,
        },
        description="Notification preferences by type",
    )
    dashboard_config: dict[str, Any] = Field(
        default_factory=dict, description="Custom dashboard configuration"
    )


@beartype
class AdminUser(AdminUserBase, IdentifiableModel):
    """Full admin user model with security and audit fields."""

    # Security
    last_login_at: datetime | None = Field(
        None, description="Last successful login timestamp"
    )
    last_login_ip: str | None = Field(
        None,
        pattern=r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$|^(?:[a-fA-F0-9]{1,4}:){7}[a-fA-F0-9]{1,4}$",
        description="Last login IP address (IPv4 or IPv6)",
    )
    failed_login_attempts: int = Field(
        default=0, ge=0, le=10, description="Consecutive failed login attempts"
    )
    locked_until: datetime | None = Field(
        None, description="Account locked until this timestamp"
    )

    # Password management
    password_changed_at: datetime | None = Field(
        None, description="Last password change timestamp"
    )
    password_expires_at: datetime | None = Field(
        None, description="Password expiration timestamp"
    )
    must_change_password: bool = Field(
        default=False, description="Force password change on next login"
    )

    # Session management
    active_sessions: int = Field(
        default=0, ge=0, le=5, description="Number of active sessions"
    )
    last_activity_at: datetime | None = Field(
        None, description="Last API activity timestamp"
    )

    # Audit
    created_by: UUID4 | None = Field(None, description="Admin who created this user")
    deactivated_at: datetime | None = Field(
        None, description="When account was deactivated"
    )
    deactivated_by: UUID4 | None = Field(
        None, description="Admin who deactivated this user"
    )
    deactivation_reason: str | None = Field(
        None, max_length=500, description="Reason for deactivation"
    )

    # Relationships
    role: AdminRoleModel | None = Field(None, description="Populated role information")

    @computed_field  # type: ignore[misc]
    @property
    def is_locked(self) -> bool:
        """Check if account is currently locked."""
        if self.locked_until:
            return datetime.utcnow() < self.locked_until
        return False

    @computed_field  # type: ignore[misc]
    @property
    def is_active(self) -> bool:
        """Check if account is active and usable."""
        return (
            self.deactivated_at is None
            and not self.is_locked
            and (
                self.password_expires_at is None
                or datetime.utcnow() < self.password_expires_at
            )
        )

    @computed_field  # type: ignore[misc]
    @property
    def effective_permissions(self) -> list[Permission]:
        """Get all permissions including role and super admin."""
        if self.is_super_admin:
            return list(Permission)  # All permissions

        if self.role:
            return self.role.permissions

        return []

    @computed_field  # type: ignore[misc]
    @property
    def requires_password_change(self) -> bool:
        """Check if password change is required."""
        if self.must_change_password:
            return True

        if self.password_expires_at:
            return datetime.utcnow() >= self.password_expires_at

        return False

    @computed_field  # type: ignore[misc]
    @property
    def days_since_last_login(self) -> int | None:
        """Calculate days since last login."""
        if self.last_login_at:
            delta = datetime.utcnow() - self.last_login_at
            return delta.days
        return None


@beartype
class AdminUserCreate(AdminUserBase):
    """Model for creating admin user with password."""

    password: str = Field(
        ...,
        min_length=12,
        max_length=128,
        description="Strong password meeting security requirements",
    )

    # Optional role assignment by name
    role_name: str | None = Field(None, description="Role name instead of role_id")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Ensure password meets security requirements."""
        # Check minimum length (already enforced by Field)
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters long")

        # Check for required character types
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v)

        if not has_upper:
            raise ValueError("Password must contain at least one uppercase letter")
        if not has_lower:
            raise ValueError("Password must contain at least one lowercase letter")
        if not has_digit:
            raise ValueError("Password must contain at least one digit")
        if not has_special:
            raise ValueError("Password must contain at least one special character")

        # Check for common patterns
        if any(
            pattern in v.lower() for pattern in ["password", "12345", "admin", "qwerty"]
        ):
            raise ValueError("Password contains common patterns")

        return v


@beartype
class AdminUserUpdate(BaseModelConfig):
    """Model for updating admin user with partial data."""

    role_id: UUID4 | None = Field(None, description="Update role assignment")
    is_super_admin: bool | None = Field(None, description="Update super admin status")
    two_factor_enabled: bool | None = Field(None, description="Update 2FA status")

    # Profile updates
    full_name: str | None = Field(
        None, min_length=1, max_length=100, pattern=r"^[a-zA-Z\s\-'\.]+$"
    )
    phone: str | None = Field(None, pattern=r"^\+?1?\d{10,14}$")
    department: str | None = Field(None, max_length=50, pattern=r"^[a-zA-Z\s\-]+$")
    timezone: str | None = Field(None, pattern=r"^[A-Za-z]+/[A-Za-z_]+$")
    work_hours_start: int | None = Field(None, ge=0, le=23)
    work_hours_end: int | None = Field(None, ge=0, le=23)

    # Settings updates
    notification_preferences: dict[str, bool] | None = None
    dashboard_config: dict[str, Any] | None = None

    # Security updates
    must_change_password: bool | None = Field(
        None, description="Force password change on next login"
    )


@beartype
class SystemSettingCategory(str, Enum):
    """System setting categories for organization."""

    GENERAL = "general"
    SECURITY = "security"
    QUOTES = "quotes"
    POLICIES = "policies"
    CLAIMS = "claims"
    RATES = "rates"
    NOTIFICATIONS = "notifications"
    INTEGRATIONS = "integrations"
    COMPLIANCE = "compliance"
    ANALYTICS = "analytics"


@beartype
class SystemSetting(IdentifiableModel):
    """System configuration setting with validation and audit."""

    category: SystemSettingCategory = Field(
        ..., description="Setting category for organization"
    )
    key: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-zA-Z0-9_\-\.]+$",
        description="Unique setting key within category",
    )
    value: Any = Field(..., description="Setting value (type varies by setting)")
    data_type: str = Field(
        ...,
        pattern=r"^(string|number|boolean|json|datetime|decimal)$",
        description="Expected data type for validation",
    )

    # Metadata
    description: str | None = Field(
        None, max_length=500, description="Human-readable description of setting"
    )
    validation_rules: dict[str, Any] | None = Field(
        None, description="Additional validation rules (min, max, regex, etc.)"
    )
    default_value: Any | None = Field(None, description="Default value if not set")

    # Security
    is_sensitive: bool = Field(
        default=False, description="Contains sensitive data (masked in logs)"
    )
    encrypted: bool = Field(default=False, description="Value is encrypted at rest")
    requires_restart: bool = Field(
        default=False, description="Changing this setting requires service restart"
    )

    # Access control
    min_permission: Permission | None = Field(
        None, description="Minimum permission required to modify"
    )

    # Audit
    last_modified_by: UUID4 | None = Field(
        None, description="Admin who last modified this setting"
    )
    last_modified_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last modification timestamp"
    )
    version: int = Field(
        default=1, ge=1, description="Setting version for change tracking"
    )

    @field_validator("value")
    @classmethod
    def validate_value_type(cls, v: Any) -> Any:
        """Validate value matches declared type."""
        # Note: Can't access data_type and validation_rules here with beartype
        # Moving validation to model_validator
        return v

    @model_validator(mode="after")
    def validate_setting_consistency(self) -> "SystemSetting":
        """Validate value matches declared type and rules."""
        # Type validation
        if self.data_type == "string" and not isinstance(self.value, str):
            raise ValueError("Value must be string")
        elif self.data_type == "number" and not isinstance(self.value, (int, float)):
            raise ValueError("Value must be number")
        elif self.data_type == "boolean" and not isinstance(self.value, bool):
            raise ValueError("Value must be boolean")
        elif self.data_type == "decimal" and not isinstance(
            self.value, (Decimal, str, int, float)
        ):
            # Convert to Decimal for validation
            try:
                Decimal(str(self.value))
            except:
                raise ValueError("Value must be valid decimal")

        # Additional validation rules
        if self.validation_rules:
            if (
                "min" in self.validation_rules
                and self.value < self.validation_rules["min"]
            ):
                raise ValueError(f"Value must be >= {self.validation_rules['min']}")
            if (
                "max" in self.validation_rules
                and self.value > self.validation_rules["max"]
            ):
                raise ValueError(f"Value must be <= {self.validation_rules['max']}")
            if "regex" in self.validation_rules and isinstance(self.value, str):
                import re

                if not re.match(self.validation_rules["regex"], self.value):
                    raise ValueError(
                        f"Value must match pattern: {self.validation_rules['regex']}"
                    )
            if (
                "enum" in self.validation_rules
                and self.value not in self.validation_rules["enum"]
            ):
                raise ValueError(
                    f"Value must be one of: {self.validation_rules['enum']}"
                )

        return self

    @computed_field  # type: ignore[misc]
    @property
    def display_value(self) -> str:
        """Get display value (masked if sensitive)."""
        if self.is_sensitive:
            return "***SENSITIVE***"
        return str(self.value)


@beartype
class ActivityAction(str, Enum):
    """Types of admin activities to track."""

    # Authentication
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_CHANGED = "password_changed"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"

    # User management
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_SUSPENDED = "user_suspended"
    USER_RESTORED = "user_restored"

    # Quote actions
    QUOTE_VIEWED = "quote_viewed"
    QUOTE_CREATED = "quote_created"
    QUOTE_UPDATED = "quote_updated"
    QUOTE_APPROVED = "quote_approved"
    QUOTE_DECLINED = "quote_declined"
    QUOTE_DELETED = "quote_deleted"

    # Policy actions
    POLICY_VIEWED = "policy_viewed"
    POLICY_CREATED = "policy_created"
    POLICY_UPDATED = "policy_updated"
    POLICY_CANCELLED = "policy_cancelled"
    POLICY_REINSTATED = "policy_reinstated"

    # Claim actions
    CLAIM_VIEWED = "claim_viewed"
    CLAIM_CREATED = "claim_created"
    CLAIM_UPDATED = "claim_updated"
    CLAIM_APPROVED = "claim_approved"
    CLAIM_DENIED = "claim_denied"

    # System actions
    SETTINGS_VIEWED = "settings_viewed"
    SETTINGS_UPDATED = "settings_updated"
    EXPORT_CREATED = "export_created"
    REPORT_GENERATED = "report_generated"

    # Security actions
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    ROLE_ASSIGNED = "role_assigned"
    SECURITY_ALERT = "security_alert"


@beartype
class AdminActivityLog(IdentifiableModel):
    """Admin activity audit log with comprehensive tracking."""

    admin_user_id: UUID4 = Field(..., description="Admin user who performed the action")
    action: ActivityAction = Field(..., description="Type of action performed")
    resource_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[a-z_]+$",
        description="Type of resource affected (quote, policy, etc.)",
    )
    resource_id: UUID4 | None = Field(None, description="ID of affected resource")

    # Change tracking
    old_values: dict[str, Any] | None = Field(
        None, description="Previous values (for updates)"
    )
    new_values: dict[str, Any] | None = Field(
        None, description="New values (for updates)"
    )
    changes_summary: str | None = Field(
        None, max_length=1000, description="Human-readable summary of changes"
    )

    # Context
    ip_address: str | None = Field(
        None,
        pattern=r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$|^(?:[a-fA-F0-9]{1,4}:){7}[a-fA-F0-9]{1,4}$",
        description="Request IP address",
    )
    user_agent: str | None = Field(
        None, max_length=500, description="Browser/client user agent"
    )
    request_id: UUID4 | None = Field(
        None, description="Unique request ID for correlation"
    )
    session_id: str | None = Field(
        None, max_length=100, description="Session ID for tracking"
    )

    # Result
    status: str = Field(
        ...,
        pattern=r"^(success|failed|unauthorized|error)$",
        description="Action result status",
    )
    error_message: str | None = Field(
        None, max_length=1000, description="Error details if failed"
    )
    duration_ms: int | None = Field(
        None,
        ge=0,
        le=300000,  # Max 5 minutes
        description="Operation duration in milliseconds",
    )

    # Additional metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional context-specific metadata"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="When the activity occurred"
    )

    @field_validator("old_values", "new_values")
    @classmethod
    def sanitize_sensitive_data(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """Remove sensitive data from logged values."""
        if not v:
            return v

        sensitive_fields = {"password", "token", "secret", "api_key", "ssn", "tax_id"}
        sanitized = {}

        for key, value in v.items():
            if any(sensitive in key.lower() for sensitive in sensitive_fields):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = value

        return sanitized


@beartype
class AdminDashboardWidget(str, Enum):
    """Available dashboard widget types."""

    QUOTE_SUMMARY = "quote_summary"
    POLICY_SUMMARY = "policy_summary"
    CLAIM_SUMMARY = "claim_summary"
    REVENUE_CHART = "revenue_chart"
    CONVERSION_FUNNEL = "conversion_funnel"
    AGENT_PERFORMANCE = "agent_performance"
    RISK_METRICS = "risk_metrics"
    SYSTEM_HEALTH = "system_health"
    RECENT_ACTIVITY = "recent_activity"
    ALERTS = "alerts"


@beartype
class DashboardWidget(BaseModelConfig):
    """Individual dashboard widget configuration."""

    widget_type: AdminDashboardWidget = Field(
        ..., description="Type of widget to display"
    )
    title: str = Field(..., min_length=1, max_length=100, description="Widget title")
    position: dict[str, int] = Field(
        ..., description="Grid position (x, y, width, height)"
    )
    config: dict[str, Any] = Field(
        default_factory=dict, description="Widget-specific configuration"
    )
    refresh_interval: int | None = Field(
        None, ge=10, le=3600, description="Auto-refresh interval in seconds"
    )

    @field_validator("position")
    @classmethod
    def validate_position(cls, v: dict[str, int]) -> dict[str, int]:
        """Ensure position has required fields."""
        required = {"x", "y", "width", "height"}
        if not all(key in v for key in required):
            raise ValueError(f"Position must include: {required}")

        # Validate reasonable values
        if v["x"] < 0 or v["y"] < 0:
            raise ValueError("Position x and y must be non-negative")
        if v["width"] < 1 or v["width"] > 12:
            raise ValueError("Width must be between 1 and 12")
        if v["height"] < 1 or v["height"] > 10:
            raise ValueError("Height must be between 1 and 10")

        return v


@beartype
class AdminDashboard(IdentifiableModel):
    """Admin dashboard configuration with customizable widgets."""

    name: str = Field(..., min_length=1, max_length=100, description="Dashboard name")
    slug: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9\-]+$",
        description="URL-friendly dashboard identifier",
    )
    description: str | None = Field(
        None, max_length=500, description="Dashboard description"
    )

    # Layout configuration
    layout_type: str = Field(
        default="grid",
        pattern=r"^(grid|flex|fixed)$",
        description="Layout type for widget arrangement",
    )
    widgets: list[DashboardWidget] = Field(
        default_factory=list, description="Dashboard widgets configuration"
    )

    # Settings
    refresh_interval: int = Field(
        default=60, ge=10, le=3600, description="Default refresh interval in seconds"
    )
    required_permission: Permission | None = Field(
        None, description="Permission required to view this dashboard"
    )
    theme: str = Field(
        default="light", pattern=r"^(light|dark|auto)$", description="Dashboard theme"
    )

    # Metadata
    is_default: bool = Field(
        default=False, description="Default dashboard for new users"
    )
    is_public: bool = Field(
        default=False, description="Available to all authenticated users"
    )
    is_system: bool = Field(
        default=False, description="System dashboard that cannot be deleted"
    )

    # Ownership
    created_by: UUID4 | None = Field(
        None, description="Admin who created the dashboard"
    )
    shared_with: list[UUID4] = Field(
        default_factory=list, description="Admin users this dashboard is shared with"
    )

    @field_validator("widgets")
    @classmethod
    def validate_widget_positions(
        cls, v: list[DashboardWidget]
    ) -> list[DashboardWidget]:
        """Ensure widgets don't overlap."""
        # Simple validation - in production would check for actual overlaps
        positions = [(w.position["x"], w.position["y"]) for w in v]
        if len(positions) != len(set(positions)):
            # More complex overlap detection would go here
            pass
        return v

    @computed_field  # type: ignore[misc]
    @property
    def widget_count(self) -> int:
        """Number of widgets in this dashboard."""
        return len(self.widgets)
