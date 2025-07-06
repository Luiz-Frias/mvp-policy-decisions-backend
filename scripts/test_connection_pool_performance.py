#!/usr/bin/env python3
"""Connection pool performance testing and benchmarking."""

import asyncio
import statistics
import sys
import time
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from beartype import beartype


@beartype
class ConnectionPoolBenchmark:
    """Benchmark connection pool performance under various loads."""

    def __init__(self) -> None:
        """Initialize benchmark."""
        self.results: dict[str, Any] = {}

    @beartype
    async def simulate_connection_acquisition(
        self, pool_size: int, concurrent_requests: int, duration_seconds: int = 10
    ) -> dict[str, Any]:
        """Simulate concurrent connection acquisition."""
        print(
            f"🔍 Testing pool_size={pool_size}, concurrent_requests={concurrent_requests}"
        )

        # Simulate connection pool behavior
        semaphore = asyncio.Semaphore(pool_size)

        request_times = []
        timeouts = 0
        successful_acquisitions = 0

        async def simulate_request():
            """Simulate a single request requiring database connection."""
            nonlocal timeouts, successful_acquisitions

            start_time = time.perf_counter()

            try:
                # Try to acquire connection (simulate with semaphore)
                async with asyncio.timeout(1.0):  # 1 second timeout
                    async with semaphore:
                        successful_acquisitions += 1
                        # Simulate query execution time
                        await asyncio.sleep(
                            0.01 + (time.perf_counter() % 0.05)
                        )  # 10-60ms queries

                        duration = time.perf_counter() - start_time
                        request_times.append(duration * 1000)  # Convert to ms

            except TimeoutError:
                timeouts += 1

        # Start requests continuously for the specified duration
        tasks = []
        start_time = time.perf_counter()

        while time.perf_counter() - start_time < duration_seconds:
            # Start batch of concurrent requests
            batch_tasks = [
                asyncio.create_task(simulate_request())
                for _ in range(min(concurrent_requests, 100))  # Batch size limit
            ]
            tasks.extend(batch_tasks)

            # Small delay between batches to simulate realistic load
            await asyncio.sleep(0.001)

        # Wait for all tasks to complete
        await asyncio.gather(*tasks, return_exceptions=True)

        # Calculate metrics
        if request_times:
            avg_time = statistics.mean(request_times)
            p95_time = statistics.quantiles(request_times, n=20)[18]  # 95th percentile
            p99_time = statistics.quantiles(request_times, n=100)[98]  # 99th percentile
            max_time = max(request_times)
        else:
            avg_time = p95_time = p99_time = max_time = 0

        throughput = successful_acquisitions / duration_seconds

        return {
            "pool_size": pool_size,
            "concurrent_requests": concurrent_requests,
            "duration_seconds": duration_seconds,
            "successful_acquisitions": successful_acquisitions,
            "timeouts": timeouts,
            "throughput_rps": throughput,
            "avg_response_time_ms": avg_time,
            "p95_response_time_ms": p95_time,
            "p99_response_time_ms": p99_time,
            "max_response_time_ms": max_time,
            "timeout_rate": (
                timeouts / (successful_acquisitions + timeouts)
                if (successful_acquisitions + timeouts) > 0
                else 0
            ),
        }

    @beartype
    async def run_benchmark_suite(self) -> dict[str, Any]:
        """Run comprehensive benchmark suite."""
        print("🚀 Starting Connection Pool Performance Benchmark")
        print("=" * 60)

        # Test scenarios: (pool_size, concurrent_requests)
        scenarios = [
            (10, 50),  # Under-provisioned pool
            (20, 50),  # Adequate pool
            (30, 50),  # Over-provisioned pool
            (25, 100),  # High concurrency
            (25, 200),  # Very high concurrency
            (50, 500),  # Stress test
            (25, 1000),  # 10,000 concurrent users simulation (scaled down)
        ]

        benchmark_results = []

        for pool_size, concurrent_requests in scenarios:
            result = await self.simulate_connection_acquisition(
                pool_size=pool_size,
                concurrent_requests=concurrent_requests,
                duration_seconds=5,  # Shorter duration for testing
            )
            benchmark_results.append(result)

            # Print immediate results
            print(
                f"Pool {pool_size:2d} | Concurrency {concurrent_requests:4d} | "
                f"Throughput: {result['throughput_rps']:6.1f} RPS | "
                f"P95: {result['p95_response_time_ms']:6.1f}ms | "
                f"Timeouts: {result['timeout_rate']:5.1%}"
            )

        # Find optimal configuration
        optimal_config = self._find_optimal_configuration(benchmark_results)

        return {
            "benchmark_results": benchmark_results,
            "optimal_configuration": optimal_config,
            "recommendations": self._generate_recommendations(benchmark_results),
        }

    @beartype
    def _find_optimal_configuration(
        self, results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Find optimal pool configuration based on benchmark results."""
        # Score each configuration based on throughput, latency, and timeout rate
        scored_results = []

        for result in results:
            # Normalize metrics for scoring
            throughput_score = min(
                result["throughput_rps"] / 1000, 1.0
            )  # Max score at 1000 RPS
            latency_score = max(
                0, 1.0 - (result["p95_response_time_ms"] / 100)
            )  # Penalty for > 100ms
            timeout_score = max(
                0, 1.0 - (result["timeout_rate"] * 10)
            )  # Heavy penalty for timeouts

            # Weighted composite score
            composite_score = (
                throughput_score * 0.4 + latency_score * 0.4 + timeout_score * 0.2
            )

            scored_results.append(
                {
                    **result,
                    "composite_score": composite_score,
                    "throughput_score": throughput_score,
                    "latency_score": latency_score,
                    "timeout_score": timeout_score,
                }
            )

        # Sort by composite score
        scored_results.sort(key=lambda x: x["composite_score"], reverse=True)

        return scored_results[0]

    @beartype
    def _generate_recommendations(self, results: list[dict[str, Any]]) -> list[str]:
        """Generate pool configuration recommendations."""
        recommendations = []

        # Find results with high timeout rates
        high_timeout_results = [r for r in results if r["timeout_rate"] > 0.05]
        if high_timeout_results:
            recommendations.append(
                "🚨 High timeout rates detected - consider increasing pool size or optimizing query performance"
            )

        # Find results with high latency
        high_latency_results = [r for r in results if r["p95_response_time_ms"] > 100]
        if high_latency_results:
            recommendations.append(
                "⚠️ High P95 latency detected - consider using connection pre-warming or query optimization"
            )

        # Pool sizing recommendations
        max_throughput_result = max(results, key=lambda x: x["throughput_rps"])
        recommendations.append(
            f"💡 Optimal pool size appears to be around {max_throughput_result['pool_size']} "
            f"for {max_throughput_result['concurrent_requests']} concurrent requests"
        )

        # pgBouncer recommendations
        if any(r["concurrent_requests"] > r["pool_size"] * 10 for r in results):
            recommendations.append(
                "🔧 Consider using pgBouncer with transaction pooling for high concurrency scenarios"
            )

        return recommendations

    @beartype
    def print_results(self, results: dict[str, Any]) -> None:
        """Print formatted benchmark results."""
        print("\n" + "=" * 80)
        print("CONNECTION POOL PERFORMANCE BENCHMARK RESULTS")
        print("=" * 80)

        # Summary table
        print("\n📊 Performance Summary:")
        print("Pool | Concurrency | Throughput |   P95  |   P99  | Timeout%")
        print("-" * 58)

        for result in results["benchmark_results"]:
            print(
                f"{result['pool_size']:4d} | "
                f"{result['concurrent_requests']:11d} | "
                f"{result['throughput_rps']:10.1f} | "
                f"{result['p95_response_time_ms']:6.1f} | "
                f"{result['p99_response_time_ms']:6.1f} | "
                f"{result['timeout_rate']:7.1%}"
            )

        # Optimal configuration
        optimal = results["optimal_configuration"]
        print("\n🏆 OPTIMAL CONFIGURATION:")
        print(f"   Pool Size: {optimal['pool_size']}")
        print(f"   Concurrent Requests: {optimal['concurrent_requests']}")
        print(f"   Throughput: {optimal['throughput_rps']:.1f} RPS")
        print(f"   P95 Latency: {optimal['p95_response_time_ms']:.1f}ms")
        print(f"   Timeout Rate: {optimal['timeout_rate']:.1%}")
        print(f"   Composite Score: {optimal['composite_score']:.3f}")

        # Recommendations
        print("\n📋 RECOMMENDATIONS:")
        for i, rec in enumerate(results["recommendations"], 1):
            print(f"   {i}. {rec}")

        print("\n" + "=" * 80)


@beartype
async def main() -> None:
    """Run connection pool benchmark."""
    benchmark = ConnectionPoolBenchmark()
    results = await benchmark.run_benchmark_suite()
    benchmark.print_results(results)


if __name__ == "__main__":
    asyncio.run(main())
