"""Add admin system tables.

Revision ID: 006
Revises: 005
Create Date: 2025-07-05

This migration creates:
1. Admin roles with hierarchical permissions
2. Admin permissions registry
3. System settings configuration
4. Admin activity logs
5. Admin dashboards configuration
6. Rate approval workflow tables
7. Admin-specific indexes and constraints
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create admin system tables."""

    # Create admin roles table first (referenced by admin_users)
    op.create_table(
        "admin_roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "name",
            sa.String(50),
            nullable=False,
            comment="Role name (e.g., 'Super Admin', 'Rate Manager')",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Role description and purpose",
        ),
        # Permissions as JSONB for flexibility
        sa.Column(
            "permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
            comment="Array of permission identifiers",
        ),
        # Hierarchy support
        sa.Column(
            "parent_role_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Parent role for inheritance",
        ),
        sa.Column(
            "is_system_role",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="System roles cannot be deleted",
        ),
        # Metadata
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["parent_role_id"],
            ["admin_roles.id"],
            name=op.f("fk_admin_roles_parent_role_id_admin_roles"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_roles")),
        sa.UniqueConstraint("name", name=op.f("uq_admin_roles_name")),
    )

    # Create admin users table (extends regular users)
    op.create_table(
        "admin_users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Reference to main users table",
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Admin role assignment",
        ),
        # Admin-specific fields
        sa.Column(
            "is_super_admin",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Super admin bypass all permissions",
        ),
        sa.Column(
            "department",
            sa.String(100),
            nullable=True,
            comment="Department assignment",
        ),
        sa.Column(
            "employee_id",
            sa.String(50),
            nullable=True,
            comment="Internal employee identifier",
        ),
        # Security features
        sa.Column(
            "requires_2fa",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Enforce 2FA for this admin",
        ),
        sa.Column(
            "ip_whitelist",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="[]",
            comment="Array of allowed IP addresses/ranges",
        ),
        sa.Column(
            "access_hours",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Allowed access hours (e.g., business hours only)",
        ),
        # Activity tracking
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last admin action timestamp",
        ),
        sa.Column(
            "total_actions",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Total admin actions performed",
        ),
        # Status
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
            comment="Admin account status",
        ),
        sa.Column(
            "deactivated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the admin access was revoked",
        ),
        sa.Column(
            "deactivation_reason",
            sa.Text(),
            nullable=True,
            comment="Reason for deactivation",
        ),
        # Audit
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Admin who created this admin user",
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_admin_users_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["admin_roles.id"],
            name=op.f("fk_admin_users_role_id_admin_roles"),
            ondelete="RESTRICT",  # Prevent role deletion if admins assigned
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["admin_users.id"],
            name=op.f("fk_admin_users_created_by_admin_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_users")),
        sa.UniqueConstraint("user_id", name=op.f("uq_admin_users_user_id")),
        sa.UniqueConstraint("employee_id", name=op.f("uq_admin_users_employee_id")),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'deactivated')",
            name=op.f("ck_admin_users_status"),
        ),
        sa.CheckConstraint(
            "total_actions >= 0",
            name=op.f("ck_admin_users_total_actions_positive"),
        ),
        # Business rule: deactivated accounts must have reason
        sa.CheckConstraint(
            "(status != 'deactivated') OR (deactivation_reason IS NOT NULL)",
            name=op.f("ck_admin_users_deactivation_reason_required"),
        ),
    )

    # Create admin permissions registry
    op.create_table(
        "admin_permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "resource",
            sa.String(50),
            nullable=False,
            comment="Resource name (quotes, policies, users, etc.)",
        ),
        sa.Column(
            "action",
            sa.String(50),
            nullable=False,
            comment="Action name (read, write, delete, approve, etc.)",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Permission description",
        ),
        sa.Column(
            "risk_level",
            sa.String(20),
            nullable=False,
            server_default="medium",
            comment="Risk level of this permission",
        ),
        sa.Column(
            "requires_2fa",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether this permission requires 2FA",
        ),
        sa.Column(
            "requires_approval",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether actions need approval",
        ),
        # Metadata
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_permissions")),
        sa.UniqueConstraint(
            "resource",
            "action",
            name=op.f("uq_admin_permissions_resource_action"),
        ),
        sa.CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name=op.f("ck_admin_permissions_risk_level"),
        ),
    )

    # Create system settings table
    op.create_table(
        "system_settings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "category",
            sa.String(50),
            nullable=False,
            comment="Setting category (general, security, features, etc.)",
        ),
        sa.Column(
            "key",
            sa.String(100),
            nullable=False,
            comment="Setting key within category",
        ),
        sa.Column(
            "value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Setting value (can be any JSON type)",
        ),
        # Type information
        sa.Column(
            "data_type",
            sa.String(20),
            nullable=False,
            comment="Expected data type",
        ),
        sa.Column(
            "validation_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Validation rules for the setting",
        ),
        sa.Column(
            "default_value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Default value if not set",
        ),
        # Metadata
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Setting description and purpose",
        ),
        sa.Column(
            "display_name",
            sa.String(100),
            nullable=True,
            comment="Human-friendly display name",
        ),
        sa.Column(
            "help_text",
            sa.Text(),
            nullable=True,
            comment="Help text for admin UI",
        ),
        # Security
        sa.Column(
            "is_sensitive",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether this contains sensitive data",
        ),
        sa.Column(
            "is_encrypted",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether value is encrypted",
        ),
        sa.Column(
            "requires_restart",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether changing requires system restart",
        ),
        # Audit
        sa.Column(
            "last_modified_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Admin who last modified this setting",
        ),
        sa.Column(
            "last_modified_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["last_modified_by"],
            ["admin_users.id"],
            name=op.f("fk_system_settings_last_modified_by_admin_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_system_settings")),
        sa.UniqueConstraint(
            "category",
            "key",
            name=op.f("uq_system_settings_category_key"),
        ),
        sa.CheckConstraint(
            "data_type IN ('string', 'number', 'boolean', 'json', 'array')",
            name=op.f("ck_system_settings_data_type"),
        ),
        sa.CheckConstraint(
            "category IN ('general', 'security', 'features', 'integrations', "
            "'notifications', 'performance', 'compliance')",
            name=op.f("ck_system_settings_category"),
        ),
    )

    # Create admin activity logs table
    op.create_table(
        "admin_activity_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "admin_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Admin who performed the action",
        ),
        # Activity details
        sa.Column(
            "action",
            sa.String(100),
            nullable=False,
            comment="Action performed (e.g., 'rate_table.update')",
        ),
        sa.Column(
            "resource_type",
            sa.String(50),
            nullable=False,
            comment="Type of resource affected",
        ),
        sa.Column(
            "resource_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="ID of affected resource",
        ),
        sa.Column(
            "resource_name",
            sa.String(200),
            nullable=True,
            comment="Human-readable resource identifier",
        ),
        # Changes made
        sa.Column(
            "old_values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Previous values before change",
        ),
        sa.Column(
            "new_values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="New values after change",
        ),
        sa.Column(
            "change_summary",
            sa.Text(),
            nullable=True,
            comment="Human-readable change summary",
        ),
        # Context
        sa.Column(
            "ip_address",
            postgresql.INET(),
            nullable=True,
            comment="IP address of admin",
        ),
        sa.Column(
            "user_agent",
            sa.Text(),
            nullable=True,
            comment="Browser user agent",
        ),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="API request ID for correlation",
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Admin session ID",
        ),
        # Result
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            comment="Result of the action",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="Error details if failed",
        ),
        sa.Column(
            "duration_ms",
            sa.Integer(),
            nullable=True,
            comment="Action duration in milliseconds",
        ),
        # Risk assessment
        sa.Column(
            "risk_score",
            sa.Integer(),
            nullable=True,
            comment="Risk score of the action (0-100)",
        ),
        sa.Column(
            "risk_factors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Factors contributing to risk score",
        ),
        # Timestamp
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["admin_user_id"],
            ["admin_users.id"],
            name=op.f("fk_admin_activity_logs_admin_user_id_admin_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_activity_logs")),
        sa.CheckConstraint(
            "status IN ('success', 'failed', 'unauthorized', 'pending_approval')",
            name=op.f("ck_admin_activity_logs_status"),
        ),
        sa.CheckConstraint(
            "duration_ms >= 0",
            name=op.f("ck_admin_activity_logs_duration_positive"),
        ),
        sa.CheckConstraint(
            "risk_score >= 0 AND risk_score <= 100",
            name=op.f("ck_admin_activity_logs_risk_score_range"),
        ),
    )

    # Create admin dashboards configuration
    op.create_table(
        "admin_dashboards",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "name",
            sa.String(100),
            nullable=False,
            comment="Dashboard name",
        ),
        sa.Column(
            "slug",
            sa.String(100),
            nullable=False,
            comment="URL-friendly identifier",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
            comment="Dashboard description",
        ),
        # Dashboard configuration
        sa.Column(
            "layout",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Grid layout configuration",
        ),
        sa.Column(
            "widgets",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Widget configurations",
        ),
        sa.Column(
            "filters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
            comment="Default filter settings",
        ),
        sa.Column(
            "refresh_interval",
            sa.Integer(),
            nullable=False,
            server_default="60",
            comment="Auto-refresh interval in seconds",
        ),
        # Access control
        sa.Column(
            "required_permission",
            sa.String(100),
            nullable=True,
            comment="Permission required to view",
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Default dashboard for new admins",
        ),
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="System dashboards cannot be deleted",
        ),
        # Ownership
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Admin who created the dashboard",
        ),
        sa.Column(
            "is_public",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Whether other admins can view",
        ),
        # Metadata
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["admin_users.id"],
            name=op.f("fk_admin_dashboards_created_by_admin_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_dashboards")),
        sa.UniqueConstraint("slug", name=op.f("uq_admin_dashboards_slug")),
        sa.CheckConstraint(
            "refresh_interval >= 10",
            name=op.f("ck_admin_dashboards_refresh_interval_min"),
        ),
    )

    # Create rate approval workflow table
    op.create_table(
        "admin_rate_approvals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "rate_table_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Rate table pending approval",
        ),
        # Submission details
        sa.Column(
            "submitted_by",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Admin who submitted for approval",
        ),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "submission_notes",
            sa.Text(),
            nullable=True,
            comment="Notes from submitter",
        ),
        # Approval details
        sa.Column(
            "approved_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Admin who approved",
        ),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "approval_notes",
            sa.Text(),
            nullable=True,
            comment="Notes from approver",
        ),
        # Rejection details
        sa.Column(
            "rejected_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Admin who rejected",
        ),
        sa.Column(
            "rejected_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "rejection_reason",
            sa.Text(),
            nullable=True,
            comment="Reason for rejection",
        ),
        # Changes and metadata
        sa.Column(
            "changes_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Summary of changes being approved",
        ),
        sa.Column(
            "impact_analysis",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Analysis of rate change impact",
        ),
        sa.Column(
            "effective_date",
            sa.Date(),
            nullable=False,
            comment="When rates become effective",
        ),
        sa.Column(
            "filing_reference",
            sa.String(100),
            nullable=True,
            comment="Regulatory filing reference",
        ),
        # Status
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            server_default="normal",
        ),
        sa.Column(
            "requires_filing",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether regulatory filing needed",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["rate_table_id"],
            ["rate_tables.id"],
            name=op.f("fk_admin_rate_approvals_rate_table_id_rate_tables"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"],
            ["admin_users.id"],
            name=op.f("fk_admin_rate_approvals_submitted_by_admin_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["admin_users.id"],
            name=op.f("fk_admin_rate_approvals_approved_by_admin_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["rejected_by"],
            ["admin_users.id"],
            name=op.f("fk_admin_rate_approvals_rejected_by_admin_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_rate_approvals")),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'withdrawn')",
            name=op.f("ck_admin_rate_approvals_status"),
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name=op.f("ck_admin_rate_approvals_priority"),
        ),
        # Business rules
        sa.CheckConstraint(
            "(status = 'approved' AND approved_by IS NOT NULL) OR status != 'approved'",
            name=op.f("ck_admin_rate_approvals_approval_required"),
        ),
        sa.CheckConstraint(
            "(status = 'rejected' AND rejection_reason IS NOT NULL) OR status != 'rejected'",
            name=op.f("ck_admin_rate_approvals_rejection_reason_required"),
        ),
    )

    # Create indexes for admin tables

    # Admin users indexes
    op.create_index(
        op.f("ix_admin_users_role_id"),
        "admin_users",
        ["role_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_users_status"),
        "admin_users",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_users_department"),
        "admin_users",
        ["department"],
        unique=False,
    )

    # System settings indexes
    op.create_index(
        op.f("ix_system_settings_category"),
        "system_settings",
        ["category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_system_settings_is_sensitive"),
        "system_settings",
        ["is_sensitive"],
        unique=False,
    )

    # Admin activity logs indexes
    op.create_index(
        op.f("ix_admin_activity_logs_admin_user_id"),
        "admin_activity_logs",
        ["admin_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_activity_logs_created_at"),
        "admin_activity_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_activity_logs_resource"),
        "admin_activity_logs",
        ["resource_type", "resource_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_activity_logs_action"),
        "admin_activity_logs",
        ["action"],
        unique=False,
    )
    # Index for high-risk activities
    op.create_index(
        "ix_admin_activity_logs_high_risk",
        "admin_activity_logs",
        ["risk_score", "created_at"],
        unique=False,
        postgresql_where=sa.text("risk_score >= 70"),
    )

    # Admin rate approvals indexes
    op.create_index(
        op.f("ix_admin_rate_approvals_status"),
        "admin_rate_approvals",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_rate_approvals_submitted_by"),
        "admin_rate_approvals",
        ["submitted_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_rate_approvals_effective_date"),
        "admin_rate_approvals",
        ["effective_date"],
        unique=False,
    )
    # Index for pending approvals
    op.create_index(
        "ix_admin_rate_approvals_pending",
        "admin_rate_approvals",
        ["priority", "submitted_at"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )

    # Add Row Level Security (RLS) policies
    op.execute("ALTER TABLE admin_activity_logs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE system_settings ENABLE ROW LEVEL SECURITY;")

    # Create RLS policy for activity logs (admins can only see their own unless super admin)
    op.execute(
        """
        CREATE POLICY admin_activity_logs_access_policy ON admin_activity_logs
        FOR ALL
        USING (
            admin_user_id = current_setting('app.current_admin_id')::UUID
            OR EXISTS (
                SELECT 1 FROM admin_users
                WHERE id = current_setting('app.current_admin_id')::UUID
                AND is_super_admin = true
            )
        );
        """
    )

    # Create RLS policy for system settings (sensitive settings require special permission)
    op.execute(
        """
        CREATE POLICY system_settings_access_policy ON system_settings
        FOR SELECT
        USING (
            is_sensitive = false
            OR EXISTS (
                SELECT 1 FROM admin_users au
                JOIN admin_roles ar ON au.role_id = ar.id
                WHERE au.id = current_setting('app.current_admin_id')::UUID
                AND (
                    au.is_super_admin = true
                    OR ar.permissions @> '["system_settings.read_sensitive"]'
                )
            )
        );
        """
    )

    # Add update triggers
    for table in [
        "admin_roles",
        "admin_users",
        "system_settings",
        "admin_dashboards",
        "admin_rate_approvals",
    ]:
        op.execute(
            f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
            """
        )

    # Create function to calculate admin risk score
    op.execute(
        """
        CREATE OR REPLACE FUNCTION calculate_admin_risk_score(
            p_action TEXT,
            p_resource_type TEXT,
            p_old_values JSONB,
            p_new_values JSONB
        )
        RETURNS INTEGER AS $$
        DECLARE
            v_risk_score INTEGER := 0;
        BEGIN
            -- Base risk by action type
            v_risk_score := CASE
                WHEN p_action LIKE '%delete%' THEN 50
                WHEN p_action LIKE '%approve%' THEN 40
                WHEN p_action LIKE '%create%' THEN 30
                WHEN p_action LIKE '%update%' THEN 20
                ELSE 10
            END;

            -- Adjust by resource type
            v_risk_score := v_risk_score + CASE p_resource_type
                WHEN 'admin_users' THEN 30
                WHEN 'system_settings' THEN 25
                WHEN 'rate_tables' THEN 20
                WHEN 'policies' THEN 15
                ELSE 5
            END;

            -- Add risk for bulk changes
            IF p_old_values IS NOT NULL AND jsonb_array_length(p_old_values) > 10 THEN
                v_risk_score := v_risk_score + 20;
            END IF;

            -- Cap at 100
            RETURN LEAST(v_risk_score, 100);
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
        """
    )

    # Create function to validate admin permissions
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION validate_admin_permissions(permissions JSONB)
        RETURNS BOOLEAN AS $$
        DECLARE
            perm TEXT;
            resource TEXT;
            action TEXT;
        BEGIN
            IF permissions IS NULL OR jsonb_array_length(permissions) = 0 THEN
                RETURN TRUE; -- Empty permissions are valid
            END IF;

            -- Check each permission format
            FOR perm IN SELECT jsonb_array_elements_text(permissions)
            LOOP
                -- Permission format: resource.action
                IF perm !~ '^[a-z_]+\.[a-z_]+$' THEN
                    RETURN FALSE;
                END IF;

                -- Extract resource and action
                resource := split_part(perm, '.', 1);
                action := split_part(perm, '.', 2);

                -- Verify permission exists in registry
                IF NOT EXISTS (
                    SELECT 1 FROM admin_permissions
                    WHERE admin_permissions.resource = resource
                    AND admin_permissions.action = action
                ) THEN
                    RETURN FALSE;
                END IF;
            END LOOP;

            RETURN TRUE;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # Add validation constraint for role permissions
    op.create_check_constraint(
        "ck_admin_roles_permissions_valid",
        "admin_roles",
        sa.text("validate_admin_permissions(permissions)"),
    )

    # Insert default admin permissions
    op.execute(
        """
        INSERT INTO admin_permissions (resource, action, description, risk_level, requires_2fa)
        VALUES
        -- Quote permissions
        ('quotes', 'read', 'View quotes', 'low', false),
        ('quotes', 'write', 'Create/update quotes', 'medium', false),
        ('quotes', 'delete', 'Delete quotes', 'high', true),
        ('quotes', 'approve', 'Approve high-value quotes', 'high', true),

        -- Policy permissions
        ('policies', 'read', 'View policies', 'low', false),
        ('policies', 'write', 'Create/update policies', 'medium', false),
        ('policies', 'delete', 'Delete policies', 'high', true),
        ('policies', 'cancel', 'Cancel active policies', 'high', true),

        -- Rate table permissions
        ('rate_tables', 'read', 'View rate tables', 'low', false),
        ('rate_tables', 'write', 'Create/update rate tables', 'high', true),
        ('rate_tables', 'approve', 'Approve rate changes', 'critical', true),
        ('rate_tables', 'delete', 'Delete rate tables', 'critical', true),

        -- User management permissions
        ('users', 'read', 'View users', 'low', false),
        ('users', 'write', 'Create/update users', 'medium', false),
        ('users', 'delete', 'Delete users', 'high', true),

        -- Admin management permissions
        ('admin_users', 'read', 'View admin users', 'medium', false),
        ('admin_users', 'write', 'Create/update admin users', 'critical', true),
        ('admin_users', 'delete', 'Delete admin users', 'critical', true),

        -- System settings permissions
        ('system_settings', 'read', 'View system settings', 'medium', false),
        ('system_settings', 'write', 'Update system settings', 'high', true),
        ('system_settings', 'read_sensitive', 'View sensitive settings', 'high', true),

        -- Audit log permissions
        ('audit_logs', 'read', 'View audit logs', 'medium', false),
        ('audit_logs', 'export', 'Export audit logs', 'high', true),

        -- Dashboard permissions
        ('dashboards', 'read', 'View dashboards', 'low', false),
        ('dashboards', 'write', 'Create/update dashboards', 'low', false),
        ('dashboards', 'delete', 'Delete dashboards', 'medium', false);
        """
    )

    # Insert default admin roles
    op.execute(
        """
        INSERT INTO admin_roles (name, description, permissions, is_system_role)
        VALUES
        ('Super Admin', 'Full system access', '[]'::jsonb, true),
        ('Rate Manager', 'Manage rate tables and approvals',
         '["rate_tables.read", "rate_tables.write", "rate_tables.approve", "quotes.read", "policies.read"]'::jsonb, true),
        ('Underwriter', 'Review and approve quotes/policies',
         '["quotes.read", "quotes.write", "quotes.approve", "policies.read", "policies.write", "users.read"]'::jsonb, true),
        ('Support Agent', 'Customer support operations',
         '["quotes.read", "policies.read", "users.read", "users.write"]'::jsonb, true),
        ('Auditor', 'Read-only access for compliance',
         '["quotes.read", "policies.read", "users.read", "audit_logs.read", "audit_logs.export"]'::jsonb, true);
        """
    )


def downgrade() -> None:
    """Drop admin system tables and related objects."""

    # Drop RLS policies
    op.execute(
        "DROP POLICY IF EXISTS admin_activity_logs_access_policy ON admin_activity_logs;"
    )
    op.execute(
        "DROP POLICY IF EXISTS system_settings_access_policy ON system_settings;"
    )

    # Disable RLS
    op.execute("ALTER TABLE admin_activity_logs DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE system_settings DISABLE ROW LEVEL SECURITY;")

    # Drop constraint
    op.drop_constraint("ck_admin_roles_permissions_valid", "admin_roles")

    # Drop triggers
    for table in [
        "admin_roles",
        "admin_users",
        "system_settings",
        "admin_dashboards",
        "admin_rate_approvals",
    ]:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")

    # Drop functions
    op.execute(
        "DROP FUNCTION IF EXISTS calculate_admin_risk_score(TEXT, TEXT, JSONB, JSONB);"
    )
    op.execute("DROP FUNCTION IF EXISTS validate_admin_permissions(JSONB);")

    # Drop tables in correct order (due to foreign keys)
    op.drop_table("admin_rate_approvals")
    op.drop_table("admin_dashboards")
    op.drop_table("admin_activity_logs")
    op.drop_table("system_settings")
    op.drop_table("admin_permissions")
    op.drop_table("admin_users")
    op.drop_table("admin_roles")
