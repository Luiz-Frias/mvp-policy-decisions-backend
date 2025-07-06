"""Add users and quote system tables.

Revision ID: 002
Revises: 001
Create Date: 2025-07-05

This migration creates:
1. Users table for authentication and audit trails
2. Comprehensive quote system tables with versioning
3. All necessary indexes and constraints
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create users and quote system tables."""
    
    # Create users table first (referenced by many other tables)
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="agent"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.CheckConstraint(
            "role IN ('agent', 'underwriter', 'admin', 'system')",
            name=op.f("ck_users_role"),
        ),
    )
    
    # Create indexes for users
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)
    op.create_index(op.f("ix_users_is_active"), "users", ["is_active"], unique=False)
    
    # Create comprehensive quotes table
    op.create_table(
        "quotes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("quote_number", sa.String(20), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="draft",
        ),
        # Quote data fields
        sa.Column("product_type", sa.String(20), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("zip_code", sa.String(10), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        # Pricing fields
        sa.Column("base_premium", sa.Numeric(10, 2), nullable=True),
        sa.Column("total_premium", sa.Numeric(10, 2), nullable=True),
        sa.Column("monthly_premium", sa.Numeric(10, 2), nullable=True),
        # Complex data as JSONB
        sa.Column(
            "vehicle_info",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Vehicle details for auto quotes",
        ),
        sa.Column(
            "property_info",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Property details for home quotes",
        ),
        sa.Column(
            "drivers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="[]",
            comment="Array of driver information",
        ),
        sa.Column(
            "coverage_selections",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
        ),
        sa.Column(
            "discounts_applied",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="[]",
        ),
        sa.Column(
            "surcharges_applied",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="[]",
        ),
        sa.Column(
            "rating_factors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
        ),
        # AI and analytics fields
        sa.Column("ai_risk_score", sa.Numeric(3, 2), nullable=True),
        sa.Column(
            "ai_risk_factors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="[]",
        ),
        sa.Column("conversion_probability", sa.Numeric(3, 2), nullable=True),
        # Metadata fields
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "parent_quote_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="For quote versioning",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Quote expiration timestamp",
        ),
        sa.Column(
            "converted_to_policy_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "declined_reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="[]",
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
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        # Constraints
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_quotes_customer_id_customers"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_quote_id"],
            ["quotes.id"],
            name=op.f("fk_quotes_parent_quote_id_quotes"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["converted_to_policy_id"],
            ["policies.id"],
            name=op.f("fk_quotes_converted_to_policy_id_policies"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_quotes_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_quotes_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotes")),
        sa.UniqueConstraint("quote_number", name=op.f("uq_quotes_quote_number")),
        sa.CheckConstraint(
            "status IN ('draft', 'calculating', 'quoted', 'expired', 'bound', 'declined')",
            name=op.f("ck_quotes_status"),
        ),
        sa.CheckConstraint(
            "product_type IN ('auto', 'home', 'renters', 'life')",
            name=op.f("ck_quotes_product_type"),
        ),
        sa.CheckConstraint(
            "LENGTH(state) = 2",
            name=op.f("ck_quotes_state_length"),
        ),
        sa.CheckConstraint(
            "ai_risk_score >= 0 AND ai_risk_score <= 1",
            name=op.f("ck_quotes_ai_risk_score_range"),
        ),
        sa.CheckConstraint(
            "conversion_probability >= 0 AND conversion_probability <= 1",
            name=op.f("ck_quotes_conversion_probability_range"),
        ),
        sa.CheckConstraint(
            "base_premium >= 0",
            name=op.f("ck_quotes_base_premium_positive"),
        ),
        sa.CheckConstraint(
            "total_premium >= 0",
            name=op.f("ck_quotes_total_premium_positive"),
        ),
        sa.CheckConstraint(
            "monthly_premium >= 0",
            name=op.f("ck_quotes_monthly_premium_positive"),
        ),
    )
    
    # Create comprehensive indexes for quotes
    op.create_index(op.f("ix_quotes_customer_id"), "quotes", ["customer_id"], unique=False)
    op.create_index(op.f("ix_quotes_status"), "quotes", ["status"], unique=False)
    op.create_index(op.f("ix_quotes_quote_number"), "quotes", ["quote_number"], unique=False)
    op.create_index(op.f("ix_quotes_expires_at"), "quotes", ["expires_at"], unique=False)
    op.create_index(
        op.f("ix_quotes_state_product"),
        "quotes",
        ["state", "product_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_quotes_created_at"),
        "quotes",
        ["created_at"],
        unique=False,
    )
    
    # GIN indexes for JSONB columns
    op.create_index(
        "ix_quotes_vehicle_info_gin",
        "quotes",
        ["vehicle_info"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_quotes_coverage_selections_gin",
        "quotes",
        ["coverage_selections"],
        unique=False,
        postgresql_using="gin",
    )
    
    # Composite index for common queries
    op.create_index(
        "ix_quotes_customer_status_created",
        "quotes",
        ["customer_id", "status", "created_at"],
        unique=False,
    )
    
    # Add update trigger to quotes table
    op.execute(
        """
        CREATE TRIGGER update_quotes_updated_at
        BEFORE UPDATE ON quotes
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
    )
    
    # Add update trigger to users table
    op.execute(
        """
        CREATE TRIGGER update_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
    )
    
    # Create quote number sequence
    op.execute(
        """
        CREATE SEQUENCE quote_number_seq
        START WITH 1000000
        INCREMENT BY 1
        NO MAXVALUE
        CACHE 1;
        """
    )
    
    # Create function to generate quote numbers
    op.execute(
        """
        CREATE OR REPLACE FUNCTION generate_quote_number()
        RETURNS TEXT AS $$
        DECLARE
            year_part TEXT;
            seq_part TEXT;
        BEGIN
            year_part := TO_CHAR(CURRENT_DATE, 'YYYY');
            seq_part := LPAD(nextval('quote_number_seq')::TEXT, 7, '0');
            RETURN 'QUOT-' || year_part || '-' || seq_part;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    """Drop quotes and users tables and related objects."""
    
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_quotes_updated_at ON quotes;")
    op.execute("DROP TRIGGER IF EXISTS update_users_updated_at ON users;")
    
    # Drop function and sequence
    op.execute("DROP FUNCTION IF EXISTS generate_quote_number();")
    op.execute("DROP SEQUENCE IF EXISTS quote_number_seq;")
    
    # Drop tables
    op.drop_table("quotes")
    op.drop_table("users")