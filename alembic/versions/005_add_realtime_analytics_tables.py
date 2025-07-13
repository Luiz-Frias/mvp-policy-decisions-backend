"""Add real-time analytics tables.

Revision ID: 005
Revises: 004
Create Date: 2025-07-05

This migration creates:
1. WebSocket connections tracking for real-time features
2. Analytics events for dashboard metrics
3. Real-time notification system tables
4. Performance monitoring tables
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create real-time analytics tables."""

    # Create WebSocket connections tracking table
    op.create_table(
        "websocket_connections",
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="User associated with this connection",
        ),
        # Connection info
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="When the connection was established",
        ),
        sa.Column(
            "disconnected_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the connection was closed",
        ),
        sa.Column(
            "last_ping_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last heartbeat received",
        ),
        # Subscription management
        sa.Column(
            "subscribed_channels",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
            comment="Array of channel names this connection subscribes to",
        ),
        sa.Column(
            "connection_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
            comment="Additional connection metadata",
        ),
        # Client info
        sa.Column(
            "ip_address",
            postgresql.INET(),
            nullable=True,
            comment="Client IP address",
        ),
        sa.Column(
            "user_agent",
            sa.Text(),
            nullable=True,
            comment="Client user agent string",
        ),
        sa.Column(
            "client_version",
            sa.String(20),
            nullable=True,
            comment="WebSocket client library version",
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_websocket_connections_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("connection_id", name=op.f("pk_websocket_connections")),
        # Business rule: connection must have disconnected_at if not active
        sa.CheckConstraint(
            "(disconnected_at IS NULL AND last_ping_at IS NOT NULL) OR disconnected_at IS NOT NULL",
            name=op.f("ck_websocket_connections_lifecycle"),
        ),
    )

    # Create indexes for WebSocket connections
    op.create_index(
        op.f("ix_websocket_connections_user_id"),
        "websocket_connections",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_websocket_connections_connected_at"),
        "websocket_connections",
        ["connected_at"],
        unique=False,
    )
    # Index for finding active connections
    op.create_index(
        "ix_websocket_connections_active",
        "websocket_connections",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("disconnected_at IS NULL"),
    )

    # Create analytics events table for real-time dashboard
    op.create_table(
        "analytics_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Event classification
        sa.Column(
            "event_type",
            sa.String(50),
            nullable=False,
            comment="Type of event (quote_created, policy_bound, etc.)",
        ),
        sa.Column(
            "event_category",
            sa.String(50),
            nullable=False,
            comment="Category for grouping (conversion, underwriting, etc.)",
        ),
        sa.Column(
            "event_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
            comment="Event-specific data payload",
        ),
        # Context references
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="User who triggered the event",
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Session context for the event",
        ),
        sa.Column(
            "quote_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Related quote if applicable",
        ),
        sa.Column(
            "policy_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Related policy if applicable",
        ),
        # Metrics
        sa.Column(
            "value",
            sa.Numeric(10, 2),
            nullable=True,
            comment="Numeric value for the event (premium, score, etc.)",
        ),
        sa.Column(
            "duration_ms",
            sa.Integer(),
            nullable=True,
            comment="Duration in milliseconds for timed events",
        ),
        # Geo data for heat maps
        sa.Column(
            "state",
            sa.String(2),
            nullable=True,
            comment="State code for geographic analytics",
        ),
        sa.Column(
            "zip_code",
            sa.String(10),
            nullable=True,
            comment="ZIP code for detailed geographic analytics",
        ),
        # Timestamp
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="When the event occurred",
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_analytics_events_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["quote_id"],
            ["quotes.id"],
            name=op.f("fk_analytics_events_quote_id_quotes"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["policies.id"],
            name=op.f("fk_analytics_events_policy_id_policies"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_analytics_events")),
        sa.CheckConstraint(
            "event_type IN ('quote_started', 'quote_completed', 'quote_abandoned', "
            "'policy_bound', 'policy_cancelled', 'rate_lookup', 'document_generated', "
            "'ai_score_calculated', 'user_login', 'api_call', 'error_occurred')",
            name=op.f("ck_analytics_events_event_type"),
        ),
        sa.CheckConstraint(
            "event_category IN ('conversion', 'engagement', 'performance', "
            "'underwriting', 'system', 'security')",
            name=op.f("ck_analytics_events_event_category"),
        ),
        sa.CheckConstraint(
            "value >= 0",
            name=op.f("ck_analytics_events_value_positive"),
        ),
        sa.CheckConstraint(
            "duration_ms >= 0",
            name=op.f("ck_analytics_events_duration_positive"),
        ),
        sa.CheckConstraint(
            "LENGTH(state) = 2",
            name=op.f("ck_analytics_events_state_length"),
        ),
    )

    # Create comprehensive indexes for real-time queries
    op.create_index(
        op.f("ix_analytics_events_created_at"),
        "analytics_events",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_events_type_category"),
        "analytics_events",
        ["event_type", "event_category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_analytics_events_user_id"),
        "analytics_events",
        ["user_id"],
        unique=False,
    )
    # Composite index for time-series queries
    op.create_index(
        "ix_analytics_events_time_series",
        "analytics_events",
        ["event_type", "created_at"],
        unique=False,
    )
    # Geographic queries index
    op.create_index(
        "ix_analytics_events_geo",
        "analytics_events",
        ["state", "zip_code"],
        unique=False,
    )

    # Create notification queue table
    op.create_table(
        "notification_queue",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Notification details
        sa.Column(
            "notification_type",
            sa.String(50),
            nullable=False,
            comment="Type of notification",
        ),
        sa.Column(
            "priority",
            sa.String(20),
            nullable=False,
            server_default="normal",
            comment="Notification priority",
        ),
        sa.Column(
            "channel",
            sa.String(20),
            nullable=False,
            comment="Delivery channel",
        ),
        # Recipients
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Target user for the notification",
        ),
        sa.Column(
            "broadcast_channel",
            sa.String(50),
            nullable=True,
            comment="Broadcast channel name if not user-specific",
        ),
        # Content
        sa.Column(
            "title",
            sa.String(200),
            nullable=False,
            comment="Notification title",
        ),
        sa.Column(
            "message",
            sa.Text(),
            nullable=False,
            comment="Notification message body",
        ),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
            comment="Additional notification data",
        ),
        sa.Column(
            "action_url",
            sa.Text(),
            nullable=True,
            comment="URL for notification action",
        ),
        # Status tracking
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="Delivery status",
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of delivery attempts",
        ),
        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When notification was delivered",
        ),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When notification was read",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=True,
            comment="Error message if delivery failed",
        ),
        # Scheduling
        sa.Column(
            "scheduled_for",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When to send the notification",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the notification expires",
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
            name=op.f("fk_notification_queue_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification_queue")),
        sa.CheckConstraint(
            "notification_type IN ('quote_expiring', 'policy_renewal', 'payment_due', "
            "'claim_update', 'system_alert', 'marketing', 'agent_assignment')",
            name=op.f("ck_notification_queue_notification_type"),
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name=op.f("ck_notification_queue_priority"),
        ),
        sa.CheckConstraint(
            "channel IN ('websocket', 'email', 'sms', 'push', 'in_app')",
            name=op.f("ck_notification_queue_channel"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sending', 'delivered', 'failed', 'expired', 'cancelled')",
            name=op.f("ck_notification_queue_status"),
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name=op.f("ck_notification_queue_attempts_positive"),
        ),
        # Business rule: must have either user_id or broadcast_channel
        sa.CheckConstraint(
            "(user_id IS NOT NULL) OR (broadcast_channel IS NOT NULL)",
            name=op.f("ck_notification_queue_recipient_required"),
        ),
    )

    # Create indexes for notification queue
    op.create_index(
        op.f("ix_notification_queue_user_id"),
        "notification_queue",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_queue_status"),
        "notification_queue",
        ["status"],
        unique=False,
    )
    # Index for pending notifications
    op.create_index(
        "ix_notification_queue_pending",
        "notification_queue",
        ["scheduled_for", "status"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )

    # Create real-time metrics aggregation table
    op.create_table(
        "realtime_metrics",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Metric identification
        sa.Column(
            "metric_name",
            sa.String(100),
            nullable=False,
            comment="Name of the metric",
        ),
        sa.Column(
            "metric_type",
            sa.String(20),
            nullable=False,
            comment="Type of metric (counter, gauge, histogram)",
        ),
        sa.Column(
            "aggregation_period",
            sa.String(20),
            nullable=False,
            comment="Time period for aggregation",
        ),
        # Time window
        sa.Column(
            "period_start",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Start of the aggregation period",
        ),
        sa.Column(
            "period_end",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="End of the aggregation period",
        ),
        # Dimensions
        sa.Column(
            "dimensions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
            comment="Metric dimensions (state, product, etc.)",
        ),
        # Values
        sa.Column(
            "value",
            sa.Numeric(12, 4),
            nullable=False,
            comment="Metric value",
        ),
        sa.Column(
            "count",
            sa.Integer(),
            nullable=False,
            server_default="1",
            comment="Number of data points",
        ),
        sa.Column(
            "min_value",
            sa.Numeric(12, 4),
            nullable=True,
            comment="Minimum value in period",
        ),
        sa.Column(
            "max_value",
            sa.Numeric(12, 4),
            nullable=True,
            comment="Maximum value in period",
        ),
        sa.Column(
            "sum_value",
            sa.Numeric(15, 4),
            nullable=True,
            comment="Sum of values in period",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_realtime_metrics")),
        sa.UniqueConstraint(
            "metric_name",
            "aggregation_period",
            "period_start",
            "dimensions",
            name=op.f("uq_realtime_metrics_unique_metric"),
        ),
        sa.CheckConstraint(
            "metric_type IN ('counter', 'gauge', 'histogram', 'summary')",
            name=op.f("ck_realtime_metrics_metric_type"),
        ),
        sa.CheckConstraint(
            "aggregation_period IN ('minute', 'hour', 'day', 'week', 'month')",
            name=op.f("ck_realtime_metrics_aggregation_period"),
        ),
        sa.CheckConstraint(
            "period_end > period_start",
            name=op.f("ck_realtime_metrics_period_order"),
        ),
        sa.CheckConstraint(
            "count > 0",
            name=op.f("ck_realtime_metrics_count_positive"),
        ),
    )

    # Create indexes for metrics queries
    op.create_index(
        op.f("ix_realtime_metrics_metric_name"),
        "realtime_metrics",
        ["metric_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_realtime_metrics_period_start"),
        "realtime_metrics",
        ["period_start"],
        unique=False,
    )
    # Composite index for time-series queries
    op.create_index(
        "ix_realtime_metrics_time_series",
        "realtime_metrics",
        ["metric_name", "aggregation_period", "period_start"],
        unique=False,
    )

    # Add update triggers
    # Create triggers separately for asyncpg compatibility
    op.execute(
        """
        CREATE TRIGGER update_notification_queue_updated_at
        BEFORE UPDATE ON notification_queue
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column()
        """
    )
    
    op.execute(
        """
        CREATE TRIGGER update_realtime_metrics_updated_at
        BEFORE UPDATE ON realtime_metrics
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column()
        """
    )

    # Create function to clean up old connections
    op.execute(
        """
        CREATE OR REPLACE FUNCTION cleanup_stale_websocket_connections()
        RETURNS void AS $$
        BEGIN
            -- Mark connections as disconnected if no ping for 5 minutes
            UPDATE websocket_connections
            SET disconnected_at = CURRENT_TIMESTAMP
            WHERE disconnected_at IS NULL
              AND last_ping_at < CURRENT_TIMESTAMP - INTERVAL '5 minutes';
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # Create function to aggregate metrics
    op.execute(
        """
        CREATE OR REPLACE FUNCTION aggregate_analytics_metrics(
            p_metric_name TEXT,
            p_period TEXT,
            p_start_time TIMESTAMPTZ
        )
        RETURNS void AS $$
        DECLARE
            v_end_time TIMESTAMPTZ;
        BEGIN
            -- Calculate end time based on period
            v_end_time := CASE p_period
                WHEN 'minute' THEN p_start_time + INTERVAL '1 minute'
                WHEN 'hour' THEN p_start_time + INTERVAL '1 hour'
                WHEN 'day' THEN p_start_time + INTERVAL '1 day'
                WHEN 'week' THEN p_start_time + INTERVAL '1 week'
                WHEN 'month' THEN p_start_time + INTERVAL '1 month'
            END;

            -- Insert aggregated metrics
            INSERT INTO realtime_metrics (
                metric_name,
                metric_type,
                aggregation_period,
                period_start,
                period_end,
                dimensions,
                value,
                count,
                min_value,
                max_value,
                sum_value
            )
            SELECT
                p_metric_name,
                'summary',
                p_period,
                p_start_time,
                v_end_time,
                jsonb_build_object('state', state, 'event_type', event_type),
                AVG(value),
                COUNT(*),
                MIN(value),
                MAX(value),
                SUM(value)
            FROM analytics_events
            WHERE created_at >= p_start_time
              AND created_at < v_end_time
              AND value IS NOT NULL
            GROUP BY state, event_type
            ON CONFLICT (metric_name, aggregation_period, period_start, dimensions)
            DO UPDATE SET
                value = EXCLUDED.value,
                count = EXCLUDED.count,
                min_value = EXCLUDED.min_value,
                max_value = EXCLUDED.max_value,
                sum_value = EXCLUDED.sum_value,
                updated_at = CURRENT_TIMESTAMP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    """Drop real-time analytics tables and related objects."""

    # Drop triggers
    for table in ["notification_queue", "realtime_metrics"]:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS cleanup_stale_websocket_connections();")
    op.execute(
        "DROP FUNCTION IF EXISTS aggregate_analytics_metrics(TEXT, TEXT, TIMESTAMPTZ);"
    )

    # Drop tables
    op.drop_table("realtime_metrics")
    op.drop_table("notification_queue")
    op.drop_table("analytics_events")
    op.drop_table("websocket_connections")
