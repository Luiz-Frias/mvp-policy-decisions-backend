"""Add SSO integration tables.

Revision ID: 005
Revises: 004
Create Date: 2025-07-05

This migration creates:
1. User SSO links table for linking users to SSO providers
2. SSO group mappings for role assignment
3. User provisioning rules
4. SSO activity logs
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: str = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create SSO integration tables."""

    # Create user SSO links table
    op.create_table(
        "user_sso_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column(
            "profile_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Raw profile data from SSO provider",
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
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
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_sso_links_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sso_links")),
        sa.UniqueConstraint(
            "provider",
            "provider_user_id",
            name=op.f("uq_user_sso_links_provider_provider_user_id"),
        ),
    )

    # Create indexes for SSO links
    op.create_index(
        op.f("ix_user_sso_links_user_id"),
        "user_sso_links",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_sso_links_provider"),
        "user_sso_links",
        ["provider"],
        unique=False,
    )

    # Create SSO provider configurations table (enhanced version)
    op.create_table(
        "sso_provider_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provider_name", sa.String(100), nullable=False),
        sa.Column(
            "provider_type",
            sa.String(20),
            nullable=False,
            comment="oidc, saml, oauth2",
        ),
        sa.Column(
            "configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Encrypted provider configuration",
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "auto_create_users",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Allow automatic user creation",
        ),
        sa.Column(
            "allowed_domains",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
            comment="Restricted email domains for this provider",
        ),
        sa.Column(
            "default_role",
            sa.String(50),
            nullable=False,
            server_default="'agent'",
            comment="Default role for auto-created users",
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
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
            ["users.id"],
            name=op.f("fk_sso_provider_configs_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_sso_provider_configs_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sso_provider_configs")),
        sa.UniqueConstraint(
            "provider_name",
            name=op.f("uq_sso_provider_configs_provider_name"),
        ),
        sa.CheckConstraint(
            "provider_type IN ('oidc', 'saml', 'oauth2')",
            name=op.f("ck_sso_provider_configs_provider_type"),
        ),
        sa.CheckConstraint(
            "default_role IN ('agent', 'underwriter', 'admin', 'system')",
            name=op.f("ck_sso_provider_configs_default_role"),
        ),
    )

    # Create SSO group mappings table
    op.create_table(
        "sso_group_mappings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sso_group_name", sa.String(200), nullable=False),
        sa.Column("internal_role", sa.String(50), nullable=False),
        sa.Column(
            "auto_assign",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["sso_provider_configs.id"],
            name=op.f("fk_sso_group_mappings_provider_id_sso_provider_configs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_sso_group_mappings_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sso_group_mappings")),
        sa.UniqueConstraint(
            "provider_id",
            "sso_group_name",
            name=op.f("uq_sso_group_mappings_provider_id_sso_group_name"),
        ),
        sa.CheckConstraint(
            "internal_role IN ('agent', 'underwriter', 'admin', 'system')",
            name=op.f("ck_sso_group_mappings_internal_role"),
        ),
    )

    # Create user provisioning rules table
    op.create_table(
        "user_provisioning_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column(
            "conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Conditions for rule execution",
        ),
        sa.Column(
            "actions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Actions to perform when conditions are met",
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Higher priority rules execute first",
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["sso_provider_configs.id"],
            name=op.f("fk_user_provisioning_rules_provider_id_sso_provider_configs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_user_provisioning_rules_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_provisioning_rules")),
    )

    # Create index for provisioning rules priority
    op.create_index(
        op.f("ix_user_provisioning_rules_provider_id_priority"),
        "user_provisioning_rules",
        ["provider_id", "priority"],
        unique=False,
    )

    # Create SSO group sync logs table
    op.create_table(
        "sso_group_sync_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "sync_type",
            sa.String(20),
            nullable=False,
            comment="full, incremental",
        ),
        sa.Column(
            "groups_added",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "groups_removed",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            comment="success, failed, partial",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "last_sync",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["sso_provider_configs.id"],
            name=op.f("fk_sso_group_sync_logs_provider_id_sso_provider_configs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_sso_group_sync_logs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sso_group_sync_logs")),
        sa.CheckConstraint(
            "sync_type IN ('full', 'incremental')",
            name=op.f("ck_sso_group_sync_logs_sync_type"),
        ),
        sa.CheckConstraint(
            "status IN ('success', 'failed', 'partial')",
            name=op.f("ck_sso_group_sync_logs_status"),
        ),
    )

    # Create indexes for sync logs
    op.create_index(
        op.f("ix_sso_group_sync_logs_user_id"),
        "sso_group_sync_logs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_sso_group_sync_logs_last_sync"),
        "sso_group_sync_logs",
        ["last_sync"],
        unique=False,
    )

    # Create SSO activity logs table for admin dashboards
    op.create_table(
        "sso_activity_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("admin_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["admin_user_id"],
            ["users.id"],
            name=op.f("fk_sso_activity_logs_admin_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["sso_provider_configs.id"],
            name=op.f("fk_sso_activity_logs_provider_id_sso_provider_configs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sso_activity_logs")),
    )

    # Create index for activity logs
    op.create_index(
        op.f("ix_sso_activity_logs_created_at"),
        "sso_activity_logs",
        ["created_at"],
        unique=False,
    )

    # Create auth logs table for SSO authentication tracking
    op.create_table(
        "auth_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "auth_method",
            sa.String(50),
            nullable=False,
            comment="password, sso, api_key",
        ),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_auth_logs_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_logs")),
        sa.CheckConstraint(
            "auth_method IN ('password', 'sso', 'api_key')",
            name=op.f("ck_auth_logs_auth_method"),
        ),
        sa.CheckConstraint(
            "status IN ('success', 'failed', 'blocked')",
            name=op.f("ck_auth_logs_status"),
        ),
    )

    # Create indexes for auth logs
    op.create_index(
        op.f("ix_auth_logs_user_id"),
        "auth_logs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auth_logs_created_at"),
        "auth_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auth_logs_auth_method"),
        "auth_logs",
        ["auth_method"],
        unique=False,
    )

    # Add update triggers for new tables
    for table in ["user_sso_links", "sso_provider_configs"]:
        op.execute(
            f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
            """
        )


def downgrade() -> None:
    """Drop SSO integration tables."""

    # Drop triggers
    for table in ["user_sso_links", "sso_provider_configs"]:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")

    # Drop tables in reverse order
    op.drop_table("auth_logs")
    op.drop_table("sso_activity_logs")
    op.drop_table("sso_group_sync_logs")
    op.drop_table("user_provisioning_rules")
    op.drop_table("sso_group_mappings")
    op.drop_table("sso_provider_configs")
    op.drop_table("user_sso_links")
