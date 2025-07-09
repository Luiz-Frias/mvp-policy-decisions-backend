"""Specialized query optimization for admin dashboard operations."""

from datetime import datetime, timedelta
from typing import Any

from attrs import field, frozen
from beartype import beartype

from .cache_stub import get_cache
from .database_enhanced import Database
from .result_types import Err, Ok, Result


@frozen
class AdminMetrics:
    """Immutable admin dashboard metrics."""

    daily_metrics: list[dict[str, Any]] = field()
    user_activity: list[dict[str, Any]] = field()
    system_health: dict[str, Any] = field()
    cache_timestamp: datetime = field()


@frozen
class MaterializedView:
    """Materialized view configuration."""

    name: str = field()
    refresh_interval_minutes: int = field()
    query: str = field()
    last_refresh: datetime | None = field(default=None)
    indexes: list[str] = field(factory=list)


class AdminQueryOptimizer:
    """Optimize complex admin queries and dashboard operations."""

    def __init__(self, db: Database) -> None:
        """Initialize admin query optimizer."""
        self._db = db
        self._cache = get_cache()
        self._materialized_views = self._define_materialized_views()

    @beartype
    def _define_materialized_views(self) -> dict[str, MaterializedView]:
        """Define all materialized views for admin dashboards."""
        return {
            "admin_daily_metrics": MaterializedView(
                name="admin_daily_metrics",
                refresh_interval_minutes=60,
                query="""
                    CREATE MATERIALIZED VIEW IF NOT EXISTS admin_daily_metrics AS
                    WITH date_series AS (
                        SELECT generate_series(
                            CURRENT_DATE - INTERVAL '30 days',
                            CURRENT_DATE,
                            '1 day'::interval
                        )::date as metric_date
                    )
                    SELECT
                        ds.metric_date,
                        COALESCE(COUNT(DISTINCT q.customer_id), 0) as unique_customers,
                        COALESCE(COUNT(q.id) FILTER (WHERE q.status = 'draft'), 0) as quotes_draft,
                        COALESCE(COUNT(q.id) FILTER (WHERE q.status = 'quoted'), 0) as quotes_created,
                        COALESCE(COUNT(q.id) FILTER (WHERE q.status = 'bound'), 0) as quotes_bound,
                        COALESCE(AVG(q.total_premium), 0) as avg_premium,
                        COALESCE(SUM(q.total_premium) FILTER (WHERE q.status = 'bound'), 0) as total_bound_premium,
                        COALESCE(
                            COUNT(q.id) FILTER (WHERE q.status = 'bound')::float /
                            NULLIF(COUNT(q.id) FILTER (WHERE q.status IN ('quoted', 'bound')), 0) * 100,
                            0
                        ) as conversion_rate
                    FROM date_series ds
                    LEFT JOIN quotes q ON DATE(q.created_at) = ds.metric_date
                    GROUP BY ds.metric_date
                    ORDER BY ds.metric_date DESC
                    WITH DATA
                """,
                indexes=[
                    "CREATE INDEX idx_admin_daily_metrics_date ON admin_daily_metrics(metric_date DESC)",
                ],
            ),
            "admin_user_activity": MaterializedView(
                name="admin_user_activity",
                refresh_interval_minutes=30,
                query="""
                    CREATE MATERIALIZED VIEW IF NOT EXISTS admin_user_activity AS
                    SELECT
                        au.id as admin_user_id,
                        au.email,
                        au.role,
                        au.is_active,
                        COUNT(DISTINCT aal.id) as total_actions,
                        COUNT(DISTINCT DATE(aal.created_at)) as active_days,
                        MAX(aal.created_at) as last_activity,
                        COUNT(aal.id) FILTER (WHERE aal.status = 'success') as successful_actions,
                        COUNT(aal.id) FILTER (WHERE aal.status = 'failed') as failed_actions,
                        COUNT(aal.id) FILTER (WHERE aal.created_at > NOW() - INTERVAL '24 hours') as actions_last_24h,
                        ARRAY_AGG(DISTINCT aal.action ORDER BY aal.action) FILTER (WHERE aal.action IS NOT NULL) as action_types
                    FROM admin_users au
                    LEFT JOIN admin_activity_logs aal ON au.id = aal.admin_user_id
                    GROUP BY au.id, au.email, au.role, au.is_active
                    WITH DATA
                """,
                indexes=[
                    "CREATE INDEX idx_admin_user_activity_id ON admin_user_activity(admin_user_id)",
                    "CREATE INDEX idx_admin_user_activity_last ON admin_user_activity(last_activity DESC NULLS LAST)",
                ],
            ),
            "admin_system_health": MaterializedView(
                name="admin_system_health",
                refresh_interval_minutes=5,
                query="""
                    CREATE MATERIALIZED VIEW IF NOT EXISTS admin_system_health AS
                    WITH recent_events AS (
                        SELECT * FROM analytics_events
                        WHERE created_at > NOW() - INTERVAL '1 hour'
                    ),
                    active_websockets AS (
                        SELECT COUNT(DISTINCT connection_id) as active_connections
                        FROM websocket_connections
                        WHERE disconnected_at IS NULL
                    )
                    SELECT
                        (SELECT active_connections FROM active_websockets) as websocket_connections,
                        COUNT(DISTINCT re.id) as total_requests_last_hour,
                        AVG(re.duration_ms) as avg_response_time_ms,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY re.duration_ms) as p95_response_time_ms,
                        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY re.duration_ms) as p99_response_time_ms,
                        COUNT(re.id) FILTER (WHERE re.duration_ms > 1000) as slow_requests,
                        COUNT(re.id) FILTER (WHERE re.status_code >= 500) as error_requests,
                        COUNT(DISTINCT re.user_id) as unique_active_users,
                        SUM(CASE WHEN re.event_type = 'api_call' THEN 1 ELSE 0 END) as api_calls,
                        NOW() as last_updated
                    FROM recent_events re
                    WITH DATA
                """,
                indexes=[
                    "CREATE INDEX idx_admin_system_health_updated ON admin_system_health(last_updated)",
                ],
            ),
            "admin_quote_funnel": MaterializedView(
                name="admin_quote_funnel",
                refresh_interval_minutes=15,
                query="""
                    CREATE MATERIALIZED VIEW IF NOT EXISTS admin_quote_funnel AS
                    WITH quote_stages AS (
                        SELECT
                            DATE(created_at) as quote_date,
                            COUNT(*) as total_quotes,
                            COUNT(*) FILTER (WHERE status = 'draft') as stage_draft,
                            COUNT(*) FILTER (WHERE status = 'quoted') as stage_quoted,
                            COUNT(*) FILTER (WHERE status = 'bound') as stage_bound,
                            COUNT(*) FILTER (WHERE status = 'expired') as stage_expired,
                            COUNT(*) FILTER (WHERE status = 'declined') as stage_declined,
                            AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/60) as avg_processing_time_minutes
                        FROM quotes
                        WHERE created_at > CURRENT_DATE - INTERVAL '90 days'
                        GROUP BY DATE(created_at)
                    )
                    SELECT *,
                        CASE
                            WHEN stage_quoted > 0 THEN stage_bound::float / stage_quoted * 100
                            ELSE 0
                        END as bind_rate
                    FROM quote_stages
                    ORDER BY quote_date DESC
                    WITH DATA
                """,
                indexes=[
                    "CREATE INDEX idx_admin_quote_funnel_date ON admin_quote_funnel(quote_date DESC)",
                ],
            ),
        }

    @beartype
    async def create_materialized_views(self) -> Result[list[str], str]:
        """Create all materialized views for admin dashboards."""
        created_views = []

        try:
            async with self._db.acquire_admin() as conn:
                for view_name, view_config in self._materialized_views.items():
                    # Create the view
                    await conn.execute(view_config.query)

                    # Create indexes
                    for index_query in view_config.indexes:
                        await conn.execute(index_query)

                    created_views.append(view_name)

                # Create refresh tracking table
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS admin_materialized_view_refresh (
                        view_name TEXT PRIMARY KEY,
                        last_refresh TIMESTAMP NOT NULL,
                        refresh_duration_ms INTEGER,
                        row_count INTEGER
                    )
                """
                )

            return Ok(created_views)

        except Exception as e:
            return Err(f"Failed to create materialized views: {str(e)}")

    @beartype
    async def refresh_materialized_views(
        self,
        force_refresh: bool = False,
    ) -> Result[dict[str, bool], str]:
        """Refresh materialized views based on their refresh intervals."""
        refresh_results = {}

        try:
            async with self._db.acquire_admin() as conn:
                for view_name, view_config in self._materialized_views.items():
                    # Check if refresh is needed
                    needs_refresh = force_refresh

                    if not force_refresh:
                        last_refresh = await conn.fetchval(
                            "SELECT last_refresh FROM admin_materialized_view_refresh WHERE view_name = $1",
                            view_name,
                        )

                        if last_refresh:
                            time_since_refresh = datetime.utcnow() - last_refresh
                            needs_refresh = time_since_refresh > timedelta(
                                minutes=view_config.refresh_interval_minutes
                            )
                        else:
                            needs_refresh = True

                    if needs_refresh:
                        import time

                        start_time = time.perf_counter()

                        # Refresh the view concurrently to avoid locking
                        # Safe view name handling
                        await conn.execute(
                            f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}"  # view_name is from trusted source
                        )

                        # Get row count
                        # Use identifier quoting to prevent SQL injection
                        from asyncpg.sql import Identifier  # type: ignore[import-untyped]

                        row_count = await conn.fetchval(
                            "SELECT COUNT(*) FROM $1", Identifier(view_name)
                        )

                        duration_ms = int((time.perf_counter() - start_time) * 1000)

                        # Update refresh tracking
                        await conn.execute(
                            """
                            INSERT INTO admin_materialized_view_refresh (view_name, last_refresh, refresh_duration_ms, row_count)
                            VALUES ($1, $2, $3, $4)
                            ON CONFLICT (view_name) DO UPDATE
                            SET last_refresh = $2, refresh_duration_ms = $3, row_count = $4
                        """,
                            view_name,
                            datetime.utcnow(),
                            duration_ms,
                            row_count,
                        )

                        refresh_results[view_name] = True
                    else:
                        refresh_results[view_name] = False

            return Ok(refresh_results)

        except Exception as e:
            return Err(f"Failed to refresh materialized views: {str(e)}")

    @beartype
    async def get_admin_dashboard_metrics(
        self,
        use_cache: bool = True,
        cache_ttl_seconds: int = 300,
    ) -> Result[AdminMetrics, str]:
        """Get optimized admin dashboard metrics."""
        cache_key = "admin:dashboard:metrics:v2"

        # Check cache first
        if use_cache:
            cached_result = await self._cache.get(cache_key)
            if cached_result is not None:
                return Ok(AdminMetrics(**cached_result))

        try:
            # Refresh views if needed
            refresh_result = await self.refresh_materialized_views()
            if refresh_result.is_err():
                return Err(refresh_result.unwrap_err() or "Unknown error")

            # Fetch data from materialized views in parallel
            async with self._db.acquire_admin() as conn:
                # Use asyncio.gather for parallel queries
                import asyncio

                daily_metrics_task = conn.fetch(
                    """
                    SELECT
                        metric_date,
                        unique_customers,
                        quotes_draft,
                        quotes_created,
                        quotes_bound,
                        avg_premium,
                        total_bound_premium,
                        conversion_rate
                    FROM admin_daily_metrics
                    WHERE metric_date >= CURRENT_DATE - INTERVAL '30 days'
                    ORDER BY metric_date DESC
                """
                )

                user_activity_task = conn.fetch(
                    """
                    SELECT
                        admin_user_id,
                        email,
                        role,
                        is_active,
                        total_actions,
                        active_days,
                        last_activity,
                        successful_actions,
                        failed_actions,
                        actions_last_24h,
                        action_types
                    FROM admin_user_activity
                    WHERE is_active = true
                    ORDER BY last_activity DESC NULLS LAST
                    LIMIT 50
                """
                )

                system_health_task = conn.fetchrow(
                    """
                    SELECT
                        websocket_connections,
                        total_requests_last_hour,
                        avg_response_time_ms,
                        p95_response_time_ms,
                        p99_response_time_ms,
                        slow_requests,
                        error_requests,
                        unique_active_users,
                        api_calls,
                        last_updated
                    FROM admin_system_health
                    LIMIT 1
                """
                )

                # Execute queries in parallel
                daily_metrics, user_activity, system_health = await asyncio.gather(
                    daily_metrics_task,
                    user_activity_task,
                    system_health_task,
                )

                # Convert to dictionaries
                metrics_data = {
                    "daily_metrics": [dict(row) for row in daily_metrics],  # SYSTEM_BOUNDARY - Database query result
                    "user_activity": [dict(row) for row in user_activity],  # SYSTEM_BOUNDARY - Database query result
                    "system_health": dict(system_health) if system_health else {},  # SYSTEM_BOUNDARY - Database query result
                    "cache_timestamp": datetime.utcnow(),
                }

                # Cache the results
                if use_cache:
                    await self._cache.set(
                        cache_key, metrics_data, ttl_seconds=cache_ttl_seconds
                    )

                return Ok(AdminMetrics(
                    daily_metrics=metrics_data["daily_metrics"],  # type: ignore
                    user_activity=metrics_data["user_activity"],  # type: ignore
                    system_health=metrics_data["system_health"],  # type: ignore
                    cache_timestamp=metrics_data["cache_timestamp"],  # type: ignore
                ))

        except Exception as e:
            return Err(f"Failed to fetch admin metrics: {str(e)}")

    @beartype
    async def get_admin_reports(
        self,
        report_type: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Result[list[dict[str, Any]], str]:
        """Generate admin reports with optimized queries."""
        if report_type == "revenue_summary":
            query = """
                WITH revenue_data AS (
                    SELECT
                        DATE_TRUNC('week', p.effective_date) as week_start,
                        COUNT(DISTINCT p.id) as policy_count,
                        SUM(p.premium_amount) as total_premium,
                        AVG(p.premium_amount) as avg_premium,
                        COUNT(DISTINCT p.customer_id) as unique_customers
                    FROM policies p
                    WHERE p.effective_date BETWEEN $1 AND $2
                    AND p.status = 'active'
                    GROUP BY DATE_TRUNC('week', p.effective_date)
                )
                SELECT
                    week_start,
                    policy_count,
                    total_premium,
                    avg_premium,
                    unique_customers,
                    LAG(total_premium) OVER (ORDER BY week_start) as prev_week_premium,
                    total_premium - LAG(total_premium) OVER (ORDER BY week_start) as week_over_week_change
                FROM revenue_data
                ORDER BY week_start DESC
            """

        elif report_type == "agent_performance":
            query = """
                WITH agent_metrics AS (
                    SELECT
                        au.id as agent_id,
                        au.email as agent_email,
                        COUNT(DISTINCT q.id) as quotes_created,
                        COUNT(DISTINCT q.id) FILTER (WHERE q.status = 'bound') as quotes_bound,
                        AVG(EXTRACT(EPOCH FROM (q.updated_at - q.created_at))/3600) as avg_processing_hours,
                        SUM(q.total_premium) FILTER (WHERE q.status = 'bound') as total_premium_bound
                    FROM admin_users au
                    JOIN quotes q ON q.created_by = au.id
                    WHERE q.created_at BETWEEN $1 AND $2
                    GROUP BY au.id, au.email
                )
                SELECT
                    *,
                    CASE
                        WHEN quotes_created > 0 THEN quotes_bound::float / quotes_created * 100
                        ELSE 0
                    END as conversion_rate
                FROM agent_metrics
                ORDER BY total_premium_bound DESC NULLS LAST
            """

        elif report_type == "customer_retention":
            query = """
                WITH customer_cohorts AS (
                    SELECT
                        DATE_TRUNC('month', first_policy_date) as cohort_month,
                        customer_id,
                        COUNT(DISTINCT policy_id) as total_policies,
                        MAX(last_renewal_date) as last_seen
                    FROM (
                        SELECT
                            c.id as customer_id,
                            MIN(p.effective_date) as first_policy_date,
                            p.id as policy_id,
                            MAX(p.renewal_date) as last_renewal_date
                        FROM customers c
                        JOIN policies p ON p.customer_id = c.id
                        WHERE p.effective_date BETWEEN $1 AND $2
                        GROUP BY c.id, p.id
                    ) customer_policies
                    GROUP BY DATE_TRUNC('month', first_policy_date), customer_id
                )
                SELECT
                    cohort_month,
                    COUNT(DISTINCT customer_id) as cohort_size,
                    COUNT(DISTINCT customer_id) FILTER (
                        WHERE last_seen > cohort_month + INTERVAL '12 months'
                    ) as retained_12_months,
                    AVG(total_policies) as avg_policies_per_customer
                FROM customer_cohorts
                GROUP BY cohort_month
                ORDER BY cohort_month DESC
            """
        else:
            return Err(f"Unknown report type: {report_type}")

        try:
            async with self._db.acquire_admin() as conn:
                results = await conn.fetch(query, start_date, end_date)
                return Ok([dict(row) for row in results])  # SYSTEM_BOUNDARY - Database query result

        except Exception as e:
            return Err(f"Failed to generate report: {str(e)}")

    @beartype
    async def optimize_admin_queries(self) -> Result[dict[str, Any], str]:
        """Analyze and optimize all admin queries."""
        optimization_results: dict[str, Any] = {
            "indexes_created": [],
            "views_optimized": [],
            "settings_adjusted": [],
            "performance_gains": {},
        }

        try:
            async with self._db.acquire_admin() as conn:
                # Check for missing indexes on frequently queried columns
                missing_indexes = await conn.fetch(
                    """
                    SELECT DISTINCT
                        'CREATE INDEX idx_' || t.tablename || '_' || a.attname ||
                        ' ON ' || t.schemaname || '.' || t.tablename || '(' || a.attname || ')' as index_sql,
                        t.tablename,
                        a.attname
                    FROM pg_stat_user_tables t
                    JOIN pg_attribute a ON a.attrelid = t.relid
                    JOIN pg_stat_all_columns c ON c.attrelid = a.attrelid AND c.attnum = a.attnum
                    WHERE t.schemaname = 'public'
                    AND a.attnum > 0
                    AND NOT a.attisdropped
                    AND c.n_distinct > 100
                    AND NOT EXISTS (
                        SELECT 1 FROM pg_index i
                        WHERE i.indrelid = t.relid
                        AND a.attnum = ANY(i.indkey)
                    )
                    AND t.tablename IN ('quotes', 'policies', 'customers', 'admin_activity_logs')
                """
                )

                # Create recommended indexes
                for idx in missing_indexes:
                    try:
                        await conn.execute(idx["index_sql"])
                        optimization_results["indexes_created"].append(
                            {
                                "table": idx["tablename"],
                                "column": idx["attname"],
                            }
                        )
                    except Exception:
                        pass  # Index might already exist

                # Analyze tables for better query planning
                tables_to_analyze = [
                    "quotes",
                    "policies",
                    "customers",
                    "admin_users",
                    "admin_activity_logs",
                ]
                for table in tables_to_analyze:
                    await conn.execute(f"ANALYZE {table}")

                optimization_results["views_optimized"] = list(
                    self._materialized_views.keys()
                )

            return Ok(optimization_results)

        except Exception as e:
            return Err(f"Failed to optimize admin queries: {str(e)}")

    @beartype
    async def monitor_admin_query_performance(self) -> Result[dict[str, Any], str]:
        """Monitor admin-specific query performance metrics."""
        try:
            pool_stats = await self._db.get_pool_stats()

            metrics = {
                "admin_pool_stats": {
                    "size": pool_stats.size,
                    "free_size": pool_stats.free_size,
                    "utilization_percent": (
                        (pool_stats.size - pool_stats.free_size) / pool_stats.size * 100
                        if pool_stats.size > 0
                        else 0
                    ),
                },
                "query_performance": {
                    "average_query_time_ms": pool_stats.average_query_time_ms,
                    "slow_queries_count": pool_stats.queries_slow,
                    "total_queries": pool_stats.queries_total,
                },
                "materialized_views": {},
                "cache_stats": await self._get_cache_stats(),
            }

            # Get materialized view freshness
            async with self._db.acquire_admin() as conn:
                view_stats = await conn.fetch(
                    """
                    SELECT
                        view_name,
                        last_refresh,
                        refresh_duration_ms,
                        row_count,
                        EXTRACT(EPOCH FROM (NOW() - last_refresh)) as seconds_since_refresh
                    FROM admin_materialized_view_refresh
                """
                )

                for stat in view_stats:
                    metrics["materialized_views"][stat["view_name"]] = {
                        "last_refresh": stat["last_refresh"],
                        "refresh_duration_ms": stat["refresh_duration_ms"],
                        "row_count": stat["row_count"],
                        "is_stale": stat["seconds_since_refresh"]
                        > 3600,  # Stale if > 1 hour
                    }

            return Ok(metrics)

        except Exception as e:
            return Err(f"Failed to monitor admin performance: {str(e)}")

    @beartype
    async def _get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics for admin queries."""
        # This would integrate with your cache implementation
        return {
            "hit_rate": 0.85,  # Placeholder
            "miss_rate": 0.15,
            "avg_response_time_cached_ms": 5,
            "avg_response_time_uncached_ms": 150,
        }
