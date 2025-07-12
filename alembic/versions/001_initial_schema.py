"""Initial database schema.

Revision ID: 001
Revises:
Create Date: 2025-07-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create initial database schema."""
    # Create customers table
    op.create_table(
        "customers",
        sa.Column(
            "id",
            sa.String(36),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column(
            "data",
            sa.Text(),
            nullable=False,
            server_default="{}",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")),
        sa.UniqueConstraint("external_id", name=op.f("uq_customers_external_id")),
    )

    # Create index on external_id for fast lookups
    op.create_index(
        op.f("ix_customers_external_id"),
        "customers",
        ["external_id"],
        unique=False,
    )

    # Create GIN index on JSONB data for efficient queries
    op.create_index(
        "ix_customers_data_gin",
        "customers",
        ["data"],
        unique=False,
        postgresql_using="gin",
    )

    # Create policies table
    op.create_table(
        "policies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("policy_number", sa.String(255), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            name=op.f("fk_policies_customer_id_customers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_policies")),
        sa.UniqueConstraint("policy_number", name=op.f("uq_policies_policy_number")),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'cancelled', 'expired', 'pending')",
            name=op.f("ck_policies_status"),
        ),
    )

    # Create indexes for policies
    op.create_index(
        op.f("ix_policies_policy_number"),
        "policies",
        ["policy_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_policies_customer_id"),
        "policies",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_policies_status"),
        "policies",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_policies_data_gin",
        "policies",
        ["data"],
        unique=False,
        postgresql_using="gin",
    )
    # Composite index for date range queries
    op.create_index(
        "ix_policies_dates",
        "policies",
        ["effective_date", "expiration_date"],
        unique=False,
    )

    # Create claims table
    op.create_table(
        "claims",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("claim_number", sa.String(255), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("status", sa.String(50), nullable=False, server_default="submitted"),
        sa.Column("amount_claimed", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount_approved", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["policies.id"],
            name=op.f("fk_claims_policy_id_policies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_claims")),
        sa.UniqueConstraint("claim_number", name=op.f("uq_claims_claim_number")),
        sa.CheckConstraint(
            "status IN ('submitted', 'under_review', 'approved', 'denied', 'withdrawn', 'closed')",
            name=op.f("ck_claims_status"),
        ),
        sa.CheckConstraint(
            "amount_claimed >= 0", name=op.f("ck_claims_amount_claimed_positive")
        ),
        sa.CheckConstraint(
            "amount_approved >= 0", name=op.f("ck_claims_amount_approved_positive")
        ),
    )

    # Create indexes for claims
    op.create_index(
        op.f("ix_claims_claim_number"),
        "claims",
        ["claim_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_claims_policy_id"),
        "claims",
        ["policy_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_claims_status"),
        "claims",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_claims_data_gin",
        "claims",
        ["data"],
        unique=False,
        postgresql_using="gin",
    )
    # Composite index for status and date queries
    op.create_index(
        "ix_claims_status_submitted",
        "claims",
        ["status", "submitted_at"],
        unique=False,
    )

    # Create update timestamp triggers
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """
    )

    # Apply triggers to all tables
    for table in ["customers", "policies", "claims"]:
        op.execute(
            f"""
            CREATE TRIGGER update_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
            """
        )


def downgrade() -> None:
    """Drop all tables and functions."""
    # Drop triggers first
    for table in ["customers", "policies", "claims"]:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")

    # Drop function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")

    # Drop tables (in reverse order due to foreign keys)
    op.drop_table("claims")
    op.drop_table("policies")
    op.drop_table("customers")
