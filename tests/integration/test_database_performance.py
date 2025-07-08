"""Test database performance and verify indexes are working properly.

This script runs various queries to ensure indexes are being used effectively
and measures query performance.

Usage:
    python scripts/test_database_performance.py
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any

import asyncpg
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()


class PerformanceTester:
    """Database performance testing utility."""

    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn
        self.results: list[dict[str, Any]] = []

    async def run_query_with_timing(self, name: str, query: str, *args) -> None:
        """Run a query and measure execution time."""
        print(f"\n📊 Testing: {name}")
        print(f"   Query: {query[:100]}...")

        # Warm up cache
        await self.conn.fetch(query, *args)

        # Run multiple times for average
        times = []
        for i in range(5):
            start = time.perf_counter()
            result = await self.conn.fetch(query, *args)
            end = time.perf_counter()
            times.append((end - start) * 1000)  # Convert to ms

        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        # Get query plan
        explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
        plan_result = await self.conn.fetchval(explain_query, *args)

        # Check if index is used
        plan_str = str(plan_result)
        index_used = "Index Scan" in plan_str or "Index Only Scan" in plan_str

        print(
            f"   ✅ Average time: {avg_time:.2f}ms (min: {min_time:.2f}ms, max: {max_time:.2f}ms)"
        )
        print(f"   ✅ Rows returned: {len(result)}")
        print(f"   ✅ Index used: {'Yes' if index_used else 'No ⚠️'}")

        self.results.append(
            {
                "test": name,
                "avg_time_ms": avg_time,
                "min_time_ms": min_time,
                "max_time_ms": max_time,
                "rows": len(result),
                "index_used": index_used,
            }
        )

    async def test_quotes_indexes(self) -> None:
        """Test quote table indexes."""
        print("\n🔍 Testing Quote Table Indexes")

        # Test quote number lookup (unique index)
        await self.run_query_with_timing(
            "Quote by quote_number",
            "SELECT * FROM quotes WHERE quote_number = $1",
            "QUOT-2025-0000001",
        )

        # Test customer quotes (foreign key index)
        await self.run_query_with_timing(
            "Quotes by customer_id",
            "SELECT * FROM quotes WHERE customer_id = $1 ORDER BY created_at DESC LIMIT 10",
            "00000000-0000-0000-0000-000000000001",
        )

        # Test status filtering
        await self.run_query_with_timing(
            "Quotes by status",
            "SELECT * FROM quotes WHERE status = $1 LIMIT 100",
            "quoted",
        )

        # Test state/product composite index
        await self.run_query_with_timing(
            "Quotes by state and product",
            "SELECT * FROM quotes WHERE state = $1 AND product_type = $2 LIMIT 50",
            "CA",
            "auto",
        )

        # Test expiration queries
        await self.run_query_with_timing(
            "Expiring quotes",
            "SELECT * FROM quotes WHERE expires_at BETWEEN $1 AND $2",
            datetime.utcnow(),
            datetime.utcnow() + timedelta(days=7),
        )

        # Test JSONB GIN index on vehicle_info
        await self.run_query_with_timing(
            "Quotes by vehicle make (JSONB)",
            "SELECT * FROM quotes WHERE vehicle_info @> $1",
            '{"make": "Toyota"}',
        )

    async def test_rate_tables_indexes(self) -> None:
        """Test rate table indexes."""
        print("\n🔍 Testing Rate Table Indexes")

        # Test state/product lookup
        await self.run_query_with_timing(
            "Rates by state and product",
            """
            SELECT * FROM rate_tables
            WHERE state = $1 AND product_type = $2
            AND effective_date <= CURRENT_DATE
            AND (expiration_date IS NULL OR expiration_date > CURRENT_DATE)
            """,
            "CA",
            "auto",
        )

        # Test unique constraint lookup
        await self.run_query_with_timing(
            "Rate by unique key",
            """
            SELECT * FROM rate_tables
            WHERE state = $1 AND product_type = $2
            AND coverage_type = $3 AND effective_date = $4
            """,
            "CA",
            "auto",
            "liability",
            datetime.utcnow().date(),
        )

    async def test_analytics_indexes(self) -> None:
        """Test analytics table indexes."""
        print("\n🔍 Testing Analytics Table Indexes")

        # Test time-series queries
        await self.run_query_with_timing(
            "Analytics events by time range",
            """
            SELECT * FROM analytics_events
            WHERE created_at >= $1 AND created_at < $2
            ORDER BY created_at DESC LIMIT 1000
            """,
            datetime.utcnow() - timedelta(hours=1),
            datetime.utcnow(),
        )

        # Test type/category composite index
        await self.run_query_with_timing(
            "Analytics by type and category",
            """
            SELECT COUNT(*), AVG(value) as avg_value
            FROM analytics_events
            WHERE event_type = $1 AND event_category = $2
            AND created_at >= $3
            GROUP BY DATE_TRUNC('hour', created_at)
            """,
            "quote_created",
            "conversion",
            datetime.utcnow() - timedelta(days=1),
        )

        # Test geographic queries
        await self.run_query_with_timing(
            "Analytics by geography",
            """
            SELECT state, COUNT(*) as event_count, AVG(value) as avg_value
            FROM analytics_events
            WHERE state IS NOT NULL
            AND created_at >= $1
            GROUP BY state
            ORDER BY event_count DESC
            """,
            datetime.utcnow() - timedelta(days=7),
        )

    async def test_admin_indexes(self) -> None:
        """Test admin table indexes."""
        print("\n🔍 Testing Admin Table Indexes")

        # Test admin activity logs by user
        await self.run_query_with_timing(
            "Admin activity by user",
            """
            SELECT * FROM admin_activity_logs
            WHERE admin_user_id = $1
            ORDER BY created_at DESC LIMIT 50
            """,
            "00000000-0000-0000-0000-000000000001",
        )

        # Test high-risk activity partial index
        await self.run_query_with_timing(
            "High-risk admin activities",
            """
            SELECT * FROM admin_activity_logs
            WHERE risk_score >= 70
            AND created_at >= $1
            ORDER BY risk_score DESC, created_at DESC
            """,
            datetime.utcnow() - timedelta(days=30),
        )

        # Test pending approvals partial index
        await self.run_query_with_timing(
            "Pending rate approvals",
            """
            SELECT * FROM admin_rate_approvals
            WHERE status = 'pending'
            ORDER BY priority DESC, submitted_at ASC
            """,
        )

    async def test_security_indexes(self) -> None:
        """Test security table indexes."""
        print("\n🔍 Testing Security Table Indexes")

        # Test session lookup by token
        await self.run_query_with_timing(
            "Session by token hash",
            "SELECT * FROM user_sessions WHERE session_token_hash = $1",
            "sample_token_hash_12345",
        )

        # Test active WebSocket connections partial index
        await self.run_query_with_timing(
            "Active WebSocket connections",
            """
            SELECT * FROM websocket_connections
            WHERE user_id = $1 AND disconnected_at IS NULL
            """,
            "00000000-0000-0000-0000-000000000001",
        )

        # Test audit log partitioned queries
        await self.run_query_with_timing(
            "Audit logs for current month",
            """
            SELECT COUNT(*) as total, COUNT(DISTINCT user_id) as unique_users
            FROM audit_logs
            WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)
            """,
        )

    async def test_complex_joins(self) -> None:
        """Test complex queries with joins."""
        print("\n🔍 Testing Complex Join Queries")

        # Test quote with customer and policy join
        await self.run_query_with_timing(
            "Quote details with customer and policy",
            """
            SELECT
                q.quote_number,
                q.total_premium,
                c.external_id as customer_id,
                p.policy_number
            FROM quotes q
            LEFT JOIN customers c ON q.customer_id = c.id
            LEFT JOIN policies p ON q.converted_to_policy_id = p.id
            WHERE q.status = 'bound'
            AND q.created_at >= $1
            LIMIT 100
            """,
            datetime.utcnow() - timedelta(days=30),
        )

        # Test rate calculation join
        await self.run_query_with_timing(
            "Rate lookup with territory factors",
            """
            SELECT
                rt.base_rate,
                rt.territory_factors,
                tf.base_factor,
                tf.catastrophe_factor
            FROM rate_tables rt
            LEFT JOIN territory_factors tf ON
                tf.state = rt.state
                AND tf.product_type = rt.product_type
                AND tf.zip_code = $3
            WHERE rt.state = $1
            AND rt.product_type = $2
            AND rt.coverage_type = 'liability'
            AND rt.effective_date <= CURRENT_DATE
            AND (rt.expiration_date IS NULL OR rt.expiration_date > CURRENT_DATE)
            """,
            "CA",
            "auto",
            "90210",
        )

    def print_summary(self) -> None:
        """Print performance test summary."""
        print("\n" + "=" * 60)
        print("📊 PERFORMANCE TEST SUMMARY")
        print("=" * 60)

        # Group by performance
        fast_queries = [r for r in self.results if r["avg_time_ms"] < 10]
        medium_queries = [r for r in self.results if 10 <= r["avg_time_ms"] < 50]
        slow_queries = [r for r in self.results if r["avg_time_ms"] >= 50]

        print(f"\n✅ Fast queries (<10ms): {len(fast_queries)}")
        for r in fast_queries:
            print(f"   - {r['test']}: {r['avg_time_ms']:.2f}ms")

        print(f"\n⚠️  Medium queries (10-50ms): {len(medium_queries)}")
        for r in medium_queries:
            print(f"   - {r['test']}: {r['avg_time_ms']:.2f}ms")

        print(f"\n❌ Slow queries (>50ms): {len(slow_queries)}")
        for r in slow_queries:
            print(
                f"   - {r['test']}: {r['avg_time_ms']:.2f}ms {'(NO INDEX!)' if not r['index_used'] else ''}"
            )

        # Check for missing indexes
        no_index = [r for r in self.results if not r["index_used"]]
        if no_index:
            print(f"\n⚠️  QUERIES NOT USING INDEXES: {len(no_index)}")
            for r in no_index:
                print(f"   - {r['test']}")

        # Overall stats
        total_time = sum(r["avg_time_ms"] for r in self.results)
        avg_time = total_time / len(self.results) if self.results else 0

        print("\n📈 Overall Statistics:")
        print(f"   - Total queries tested: {len(self.results)}")
        print(f"   - Average query time: {avg_time:.2f}ms")
        print(
            f"   - Queries using indexes: {len(self.results) - len(no_index)}/{len(self.results)}"
        )

        # Performance grade
        if avg_time < 20 and len(no_index) == 0:
            grade = "A+ 🌟"
        elif avg_time < 30 and len(no_index) <= 1:
            grade = "A 🎯"
        elif avg_time < 50 and len(no_index) <= 2:
            grade = "B 👍"
        else:
            grade = "C 💔"

        print(f"\n🏆 Performance Grade: {grade}")


async def main():
    """Run all performance tests."""

    # Database connection
    database_url = os.getenv("DATABASE_URL", "postgresql://localhost/pd_prime_demo")

    try:
        print("🚀 Starting Database Performance Tests")
        print(f"📍 Database: {database_url.split('@')[-1]}")  # Hide credentials

        conn = await asyncpg.connect(database_url)
        print("✅ Connected to database")

        # Enable query timing
        await conn.execute("SET log_statement = 'all'")
        await conn.execute("SET log_duration = on")

        tester = PerformanceTester(conn)

        # Run all tests
        await tester.test_quotes_indexes()
        await tester.test_rate_tables_indexes()
        await tester.test_analytics_indexes()
        await tester.test_admin_indexes()
        await tester.test_security_indexes()
        await tester.test_complex_joins()

        # Print summary
        tester.print_summary()

    except Exception as e:
        print(f"\n❌ Error during performance testing: {e}")
        raise
    finally:
        if "conn" in locals():
            await conn.close()
            print("\n👋 Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())
