# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Query optimization utilities for database performance tuning."""

from typing import Any

from attrs import field, frozen
from beartype import beartype
from pydantic import Field

from policy_core.models.base import BaseModelConfig

from .database import Database
from .result_types import Err, Ok, Result

# Auto-generated models


@beartype
class PlanData(BaseModelConfig):
    """Structured model for query plan data."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class PlanDetailsData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@frozen
class QueryPlan:
    """Immutable query execution plan analysis."""

    query: str = field()
    execution_time_ms: float = field()
    planning_time_ms: float = field()
    total_cost: float = field()
    rows_returned: int = field()
    plan_details: PlanDetailsData = field()
    suggestions: list[str] = field(factory=list)


@frozen
class SlowQuery:
    """Immutable slow query information."""

    query: str = field()
    calls: int = field()
    total_time_ms: float = field()
    mean_time_ms: float = field()
    stddev_time_ms: float = field()
    rows: int = field()


@frozen
class IndexSuggestion:
    """Immutable index suggestion."""

    table_name: str = field()
    column_name: str = field()
    index_type: str = field()
    create_statement: str = field()
    estimated_improvement: str = field()


class QueryOptimizer:
    """Analyze and optimize database queries for performance."""

    def __init__(self, db: Database) -> None:
        """Initialize with database connection."""
        self._db = db

    @beartype
    async def explain_analyze(
        self,
        query: str,
        *args: Any,
        analyze: bool = True,
        buffers: bool = True,
        verbose: bool = False,
    ) -> Result[QueryPlan, str]:
        """Run EXPLAIN ANALYZE on a query and parse results."""
        explain_options = []
        if analyze:
            explain_options.append("ANALYZE")
        if buffers:
            explain_options.append("BUFFERS")
        if verbose:
            explain_options.append("VERBOSE")

        explain_query = f"EXPLAIN ({', '.join(explain_options)}, FORMAT JSON) {query}"

        try:
            async with self._db.acquire_admin() as conn:
                result = await conn.fetchval(explain_query, *args)

                if not result or not isinstance(result, list) or not result:
                    return Err("Invalid EXPLAIN result format")

                plan_data = result[0]

                # Extract key metrics
                execution_time = plan_data.get("Execution Time", 0.0)
                planning_time = plan_data.get("Planning Time", 0.0)
                total_cost = plan_data.get("Plan", {}).get("Total Cost", 0.0)
                rows = plan_data.get("Plan", {}).get("Actual Rows", 0)

                # Generate suggestions based on plan
                suggestions = self._analyze_plan_for_suggestions(plan_data)

                return Ok(
                    QueryPlan(
                        query=query,
                        execution_time_ms=execution_time,
                        planning_time_ms=planning_time,
                        total_cost=total_cost,
                        rows_returned=rows,
                        plan_details=plan_data,
                        suggestions=suggestions,
                    )
                )

        except Exception as e:
            return Err(f"Failed to analyze query: {str(e)}")

    @beartype
    def _analyze_plan_for_suggestions(self, plan_data: dict[str, Any]) -> list[str]:
        """Analyze query plan and generate optimization suggestions."""
        suggestions = []
        plan = plan_data.get("Plan", {})

        # Check for sequential scans on large tables
        if plan.get("Node Type") == "Seq Scan":
            rows = plan.get("Actual Rows", 0)
            if rows > 1000:
                table = plan.get("Relation Name", "unknown")
                suggestions.append(
                    f"Consider adding an index on table '{table}' - "
                    f"sequential scan on {rows} rows detected"
                )

        # Check for missing indexes on joins
        if "Hash Join" in str(plan) or "Nested Loop" in str(plan):
            if plan.get("Total Cost", 0) > 1000:
                suggestions.append(
                    "High cost join detected - consider adding indexes on join columns"
                )

        # Check for sorting operations
        if plan.get("Node Type") == "Sort":
            sort_key = plan.get("Sort Key", [])
            if sort_key:
                suggestions.append(
                    f"Consider adding an index on sort columns: {sort_key}"
                )

        # Check execution time
        exec_time = plan_data.get("Execution Time", 0)
        if exec_time > 100:  # 100ms threshold
            suggestions.append(
                f"Query execution time is {exec_time}ms - consider optimization"
            )

        return suggestions

    @beartype
    async def suggest_indexes(
        self,
        table_name: str,
        min_cardinality: int = 100,
    ) -> Result[list[IndexSuggestion], str]:
        """Suggest missing indexes based on table statistics."""
        query = """
            WITH column_stats AS (
                SELECT
                    schemaname,
                    tablename,
                    attname,
                    n_distinct,
                    correlation,
                    null_frac
                FROM pg_stats
                WHERE tablename = $1
                AND n_distinct > $2
            ),
            existing_indexes AS (
                SELECT
                    a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid
                AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = $1::regclass
            )
            SELECT
                cs.schemaname,
                cs.tablename,
                cs.attname,
                cs.n_distinct,
                cs.correlation
            FROM column_stats cs
            LEFT JOIN existing_indexes ei ON cs.attname = ei.attname
            WHERE ei.attname IS NULL
            ORDER BY cs.n_distinct DESC
        """

        try:
            async with self._db.acquire_read() as conn:
                stats = await conn.fetch(query, table_name, min_cardinality)

                suggestions = []
                for stat in stats:
                    # Determine index type based on statistics
                    if stat["n_distinct"] > 10000:
                        index_type = "btree"  # B-tree for high cardinality
                    elif abs(stat["correlation"]) > 0.9:
                        index_type = "brin"  # BRIN for correlated data
                    else:
                        index_type = "btree"

                    suggestion = IndexSuggestion(
                        table_name=stat["tablename"],
                        column_name=stat["attname"],
                        index_type=index_type,
                        create_statement=(
                            f"CREATE INDEX idx_{stat['tablename']}_{stat['attname']} "
                            f"ON {stat['schemaname']}.{stat['tablename']} "
                            f"USING {index_type} ({stat['attname']})"
                        ),
                        estimated_improvement=(
                            f"High cardinality column (n_distinct: {stat['n_distinct']}) "
                            f"without index"
                        ),
                    )
                    suggestions.append(suggestion)

                return Ok(suggestions)

        except Exception as e:
            return Err(f"Failed to analyze indexes: {str(e)}")

    @beartype
    async def analyze_slow_queries(
        self,
        threshold_ms: float = 100.0,
        limit: int = 20,
    ) -> Result[list[SlowQuery], str]:
        """Find slow queries from pg_stat_statements."""
        query = """
            SELECT
                query,
                calls,
                total_exec_time as total_time_ms,
                mean_exec_time as mean_time_ms,
                stddev_exec_time as stddev_time_ms,
                rows
            FROM pg_stat_statements
            WHERE mean_exec_time > $1
            AND query NOT LIKE '%pg_stat_statements%'
            ORDER BY mean_exec_time DESC
            LIMIT $2
        """

        try:
            async with self._db.acquire_admin() as conn:
                # Enable pg_stat_statements if not already enabled
                await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")

                results = await conn.fetch(query, threshold_ms, limit)

                slow_queries = [
                    SlowQuery(
                        query=self._sanitize_query(row["query"]),
                        calls=row["calls"],
                        total_time_ms=row["total_time_ms"],
                        mean_time_ms=row["mean_time_ms"],
                        stddev_time_ms=row["stddev_time_ms"] or 0.0,
                        rows=row["rows"],
                    )
                    for row in results
                ]

                return Ok(slow_queries)

        except Exception as e:
            return Err(f"Failed to analyze slow queries: {str(e)}")

    @beartype
    def _sanitize_query(self, query: str) -> str:
        """Sanitize query for display by removing sensitive data."""
        # Remove potential sensitive data patterns
        import re

        # Remove string literals
        query = re.sub(r"'[^']*'", "'***'", query)

        # Remove numeric literals that might be IDs
        query = re.sub(r"\b\d{6,}\b", "***", query)

        # Truncate very long queries
        if len(query) > 500:
            query = query[:500] + "..."

        return query

    @beartype
    async def check_table_bloat(
        self,
        threshold_percent: float = 20.0,
    ) -> Result[list[dict[str, Any]], str]:
        """Check for table bloat that affects performance."""
        query = """
            WITH constants AS (
                SELECT current_setting('block_size')::int AS block_size
            ),
            bloat_info AS (
                SELECT
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
                    round(100 * (pg_relation_size(schemaname||'.'||tablename) -
                          pg_stat_get_live_tuples(c.oid) *
                          (SELECT block_size FROM constants)) /
                          pg_relation_size(schemaname||'.'||tablename)::numeric, 2) AS bloat_percent
                FROM pg_tables
                JOIN pg_class c ON c.relname = tablename
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                AND pg_relation_size(schemaname||'.'||tablename) > 1000000  -- 1MB minimum
            )
            SELECT * FROM bloat_info
            WHERE bloat_percent > $1
            ORDER BY bloat_percent DESC
        """

        try:
            async with self._db.acquire_admin() as conn:
                results = await conn.fetch(query, threshold_percent)

                bloated_tables = [
                    {
                        "schema": row["schemaname"],
                        "table": row["tablename"],
                        "size": row["table_size"],
                        "bloat_percent": float(row["bloat_percent"]),
                        "action": f"VACUUM FULL {row['schemaname']}.{row['tablename']}",
                    }
                    for row in results
                ]

                return Ok(bloated_tables)

        except Exception as e:
            return Err(f"Failed to check table bloat: {str(e)}")

    @beartype
    async def optimize_connection_settings(
        self,
        workload_type: str = "mixed",  # oltp, olap, mixed
    ) -> dict[str, str]:
        """Generate optimal PostgreSQL settings for workload type."""
        settings = {}

        if workload_type == "oltp":
            settings.update(
                {
                    "shared_buffers": "25%",  # of RAM
                    "effective_cache_size": "75%",  # of RAM
                    "work_mem": "4MB",
                    "maintenance_work_mem": "64MB",
                    "random_page_cost": "1.1",  # SSD
                    "checkpoint_completion_target": "0.9",
                    "wal_buffers": "16MB",
                    "max_connections": "200",
                }
            )
        elif workload_type == "olap":
            settings.update(
                {
                    "shared_buffers": "40%",  # More for analytics
                    "effective_cache_size": "80%",
                    "work_mem": "128MB",  # More for sorts/joins
                    "maintenance_work_mem": "2GB",
                    "random_page_cost": "1.1",
                    "max_parallel_workers_per_gather": "4",
                    "max_parallel_workers": "8",
                    "enable_partitionwise_join": "on",
                }
            )
        else:  # mixed
            settings.update(
                {
                    "shared_buffers": "30%",
                    "effective_cache_size": "75%",
                    "work_mem": "16MB",
                    "maintenance_work_mem": "256MB",
                    "random_page_cost": "1.1",
                    "checkpoint_completion_target": "0.9",
                    "max_connections": "300",
                    "statement_timeout": "300000",  # 5 minutes
                }
            )

        # Common optimizations
        settings.update(
            {
                "log_min_duration_statement": "1000",  # Log queries > 1s
                "log_checkpoints": "on",
                "log_connections": "on",
                "log_disconnections": "on",
                "log_lock_waits": "on",
                "log_temp_files": "0",
                "track_io_timing": "on",
                "track_functions": "all",
                "autovacuum": "on",
                "autovacuum_naptime": "30s",
            }
        )

        return settings
# SYSTEM_BOUNDARY: Query optimization requires flexible dict structures for query plan analysis and performance metrics collection
