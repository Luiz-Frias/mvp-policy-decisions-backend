"""Add missing OAuth2 tables.

Revision ID: 009
Revises: 008
Create Date: 2025-07-09

This migration creates the missing OAuth2 tables that are referenced in the code:
1. oauth2_refresh_tokens - For refresh token storage and rotation
2. oauth2_token_logs - For token usage audit logging
3. oauth2_authorization_codes - For authorization code flow
4. oauth2_access_tokens - For access token storage (if needed)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: str = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create missing OAuth2 tables."""

    # Create OAuth2 refresh tokens table
    op.create_table(
        "oauth2_refresh_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("access_token_hash", sa.String(255), nullable=True),
        # Token metadata
        sa.Column(
            "scope",
            sa.String(500),
            nullable=False,
            server_default="",
            comment="Space-separated scopes",
        ),
        sa.Column(
            "token_type",
            sa.String(20),
            nullable=False,
            server_default="Bearer",
        ),
        # Token lifecycle
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "revoke_reason",
            sa.String(100),
            nullable=True,
            comment="Reason for token revocation",
        ),
        # Token rotation
        sa.Column(
            "parent_token_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="For token rotation tracking",
        ),
        sa.Column(
            "used_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When this refresh token was used",
        ),
        # Security fields
        sa.Column(
            "ip_address",
            postgresql.INET(),
            nullable=True,
            comment="IP address when token was issued",
        ),
        sa.Column(
            "user_agent",
            sa.Text(),
            nullable=True,
            comment="User agent when token was issued",
        ),
        # Audit fields
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
            ["client_id"],
            ["oauth2_clients.id"],
            name=op.f("fk_oauth2_refresh_tokens_client_id_oauth2_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_oauth2_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_token_id"],
            ["oauth2_refresh_tokens.id"],
            name=op.f("fk_oauth2_refresh_tokens_parent_token_id_oauth2_refresh_tokens"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth2_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_oauth2_refresh_tokens_token_hash")),
        sa.CheckConstraint(
            "token_type IN ('Bearer', 'JWT')",
            name=op.f("ck_oauth2_refresh_tokens_token_type"),
        ),
        sa.CheckConstraint(
            "expires_at > issued_at",
            name=op.f("ck_oauth2_refresh_tokens_expires_after_issued"),
        ),
    )

    # Create indexes for refresh tokens
    op.create_index(
        op.f("ix_oauth2_refresh_tokens_client_id"),
        "oauth2_refresh_tokens",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth2_refresh_tokens_user_id"),
        "oauth2_refresh_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth2_refresh_tokens_expires_at"),
        "oauth2_refresh_tokens",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth2_refresh_tokens_revoked_at"),
        "oauth2_refresh_tokens",
        ["revoked_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth2_refresh_tokens_access_token_hash"),
        "oauth2_refresh_tokens",
        ["access_token_hash"],
        unique=False,
    )

    # Create OAuth2 token logs table for audit purposes
    op.create_table(
        "oauth2_token_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        # Token information
        sa.Column("token_type", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("scope", sa.String(500), nullable=False),
        # Action details
        sa.Column(
            "action",
            sa.String(50),
            nullable=False,
            comment="issued, refreshed, revoked, expired, used",
        ),
        sa.Column(
            "grant_type",
            sa.String(50),
            nullable=True,
            comment="authorization_code, refresh_token, client_credentials, password",
        ),
        # Request details
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
        # Security information
        sa.Column(
            "risk_score",
            sa.Numeric(3, 2),
            nullable=True,
            comment="Risk score from 0.00 to 1.00",
        ),
        sa.Column(
            "security_flags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="[]",
            comment="Array of security flags or alerts",
        ),
        # Timing information
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Token expiration time",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["oauth2_clients.id"],
            name=op.f("fk_oauth2_token_logs_client_id_oauth2_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_oauth2_token_logs_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth2_token_logs")),
        sa.CheckConstraint(
            "token_type IN ('access_token', 'refresh_token', 'authorization_code')",
            name=op.f("ck_oauth2_token_logs_token_type"),
        ),
        sa.CheckConstraint(
            "action IN ('issued', 'refreshed', 'revoked', 'expired', 'used', 'introspected')",
            name=op.f("ck_oauth2_token_logs_action"),
        ),
        sa.CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 1)",
            name=op.f("ck_oauth2_token_logs_risk_score_range"),
        ),
    )

    # Create indexes for token logs
    op.create_index(
        op.f("ix_oauth2_token_logs_client_id"),
        "oauth2_token_logs",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth2_token_logs_user_id"),
        "oauth2_token_logs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth2_token_logs_action"),
        "oauth2_token_logs",
        ["action"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth2_token_logs_token_type"),
        "oauth2_token_logs",
        ["token_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth2_token_logs_created_at"),
        "oauth2_token_logs",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth2_token_logs_token_hash"),
        "oauth2_token_logs",
        ["token_hash"],
        unique=False,
    )
    
    # Composite index for common queries
    op.create_index(
        "ix_oauth2_token_logs_client_action_created",
        "oauth2_token_logs",
        ["client_id", "action", "created_at"],
        unique=False,
    )

    # Create OAuth2 authorization codes table
    op.create_table(
        "oauth2_authorization_codes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("redirect_uri", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(500), nullable=False),
        # PKCE support
        sa.Column(
            "code_challenge",
            sa.String(255),
            nullable=True,
            comment="PKCE code challenge",
        ),
        sa.Column(
            "code_challenge_method",
            sa.String(20),
            nullable=True,
            comment="PKCE code challenge method (plain or S256)",
        ),
        # State parameter
        sa.Column(
            "state",
            sa.String(255),
            nullable=True,
            comment="OAuth2 state parameter",
        ),
        # Nonce for OpenID Connect
        sa.Column(
            "nonce",
            sa.String(255),
            nullable=True,
            comment="OpenID Connect nonce",
        ),
        # Timing
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "used_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the code was exchanged for tokens",
        ),
        # Security
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["oauth2_clients.id"],
            name=op.f("fk_oauth2_authorization_codes_client_id_oauth2_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_oauth2_authorization_codes_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth2_authorization_codes")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_oauth2_authorization_codes_code_hash")),
        sa.CheckConstraint(
            "code_challenge_method IS NULL OR code_challenge_method IN ('plain', 'S256')",
            name=op.f("ck_oauth2_authorization_codes_challenge_method"),
        ),
        sa.CheckConstraint(
            "expires_at > issued_at",
            name=op.f("ck_oauth2_authorization_codes_expires_after_issued"),
        ),
    )

    # Create indexes for authorization codes
    op.create_index(
        op.f("ix_oauth2_authorization_codes_client_id"),
        "oauth2_authorization_codes",
        ["client_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth2_authorization_codes_user_id"),
        "oauth2_authorization_codes",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth2_authorization_codes_expires_at"),
        "oauth2_authorization_codes",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_oauth2_authorization_codes_used_at"),
        "oauth2_authorization_codes",
        ["used_at"],
        unique=False,
    )

    # Add update triggers for tables that need them
    for table in ["oauth2_refresh_tokens"]:
        op.execute(
            f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
            """
        )

    # Create function to automatically clean up expired tokens
    op.execute(
        """
        CREATE OR REPLACE FUNCTION cleanup_expired_oauth2_tokens()
        RETURNS INTEGER AS $$
        DECLARE
            deleted_count INTEGER := 0;
        BEGIN
            -- Delete expired authorization codes (older than 24 hours)
            DELETE FROM oauth2_authorization_codes
            WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '24 hours';
            
            GET DIAGNOSTICS deleted_count = ROW_COUNT;
            
            -- Delete expired refresh tokens (keeping recent ones for audit)
            DELETE FROM oauth2_refresh_tokens
            WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '7 days';
            
            GET DIAGNOSTICS deleted_count = deleted_count + ROW_COUNT;
            
            -- Archive old token logs (older than 90 days)
            DELETE FROM oauth2_token_logs
            WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '90 days';
            
            GET DIAGNOSTICS deleted_count = deleted_count + ROW_COUNT;
            
            RETURN deleted_count;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # Create function to revoke all tokens for a user
    op.execute(
        """
        CREATE OR REPLACE FUNCTION revoke_user_tokens(
            p_user_id UUID,
            p_reason TEXT DEFAULT 'user_revoked'
        )
        RETURNS INTEGER AS $$
        DECLARE
            revoked_count INTEGER := 0;
        BEGIN
            -- Revoke all active refresh tokens for the user
            UPDATE oauth2_refresh_tokens
            SET revoked_at = CURRENT_TIMESTAMP,
                revoke_reason = p_reason,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = p_user_id
            AND revoked_at IS NULL;
            
            GET DIAGNOSTICS revoked_count = ROW_COUNT;
            
            -- Log the revocation
            INSERT INTO oauth2_token_logs (
                client_id, user_id, token_type, token_hash, scope, action,
                ip_address, user_agent, created_at
            )
            SELECT 
                client_id, user_id, 'refresh_token', token_hash, scope, 'revoked',
                ip_address, user_agent, CURRENT_TIMESTAMP
            FROM oauth2_refresh_tokens
            WHERE user_id = p_user_id
            AND revoked_at = CURRENT_TIMESTAMP;
            
            RETURN revoked_count;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    """Drop OAuth2 tables and related objects."""
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_oauth2_refresh_tokens_updated_at ON oauth2_refresh_tokens;")
    
    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS cleanup_expired_oauth2_tokens();")
    op.execute("DROP FUNCTION IF EXISTS revoke_user_tokens(UUID, TEXT);")
    
    # Drop tables in reverse order
    op.drop_table("oauth2_authorization_codes")
    op.drop_table("oauth2_token_logs")
    op.drop_table("oauth2_refresh_tokens")