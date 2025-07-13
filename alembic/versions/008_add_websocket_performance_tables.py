"""Add WebSocket performance monitoring tables.

Revision ID: 008
Revises: 007
Create Date: 2025-07-08

This migration creates performance monitoring tables for WebSocket infrastructure:
1. Connection performance logs
2. Connection events tracking
3. Error logging
4. System metrics history
5. Performance alerts
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: str = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create WebSocket performance monitoring tables."""

    # Create WebSocket performance logs table
    op.create_table(
        "websocket_performance_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "connection_id",
            sa.String(100),
            nullable=False,
            comment="Unique connection identifier",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Associated user if authenticated",
        ),
        # Connection timing
        sa.Column(
            "connected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When connection was established",
        ),
        sa.Column(
            "disconnected_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When connection was closed",
        ),
        # Performance metrics
        sa.Column(
            "message_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Total messages sent/received",
        ),
        sa.Column(
            "bytes_sent",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="Total bytes sent to client",
        ),
        sa.Column(
            "bytes_received",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="Total bytes received from client",
        ),
        sa.Column(
            "avg_response_time_ms",
            sa.Numeric(10, 3),
            nullable=False,
            server_default="0",
            comment="Average response time in milliseconds",
        ),
        sa.Column(
            "error_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of errors encountered",
        ),
        sa.Column(
            "reconnection_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of reconnection attempts",
        ),
        # Metadata
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_websocket_performance_logs")),
        sa.UniqueConstraint(
            "connection_id",
            name=op.f("uq_websocket_performance_logs_connection_id"),
        ),
        sa.CheckConstraint(
            "message_count >= 0",
            name=op.f("ck_websocket_performance_logs_message_count_positive"),
        ),
        sa.CheckConstraint(
            "bytes_sent >= 0",
            name=op.f("ck_websocket_performance_logs_bytes_sent_positive"),
        ),
        sa.CheckConstraint(
            "bytes_received >= 0",
            name=op.f("ck_websocket_performance_logs_bytes_received_positive"),
        ),
        sa.CheckConstraint(
            "avg_response_time_ms >= 0",
            name=op.f("ck_websocket_performance_logs_response_time_positive"),
        ),
    )

    # Create indexes
    op.create_index(
        op.f("ix_websocket_performance_logs_user_id"),
        "websocket_performance_logs",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_websocket_performance_logs_connected_at"),
        "websocket_performance_logs",
        ["connected_at"],
        unique=False,
    )

    # Create WebSocket connection events table
    op.create_table(
        "websocket_connection_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "event_type",
            sa.String(50),
            nullable=False,
            comment="Type of event (connected, disconnected, etc.)",
        ),
        sa.Column(
            "connection_id",
            sa.String(100),
            nullable=False,
            comment="Connection identifier",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Associated user if authenticated",
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
            comment="Additional event metadata",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_websocket_connection_events")),
        sa.CheckConstraint(
            "event_type IN ('connected', 'disconnected', 'authenticated', 'error', 'reconnected')",
            name=op.f("ck_websocket_connection_events_event_type"),
        ),
    )

    # Create indexes
    op.create_index(
        op.f("ix_websocket_connection_events_connection_id"),
        "websocket_connection_events",
        ["connection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_websocket_connection_events_created_at"),
        "websocket_connection_events",
        ["created_at"],
        unique=False,
    )

    # Create WebSocket connection stats table
    op.create_table(
        "websocket_connection_stats",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "connection_id",
            sa.String(100),
            nullable=False,
            comment="Connection identifier",
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="Associated user if authenticated",
        ),
        sa.Column(
            "duration_seconds",
            sa.Numeric(12, 3),
            nullable=False,
            comment="Connection duration in seconds",
        ),
        sa.Column(
            "messages_sent",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Messages sent to client",
        ),
        sa.Column(
            "messages_received",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Messages received from client",
        ),
        sa.Column(
            "bytes_sent",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="Bytes sent to client",
        ),
        sa.Column(
            "bytes_received",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
            comment="Bytes received from client",
        ),
        sa.Column(
            "max_rooms_subscribed",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Maximum rooms subscribed simultaneously",
        ),
        sa.Column(
            "errors_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of errors encountered",
        ),
        sa.Column(
            "close_reason",
            sa.Text(),
            nullable=True,
            comment="Reason for connection closure",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_websocket_connection_stats")),
        sa.CheckConstraint(
            "duration_seconds >= 0",
            name=op.f("ck_websocket_connection_stats_duration_positive"),
        ),
    )

    # Create indexes
    op.create_index(
        op.f("ix_websocket_connection_stats_user_id"),
        "websocket_connection_stats",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_websocket_connection_stats_created_at"),
        "websocket_connection_stats",
        ["created_at"],
        unique=False,
    )

    # Create WebSocket errors table
    op.create_table(
        "websocket_errors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "connection_id",
            sa.String(100),
            nullable=True,
            comment="Connection identifier if applicable",
        ),
        sa.Column(
            "error_type",
            sa.String(100),
            nullable=False,
            comment="Type/category of error",
        ),
        sa.Column(
            "error_message",
            sa.Text(),
            nullable=False,
            comment="Error message details",
        ),
        sa.Column(
            "stack_trace",
            sa.Text(),
            nullable=True,
            comment="Stack trace if available",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_websocket_errors")),
    )

    # Create indexes
    op.create_index(
        op.f("ix_websocket_errors_error_type"),
        "websocket_errors",
        ["error_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_websocket_errors_created_at"),
        "websocket_errors",
        ["created_at"],
        unique=False,
    )

    # Create WebSocket system metrics table
    op.create_table(
        "websocket_system_metrics",
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
            comment="Metric timestamp",
        ),
        sa.Column(
            "total_connections",
            sa.Integer(),
            nullable=False,
            comment="Total connections tracked",
        ),
        sa.Column(
            "active_connections",
            sa.Integer(),
            nullable=False,
            comment="Currently active connections",
        ),
        sa.Column(
            "peak_connections",
            sa.Integer(),
            nullable=False,
            comment="Peak connections reached",
        ),
        sa.Column(
            "messages_per_second",
            sa.Numeric(10, 2),
            nullable=False,
            comment="Message throughput",
        ),
        sa.Column(
            "avg_message_latency_ms",
            sa.Numeric(10, 3),
            nullable=False,
            comment="Average message latency",
        ),
        sa.Column(
            "p95_message_latency_ms",
            sa.Numeric(10, 3),
            nullable=False,
            comment="95th percentile message latency",
        ),
        sa.Column(
            "error_rate",
            sa.Numeric(5, 4),
            nullable=False,
            comment="Error rate (0-1)",
        ),
        sa.Column(
            "memory_usage_mb",
            sa.Numeric(10, 2),
            nullable=False,
            comment="Memory usage in MB",
        ),
        sa.Column(
            "cpu_usage_percent",
            sa.Numeric(5, 2),
            nullable=False,
            comment="CPU usage percentage",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_websocket_system_metrics")),
        sa.CheckConstraint(
            "total_connections >= 0",
            name=op.f("ck_websocket_system_metrics_total_connections_positive"),
        ),
        sa.CheckConstraint(
            "active_connections >= 0",
            name=op.f("ck_websocket_system_metrics_active_connections_positive"),
        ),
        sa.CheckConstraint(
            "error_rate >= 0 AND error_rate <= 1",
            name=op.f("ck_websocket_system_metrics_error_rate_valid"),
        ),
        sa.CheckConstraint(
            "cpu_usage_percent >= 0 AND cpu_usage_percent <= 100",
            name=op.f("ck_websocket_system_metrics_cpu_usage_valid"),
        ),
    )

    # Create indexes
    op.create_index(
        op.f("ix_websocket_system_metrics_timestamp"),
        "websocket_system_metrics",
        ["timestamp"],
        unique=False,
    )

    # Create performance alerts table
    op.create_table(
        "performance_alerts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "alert_type",
            sa.String(100),
            nullable=False,
            comment="Type of alert",
        ),
        sa.Column(
            "severity",
            sa.String(20),
            nullable=False,
            comment="Alert severity level",
        ),
        sa.Column(
            "metric_name",
            sa.String(100),
            nullable=False,
            comment="Metric that triggered the alert",
        ),
        sa.Column(
            "threshold_value",
            sa.Numeric(12, 4),
            nullable=False,
            comment="Threshold that was exceeded",
        ),
        sa.Column(
            "current_value",
            sa.Numeric(12, 4),
            nullable=False,
            comment="Current value of the metric",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            comment="Alert description",
        ),
        sa.Column(
            "recommended_action",
            sa.Text(),
            nullable=True,
            comment="Recommended action to resolve",
        ),
        sa.Column(
            "resolved",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether alert has been resolved",
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When alert was resolved",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # Constraints
        sa.PrimaryKeyConstraint("id", name=op.f("pk_performance_alerts")),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name=op.f("ck_performance_alerts_severity"),
        ),
    )

    # Create indexes
    op.create_index(
        op.f("ix_performance_alerts_alert_type"),
        "performance_alerts",
        ["alert_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_performance_alerts_severity"),
        "performance_alerts",
        ["severity"],
        unique=False,
    )
    op.create_index(
        op.f("ix_performance_alerts_created_at"),
        "performance_alerts",
        ["created_at"],
        unique=False,
    )
    # Index for unresolved alerts
    op.create_index(
        "ix_performance_alerts_unresolved",
        "performance_alerts",
        ["severity", "created_at"],
        unique=False,
        postgresql_where=sa.text("resolved = false"),
    )

    # Create function to calculate message throughput
    op.execute(
        """
        CREATE OR REPLACE FUNCTION calculate_websocket_throughput(
            p_interval INTERVAL DEFAULT '1 minute'
        )
        RETURNS TABLE (
            event_timestamp TIMESTAMPTZ,
            messages_per_second NUMERIC,
            bytes_per_second NUMERIC,
            active_connections INTEGER
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                date_trunc('minute', e.created_at) AS event_timestamp,
                COUNT(*)::NUMERIC / EXTRACT(EPOCH FROM p_interval) AS messages_per_second,
                SUM(
                    CASE
                        WHEN e.metadata->>'bytes' IS NOT NULL
                        THEN (e.metadata->>'bytes')::NUMERIC
                        ELSE 0
                    END
                ) / EXTRACT(EPOCH FROM p_interval) AS bytes_per_second,
                COUNT(DISTINCT e.connection_id)::INTEGER AS active_connections
            FROM websocket_connection_events e
            WHERE e.created_at >= CURRENT_TIMESTAMP - p_interval
              AND e.event_type IN ('message_sent', 'message_received')
            GROUP BY date_trunc('minute', e.created_at);
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # Create function to analyze connection patterns
    op.execute(
        """
        CREATE OR REPLACE FUNCTION analyze_connection_patterns(
            p_days INTEGER DEFAULT 7
        )
        RETURNS TABLE (
            hour_of_day INTEGER,
            avg_connections NUMERIC,
            max_connections INTEGER,
            avg_duration_minutes NUMERIC
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                EXTRACT(HOUR FROM connected_at)::INTEGER AS hour_of_day,
                AVG(message_count)::NUMERIC AS avg_connections,
                MAX(message_count)::INTEGER AS max_connections,
                AVG(
                    EXTRACT(EPOCH FROM (disconnected_at - connected_at)) / 60
                )::NUMERIC AS avg_duration_minutes
            FROM websocket_performance_logs
            WHERE connected_at >= CURRENT_TIMESTAMP - (p_days || ' days')::INTERVAL
              AND disconnected_at IS NOT NULL
            GROUP BY EXTRACT(HOUR FROM connected_at)
            ORDER BY hour_of_day;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
    """Drop WebSocket performance monitoring tables and related objects."""

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS calculate_websocket_throughput(INTERVAL);")
    op.execute("DROP FUNCTION IF EXISTS analyze_connection_patterns(INTEGER);")

    # Drop tables
    op.drop_table("performance_alerts")
    op.drop_table("websocket_system_metrics")
    op.drop_table("websocket_errors")
    op.drop_table("websocket_connection_stats")
    op.drop_table("websocket_connection_events")
    op.drop_table("websocket_performance_logs")
