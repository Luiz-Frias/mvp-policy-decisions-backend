#!/usr/bin/env python3
"""Database health monitoring script for proactive issue detection."""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from beartype import beartype

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.policy_core.core.config import get_settings
from src.policy_core.core.database_enhanced import Database
from src.policy_core.core.query_optimizer import QueryOptimizer


@beartype
class DatabaseHealthMonitor:
    """Monitor database health metrics and alert on issues."""

    def __init__(self) -> None:
        """Initialize health monitor."""
        self.db = Database()
        self.optimizer = QueryOptimizer(self.db)
        self.settings = get_settings()
        self.alerts: list[dict[str, Any]] = []

    @beartype
    async def check_connection_pool_health(self) -> dict[str, Any]:
        """Check connection pool utilization and health."""
        stats = await self.db.get_pool_stats()

        health_status = {
            "pool_size": stats.size,
            "free_connections": stats.free_size,
            "active_connections": stats.connections_active,
            "utilization_percent": 0.0,
            "exhausted_events": stats.pool_exhausted_count,
            "status": "healthy",
            "issues": [],
        }

        # Calculate utilization
        if stats.size > 0:
            utilization = (stats.size - stats.free_size) / stats.size
            health_status["utilization_percent"] = utilization * 100

            # Check thresholds
            if utilization > 0.9:
                health_status["status"] = "critical"
                health_status["issues"].append(
                    f"Pool utilization critically high: {utilization:.1%}"
                )
                self.alerts.append(
                    {
                        "severity": "critical",
                        "component": "connection_pool",
                        "message": f"Connection pool at {utilization:.1%} capacity",
                        "timestamp": datetime.utcnow(),
                    }
                )
            elif utilization > 0.7:
                health_status["status"] = "warning"
                health_status["issues"].append(
                    f"Pool utilization high: {utilization:.1%}"
                )

        # Check exhaustion events
        if stats.pool_exhausted_count > 0:
            health_status["issues"].append(
                f"Pool exhausted {stats.pool_exhausted_count} times"
            )

        return health_status

    @beartype
    async def check_query_performance(self) -> dict[str, Any]:
        """Check query performance metrics."""
        stats = await self.db.get_pool_stats()

        perf_status = {
            "average_query_time_ms": stats.average_query_time_ms,
            "slow_queries_count": stats.queries_slow,
            "total_queries": stats.queries_total,
            "slow_query_rate": 0.0,
            "status": "healthy",
            "issues": [],
        }

        # Calculate slow query rate
        if stats.queries_total > 0:
            slow_rate = stats.queries_slow / stats.queries_total
            perf_status["slow_query_rate"] = slow_rate * 100

            if slow_rate > 0.05:  # More than 5% slow queries
                perf_status["status"] = "warning"
                perf_status["issues"].append(f"High slow query rate: {slow_rate:.1%}")

                # Get specific slow queries
                slow_queries_result = await self.optimizer.analyze_slow_queries(
                    threshold_ms=1000, limit=5
                )
                if slow_queries_result.is_ok():
                    perf_status["top_slow_queries"] = [
                        {
                            "query": (
                                sq.query[:100] + "..."
                                if len(sq.query) > 100
                                else sq.query
                            ),
                            "mean_time_ms": sq.mean_time_ms,
                            "calls": sq.calls,
                        }
                        for sq in slow_queries_result.ok_value
                    ]

        # Check average query time
        if stats.average_query_time_ms > 100:
            perf_status["status"] = "warning"
            perf_status["issues"].append(
                f"High average query time: {stats.average_query_time_ms:.1f}ms"
            )

        return perf_status

    @beartype
    async def check_cache_effectiveness(self) -> dict[str, Any]:
        """Check cache hit rates and effectiveness."""
        # Query PostgreSQL cache statistics
        cache_query = """
            SELECT
                sum(heap_blks_read) as heap_read,
                sum(heap_blks_hit) as heap_hit,
                sum(idx_blks_read) as idx_read,
                sum(idx_blks_hit) as idx_hit,
                CASE
                    WHEN sum(heap_blks_hit) + sum(heap_blks_read) > 0
                    THEN sum(heap_blks_hit)::float / (sum(heap_blks_hit) + sum(heap_blks_read))
                    ELSE 0
                END as heap_hit_rate,
                CASE
                    WHEN sum(idx_blks_hit) + sum(idx_blks_read) > 0
                    THEN sum(idx_blks_hit)::float / (sum(idx_blks_hit) + sum(idx_blks_read))
                    ELSE 0
                END as idx_hit_rate
            FROM pg_statio_user_tables
        """

        async with self.db.acquire_read() as conn:
            cache_stats = await conn.fetchrow(cache_query)

        cache_status = {
            "heap_hit_rate": float(cache_stats["heap_hit_rate"]) * 100,
            "index_hit_rate": float(cache_stats["idx_hit_rate"]) * 100,
            "status": "healthy",
            "issues": [],
        }

        # Check thresholds
        if cache_stats["heap_hit_rate"] < 0.9:
            cache_status["status"] = "warning"
            cache_status["issues"].append(
                f"Low heap cache hit rate: {cache_stats['heap_hit_rate']:.1%}"
            )

        if cache_stats["idx_hit_rate"] < 0.95:
            cache_status["status"] = "warning"
            cache_status["issues"].append(
                f"Low index cache hit rate: {cache_stats['idx_hit_rate']:.1%}"
            )

        return cache_status

    @beartype
    async def check_replication_lag(self) -> dict[str, Any]:
        """Check replication lag for read replicas."""
        replication_status = {
            "replicas": [],
            "max_lag_seconds": 0,
            "status": "healthy",
            "issues": [],
        }

        # Check replication status
        replication_query = """
            SELECT
                client_addr,
                state,
                sync_state,
                EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) as lag_seconds
            FROM pg_stat_replication
        """

        try:
            async with self.db.acquire_admin() as conn:
                replicas = await conn.fetch(replication_query)

                for replica in replicas:
                    lag = replica["lag_seconds"] or 0
                    replica_info = {
                        "address": str(replica["client_addr"]),
                        "state": replica["state"],
                        "sync_state": replica["sync_state"],
                        "lag_seconds": lag,
                    }
                    replication_status["replicas"].append(replica_info)

                    if lag > replication_status["max_lag_seconds"]:
                        replication_status["max_lag_seconds"] = lag

                    # Check lag thresholds
                    if lag > 10:
                        replication_status["status"] = "critical"
                        replication_status["issues"].append(
                            f"High replication lag on {replica['client_addr']}: {lag:.1f}s"
                        )
                    elif lag > 5:
                        replication_status["status"] = "warning"
                        replication_status["issues"].append(
                            f"Replication lag on {replica['client_addr']}: {lag:.1f}s"
                        )

        except Exception as e:
            replication_status["issues"].append(
                f"Failed to check replication: {str(e)}"
            )

        return replication_status

    @beartype
    async def check_index_usage(self) -> dict[str, Any]:
        """Check for unused or missing indexes."""
        index_status = {
            "unused_indexes": [],
            "missing_indexes": [],
            "status": "healthy",
            "issues": [],
        }

        # Find unused indexes
        unused_query = """
            SELECT
                schemaname,
                tablename,
                indexname,
                idx_scan,
                pg_size_pretty(pg_relation_size(indexrelid)) as index_size
            FROM pg_stat_user_indexes
            WHERE idx_scan = 0
            AND indexrelid::regclass::text !~ 'pkey'
            AND pg_relation_size(indexrelid) > 1000000  -- Only indexes > 1MB
            ORDER BY pg_relation_size(indexrelid) DESC
        """

        async with self.db.acquire_read() as conn:
            unused = await conn.fetch(unused_query)

            for idx in unused:
                index_status["unused_indexes"].append(
                    {
                        "table": f"{idx['schemaname']}.{idx['tablename']}",
                        "index": idx["indexname"],
                        "size": idx["index_size"],
                    }
                )

        # Check for missing indexes on important tables
        important_tables = ["quotes", "policies", "customers", "claims"]
        for table in important_tables:
            suggestions_result = await self.optimizer.suggest_indexes(table)
            if suggestions_result.is_ok() and suggestions_result.ok_value:
                for suggestion in suggestions_result.ok_value[:3]:  # Top 3 per table
                    index_status["missing_indexes"].append(
                        {
                            "table": table,
                            "column": suggestion.column_name,
                            "type": suggestion.index_type,
                            "reason": suggestion.estimated_improvement,
                        }
                    )

        # Update status based on findings
        if len(index_status["unused_indexes"]) > 5:
            index_status["status"] = "warning"
            index_status["issues"].append(
                f"Found {len(index_status['unused_indexes'])} unused indexes"
            )

        if len(index_status["missing_indexes"]) > 0:
            index_status["status"] = "warning"
            index_status["issues"].append(
                f"Found {len(index_status['missing_indexes'])} missing indexes"
            )

        return index_status

    @beartype
    async def check_table_bloat(self) -> dict[str, Any]:
        """Check for table bloat."""
        bloat_result = await self.optimizer.check_table_bloat(threshold_percent=20.0)

        bloat_status = {
            "bloated_tables": [],
            "total_wasted_space": 0,
            "status": "healthy",
            "issues": [],
        }

        if bloat_result.is_ok():
            bloated = bloat_result.ok_value
            bloat_status["bloated_tables"] = bloated

            if len(bloated) > 0:
                bloat_status["status"] = "warning"
                bloat_status["issues"].append(f"Found {len(bloated)} bloated tables")

                # Alert on severely bloated tables
                for table in bloated:
                    if table["bloat_percent"] > 40:
                        self.alerts.append(
                            {
                                "severity": "warning",
                                "component": "table_bloat",
                                "message": f"Table {table['table']} is {table['bloat_percent']}% bloated",
                                "timestamp": datetime.utcnow(),
                                "action": table["action"],
                            }
                        )

        return bloat_status

    @beartype
    async def generate_health_report(self) -> dict[str, Any]:
        """Generate comprehensive health report."""
        print("🏥 Starting database health check...")

        # Initialize database connection
        await self.db.connect()

        try:
            # Run all health checks
            connection_health = await self.check_connection_pool_health()
            query_performance = await self.check_query_performance()
            cache_health = await self.check_cache_effectiveness()
            replication_health = await self.check_replication_lag()
            index_health = await self.check_index_usage()
            bloat_health = await self.check_table_bloat()

            # Determine overall health
            all_statuses = [
                connection_health["status"],
                query_performance["status"],
                cache_health["status"],
                replication_health["status"],
                index_health["status"],
                bloat_health["status"],
            ]

            if "critical" in all_statuses:
                overall_status = "critical"
            elif "warning" in all_statuses:
                overall_status = "warning"
            else:
                overall_status = "healthy"

            report = {
                "timestamp": datetime.utcnow().isoformat(),
                "overall_status": overall_status,
                "components": {
                    "connection_pool": connection_health,
                    "query_performance": query_performance,
                    "cache": cache_health,
                    "replication": replication_health,
                    "indexes": index_health,
                    "table_bloat": bloat_health,
                },
                "alerts": self.alerts,
                "recommendations": self._generate_recommendations(all_statuses),
            }

            return report

        finally:
            await self.db.disconnect()

    @beartype
    def _generate_recommendations(self, component_statuses: list[str]) -> list[str]:
        """Generate actionable recommendations based on health status."""
        recommendations = []

        # Connection pool recommendations
        if any(alert["component"] == "connection_pool" for alert in self.alerts):
            recommendations.append(
                "Consider increasing connection pool size or adding more app instances"
            )
            recommendations.append(
                "Review pgBouncer configuration for optimal connection multiplexing"
            )

        # Query performance recommendations
        if any(alert.get("component") == "query_performance" for alert in self.alerts):
            recommendations.append(
                "Run EXPLAIN ANALYZE on slow queries to identify optimization opportunities"
            )
            recommendations.append(
                "Consider adding missing indexes identified in the index health check"
            )

        # General recommendations
        if "warning" in component_statuses or "critical" in component_statuses:
            recommendations.append(
                "Schedule maintenance window for VACUUM FULL on bloated tables"
            )
            recommendations.append(
                "Review and drop unused indexes to improve write performance"
            )
            recommendations.append(
                "Enable query performance monitoring with pg_stat_statements"
            )

        return recommendations

    @beartype
    def print_report(self, report: dict[str, Any]) -> None:
        """Print formatted health report."""
        print("\n" + "=" * 80)
        print(f"DATABASE HEALTH REPORT - {report['timestamp']}")
        print("=" * 80)

        # Overall status with emoji
        status_emoji = {
            "healthy": "✅",
            "warning": "⚠️",
            "critical": "🚨",
        }
        print(
            f"\nOverall Status: {status_emoji.get(report['overall_status'], '❓')} {report['overall_status'].upper()}"
        )

        # Component summaries
        print("\nComponent Health:")
        for component, health in report["components"].items():
            emoji = status_emoji.get(health["status"], "❓")
            print(
                f"  {emoji} {component.replace('_', ' ').title()}: {health['status']}"
            )
            for issue in health.get("issues", []):
                print(f"     - {issue}")

        # Alerts
        if report["alerts"]:
            print("\n🚨 ALERTS:")
            for alert in report["alerts"]:
                print(
                    f"  [{alert['severity'].upper()}] {alert['component']}: {alert['message']}"
                )
                if "action" in alert:
                    print(f"    Action: {alert['action']}")

        # Recommendations
        if report["recommendations"]:
            print("\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(report["recommendations"], 1):
                print(f"  {i}. {rec}")

        print("\n" + "=" * 80)


@beartype
async def main() -> None:
    """Run health monitoring."""
    monitor = DatabaseHealthMonitor()
    report = await monitor.generate_health_report()

    # Print human-readable report
    monitor.print_report(report)

    # Save JSON report
    report_path = Path("db_health_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n📄 Full report saved to: {report_path}")

    # Exit with appropriate code
    if report["overall_status"] == "critical":
        sys.exit(2)
    elif report["overall_status"] == "warning":
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
