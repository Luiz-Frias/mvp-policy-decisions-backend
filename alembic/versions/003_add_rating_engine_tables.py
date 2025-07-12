"""Add rating engine tables.

Revision ID: 003
Revises: 002
Create Date: 2025-07-05

This migration creates:
1. Rate tables for base rates by state/product/coverage
2. Discount rules with eligibility and stacking logic
3. Surcharge rules for risk factors
4. Territory factors for ZIP-based rating
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create rating engine tables."""

    # Create rate tables for base rates
    op.create_table(
        "rate_tables",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("product_type", sa.String(20), nullable=False),
        sa.Column("coverage_type", sa.String(50), nullable=False),
        # Rate information
        sa.Column(
            "base_rate",
            sa.Numeric(8, 6),
            nullable=False,
            comment="Base rate multiplier",
        ),
        sa.Column(
            "min_premium",
            sa.Numeric(10, 2),
            nullable=True,
            comment="Minimum premium amount",
        ),
        sa.Column(
            "max_premium",
            sa.Numeric(10, 2),
            nullable=True,
            comment="Maximum premium amount",
        ),
        # Factors as JSONB for flexibility
        sa.Column(
            "territory_factors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
            comment="ZIP-based multipliers",
        ),
        sa.Column(
            "vehicle_factors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
            comment="Make/model/year multipliers",
        ),
        sa.Column(
            "driver_factors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
            comment="Age/experience multipliers",
        ),
        sa.Column(
            "credit_factors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
            comment="Credit score tier multipliers",
        ),
        # Metadata
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column(
            "filing_id",
            sa.String(50),
            nullable=True,
            comment="State regulatory filing reference",
        ),
        sa.Column("approved_by", sa.String(100), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate_tables")),
        sa.UniqueConstraint(
            "state",
            "product_type",
            "coverage_type",
            "effective_date",
            name=op.f("uq_rate_tables_state_product_coverage_date"),
        ),
        sa.CheckConstraint(
            "LENGTH(state) = 2",
            name=op.f("ck_rate_tables_state_length"),
        ),
        sa.CheckConstraint(
            "product_type IN ('auto', 'home', 'renters', 'life')",
            name=op.f("ck_rate_tables_product_type"),
        ),
        sa.CheckConstraint(
            "base_rate > 0",
            name=op.f("ck_rate_tables_base_rate_positive"),
        ),
        sa.CheckConstraint(
            "min_premium >= 0",
            name=op.f("ck_rate_tables_min_premium_positive"),
        ),
        sa.CheckConstraint(
            "max_premium >= 0",
            name=op.f("ck_rate_tables_max_premium_positive"),
        ),
        sa.CheckConstraint(
            "min_premium <= max_premium OR max_premium IS NULL OR min_premium IS NULL",
            name=op.f("ck_rate_tables_min_max_premium_order"),
        ),
    )

    # Create indexes for rate tables
    op.create_index(
        op.f("ix_rate_tables_state_product"),
        "rate_tables",
        ["state", "product_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_rate_tables_effective_date"),
        "rate_tables",
        ["effective_date"],
        unique=False,
    )
    op.create_index(
        "ix_rate_tables_state_product_coverage_date",
        "rate_tables",
        ["state", "product_type", "coverage_type", "effective_date"],
        unique=False,
    )

    # Create discount rules table
    op.create_table(
        "discount_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Applicability
        sa.Column(
            "product_types",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
            comment="Array of applicable products",
        ),
        sa.Column(
            "states",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
            comment="Array of applicable states",
        ),
        # Discount calculation
        sa.Column("discount_type", sa.String(20), nullable=False),
        sa.Column("discount_value", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "max_discount_amount",
            sa.Numeric(10, 2),
            nullable=True,
            comment="Maximum discount cap",
        ),
        # Rules and configuration
        sa.Column(
            "eligibility_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
            comment="Eligibility criteria",
        ),
        sa.Column(
            "stackable",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Can be combined with other discounts",
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default="100",
            comment="Application order (lower = earlier)",
        ),
        # Validity period
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discount_rules")),
        sa.UniqueConstraint("code", name=op.f("uq_discount_rules_code")),
        sa.CheckConstraint(
            "discount_type IN ('percentage', 'fixed')",
            name=op.f("ck_discount_rules_discount_type"),
        ),
        sa.CheckConstraint(
            "discount_value > 0",
            name=op.f("ck_discount_rules_discount_value_positive"),
        ),
        sa.CheckConstraint(
            "max_discount_amount >= 0",
            name=op.f("ck_discount_rules_max_discount_amount_positive"),
        ),
    )

    # Create indexes for discount rules
    op.create_index(
        op.f("ix_discount_rules_code"),
        "discount_rules",
        ["code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_discount_rules_effective_date"),
        "discount_rules",
        ["effective_date"],
        unique=False,
    )

    # Create surcharge rules table
    op.create_table(
        "surcharge_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # Applicability
        sa.Column(
            "product_types",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
            comment="Array of applicable products",
        ),
        sa.Column(
            "states",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
            comment="Array of applicable states",
        ),
        # Surcharge calculation
        sa.Column("surcharge_type", sa.String(20), nullable=False),
        sa.Column("surcharge_value", sa.Numeric(10, 2), nullable=False),
        sa.Column(
            "max_surcharge_amount",
            sa.Numeric(10, 2),
            nullable=True,
            comment="Maximum surcharge cap",
        ),
        # Rules and configuration
        sa.Column(
            "trigger_conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
            comment="Conditions that trigger surcharge",
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default="100",
            comment="Application order (lower = earlier)",
        ),
        # Validity period
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_surcharge_rules")),
        sa.UniqueConstraint("code", name=op.f("uq_surcharge_rules_code")),
        sa.CheckConstraint(
            "surcharge_type IN ('percentage', 'fixed')",
            name=op.f("ck_surcharge_rules_surcharge_type"),
        ),
        sa.CheckConstraint(
            "surcharge_value > 0",
            name=op.f("ck_surcharge_rules_surcharge_value_positive"),
        ),
        sa.CheckConstraint(
            "max_surcharge_amount >= 0",
            name=op.f("ck_surcharge_rules_max_surcharge_amount_positive"),
        ),
    )

    # Create indexes for surcharge rules
    op.create_index(
        op.f("ix_surcharge_rules_code"),
        "surcharge_rules",
        ["code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_surcharge_rules_effective_date"),
        "surcharge_rules",
        ["effective_date"],
        unique=False,
    )

    # Create territory factors table
    op.create_table(
        "territory_factors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("zip_code", sa.String(10), nullable=False),
        sa.Column("product_type", sa.String(20), nullable=False),
        # Factor values
        sa.Column(
            "base_factor",
            sa.Numeric(5, 4),
            nullable=False,
            server_default="1.0000",
            comment="Base territory multiplier",
        ),
        sa.Column(
            "loss_ratio_factor",
            sa.Numeric(5, 4),
            nullable=True,
            comment="Historical loss ratio adjustment",
        ),
        sa.Column(
            "catastrophe_factor",
            sa.Numeric(5, 4),
            nullable=True,
            comment="Natural disaster risk adjustment",
        ),
        # Metadata
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_territory_factors")),
        sa.UniqueConstraint(
            "state",
            "zip_code",
            "product_type",
            "effective_date",
            name=op.f("uq_territory_factors_state_zip_product_date"),
        ),
        sa.CheckConstraint(
            "LENGTH(state) = 2",
            name=op.f("ck_territory_factors_state_length"),
        ),
        sa.CheckConstraint(
            "product_type IN ('auto', 'home', 'renters', 'life')",
            name=op.f("ck_territory_factors_product_type"),
        ),
        sa.CheckConstraint(
            "base_factor > 0",
            name=op.f("ck_territory_factors_base_factor_positive"),
        ),
        sa.CheckConstraint(
            "loss_ratio_factor > 0",
            name=op.f("ck_territory_factors_loss_ratio_factor_positive"),
        ),
        sa.CheckConstraint(
            "catastrophe_factor > 0",
            name=op.f("ck_territory_factors_catastrophe_factor_positive"),
        ),
    )

    # Create indexes for territory factors
    op.create_index(
        op.f("ix_territory_factors_state_zip"),
        "territory_factors",
        ["state", "zip_code"],
        unique=False,
    )
    op.create_index(
        op.f("ix_territory_factors_zip_code"),
        "territory_factors",
        ["zip_code"],
        unique=False,
    )
    op.create_index(
        "ix_territory_factors_state_zip_product_date",
        "territory_factors",
        ["state", "zip_code", "product_type", "effective_date"],
        unique=False,
    )

    # Add update triggers
    op.execute(
        """
        CREATE TRIGGER update_rate_tables_updated_at
        BEFORE UPDATE ON rate_tables
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
        """
    )

    # Create function to validate rate table factors
    op.execute(
        """
        CREATE OR REPLACE FUNCTION validate_rate_factors(factors JSONB)
        RETURNS BOOLEAN AS $$
        BEGIN
            -- Ensure all factor values are positive numbers
            IF factors IS NULL THEN
                RETURN TRUE;
            END IF;

            -- Check if all values in the JSONB are numeric and positive
            RETURN NOT EXISTS (
                SELECT 1
                FROM jsonb_each(factors)
                WHERE jsonb_typeof(value) != 'number'
                   OR (value::TEXT)::NUMERIC <= 0
            );
        END;
        $$ LANGUAGE plpgsql IMMUTABLE;
        """
    )

    # Add validation constraints for JSONB factors
    op.create_check_constraint(
        "ck_rate_tables_territory_factors_valid",
        "rate_tables",
        sa.text("validate_rate_factors(territory_factors)"),
    )
    op.create_check_constraint(
        "ck_rate_tables_vehicle_factors_valid",
        "rate_tables",
        sa.text("validate_rate_factors(vehicle_factors)"),
    )
    op.create_check_constraint(
        "ck_rate_tables_driver_factors_valid",
        "rate_tables",
        sa.text("validate_rate_factors(driver_factors)"),
    )
    op.create_check_constraint(
        "ck_rate_tables_credit_factors_valid",
        "rate_tables",
        sa.text("validate_rate_factors(credit_factors)"),
    )


def downgrade() -> None:
    """Drop rating engine tables and related objects."""

    # Drop constraints first
    op.drop_constraint("ck_rate_tables_territory_factors_valid", "rate_tables")
    op.drop_constraint("ck_rate_tables_vehicle_factors_valid", "rate_tables")
    op.drop_constraint("ck_rate_tables_driver_factors_valid", "rate_tables")
    op.drop_constraint("ck_rate_tables_credit_factors_valid", "rate_tables")

    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS update_rate_tables_updated_at ON rate_tables;")

    # Drop function
    op.execute("DROP FUNCTION IF EXISTS validate_rate_factors(JSONB);")

    # Drop tables
    op.drop_table("territory_factors")
    op.drop_table("surcharge_rules")
    op.drop_table("discount_rules")
    op.drop_table("rate_tables")
