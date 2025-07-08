"""Admin API schemas for request/response validation."""

from datetime import datetime
from typing import Any, Dict, List

from beartype import beartype
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from pydantic.types import UUID4

from ..models.admin import ActivityAction, Permission, SystemSettingCategory


@beartype
class AdminRoleCreateRequest(BaseModel):
    """Request schema for creating an admin role."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

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
        ..., min_items=1, description="List of permissions to grant"
    )
    parent_role_id: UUID4 | None = Field(
        None, description="Parent role for permission inheritance"
    )
    max_session_duration: int = Field(
        default=28800,
        ge=900,
        le=86400,
        description="Maximum session duration in seconds",
    )
    require_mfa: bool = Field(
        default=False, description="Whether this role requires MFA"
    )


@beartype
class AdminRoleUpdateRequest(BaseModel):
    """Request schema for updating an admin role."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    description: str | None = Field(
        None, max_length=200, description="Updated description"
    )
    permissions: list[Permission] | None = Field(
        None, description="Updated permissions list"
    )
    parent_role_id: UUID4 | None = Field(None, description="Updated parent role")
    max_session_duration: int | None = Field(
        None, ge=900, le=86400, description="Updated session duration"
    )
    require_mfa: bool | None = Field(None, description="Updated MFA requirement")


@beartype
class AdminRoleResponse(BaseModel):
    """Response schema for admin role details."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    id: UUID4
    name: str
    description: str | None
    permissions: list[Permission]
    permission_count: int
    parent_role_id: UUID4 | None
    is_system_role: bool
    max_session_duration: int
    require_mfa: bool
    created_at: datetime
    updated_at: datetime


@beartype
class AdminUserCreateRequest(BaseModel):
    """Request schema for creating an admin user."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    email: EmailStr
    password: str = Field(
        ...,
        min_length=12,
        max_length=128,
        description="Strong password meeting security requirements",
    )
    role_id: UUID4
    is_super_admin: bool = Field(default=False)

    # Profile
    full_name: str = Field(
        ..., min_length=1, max_length=100, pattern=r"^[a-zA-Z\s\-'\.]+$"
    )
    phone: str | None = Field(None, pattern=r"^\+?1?\d{10,14}$")
    department: str | None = Field(None, max_length=50, pattern=r"^[a-zA-Z\s\-]+$")

    # Work schedule
    timezone: str = Field(default="UTC", pattern=r"^[A-Za-z]+/[A-Za-z_]+$")
    work_hours_start: int | None = Field(None, ge=0, le=23)
    work_hours_end: int | None = Field(None, ge=0, le=23)

    # Initial settings
    must_change_password: bool = Field(
        default=True, description="Force password change on first login"
    )
    send_welcome_email: bool = Field(
        default=True, description="Send welcome email with login instructions"
    )


@beartype
class AdminUserUpdateRequest(BaseModel):
    """Request schema for updating an admin user."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    role_id: UUID4 | None = None
    is_super_admin: bool | None = None
    two_factor_enabled: bool | None = None

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
    must_change_password: bool | None = None


@beartype
class AdminUserResponse(BaseModel):
    """Response schema for admin user details."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    id: UUID4
    email: EmailStr
    role_id: UUID4
    role: AdminRoleResponse | None
    is_super_admin: bool
    two_factor_enabled: bool

    # Profile
    full_name: str
    phone: str | None
    department: str | None
    timezone: str
    work_hours_start: int | None
    work_hours_end: int | None

    # Security status
    is_locked: bool
    is_active: bool
    requires_password_change: bool
    last_login_at: datetime | None
    last_login_ip: str | None
    failed_login_attempts: int

    # Session info
    active_sessions: int
    last_activity_at: datetime | None

    # Permissions
    effective_permissions: list[Permission]

    # Metadata
    created_at: datetime
    updated_at: datetime
    created_by: UUID4 | None


@beartype
class AdminUserListResponse(BaseModel):
    """Response schema for listing admin users."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    users: list[AdminUserResponse]
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    has_next: bool
    has_previous: bool


@beartype
class AdminPasswordChangeRequest(BaseModel):
    """Request schema for changing admin password."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    current_password: str = Field(..., description="Current password for verification")
    new_password: str = Field(
        ...,
        min_length=12,
        max_length=128,
        description="New password meeting security requirements",
    )


@beartype
class AdminPasswordResetRequest(BaseModel):
    """Request schema for admin password reset."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    email: EmailStr = Field(..., description="Email address of admin user")


@beartype
class SystemSettingCreateRequest(BaseModel):
    """Request schema for creating a system setting."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    category: SystemSettingCategory
    key: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_\-\.]+$")
    value: Any
    data_type: str = Field(
        ..., pattern=r"^(string|number|boolean|json|datetime|decimal)$"
    )
    description: str | None = Field(None, max_length=500)
    validation_rules: dict[str, Any] | None = None
    default_value: Any | None = None
    is_sensitive: bool = Field(default=False)
    encrypted: bool = Field(default=False)
    requires_restart: bool = Field(default=False)
    min_permission: Permission | None = None


