"""Add security and compliance tables.

Revision ID: 004
Revises: 003
Create Date: 2025-07-05

This migration creates:
1. SSO provider configurations
2. OAuth2 client management
3. MFA settings per user
4. Comprehensive audit logging with partitioning
5. Session management tables
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: str = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create security and compliance tables."""

    # Create SSO providers configuration table
    op.create_table(
        "sso_providers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provider_name", sa.String(50), nullable=False),
        sa.Column("provider_type", sa.String(20), nullable=False),
        # Configuration fields (encrypted in production)
        sa.Column("client_id", sa.String(255), nullable=False),
        sa.Column(
            "client_secret_encrypted",
            sa.Text(),
            nullable=False,
            comment="Encrypted with KMS in production",
        ),
        sa.Column("issuer_url", sa.Text(), nullable=True),
        sa.Column("authorize_url", sa.Text(), nullable=True),
        sa.Column("token_url", sa.Text(), nullable=True),
        sa.Column("userinfo_url", sa.Text(), nullable=True),
        # Settings
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "auto_create_users",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Auto-provision users on first login",
        ),
        sa.Column(
            "allowed_domains",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="[]",
            comment="Array of allowed email domains",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sso_providers")),
        sa.UniqueConstraint(
            "provider_name", name=op.f("uq_sso_providers_provider_name")
        ),
        sa.CheckConstraint(
            "provider_type IN ('google', 'azure', 'okta', 'auth0', 'saml', 'oidc')",
            name=op.f("ck_sso_providers_provider_type"),
        ),
    )

    # Create OAuth2 clients table
    op.create_table(
        "oauth2_clients",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("client_id", sa.String(100), nullable=False),
        sa.Column(
            "client_secret_hash",
            sa.Text(),
            nullable=False,
            comment="Hashed client secret",
        ),
        sa.Column("client_name", sa.String(100), nullable=False),
        # OAuth2 settings
        sa.Column(
            "redirect_uris",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
            comment="Array of allowed redirect URIs",
        ),
        sa.Column(
            "allowed_grant_types",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
            comment="Array of allowed grant types",
        ),
        sa.Column(
            "allowed_scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
            comment="Array of allowed scopes",
        ),
        # Rate limiting
        sa.Column(
            "rate_limit_per_minute",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
        sa.Column(
            "rate_limit_per_hour",
            sa.Integer(),
            nullable=False,
            server_default="1000",
        ),
        # Status
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth2_clients")),
        sa.UniqueConstraint("client_id", name=op.f("uq_oauth2_clients_client_id")),
        sa.CheckConstraint(
            "rate_limit_per_minute > 0",
            name=op.f("ck_oauth2_clients_rate_limit_per_minute_positive"),
        ),
        sa.CheckConstraint(
            "rate_limit_per_hour > 0",
            name=op.f("ck_oauth2_clients_rate_limit_per_hour_positive"),
        ),
    )

    # Create MFA settings table
    op.create_table(
        "user_mfa_settings",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # TOTP settings
        sa.Column(
            "totp_secret_encrypted",
            sa.Text(),
            nullable=True,
            comment="Encrypted TOTP secret",
        ),
        sa.Column(
            "totp_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        # WebAuthn settings
        sa.Column(
            "webauthn_credentials",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="[]",
            comment="Array of WebAuthn credential info",
        ),
        sa.Column(
            "webauthn_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        # SMS backup
        sa.Column(
            "sms_phone_encrypted",
            sa.Text(),
            nullable=True,
            comment="Encrypted phone number for SMS",
        ),
        sa.Column(
            "sms_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        # Recovery codes
        sa.Column(
            "recovery_codes_encrypted",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Encrypted array of recovery codes",
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
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_mfa_settings_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_mfa_settings")),
    )

    # Create sessions table for session management
    op.create_table(
        "user_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_token_hash", sa.String(255), nullable=False),
        # Session info
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("device_fingerprint", sa.String(255), nullable=True),
        # Authentication method
        sa.Column(
            "auth_method",
            sa.String(50),
            nullable=False,
            comment="password, sso_google, sso_azure, etc.",
        ),
        sa.Column("sso_provider_id", postgresql.UUID(as_uuid=True), nullable=True),
        # Session lifecycle
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(100), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sso_provider_id"],
            ["sso_providers.id"],
            name=op.f("fk_user_sessions_sso_provider_id_sso_providers"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
    )

    # Create indexes for sessions
    op.create_index(
        op.f("ix_user_sessions_user_id"),
        "user_sessions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_sessions_session_token_hash"),
        "user_sessions",
        ["session_token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_user_sessions_expires_at"),
        "user_sessions",
        ["expires_at"],
        unique=False,
    )

    # Create partitioned audit logs table
    op.execute(
        """
        CREATE TABLE audit_logs (
            id UUID NOT NULL DEFAULT gen_random_uuid(),
            -- Who
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            ip_address INET,
            user_agent TEXT,
            session_id UUID,
            -- What
            action VARCHAR(100) NOT NULL,
            resource_type VARCHAR(50) NOT NULL,
            resource_id UUID,
            -- Details
            request_method VARCHAR(10),
            request_path TEXT,
            request_body JSONB,
            response_status INTEGER,
            response_time_ms INTEGER,
            -- Security
            risk_score NUMERIC(3,2) CHECK (risk_score >= 0 AND risk_score <= 1),
            security_alerts JSONB DEFAULT '[]',
            -- Timestamp
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id, created_at)
        ) PARTITION BY RANGE (created_at);
        """
    )

    # Create audit log indexes
    op.create_index(
        "ix_audit_logs_user_id",
        "audit_logs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_created_at",
        "audit_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_action",
        "audit_logs",
        ["action"],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_resource",
        "audit_logs",
        ["resource_type", "resource_id"],
        unique=False,
    )

    # Create partitions for audit logs (monthly partitions)
    op.execute(
        """
        -- Create partitions for current and next 3 months
        CREATE TABLE audit_logs_2025_01 PARTITION OF audit_logs
            FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

        CREATE TABLE audit_logs_2025_02 PARTITION OF audit_logs
            FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');

        CREATE TABLE audit_logs_2025_03 PARTITION OF audit_logs
            FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');

        CREATE TABLE audit_logs_2025_04 PARTITION OF audit_logs
            FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
        """
    )

    # Create function for automatic partition creation
    op.execute(
        """
        CREATE OR REPLACE FUNCTION create_monthly_audit_partition()
        RETURNS void AS $$
        DECLARE
            partition_date DATE;
            partition_name TEXT;
            start_date DATE;
            end_date DATE;
        BEGIN
            -- Calculate next month
            partition_date := DATE_TRUNC('month', CURRENT_DATE + INTERVAL '1 month');
            partition_name := 'audit_logs_' || TO_CHAR(partition_date, 'YYYY_MM');
            start_date := partition_date;
            end_date := partition_date + INTERVAL '1 month';

            -- Check if partition already exists
            IF NOT EXISTS (
                SELECT 1 FROM pg_tables
                WHERE tablename = partition_name
            ) THEN
                -- Create the partition
                EXECUTE format(
                    'CREATE TABLE %I PARTITION OF audit_logs FOR VALUES FROM (%L) TO (%L)',
                    partition_name,
                    start_date,
                    end_date
                );
            END IF;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # Create data retention policies table
    op.create_table(
        "data_retention_policies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("table_name", sa.String(100), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column(
            "archive_enabled", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("archive_location", sa.String(255), nullable=True),
        sa.Column(
            "last_cleanup_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_retention_policies")),
        sa.UniqueConstraint(
            "table_name", name=op.f("uq_data_retention_policies_table_name")
        ),
        sa.CheckConstraint(
            "retention_days > 0",
            name=op.f("ck_data_retention_policies_retention_days_positive"),
        ),
    )

    # Add update triggers
    for table in ["sso_providers", "user_mfa_settings"]:
        op.execute(
            f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
            """
        )

    # Create function to validate grant types
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_grant_types(grant_types JSONB)
        RETURNS BOOLEAN AS $$
        DECLARE
            valid_types TEXT[] := ARRAY['authorization_code', 'implicit', 'password', 'client_credentials', 'refresh_token'];
            grant_type TEXT;
        BEGIN
            IF grant_types IS NULL OR jsonb_array_length(grant_types) = 0 THEN
                RETURN FALSE;
            END IF;

            FOR grant_type IN SELECT jsonb_array_elements_text(grant_types)
            LOOP
                IF grant_type != ALL(valid_types) THEN
                    RETURN FALSE;
                END IF;
            END LOOP;

            RETURN TRUE;
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
        """
    )

    # Add validation constraint for grant types
    op.create_check_constraint(
        "ck_oauth2_clients_grant_types_valid",
        "oauth2_clients",
        sa.text("validate_grant_types(allowed_grant_types)"),
    )


def downgrade() -> None:
    """Drop security and compliance tables and related objects."""

    # Drop constraint
    op.drop_constraint("ck_oauth2_clients_grant_types_valid", "oauth2_clients")

    # Drop triggers
    for table in ["sso_providers", "user_mfa_settings"]:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS validate_grant_types(JSONB);")
    op.execute("DROP FUNCTION IF EXISTS create_monthly_audit_partition();")

    # Drop tables (non-partitioned)
    op.drop_table("data_retention_policies")
    op.drop_table("user_sessions")
    op.drop_table("user_mfa_settings")
    op.drop_table("oauth2_clients")
    op.drop_table("sso_providers")

    # Drop partitioned table and its partitions
    op.execute("DROP TABLE IF EXISTS audit_logs CASCADE;")
