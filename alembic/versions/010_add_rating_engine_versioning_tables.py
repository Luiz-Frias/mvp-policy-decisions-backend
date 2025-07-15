"""Add rating engine versioning tables.

Revision ID: 010
Revises: 009
Create Date: 2025-07-14

This migration creates the versioning tables expected by the rating engine:
1. rate_table_versions - For versioned rate table management
2. discount_configurations - For discount rule configurations  
3. surcharge_configurations - For surcharge rule configurations
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: str = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create rating engine versioning tables."""
    
    # Create rate_table_versions table
    op.create_table(
        "rate_table_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("product_type", sa.String(20), nullable=False),
        sa.Column("coverage_type", sa.String(50), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column(
            "rate_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Complete rate structure including base rates and factors",
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("approved_by", sa.String(100), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("filing_reference", sa.String(100), nullable=True),
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
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("updated_by", sa.String(100), nullable=True),
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate_table_versions")),
        sa.UniqueConstraint(
            "state",
            "product_type", 
            "coverage_type",
            "version",
            name=op.f("uq_rate_table_versions_state_product_coverage_version"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'pending', 'approved', 'active', 'archived')",
            name=op.f("ck_rate_table_versions_status"),
        ),
    )
    
    # Create indexes for rate_table_versions
    op.create_index(
        op.f("ix_rate_table_versions_state_product"),
        "rate_table_versions",
        ["state", "product_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rate_table_versions_status"),
        "rate_table_versions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rate_table_versions_effective_date"),
        "rate_table_versions",
        ["effective_date"],
        unique=False,
    )
    
    # Create discount_configurations table
    op.create_table(
        "discount_configurations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("discount_type", sa.String(20), nullable=False),
        sa.Column(
            "configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Complete discount configuration including rules and values",
        ),
        sa.Column(
            "applicable_states",
            postgresql.ARRAY(sa.String(2)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "applicable_products", 
            postgresql.ARRAY(sa.String(20)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discount_configurations")),
        sa.UniqueConstraint("code", name=op.f("uq_discount_configurations_code")),
        sa.CheckConstraint(
            "discount_type IN ('percentage', 'fixed', 'tiered')",
            name=op.f("ck_discount_configurations_discount_type"),
        ),
    )
    
    # Create indexes for discount_configurations
    op.create_index(
        op.f("ix_discount_configurations_code"),
        "discount_configurations",
        ["code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_discount_configurations_is_active"),
        "discount_configurations",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_discount_configurations_effective_date"),
        "discount_configurations",
        ["effective_date"],
        unique=False,
    )
    
    # Create surcharge_configurations table
    op.create_table(
        "surcharge_configurations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("surcharge_type", sa.String(20), nullable=False),
        sa.Column(
            "configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Complete surcharge configuration including rules and values",
        ),
        sa.Column(
            "applicable_states",
            postgresql.ARRAY(sa.String(2)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "applicable_products",
            postgresql.ARRAY(sa.String(20)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_surcharge_configurations")),
        sa.UniqueConstraint("code", name=op.f("uq_surcharge_configurations_code")),
        sa.CheckConstraint(
            "surcharge_type IN ('percentage', 'fixed', 'tiered')",
            name=op.f("ck_surcharge_configurations_surcharge_type"),
        ),
    )
    
    # Create indexes for surcharge_configurations
    op.create_index(
        op.f("ix_surcharge_configurations_code"),
        "surcharge_configurations",
        ["code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_surcharge_configurations_is_active"),
        "surcharge_configurations",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_surcharge_configurations_effective_date"),
        "surcharge_configurations",
        ["effective_date"],
        unique=False,
    )
    
    # Add update triggers (execute separately to avoid prepared statement error)
    op.execute(
        """
        CREATE TRIGGER update_rate_table_versions_updated_at
        BEFORE UPDATE ON rate_table_versions
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
    )
    
    op.execute(
        """
        CREATE TRIGGER update_discount_configurations_updated_at
        BEFORE UPDATE ON discount_configurations
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
    )
    
    op.execute(
        """
        CREATE TRIGGER update_surcharge_configurations_updated_at
        BEFORE UPDATE ON surcharge_configurations
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
    )


def downgrade() -> None:
    """Drop rating engine versioning tables."""
    
    # Drop triggers
    op.execute(
        """
        DROP TRIGGER IF EXISTS update_rate_table_versions_updated_at ON rate_table_versions;
        DROP TRIGGER IF EXISTS update_discount_configurations_updated_at ON discount_configurations;
        DROP TRIGGER IF EXISTS update_surcharge_configurations_updated_at ON surcharge_configurations;
        """
    )
    
    # Drop tables
    op.drop_table("surcharge_configurations")
    op.drop_table("discount_configurations")
    op.drop_table("rate_table_versions")