#!/usr/bin/env python3
"""Redis connectivity check utility."""

import asyncio
import sys
import time

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

try:
    from policy_core.core.cache import redis_client
except ImportError:
    print("❌ Failed to import Redis configuration")
    print("Make sure the application is properly installed")
    sys.exit(1)


class RedisCheckResult(BaseModel):
    """Result of Redis connectivity check."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
    )

    connected: bool = Field(..., description="Whether connection was successful")
    redis_version: str | None = Field(None, description="Redis server version")
    memory_used_mb: float | None = Field(None, ge=0, description="Memory used in MB")
    total_keys: int | None = Field(None, ge=0, description="Total number of keys")
    latency_ms: float | None = Field(
        None, ge=0, description="Ping latency in milliseconds"
    )
    error: str | None = Field(None, description="Error message if connection failed")


@beartype
async def check_redis_connection() -> RedisCheckResult:
    """Check Redis connectivity and return detailed results."""
    start_time = time.perf_counter()

    try:
        # Test basic connectivity with ping
        await redis_client.ping()
        latency_ms = (time.perf_counter() - start_time) * 1000

        # Get server info
        info = await redis_client.info()
        redis_version = info.get("redis_version", "Unknown")

        # Get memory usage
        memory_info = await redis_client.info("memory")
        memory_used_bytes = memory_info.get("used_memory", 0)
        memory_used_mb = round(memory_used_bytes / 1024 / 1024, 2)

        # Get total keys across all databases
        total_keys = 0
        keyspace_info = await redis_client.info("keyspace")
        for db_name, db_info in keyspace_info.items():
            if db_name.startswith("db"):
                total_keys += db_info.get("keys", 0)

        return RedisCheckResult(
            connected=True,
            redis_version=redis_version,
            memory_used_mb=memory_used_mb,
            total_keys=total_keys,
            latency_ms=round(latency_ms, 2),
        )

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        return RedisCheckResult(connected=False, error=error_msg)


@beartype
async def test_redis_operations() -> None:
    """Test basic Redis operations."""
    test_key = "pd_prime:test:connectivity_check"
    test_value = "test_value_123"

    try:
        # Test SET operation
        await redis_client.set(test_key, test_value, ex=60)  # 60 second expiry
        print("  ✅ SET operation successful")

        # Test GET operation
        retrieved = await redis_client.get(test_key)
        if retrieved == test_value:
            print("  ✅ GET operation successful")
        else:
            print("  ❌ GET operation failed: value mismatch")

        # Test DELETE operation
        deleted = await redis_client.delete(test_key)
        if deleted:
            print("  ✅ DELETE operation successful")
        else:
            print("  ❌ DELETE operation failed")

        # Test expiration
        await redis_client.set(test_key, test_value, ex=1)
        ttl = await redis_client.ttl(test_key)
        print(f"  ✅ TTL operation successful (TTL: {ttl}s)")

        # Cleanup
        await redis_client.delete(test_key)

    except Exception as e:
        print(f"  ❌ Redis operations failed: {e}")


@beartype
async def check_redis_patterns() -> None:
    """Check for application-specific Redis patterns."""
    try:
        # Check for rate limiting keys
        rate_limit_keys = await redis_client.keys("rate_limit:*")
        print(f"\n📊 Rate limiting keys: {len(rate_limit_keys)}")

        # Check for session keys
        session_keys = await redis_client.keys("session:*")
        print(f"🔐 Session keys: {len(session_keys)}")

        # Check for cache keys
        cache_keys = await redis_client.keys("cache:*")
        print(f"💾 Cache keys: {len(cache_keys)}")

        # Sample key patterns
        all_keys = await redis_client.keys("*")
        if all_keys and len(all_keys) > 0:
            print("\n🔑 Sample keys (first 5):")
            for key in all_keys[:5]:
                key_type = await redis_client.type(key)
                ttl = await redis_client.ttl(key)
                ttl_str = f"{ttl}s" if ttl > 0 else "no expiry"
                print(f"  - {key} (type: {key_type}, ttl: {ttl_str})")

    except Exception as e:
        print(f"\n❌ Failed to check Redis patterns: {e}")


@beartype
async def main() -> None:
    """Run Redis connectivity checks."""
    print("🔴 Redis Connectivity Check")
    print("=" * 50)

    # Check basic connectivity
    result = await check_redis_connection()

    if result.connected:
        print("\n✅ Successfully connected to Redis!")
        print(f"  📍 Version: {result.redis_version}")
        print(f"  💾 Memory used: {result.memory_used_mb} MB")
        print(f"  🔑 Total keys: {result.total_keys}")
        print(f"  ⚡ Latency: {result.latency_ms}ms")

        # Test basic operations
        print("\n🧪 Testing Redis operations...")
        await test_redis_operations()

        # Check patterns
        await check_redis_patterns()

        # Performance test
        print("\n⚡ Running performance test...")
        operations = 100
        start = time.perf_counter()

        for i in range(operations):
            await redis_client.ping()

        elapsed = time.perf_counter() - start
        ops_per_sec = operations / elapsed

        print(f"  ✅ Completed {operations} pings in {elapsed:.2f}s")
        print(f"  📈 Performance: {ops_per_sec:.0f} ops/sec")

    else:
        print("\n❌ Failed to connect to Redis!")
        print(f"  Error: {result.error}")
        print("\n💡 Troubleshooting tips:")
        print("  1. Check REDIS_URL in .env file")
        print("  2. Ensure Redis server is running")
        print("  3. Verify Redis port (default: 6379)")
        print("  4. Check network connectivity")
        sys.exit(1)

    # Close connection
    await redis_client.close()


if __name__ == "__main__":
    asyncio.run(main())
