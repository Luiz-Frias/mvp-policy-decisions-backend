"""Modularize user tables for progressive data capture.

Revision ID: 011
Revises: 010
Create Date: 2025-07-14

This migration refactors the monolithic users table into modular tables:
1. users - Core authentication only (email, password)
2. user_profiles - Optional profile information
3. user_addresses - Multiple addresses per user
4. user_phones - Multiple phone numbers per user
5. user_preferences - Notification and app preferences
6. user_security - Security settings (2FA, security questions)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: str = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create modular user tables."""
    
    # First, rename the existing users table to users_legacy for data preservation
    op.rename_table("users", "users_legacy")
    
    # Rename all constraints on the legacy table to avoid conflicts
    op.execute("ALTER TABLE users_legacy RENAME CONSTRAINT pk_users TO pk_users_legacy")
    op.execute("ALTER TABLE users_legacy RENAME CONSTRAINT uq_users_email TO uq_users_legacy_email")
    op.execute("ALTER TABLE users_legacy RENAME CONSTRAINT ck_users_role TO ck_users_legacy_role")
    
    # Rename indexes to avoid conflicts
    op.execute("ALTER INDEX ix_users_email RENAME TO ix_users_legacy_email")
    op.execute("ALTER INDEX ix_users_is_active RENAME TO ix_users_legacy_is_active")
    op.execute("ALTER INDEX ix_users_role RENAME TO ix_users_legacy_role")
    
    # Create new modular users table (authentication core)
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "password_hash", 
            sa.Text(), 
            nullable=True,  # Nullable for OAuth users
            comment="Null for OAuth-only users"
        ),
        sa.Column(
            "auth_provider",
            sa.String(50),
            nullable=False,
            server_default="local",
            comment="local, google, github, okta, etc."
        ),
        sa.Column(
            "auth_provider_id",
            sa.String(255),
            nullable=True,
            comment="External provider user ID"
        ),
        sa.Column(
            "email_verified",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "email_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "is_locked",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Account locked due to security reasons"
        ),
        sa.Column(
            "locked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "locked_reason",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_login_ip",
            sa.String(45),
            nullable=True,
            comment="IPv4 or IPv6 address"
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint(
            "auth_provider", "auth_provider_id",
            name=op.f("uq_users_provider_id")
        ),
        sa.CheckConstraint(
            "email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
            name=op.f("ck_users_email_format"),
        ),
        sa.CheckConstraint(
            "auth_provider IN ('local', 'google', 'github', 'microsoft', 'okta', 'auth0', 'facebook')",
            name=op.f("ck_users_auth_provider"),
        ),
    )
    
    # Create indexes for users table
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_index(op.f("ix_users_auth_provider"), "users", ["auth_provider"], unique=False)
    op.create_index(op.f("ix_users_is_active"), "users", ["is_active"], unique=False)
    op.create_index(op.f("ix_users_created_at"), "users", ["created_at"], unique=False)
    
    # Create user_profiles table
    op.create_table(
        "user_profiles",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column(
            "gender",
            sa.String(20),
            nullable=True,
            comment="male, female, other, prefer_not_to_say"
        ),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("timezone", sa.String(50), nullable=True, server_default="UTC"),
        sa.Column("locale", sa.String(10), nullable=True, server_default="en-US"),
        sa.Column(
            "profile_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When user completed their profile"
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
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_profiles")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "gender IN ('male', 'female', 'other', 'prefer_not_to_say')",
            name=op.f("ck_user_profiles_gender"),
        ),
    )
    
    # Create user_addresses table
    op.create_table(
        "user_addresses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "address_type",
            sa.String(20),
            nullable=False,
            server_default="home",
            comment="home, work, billing, shipping, other"
        ),
        sa.Column("label", sa.String(50), nullable=True, comment="Custom label"),
        sa.Column("street_address_1", sa.String(200), nullable=False),
        sa.Column("street_address_2", sa.String(200), nullable=True),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state_province", sa.String(100), nullable=False),
        sa.Column("postal_code", sa.String(20), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False, server_default="US"),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "is_validated",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Address validated via service"
        ),
        sa.Column(
            "validated_at",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_addresses")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_addresses_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "address_type IN ('home', 'work', 'billing', 'shipping', 'other')",
            name=op.f("ck_user_addresses_type"),
        ),
        sa.CheckConstraint(
            "LENGTH(country_code) = 2",
            name=op.f("ck_user_addresses_country_code_length"),
        ),
    )
    
    # Create indexes for user_addresses
    op.create_index(
        op.f("ix_user_addresses_user_id"),
        "user_addresses",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_addresses_type"),
        "user_addresses",
        ["address_type"],
        unique=False,
    )
    
    # Create user_phones table
    op.create_table(
        "user_phones",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "phone_type",
            sa.String(20),
            nullable=False,
            server_default="mobile",
            comment="mobile, home, work, other"
        ),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("country_code", sa.String(5), nullable=False, server_default="+1"),
        sa.Column(
            "is_primary",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "is_verified",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "can_receive_sms",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_phones")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_phones_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "country_code", "phone_number",
            name=op.f("uq_user_phones_number")
        ),
        sa.CheckConstraint(
            "phone_type IN ('mobile', 'home', 'work', 'other')",
            name=op.f("ck_user_phones_type"),
        ),
    )
    
    # Create indexes for user_phones
    op.create_index(
        op.f("ix_user_phones_user_id"),
        "user_phones",
        ["user_id"],
        unique=False,
    )
    
    # Create user_preferences table
    op.create_table(
        "user_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Communication preferences
        sa.Column("email_notifications", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sms_notifications", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("push_notifications", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("marketing_emails", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("product_updates", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("newsletter", sa.Boolean(), nullable=False, server_default="false"),
        # App preferences
        sa.Column("theme", sa.String(20), nullable=False, server_default="light"),
        sa.Column("language", sa.String(10), nullable=False, server_default="en-US"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("date_format", sa.String(20), nullable=False, server_default="MM/DD/YYYY"),
        sa.Column("time_format", sa.String(10), nullable=False, server_default="12h"),
        # Privacy preferences
        sa.Column("profile_visibility", sa.String(20), nullable=False, server_default="private"),
        sa.Column("show_online_status", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("data_collection_consent", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("analytics_consent", sa.Boolean(), nullable=False, server_default="false"),
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
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_preferences")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_preferences_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "theme IN ('light', 'dark', 'auto')",
            name=op.f("ck_user_preferences_theme"),
        ),
        sa.CheckConstraint(
            "profile_visibility IN ('public', 'private', 'contacts_only')",
            name=op.f("ck_user_preferences_visibility"),
        ),
    )
    
    # Create user_security table
    op.create_table(
        "user_security",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # Two-factor authentication
        sa.Column("two_factor_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("two_factor_secret", sa.String(255), nullable=True),
        sa.Column("two_factor_backup_codes", postgresql.JSONB(), nullable=True),
        sa.Column("two_factor_enabled_at", sa.DateTime(timezone=True), nullable=True),
        # Security questions
        sa.Column(
            "security_questions",
            postgresql.JSONB(),
            nullable=True,
            comment="Array of {question_id, answer_hash}"
        ),
        # Session management
        sa.Column("require_password_change", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("session_timeout_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("concurrent_sessions_allowed", sa.Integer(), nullable=False, server_default="5"),
        # IP restrictions
        sa.Column(
            "allowed_ip_addresses",
            postgresql.JSONB(),
            nullable=True,
            comment="Array of allowed IP addresses/ranges"
        ),
        sa.Column("last_security_audit_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_security")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_security_user_id_users"),
            ondelete="CASCADE",
        ),
    )
    
    # Create user roles table (many-to-many)
    op.create_table(
        "user_roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_roles")),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_roles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.id"],
            name=op.f("fk_user_roles_granted_by_users"),
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "user_id", "role",
            name=op.f("uq_user_roles_user_role")
        ),
        sa.CheckConstraint(
            "role IN ('customer', 'agent', 'underwriter', 'admin', 'super_admin', 'system')",
            name=op.f("ck_user_roles_role"),
        ),
    )
    
    # Create indexes for user_roles
    op.create_index(
        op.f("ix_user_roles_user_id"),
        "user_roles",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_roles_role"),
        "user_roles",
        ["role"],
        unique=False,
    )
    
    # Add update triggers
    op.execute(
        """
        CREATE TRIGGER update_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
    )
    
    op.execute(
        """
        CREATE TRIGGER update_user_profiles_updated_at
        BEFORE UPDATE ON user_profiles
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
    )
    
    op.execute(
        """
        CREATE TRIGGER update_user_addresses_updated_at
        BEFORE UPDATE ON user_addresses
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
    )
    
    op.execute(
        """
        CREATE TRIGGER update_user_preferences_updated_at
        BEFORE UPDATE ON user_preferences
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
    )
    
    op.execute(
        """
        CREATE TRIGGER update_user_security_updated_at
        BEFORE UPDATE ON user_security
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
    )
    
    # Migrate data from users_legacy to new tables (execute separately)
    
    # Migrate core user data
    op.execute(
        """
        INSERT INTO users (id, email, password_hash, email_verified, is_active, created_at, updated_at, last_login_at)
        SELECT id, email, password_hash, 
               COALESCE(is_active, true) as email_verified,
               is_active, created_at, updated_at, last_login_at
        FROM users_legacy
        """
    )
    
    # Migrate profile data
    op.execute(
        """
        INSERT INTO user_profiles (user_id, first_name, last_name, created_at, updated_at)
        SELECT id, first_name, last_name, created_at, updated_at
        FROM users_legacy
        WHERE first_name IS NOT NULL OR last_name IS NOT NULL
        """
    )
    
    # Migrate roles
    op.execute(
        """
        INSERT INTO user_roles (user_id, role, granted_at)
        SELECT id, role, created_at
        FROM users_legacy
        WHERE role IS NOT NULL
        """
    )
    
    # Create default preferences for all users
    op.execute(
        """
        INSERT INTO user_preferences (user_id)
        SELECT id FROM users_legacy
        """
    )
    
    # Create default security settings for all users
    op.execute(
        """
        INSERT INTO user_security (user_id)
        SELECT id FROM users_legacy
        """
    )
    
    # Update admin_users foreign key to reference new users table
    op.drop_constraint("fk_admin_users_user_id_users", "admin_users", type_="foreignkey")
    op.create_foreign_key(
        op.f("fk_admin_users_user_id_users"),
        "admin_users",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE"
    )


def downgrade() -> None:
    """Revert to monolithic users table."""
    
    # Drop foreign key from admin_users
    op.drop_constraint(op.f("fk_admin_users_user_id_users"), "admin_users", type_="foreignkey")
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_users_updated_at ON users;")
    op.execute("DROP TRIGGER IF EXISTS update_user_profiles_updated_at ON user_profiles;")
    op.execute("DROP TRIGGER IF EXISTS update_user_addresses_updated_at ON user_addresses;")
    op.execute("DROP TRIGGER IF EXISTS update_user_preferences_updated_at ON user_preferences;")
    op.execute("DROP TRIGGER IF EXISTS update_user_security_updated_at ON user_security;")
    
    # Drop tables
    op.drop_table("user_security")
    op.drop_table("user_preferences")
    op.drop_table("user_phones")
    op.drop_table("user_addresses")
    op.drop_table("user_profiles")
    op.drop_table("user_roles")
    op.drop_table("users")
    
    # Restore original users table
    op.rename_table("users_legacy", "users")
    
    # Restore admin_users foreign key
    op.create_foreign_key(
        "fk_admin_users_user_id_users",
        "admin_users",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE"
    )