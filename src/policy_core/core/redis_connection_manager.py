"""Redis-based connection pool manager following SAGE principles.

This module implements a sophisticated connection pooling strategy using Redis
data structures to manage database connections efficiently, preventing the
"too many connections" issue through intelligent rate limiting and queueing.

Architecture:
1. Sorted Sets for sliding window rate limiting
2. Lists for connection request queuing  
3. Hashes for connection state tracking
4. Pub/Sub for real-time coordination
"""

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import AsyncIterator, Optional

import redis.asyncio as redis
from attrs import define, field
from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

from .cache import get_cache
from .config import get_settings
from .result_types import Err, Ok, Result


class ConnectionRequest(BaseModel):
    """Immutable connection request model."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
    )
    
    request_id: str = Field(..., min_length=1, max_length=100)
    client_id: str = Field(..., min_length=1, max_length=100)
    pool_type: str = Field(default="main", pattern="^(main|read|admin)$")
    priority: int = Field(default=5, ge=1, le=10)
    timestamp: float = Field(default_factory=time.time)
    timeout: float = Field(default=5.0, gt=0, le=30.0)


class ConnectionMetrics(BaseModel):
    """Connection pool metrics."""
    
    model_config = ConfigDict(frozen=True)
    
    active_connections: int = Field(ge=0)
    queued_requests: int = Field(ge=0)
    rate_limit_hits: int = Field(ge=0)
    avg_wait_time_ms: float = Field(ge=0)
    connection_errors: int = Field(ge=0)


@define(frozen=True, slots=True)
class RateLimitConfig:
    """Rate limiting configuration."""
    
    window_seconds: int = field(default=60)
    max_requests: int = field(default=100)
    burst_size: int = field(default=20)
    

class RedisConnectionManager:
    """Manages database connections using Redis for coordination.
    
    Uses Redis data structures to implement:
    1. Sliding window rate limiting (sorted sets)
    2. Connection request queueing (lists)
    3. Connection state tracking (hashes)
    4. Real-time coordination (pub/sub)
    
    This prevents connection exhaustion by:
    - Rate limiting connection requests per client
    - Queueing requests when pools are busy
    - Distributing connections fairly
    - Providing backpressure to clients
    """
    
    def __init__(self) -> None:
        """Initialize the connection manager."""
        self._redis = get_cache()._redis  # Reuse existing Redis connection
        self._settings = get_settings()
        self._rate_limit_config = RateLimitConfig()
        
        # Redis key prefixes
        self._rate_limit_prefix = "conn_mgr:rate_limit:"
        self._queue_prefix = "conn_mgr:queue:"
        self._state_prefix = "conn_mgr:state:"
        self._metrics_prefix = "conn_mgr:metrics:"
        
        # Lua scripts for atomic operations
        self._rate_limit_script: Optional[redis.Script] = None
        self._acquire_script: Optional[redis.Script] = None
        
    @beartype
    async def initialize(self) -> Result[None, str]:
        """Initialize Redis scripts and data structures."""
        try:
            # Register Lua script for atomic rate limiting
            self._rate_limit_script = self._redis.register_script("""
                local key = KEYS[1]
                local now = tonumber(ARGV[1])
                local window = tonumber(ARGV[2])
                local max_requests = tonumber(ARGV[3])
                local request_id = ARGV[4]
                
                -- Remove old entries outside window
                local min_score = now - window
                redis.call('ZREMRANGEBYSCORE', key, '-inf', min_score)
                
                -- Count requests in current window
                local current_count = redis.call('ZCARD', key)
                
                -- Check if limit exceeded
                if current_count >= max_requests then
                    return 0  -- Rate limited
                end
                
                -- Add new request
                redis.call('ZADD', key, now, request_id)
                redis.call('EXPIRE', key, window + 60)
                
                return 1  -- Allowed
            """)
            
            # Register Lua script for atomic connection acquisition
            self._acquire_script = self._redis.register_script("""
                local state_key = KEYS[1]
                local max_connections = tonumber(ARGV[1])
                
                -- Get current active connections
                local active = tonumber(redis.call('HGET', state_key, 'active') or 0)
                
                -- Check if connections available
                if active >= max_connections then
                    return 0  -- No connections available
                end
                
                -- Increment active connections
                redis.call('HINCRBY', state_key, 'active', 1)
                redis.call('HINCRBY', state_key, 'total_acquired', 1)
                
                return 1  -- Connection acquired
            """)
            
            return Ok(None)
            
        except Exception as e:
            return Err(f"Failed to initialize Redis connection manager: {str(e)}")
    
    @beartype
    async def check_rate_limit(
        self, 
        client_id: str,
        request_id: str
    ) -> Result[bool, str]:
        """Check if client is within rate limit using sliding window."""
        try:
            key = f"{self._rate_limit_prefix}{client_id}"
            now = time.time()
            
            # Execute atomic rate limit check
            allowed = await self._rate_limit_script(
                keys=[key],
                args=[
                    now,
                    self._rate_limit_config.window_seconds,
                    self._rate_limit_config.max_requests,
                    request_id
                ]
            )
            
            if not allowed:
                # Track rate limit hit
                await self._redis.hincrby(
                    f"{self._metrics_prefix}global",
                    "rate_limit_hits",
                    1
                )
            
            return Ok(bool(allowed))
            
        except Exception as e:
            return Err(f"Rate limit check failed: {str(e)}")
    
    @beartype
    async def queue_connection_request(
        self,
        request: ConnectionRequest
    ) -> Result[int, str]:
        """Queue a connection request with priority."""
        try:
            # Check rate limit first
            rate_limit_result = await self.check_rate_limit(
                request.client_id,
                request.request_id
            )
            
            if rate_limit_result.is_err():
                return Err(rate_limit_result.unwrap_err())
                
            if not rate_limit_result.unwrap():
                return Err("Rate limit exceeded")
            
            # Add to priority queue (higher priority = lower score)
            queue_key = f"{self._queue_prefix}{request.pool_type}"
            score = time.time() - (request.priority * 10)  # Priority boost
            
            await self._redis.zadd(
                queue_key,
                {request.model_dump_json(): score}
            )
            
            # Get queue position
            position = await self._redis.zrank(
                queue_key,
                request.model_dump_json()
            )
            
            return Ok(position + 1 if position is not None else 1)
            
        except Exception as e:
            return Err(f"Failed to queue request: {str(e)}")
    
    @beartype
    async def acquire_connection_slot(
        self,
        pool_type: str,
        max_connections: int
    ) -> Result[bool, str]:
        """Atomically acquire a connection slot if available."""
        try:
            state_key = f"{self._state_prefix}{pool_type}"
            
            acquired = await self._acquire_script(
                keys=[state_key],
                args=[max_connections]
            )
            
            return Ok(bool(acquired))
            
        except Exception as e:
            return Err(f"Failed to acquire connection slot: {str(e)}")
    
    @beartype
    async def release_connection_slot(
        self,
        pool_type: str
    ) -> Result[None, str]:
        """Release a connection slot back to the pool."""
        try:
            state_key = f"{self._state_prefix}{pool_type}"
            
            # Decrement active connections
            await self._redis.hincrby(state_key, "active", -1)
            
            # Process next queued request
            await self._process_queue(pool_type)
            
            return Ok(None)
            
        except Exception as e:
            return Err(f"Failed to release connection: {str(e)}")
    
    @beartype
    async def _process_queue(self, pool_type: str) -> None:
        """Process the next request in the queue."""
        queue_key = f"{self._queue_prefix}{pool_type}"
        
        # Get highest priority request (lowest score)
        results = await self._redis.zrange(
            queue_key, 0, 0, withscores=True
        )
        
        if results:
            request_json, score = results[0]
            request = ConnectionRequest.model_validate_json(request_json)
            
            # Publish to waiting client
            await self._redis.publish(
                f"conn_mgr:notify:{request.request_id}",
                "connection_available"
            )
            
            # Remove from queue
            await self._redis.zrem(queue_key, request_json)
    
    @beartype
    async def get_metrics(self, pool_type: str = "main") -> Result[ConnectionMetrics, str]:
        """Get current connection pool metrics."""
        try:
            state_key = f"{self._state_prefix}{pool_type}"
            queue_key = f"{self._queue_prefix}{pool_type}"
            metrics_key = f"{self._metrics_prefix}global"
            
            # Get all metrics atomically
            pipe = self._redis.pipeline()
            pipe.hget(state_key, "active")
            pipe.zcard(queue_key)
            pipe.hget(metrics_key, "rate_limit_hits")
            pipe.hget(metrics_key, "avg_wait_time_ms")
            pipe.hget(metrics_key, "connection_errors")
            
            results = await pipe.execute()
            
            return Ok(ConnectionMetrics(
                active_connections=int(results[0] or 0),
                queued_requests=int(results[1] or 0),
                rate_limit_hits=int(results[2] or 0),
                avg_wait_time_ms=float(results[3] or 0),
                connection_errors=int(results[4] or 0)
            ))
            
        except Exception as e:
            return Err(f"Failed to get metrics: {str(e)}")
    
    @asynccontextmanager
    @beartype
    async def managed_connection(
        self,
        client_id: str,
        pool_type: str = "main",
        max_connections: int = 50,
        timeout: float = 5.0
    ) -> AsyncIterator[bool]:
        """Context manager for managed connection acquisition.
        
        This provides a clean interface for acquiring connections with:
        - Rate limiting
        - Queueing
        - Automatic release
        - Timeout handling
        """
        request = ConnectionRequest(
            request_id=f"{client_id}:{time.time_ns()}",
            client_id=client_id,
            pool_type=pool_type,
            timeout=timeout
        )
        
        acquired = False
        start_time = time.time()
        
        try:
            # Try direct acquisition first
            slot_result = await self.acquire_connection_slot(
                pool_type, max_connections
            )
            
            if slot_result.is_ok() and slot_result.unwrap():
                acquired = True
                yield True
            else:
                # Queue the request
                queue_result = await self.queue_connection_request(request)
                
                if queue_result.is_err():
                    yield False
                    return
                
                # Wait for notification with timeout
                pubsub = self._redis.pubsub()
                await pubsub.subscribe(f"conn_mgr:notify:{request.request_id}")
                
                try:
                    # Wait for connection availability
                    async with asyncio.timeout(timeout):
                        async for message in pubsub.listen():
                            if message["type"] == "message":
                                # Try to acquire again
                                slot_result = await self.acquire_connection_slot(
                                    pool_type, max_connections
                                )
                                if slot_result.is_ok() and slot_result.unwrap():
                                    acquired = True
                                    yield True
                                    return
                                    
                except asyncio.TimeoutError:
                    yield False
                    
                finally:
                    await pubsub.unsubscribe()
                    await pubsub.close()
                    
        finally:
            if acquired:
                # Update metrics
                wait_time_ms = (time.time() - start_time) * 1000
                await self._redis.hset(
                    f"{self._metrics_prefix}global",
                    "avg_wait_time_ms",
                    wait_time_ms
                )
                
                # Release the connection
                await self.release_connection_slot(pool_type)


# Example usage in database.py:
"""
async def connect(self) -> None:
    # Initialize Redis connection manager
    self._conn_manager = RedisConnectionManager()
    await self._conn_manager.initialize()
    
    # Use managed connections
    async with self._conn_manager.managed_connection(
        client_id="api_server_1",
        pool_type="main",
        max_connections=50
    ) as allowed:
        if allowed:
            # Proceed with actual database connection
            self._pool = await asyncpg.create_pool(...)
        else:
            raise RuntimeError("Connection limit exceeded - request queued or rate limited")
"""