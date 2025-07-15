"""Add users compatibility view for backward compatibility.

Revision ID: 012
Revises: 011
Create Date: 2025-07-14

This migration creates a view that makes the new modular tables
appear as the old monolithic users table for backward compatibility.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: str = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create users compatibility view."""
    
    # Create a view that looks like the old users table
    op.execute(
        """
        CREATE OR REPLACE VIEW users_compat AS
        SELECT 
            u.id,
            u.email,
            u.password_hash,
            up.first_name,
            up.last_name,
            ur.role,
            u.is_active,
            u.last_login_at,
            u.failed_login_attempts,
            u.created_at,
            u.updated_at
        FROM users u
        LEFT JOIN user_profiles up ON u.id = up.user_id
        LEFT JOIN user_roles ur ON u.id = ur.user_id AND ur.is_active = true
        """
    )
    
    # Add comment to the view
    op.execute(
        "COMMENT ON VIEW users_compat IS 'Compatibility view that mimics the old monolithic users table structure'"
    )


def downgrade() -> None:
    """Drop users compatibility view."""
    
    # Drop view
    op.execute("DROP VIEW IF EXISTS users_compat")