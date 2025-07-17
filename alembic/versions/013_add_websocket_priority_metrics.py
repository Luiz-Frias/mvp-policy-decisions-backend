"""Add missing websocket_priority_metrics table.

Revision ID: 013
Revises: 012
Create Date: 2025-07-15

This migration adds the websocket_priority_metrics table that was missing
from the original websocket performance tables migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: str = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create websocket_priority_metrics table."""
    
    # Create WebSocket priority metrics table
    op.create_table(
        "websocket_priority_metrics",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="When the metric was recorded",
        ),
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            comment="Priority level (low, normal, high, critical)",
        ),
        sa.Column(
            "total_sent",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="Total messages sent for this priority",
        ),
        sa.Column(
            "total_received",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="Total messages received for this priority",
        ),
        sa.Column(
            "avg_latency_ms",
            sa.Numeric(10, 3),
            nullable=False,
            server_default="0",
            comment="Average latency in milliseconds",
        ),
        sa.Column(
            "error_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of errors for this priority",
        ),
        sa.Column(
            "queue_depth",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Queue depth at time of recording",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_websocket_priority_metrics")),
    )
    
    # Create indexes for efficient querying
    op.create_index(
        op.f("ix_websocket_priority_metrics_timestamp"),
        "websocket_priority_metrics",
        ["timestamp"],
        unique=False,
    )
    
    op.create_index(
        op.f("ix_websocket_priority_metrics_priority"),
        "websocket_priority_metrics",
        ["priority"],
        unique=False,
    )
    
    # Composite index for time-series queries by priority
    op.create_index(
        "ix_websocket_priority_metrics_priority_timestamp",
        "websocket_priority_metrics",
        ["priority", "timestamp"],
        unique=False,
    )
    
    # Add check constraint for valid priority values
    op.create_check_constraint(
        op.f("ck_websocket_priority_metrics_priority"),
        "websocket_priority_metrics",
        sa.text("priority IN ('low', 'normal', 'high', 'critical')"),
    )


def downgrade() -> None:
    """Drop websocket_priority_metrics table."""
    op.drop_table("websocket_priority_metrics")