@beartype
class SystemSettingUpdateRequest(BaseModel):
    """Request schema for updating a system setting."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    value: Any
    description: str | None = Field(None, max_length=500)
    validation_rules: dict[str, Any] | None = None
    requires_restart: bool | None = None
    min_permission: Permission | None = None


@beartype
class SystemSettingResponse(BaseModel):
    """Response schema for system setting details."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    id: UUID4
    category: SystemSettingCategory
    key: str
    value: Any
    display_value: str
    data_type: str
    description: str | None
    validation_rules: dict[str, Any] | None
    default_value: Any | None
    is_sensitive: bool
    encrypted: bool
    requires_restart: bool
    min_permission: Permission | None
    version: int
    last_modified_by: UUID4 | None
    last_modified_at: datetime


@beartype
class AdminActivityLogRequest(BaseModel):
    """Request schema for querying activity logs."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Filters
    admin_user_id: UUID4 | None = None
    action: list[ActivityAction] | None = None
    resource_type: str | None = None
    resource_id: UUID4 | None = None
    status: list[str] | None = None

    # Date range
    start_date: datetime | None = None
    end_date: datetime | None = None

    # Sorting
    sort_by: str = Field(
        default="created_at", pattern=r"^(created_at|action|resource_type|status)$"
    )
    sort_order: str = Field(default="desc", pattern=r"^(asc|desc)$")

    # Pagination
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


@beartype
class AdminActivityLogResponse(BaseModel):
    """Response schema for activity log entry."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    id: UUID4
    admin_user_id: UUID4
    admin_user_name: str | None
    action: ActivityAction
    resource_type: str
    resource_id: UUID4 | None
    changes_summary: str | None
    ip_address: str | None
    user_agent: str | None
    status: str
    error_message: str | None
    duration_ms: int | None
    created_at: datetime


@beartype
class AdminActivityLogListResponse(BaseModel):
    """Response schema for listing activity logs."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    logs: list[AdminActivityLogResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_previous: bool


@beartype
class AdminDashboardCreateRequest(BaseModel):
    """Request schema for creating a dashboard."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9\-]+$")
    description: str | None = Field(None, max_length=500)
    layout_type: str = Field(default="grid", pattern=r"^(grid|flex|fixed)$")
    widgets: list[dict[str, Any]] = Field(default_factory=list, max_items=20)
    refresh_interval: int = Field(default=60, ge=10, le=3600)
    required_permission: Permission | None = None
    theme: str = Field(default="light", pattern=r"^(light|dark|auto)$")
    is_public: bool = Field(default=False)


@beartype
class AdminDashboardUpdateRequest(BaseModel):
    """Request schema for updating a dashboard."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    widgets: list[dict[str, Any]] | None = Field(None, max_items=20)
    refresh_interval: int | None = Field(None, ge=10, le=3600)
    required_permission: Permission | None = None
    theme: str | None = Field(None, pattern=r"^(light|dark|auto)$")
    is_public: bool | None = None
    shared_with: list[UUID4] | None = Field(None, max_items=100)


@beartype
class AdminDashboardResponse(BaseModel):
    """Response schema for dashboard details."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    id: UUID4
    name: str
    slug: str
    description: str | None
    layout_type: str
    widgets: list[dict[str, Any]]
    widget_count: int
    refresh_interval: int
    required_permission: Permission | None
    theme: str
    is_default: bool
    is_public: bool
    is_system: bool
    created_by: UUID4 | None
    shared_with: list[UUID4]
    created_at: datetime
    updated_at: datetime


@beartype
class AdminLoginRequest(BaseModel):
    """Request schema for admin login."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    email: EmailStr
    password: str
    mfa_code: str | None = Field(
        None, pattern=r"^\d{6}$", description="6-digit MFA code if enabled"
    )


@beartype
class AdminLoginResponse(BaseModel):
    """Response schema for successful admin login."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int

    # User info
    user: AdminUserResponse

    # Session info
    session_id: str
    requires_mfa: bool = False
    requires_password_change: bool = False


@beartype
class AdminSessionResponse(BaseModel):
    """Response schema for admin session details."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    session_id: str
    user_id: UUID4
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    ip_address: str
    user_agent: str
    is_active: bool


@beartype
class AdminStatsResponse(BaseModel):
    """Response schema for admin dashboard statistics."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # User stats
    total_admins: int
    active_admins: int
    admins_online: int

    # Activity stats
    activities_today: int
    activities_this_week: int
    activities_this_month: int

    # Security stats
    failed_logins_today: int
    locked_accounts: int
    expired_passwords: int

    # System stats
    total_settings: int
    total_dashboards: int
    total_roles: int
