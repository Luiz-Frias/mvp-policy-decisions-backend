-- 002_monitoring_bootstrap.sql
-- Enable pg_stat_statements extension and create admin monitoring materialized views.
-- Idempotent: all CREATE statements use IF NOT EXISTS.

-- 1. pg_stat_statements extension (required for slow-query analysis)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 2. admin_daily_metrics materialized view
CREATE MATERIALIZED VIEW IF NOT EXISTS admin_daily_metrics AS
WITH date_series AS (
    SELECT generate_series(
        CURRENT_DATE - INTERVAL '30 days',
        CURRENT_DATE,
        '1 day'::interval
    )::date AS metric_date
)
SELECT
    ds.metric_date,
    COALESCE(COUNT(DISTINCT q.customer_id), 0) AS unique_customers,
    COALESCE(COUNT(q.id) FILTER (WHERE q.status = 'draft'), 0) AS quotes_draft,
    COALESCE(COUNT(q.id) FILTER (WHERE q.status = 'quoted'), 0) AS quotes_created,
    COALESCE(COUNT(q.id) FILTER (WHERE q.status = 'bound'), 0) AS quotes_bound,
    COALESCE(AVG(q.total_premium), 0) AS avg_premium,
    COALESCE(SUM(q.total_premium) FILTER (WHERE q.status = 'bound'), 0) AS total_bound_premium,
    COALESCE(
        COUNT(q.id) FILTER (WHERE q.status = 'bound')::float /
        NULLIF(COUNT(q.id) FILTER (WHERE q.status IN ('quoted', 'bound')), 0) * 100,
        0
    ) AS conversion_rate
FROM date_series ds
LEFT JOIN quotes q ON DATE(q.created_at) = ds.metric_date
GROUP BY ds.metric_date
ORDER BY ds.metric_date DESC
WITH DATA;

CREATE INDEX IF NOT EXISTS idx_admin_daily_metrics_date ON admin_daily_metrics(metric_date DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_admin_daily_metrics_date ON admin_daily_metrics(metric_date);

-- Add missing columns in admin_users to support monitoring views
ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS role TEXT;
ALTER TABLE admin_users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- 3. admin_user_activity materialized view (admin activity dashboard)
CREATE MATERIALIZED VIEW IF NOT EXISTS admin_user_activity AS
SELECT
    au.id AS admin_user_id,
    au.email,
    au.role,
    au.is_active,
    COUNT(DISTINCT aal.id) AS total_actions,
    COUNT(DISTINCT DATE(aal.created_at)) AS active_days,
    MAX(aal.created_at) AS last_activity,
    COUNT(aal.id) FILTER (WHERE aal.status = 'success') AS successful_actions,
    COUNT(aal.id) FILTER (WHERE aal.status = 'failed') AS failed_actions,
    COUNT(aal.id) FILTER (WHERE aal.created_at > NOW() - INTERVAL '24 hours') AS actions_last_24h,
    ARRAY_REMOVE(ARRAY_AGG(DISTINCT aal.action ORDER BY aal.action), NULL) AS action_types
FROM admin_users au
LEFT JOIN admin_activity_logs aal ON au.id = aal.admin_user_id
GROUP BY au.id, au.email, au.role, au.is_active
WITH DATA;

CREATE INDEX IF NOT EXISTS idx_admin_user_activity_id ON admin_user_activity(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_user_activity_last ON admin_user_activity(last_activity DESC NULLS LAST);
CREATE UNIQUE INDEX IF NOT EXISTS uq_admin_user_activity_id ON admin_user_activity(admin_user_id);

-- 4. admin_system_health materialized view (system performance dashboard)
CREATE MATERIALIZED VIEW IF NOT EXISTS admin_system_health AS
WITH recent_events AS (
    SELECT *
    FROM analytics_events
    WHERE created_at > NOW() - INTERVAL '1 hour'
),
active_websockets AS (
    SELECT COUNT(DISTINCT connection_id) AS active_connections
    FROM websocket_connections
    WHERE disconnected_at IS NULL
)
SELECT
    (SELECT active_connections FROM active_websockets) AS websocket_connections,
    COUNT(*) AS total_events_last_hour,
    AVG(duration_ms) AS avg_event_duration_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_event_duration_ms,
    PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms) AS p99_event_duration_ms,
    COUNT(*) FILTER (WHERE duration_ms > 1000) AS slow_events,
    COUNT(*) FILTER (WHERE event_category = 'system' AND event_type = 'error_occurred') AS error_events,
    COUNT(DISTINCT user_id) AS unique_active_users,
    SUM(CASE WHEN event_type = 'api_call' THEN 1 ELSE 0 END) AS api_calls,
    NOW() AS last_updated
FROM recent_events
WITH DATA;

CREATE INDEX IF NOT EXISTS idx_admin_system_health_updated ON admin_system_health(last_updated);
CREATE UNIQUE INDEX IF NOT EXISTS uq_admin_system_health_updated ON admin_system_health(last_updated);

-- 5. admin_quote_funnel materialized view (quote stage conversion dashboard)
CREATE MATERIALIZED VIEW IF NOT EXISTS admin_quote_funnel AS
WITH quote_stages AS (
    SELECT
        DATE(created_at) AS quote_date,
        COUNT(*) AS total_quotes,
        COUNT(*) FILTER (WHERE status = 'draft') AS stage_draft,
        COUNT(*) FILTER (WHERE status = 'quoted') AS stage_quoted,
        COUNT(*) FILTER (WHERE status = 'bound') AS stage_bound,
        COUNT(*) FILTER (WHERE status = 'expired') AS stage_expired,
        COUNT(*) FILTER (WHERE status = 'declined') AS stage_declined,
        AVG(EXTRACT(EPOCH FROM (updated_at - created_at)) / 60) AS avg_processing_time_minutes
    FROM quotes
    WHERE created_at > CURRENT_DATE - INTERVAL '90 days'
    GROUP BY DATE(created_at)
)
SELECT *,
    CASE WHEN stage_quoted > 0 THEN stage_bound::float / stage_quoted * 100 ELSE 0 END AS bind_rate
FROM quote_stages
ORDER BY quote_date DESC
WITH DATA;

CREATE INDEX IF NOT EXISTS idx_admin_quote_funnel_date ON admin_quote_funnel(quote_date DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_admin_quote_funnel_date ON admin_quote_funnel(quote_date);

-- 6. refresh tracking table for materialized views
CREATE TABLE IF NOT EXISTS admin_materialized_view_refresh (
    view_name TEXT PRIMARY KEY,
    last_refresh TIMESTAMP NOT NULL,
    refresh_duration_ms INTEGER,
    row_count INTEGER
); 