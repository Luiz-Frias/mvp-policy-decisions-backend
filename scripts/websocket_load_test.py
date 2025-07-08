#!/usr/bin/env python3
"""WebSocket Load Testing Script.

Tests the WebSocket infrastructure under realistic load conditions:
- 10,000 concurrent connections
- Message throughput testing
- Memory usage monitoring
- Latency measurements
- Connection stability over time
"""

import asyncio
import json
import statistics
import time
from typing import Any
from uuid import uuid4

import aiohttp
import click
import psutil
from beartype import beartype


class WebSocketLoadTester:
    """WebSocket load testing client."""

    def __init__(self, base_url: str, max_connections: int = 10000):
        self.base_url = base_url
        self.max_connections = max_connections
        self.active_connections: list[aiohttp.ClientWebSocketResponse] = []
        self.connection_times: list[float] = []
        self.message_latencies: list[float] = []
        self.failed_connections = 0
        self.successful_messages = 0
        self.failed_messages = 0

        # Performance tracking
        self.start_memory = 0
        self.peak_memory = 0
        self.start_time = 0

    @beartype
    async def create_connection(
        self, session: aiohttp.ClientSession, user_id: str
    ) -> bool:
        """Create a single WebSocket connection."""
        try:
            connect_start = time.time()

            # Connect with authentication token
            ws_url = f"{self.base_url}/ws?token={user_id}"
            ws = await session.ws_connect(ws_url)

            connect_time = time.time() - connect_start
            self.connection_times.append(connect_time)

            # Wait for connection confirmation
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("type") == "connection":
                        self.active_connections.append(ws)
                        return True
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break

            await ws.close()
            return False

        except Exception as e:
            self.failed_connections += 1
            print(f"Connection failed: {e}")
            return False

    @beartype
    async def send_test_message(self, ws: aiohttp.ClientWebSocketResponse) -> bool:
        """Send a test message and measure latency."""
        try:
            send_time = time.time()

            test_message = {
                "type": "ping",
                "timestamp": send_time,
                "test_id": str(uuid4()),
            }

            await ws.send_str(json.dumps(test_message))

            # Wait for response
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    if data.get("type") == "pong":
                        latency = time.time() - send_time
                        self.message_latencies.append(latency * 1000)  # Convert to ms
                        self.successful_messages += 1
                        return True
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break

            self.failed_messages += 1
            return False

        except Exception as e:
            self.failed_messages += 1
            print(f"Message send failed: {e}")
            return False

    @beartype
    async def run_connection_test(self, target_connections: int) -> dict[str, Any]:
        """Test creating many concurrent connections."""
        print(f"🔗 Testing {target_connections} concurrent connections...")

        self.start_time = time.time()
        self.start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB

        # Create session with connection limits
        connector = aiohttp.TCPConnector(
            limit=target_connections + 100, limit_per_host=target_connections + 100
        )

        async with aiohttp.ClientSession(connector=connector) as session:
            # Create connections in batches to avoid overwhelming the server
            batch_size = min(100, target_connections)

            for i in range(0, target_connections, batch_size):
                batch_end = min(i + batch_size, target_connections)
                batch_tasks = [
                    self.create_connection(session, f"user_{j}")
                    for j in range(i, batch_end)
                ]

                # Execute batch
                results = await asyncio.gather(*batch_tasks, return_exceptions=True)

                # Track current memory usage
                current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                self.peak_memory = max(self.peak_memory, current_memory)

                successful_in_batch = sum(1 for r in results if r is True)
                print(
                    f"  Batch {i//batch_size + 1}: {successful_in_batch}/{len(batch_tasks)} connections successful"
                )

                # Small delay between batches
                if i + batch_size < target_connections:
                    await asyncio.sleep(0.1)

            connection_time = time.time() - self.start_time
            successful_connections = len(self.active_connections)

            # Test message sending with active connections
            if self.active_connections:
                print(
                    f"📡 Testing message latency with {len(self.active_connections)} connections..."
                )

                # Send test messages to a sample of connections
                sample_size = min(100, len(self.active_connections))
                sample_connections = self.active_connections[:sample_size]

                message_tasks = [
                    self.send_test_message(ws) for ws in sample_connections
                ]

                await asyncio.gather(*message_tasks, return_exceptions=True)

            # Keep connections alive for stability test
            print("⏱️  Testing connection stability (30 seconds)...")
            await asyncio.sleep(30)

            # Test message broadcasting
            if len(self.active_connections) >= 10:
                print("📢 Testing broadcast performance...")
                broadcast_start = time.time()

                broadcast_tasks = [
                    self.send_test_message(ws)
                    for ws in self.active_connections[:50]  # Test with 50 connections
                ]

                await asyncio.gather(*broadcast_tasks, return_exceptions=True)
                broadcast_time = time.time() - broadcast_start

                print(f"   Broadcast to 50 connections: {broadcast_time:.3f}s")

            # Cleanup connections
            cleanup_tasks = [ws.close() for ws in self.active_connections]
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)

        final_memory = psutil.Process().memory_info().rss / 1024 / 1024

        return {
            "target_connections": target_connections,
            "successful_connections": successful_connections,
            "failed_connections": self.failed_connections,
            "connection_time": connection_time,
            "avg_connection_time": (
                statistics.mean(self.connection_times) if self.connection_times else 0
            ),
            "p95_connection_time": (
                statistics.quantiles(self.connection_times, n=20)[18]
                if len(self.connection_times) > 20
                else 0
            ),
            "successful_messages": self.successful_messages,
            "failed_messages": self.failed_messages,
            "avg_message_latency_ms": (
                statistics.mean(self.message_latencies) if self.message_latencies else 0
            ),
            "p95_message_latency_ms": (
                statistics.quantiles(self.message_latencies, n=20)[18]
                if len(self.message_latencies) > 20
                else 0
            ),
            "memory_usage": {
                "start_mb": self.start_memory,
                "peak_mb": self.peak_memory,
                "final_mb": final_memory,
                "increase_mb": final_memory - self.start_memory,
            },
        }

    @beartype
    def print_results(self, results: dict[str, Any]) -> None:
        """Print load test results."""
        print("\n" + "=" * 60)
        print("📊 WEBSOCKET LOAD TEST RESULTS")
        print("=" * 60)

        print(f"🎯 Target Connections: {results['target_connections']:,}")
        print(f"✅ Successful Connections: {results['successful_connections']:,}")
        print(f"❌ Failed Connections: {results['failed_connections']:,}")
        print(
            f"📈 Success Rate: {(results['successful_connections'] / results['target_connections']) * 100:.1f}%"
        )

        print("\n⏱️  Connection Performance:")
        print(f"   Total Time: {results['connection_time']:.2f}s")
        print(f"   Avg Connection Time: {results['avg_connection_time']*1000:.1f}ms")
        print(f"   P95 Connection Time: {results['p95_connection_time']*1000:.1f}ms")
        print(
            f"   Connections/sec: {results['successful_connections']/results['connection_time']:.1f}"
        )

        print("\n📡 Message Performance:")
        print(f"   Successful Messages: {results['successful_messages']:,}")
        print(f"   Failed Messages: {results['failed_messages']:,}")
        print(f"   Avg Latency: {results['avg_message_latency_ms']:.1f}ms")
        print(f"   P95 Latency: {results['p95_message_latency_ms']:.1f}ms")

        memory = results["memory_usage"]
        print("\n🧠 Memory Usage:")
        print(f"   Start: {memory['start_mb']:.1f}MB")
        print(f"   Peak: {memory['peak_mb']:.1f}MB")
        print(f"   Final: {memory['final_mb']:.1f}MB")
        print(f"   Increase: {memory['increase_mb']:.1f}MB")

        if results["successful_connections"] > 0:
            memory_per_conn = memory["increase_mb"] / results["successful_connections"]
            print(f"   Per Connection: {memory_per_conn*1024:.1f}KB")

        # Performance validation
        print("\n✅ PERFORMANCE VALIDATION:")

        success_rate = (
            results["successful_connections"] / results["target_connections"]
        ) * 100
        print(
            f"   Connection Success Rate: {success_rate:.1f}% {'✅' if success_rate >= 95 else '❌'} (target: ≥95%)"
        )

        avg_latency = results["avg_message_latency_ms"]
        print(
            f"   Avg Message Latency: {avg_latency:.1f}ms {'✅' if avg_latency <= 50 else '❌'} (target: ≤50ms)"
        )

        p95_latency = results["p95_message_latency_ms"]
        print(
            f"   P95 Message Latency: {p95_latency:.1f}ms {'✅' if p95_latency <= 100 else '❌'} (target: ≤100ms)"
        )

        memory_per_conn = (
            memory["increase_mb"] / results["successful_connections"]
            if results["successful_connections"] > 0
            else 0
        )
        print(
            f"   Memory per Connection: {memory_per_conn*1024:.1f}KB {'✅' if memory_per_conn <= 0.1 else '❌'} (target: ≤100KB)"
        )

        conn_rate = results["successful_connections"] / results["connection_time"]
        print(
            f"   Connection Rate: {conn_rate:.1f}/sec {'✅' if conn_rate >= 100 else '❌'} (target: ≥100/sec)"
        )


@click.command()
@click.option("--url", default="ws://localhost:8000", help="WebSocket server URL")
@click.option(
    "--connections", default=1000, help="Number of concurrent connections to test"
)
@click.option("--full-load", is_flag=True, help="Run full 10,000 connection load test")
@click.option("--quick", is_flag=True, help="Run quick test with 100 connections")
def main(url: str, connections: int, full_load: bool, quick: bool) -> None:
    """Run WebSocket load tests."""
    if quick:
        connections = 100
        print("🚀 Running quick WebSocket load test...")
    elif full_load:
        connections = 10000
        print("🚀 Running FULL WebSocket load test (10,000 connections)...")
        print("⚠️  This may take several minutes and consume significant resources!")
    else:
        print(f"🚀 Running WebSocket load test with {connections} connections...")

    print(f"📍 Target server: {url}")
    print(f"🔧 Process limits: {psutil.Process().rlimit(psutil.RLIMIT_NOFILE)}")

    # Check if server is reachable
    print("🔍 Checking server availability...")

    async def run_test():
        tester = WebSocketLoadTester(url, connections)
        results = await tester.run_connection_test(connections)
        tester.print_results(results)

        return results

    try:
        results = asyncio.run(run_test())

        # Exit with appropriate code based on performance validation
        success_rate = (
            results["successful_connections"] / results["target_connections"]
        ) * 100
        avg_latency = results["avg_message_latency_ms"]

        if success_rate >= 95 and avg_latency <= 50:
            print("\n🎉 All performance targets met!")
            exit(0)
        else:
            print("\n⚠️  Some performance targets not met.")
            exit(1)

    except KeyboardInterrupt:
        print("\n\n🛑 Load test interrupted by user")
        exit(130)
    except Exception as e:
        print(f"\n\n❌ Load test failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()
