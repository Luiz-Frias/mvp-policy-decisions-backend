# Performance Optimization Guide

## Overview

This guide provides comprehensive strategies for optimizing the performance of the MVP Policy Decision Backend, including profiling techniques, optimization patterns, and monitoring strategies.

## Performance Requirements

### Target Metrics

| Metric                   | Target     | Critical Threshold |
| ------------------------ | ---------- | ------------------ |
| API Response Time (p95)  | < 100ms    | < 200ms            |
| API Response Time (p99)  | < 200ms    | < 500ms            |
| Throughput               | 1000 req/s | 500 req/s          |
| Memory Usage per Request | < 1MB      | < 2MB              |
| Database Query Time      | < 50ms     | < 100ms            |
| Cache Hit Rate           | > 80%      | > 60%              |

## Profiling Tools

### CPU Profiling

#### Using py-spy

```bash
# Profile running application
py-spy record -o profile.svg --pid $(pgrep -f "uvicorn")

# Profile specific function
py-spy record -o profile.svg -- python -m pytest tests/benchmarks/test_performance.py

# Generate flame graph
py-spy record -o flame.svg --flame -- python src/pd_prime_demo/main.py
```

#### Using cProfile

```python
import cProfile
import pstats
from pstats import SortKey

def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()

    # Code to profile
    result = expensive_operation()

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats(SortKey.CUMULATIVE)
    stats.print_stats(10)  # Top 10 functions

    return result
```

### Memory Profiling

#### Using memray

```bash
# Profile memory usage
memray run --output memory.bin python src/pd_prime_demo/main.py

# Generate flame graph
memray flamegraph memory.bin

# Generate summary
memray summary memory.bin

# Track allocations
memray tree memory.bin
```

#### Using memory_profiler

```python
from memory_profiler import profile

@profile
def memory_intensive_function():
    # This will show line-by-line memory usage
    large_list = [i for i in range(1000000)]
    return sum(large_list)
```

### Async Profiling

```python
import asyncio
import time
from contextlib import asynccontextmanager

@asynccontextmanager
async def async_timer(name: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"{name} took {elapsed:.4f} seconds")

# Usage
async def main():
    async with async_timer("database_query"):
        result = await db.fetch_all(query)
```

## Database Optimization

### Query Optimization

#### 1. Use Indexes Effectively

```sql
-- Create indexes for frequently queried columns
CREATE INDEX idx_policies_policy_number ON policies(policy_number);
CREATE INDEX idx_policies_effective_date ON policies(effective_date);
CREATE INDEX idx_policies_status ON policies(status) WHERE status = 'active';

-- Composite indexes for complex queries
CREATE INDEX idx_policies_composite ON policies(state, policy_type, effective_date);

-- Partial indexes for specific conditions
CREATE INDEX idx_active_policies ON policies(policy_number) WHERE status = 'active';
```

#### 2. Optimize Queries

```python
# Bad: N+1 query problem
policies = await db.fetch_all("SELECT * FROM policies")
for policy in policies:
    claims = await db.fetch_all(f"SELECT * FROM claims WHERE policy_id = {policy.id}")

# Good: Use joins or batch loading
policies = await db.fetch_all("""
    SELECT p.*, c.*
    FROM policies p
    LEFT JOIN claims c ON p.id = c.policy_id
""")

# Or use SQLAlchemy eager loading
from sqlalchemy.orm import selectinload

stmt = select(Policy).options(selectinload(Policy.claims))
policies = await session.execute(stmt)
```

#### 3. Connection Pooling

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,              # Number of connections to maintain
    max_overflow=0,            # Maximum overflow connections
    pool_timeout=30,           # Timeout for getting connection
    pool_recycle=1800,         # Recycle connections after 30 minutes
    pool_pre_ping=True,        # Test connections before using
    echo_pool=True            # Log pool checkouts/checkins
)
```

### Query Analysis

```python
# Enable query logging for analysis
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Analyze slow queries
async def analyze_query_performance(query: str):
    start = time.perf_counter()

    # Explain query plan
    explain = await db.fetch_one(f"EXPLAIN ANALYZE {query}")

    result = await db.fetch_all(query)
    elapsed = time.perf_counter() - start

    if elapsed > 0.1:  # Log slow queries
        logger.warning(
            "Slow query detected",
            query=query,
            elapsed=elapsed,
            explain=explain
        )

    return result
```

## Caching Strategies

### Multi-Level Caching

```python
from functools import lru_cache
from typing import Optional
import redis.asyncio as redis

class CacheManager:
    def __init__(self):
        self.redis_client = redis.Redis()
        self.local_cache = {}

    async def get(self, key: str) -> Optional[Any]:
        # L1: Check local cache
        if key in self.local_cache:
            return self.local_cache[key]

        # L2: Check Redis
        value = await self.redis_client.get(key)
        if value:
            self.local_cache[key] = value
            return value

        return None

    async def set(self, key: str, value: Any, ttl: int = 300):
        # Set in both caches
        self.local_cache[key] = value
        await self.redis_client.setex(key, ttl, value)
```

### Cache Warming

```python
async def warm_cache():
    """Pre-populate cache with frequently accessed data"""
    # Load rate tables
    rates = await db.fetch_all("SELECT * FROM rates WHERE active = true")
    for rate in rates:
        key = f"rate:{rate.state}:{rate.policy_type}"
        await cache.set(key, rate, ttl=3600)

    # Load reference data
    states = await db.fetch_all("SELECT * FROM states")
    await cache.set("states:all", states, ttl=86400)
```

### Cache Invalidation

```python
from typing import List

class SmartCache:
    def __init__(self):
        self.cache = {}
        self.dependencies = {}  # Track cache dependencies

    async def invalidate_pattern(self, pattern: str):
        """Invalidate all keys matching pattern"""
        keys_to_delete = [
            key for key in self.cache.keys()
            if key.startswith(pattern)
        ]
        for key in keys_to_delete:
            del self.cache[key]

    async def tag_invalidation(self, tags: List[str]):
        """Invalidate all entries with specific tags"""
        for tag in tags:
            if tag in self.dependencies:
                for key in self.dependencies[tag]:
                    if key in self.cache:
                        del self.cache[key]
```

## API Optimization

### Request/Response Optimization

```python
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import ORJSONResponse
import orjson

app = FastAPI(default_response_class=ORJSONResponse)

class OptimizedResponse(ORJSONResponse):
    def render(self, content: Any) -> bytes:
        # Use orjson for faster JSON serialization
        return orjson.dumps(
            content,
            option=orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY
        )

@app.get("/policies", response_class=OptimizedResponse)
async def get_policies(limit: int = 100):
    # Use pagination to limit response size
    policies = await db.fetch_policies(limit=limit)

    # Only return necessary fields
    return [
        {
            "id": p.id,
            "policy_number": p.policy_number,
            "premium": p.premium,
            "status": p.status
        }
        for p in policies
    ]
```

### Async Best Practices

```python
import asyncio
from typing import List

async def process_policies_parallel(policy_ids: List[str]):
    """Process multiple policies in parallel"""
    tasks = [
        process_single_policy(policy_id)
        for policy_id in policy_ids
    ]

    # Process in batches to avoid overwhelming the system
    batch_size = 10
    results = []

    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i + batch_size]
        batch_results = await asyncio.gather(*batch)
        results.extend(batch_results)

    return results

async def optimized_bulk_operation():
    """Use bulk operations instead of individual queries"""
    # Bad: Individual inserts
    for policy in policies:
        await db.execute(
            "INSERT INTO policies VALUES (...)",
            policy.dict()
        )

    # Good: Bulk insert
    await db.execute_many(
        "INSERT INTO policies VALUES (...)",
        [policy.dict() for policy in policies]
    )
```

## Memory Optimization

### Pydantic Model Optimization

```python
from pydantic import BaseModel, ConfigDict
from typing import Optional

class OptimizedPolicy(BaseModel):
    model_config = ConfigDict(
        # Use slots for memory efficiency
        extra="forbid",
        arbitrary_types_allowed=False,
        # Validate on assignment for early error detection
        validate_assignment=True,
        # Use Rust-based validation
        str_strip_whitespace=True,
    )

    # Use __slots__ to reduce memory overhead
    __slots__ = ('id', 'policy_number', 'premium')

    id: str
    policy_number: str
    premium: Decimal

# Memory-efficient data structures
from array import array
from collections import deque

# Use array for homogeneous numeric data
premiums = array('f', [100.0, 200.0, 300.0])

# Use deque for efficient queue operations
task_queue = deque(maxlen=1000)
```

### Generator Patterns

```python
async def stream_large_dataset():
    """Stream data instead of loading all at once"""
    offset = 0
    batch_size = 1000

    while True:
        batch = await db.fetch_all(
            f"SELECT * FROM policies LIMIT {batch_size} OFFSET {offset}"
        )

        if not batch:
            break

        for record in batch:
            yield record

        offset += batch_size

# Usage
async for policy in stream_large_dataset():
    await process_policy(policy)
```

## Algorithmic Optimization

### Rate Calculation Optimization

```python
from functools import lru_cache
import numpy as np

class RateCalculator:
    def __init__(self):
        self.rate_matrix = self._load_rate_matrix()

    @lru_cache(maxsize=1000)
    def calculate_base_rate(self, state: str, coverage: int) -> Decimal:
        """Cache frequently calculated rates"""
        return self.rate_matrix[state][coverage]

    def batch_calculate_premiums(self, policies: List[Policy]) -> np.ndarray:
        """Vectorized calculation for multiple policies"""
        # Extract features into numpy arrays
        ages = np.array([p.driver_age for p in policies])
        coverages = np.array([p.coverage_amount for p in policies])

        # Vectorized operations
        age_factors = np.where(ages < 25, 1.5, 1.0)
        base_rates = coverages * 0.001  # Simplified calculation

        return base_rates * age_factors
```

### Business Logic Optimization

```python
# Use lookup tables instead of complex conditionals
DISCOUNT_MATRIX = {
    ('safe_driver', 0): 0.0,
    ('safe_driver', 1): 0.05,
    ('safe_driver', 2): 0.10,
    ('safe_driver', 3): 0.15,
}

def calculate_discount_optimized(driver_type: str, years: int) -> float:
    return DISCOUNT_MATRIX.get((driver_type, min(years, 3)), 0.0)

# Pre-compute complex calculations
from datetime import datetime, timedelta

# Cache date calculations
POLICY_PERIODS = {
    'annual': timedelta(days=365),
    'semi_annual': timedelta(days=182),
    'quarterly': timedelta(days=91),
    'monthly': timedelta(days=30),
}

def calculate_expiration_optimized(
    effective_date: datetime,
    period: str
) -> datetime:
    return effective_date + POLICY_PERIODS[period]
```

## Monitoring and Alerting

### Performance Metrics Collection

```python
from prometheus_client import Counter, Histogram, Gauge
import time

# Define metrics
request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint', 'status']
)

active_connections = Gauge(
    'active_connections',
    'Number of active connections'
)

cache_hits = Counter(
    'cache_hits_total',
    'Total number of cache hits',
    ['cache_type']
)

@app.middleware("http")
async def track_metrics(request, call_next):
    start_time = time.time()

    # Track active connections
    active_connections.inc()

    try:
        response = await call_next(request)

        # Record request duration
        duration = time.time() - start_time
        request_duration.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).observe(duration)

        return response
    finally:
        active_connections.dec()
```

### Custom Performance Decorator

```python
from functools import wraps
import tracemalloc
import time

def performance_monitor(
    track_memory: bool = True,
    log_slow_queries: bool = True,
    threshold_ms: float = 100
):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Start monitoring
            start_time = time.perf_counter()
            if track_memory:
                tracemalloc.start()

            try:
                result = await func(*args, **kwargs)

                # Calculate metrics
                elapsed_ms = (time.perf_counter() - start_time) * 1000

                if track_memory:
                    current, peak = tracemalloc.get_traced_memory()
                    tracemalloc.stop()
                    memory_mb = peak / 1024 / 1024
                else:
                    memory_mb = 0

                # Log if slow
                if elapsed_ms > threshold_ms:
                    logger.warning(
                        f"Slow function: {func.__name__}",
                        elapsed_ms=elapsed_ms,
                        memory_mb=memory_mb,
                        args=args[:2]  # Log first 2 args only
                    )

                return result

            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                raise

        return wrapper
    return decorator

# Usage
@performance_monitor(threshold_ms=50)
async def calculate_complex_premium(policy_data: PolicyData) -> Decimal:
    # Function implementation
    pass
```

## Load Testing

### Using Locust

```python
# locustfile.py
from locust import HttpUser, task, between
import random

class PolicyAPIUser(HttpUser):
    wait_time = between(1, 3)

    @task(3)
    def get_policies(self):
        self.client.get("/api/v1/policies?limit=10")

    @task(2)
    def create_quote(self):
        self.client.post("/api/v1/quotes", json={
            "policy_type": "auto",
            "state": random.choice(["CA", "NY", "TX"]),
            "coverage_requested": {
                "liability": 500000,
                "collision": 50000
            }
        })

    @task(1)
    def calculate_rate(self):
        self.client.post("/api/v1/rates/calculate", json={
            "state": "CA",
            "policy_type": "auto",
            "coverage": {
                "liability": 500000
            }
        })

# Run with: locust -H http://localhost:8000 -u 100 -r 10
```

### Using Apache Bench

```bash
# Simple load test
ab -n 1000 -c 10 http://localhost:8000/api/v1/health

# POST request with JSON
ab -n 1000 -c 10 -p quote.json -T application/json \
   -H "Authorization: Bearer $TOKEN" \
   http://localhost:8000/api/v1/quotes
```

## Performance Checklist

### Before Deployment

- [ ] Run profiling on critical paths
- [ ] Verify database indexes are optimized
- [ ] Check query execution plans
- [ ] Validate caching strategy
- [ ] Run load tests
- [ ] Monitor memory usage patterns
- [ ] Review async operation efficiency
- [ ] Optimize JSON serialization

### Production Monitoring

- [ ] Set up APM (Application Performance Monitoring)
- [ ] Configure alerts for slow queries
- [ ] Monitor cache hit rates
- [ ] Track memory usage trends
- [ ] Watch for connection pool exhaustion
- [ ] Monitor API response times
- [ ] Track error rates
- [ ] Review performance metrics daily

## Performance Anti-Patterns to Avoid

1. **Synchronous Operations in Async Code**

   ```python
   # Bad
   async def bad_example():
       time.sleep(1)  # Blocks event loop

   # Good
   async def good_example():
       await asyncio.sleep(1)  # Non-blocking
   ```

2. **Unbounded Queries**

   ```python
   # Bad
   all_policies = await db.fetch_all("SELECT * FROM policies")

   # Good
   policies = await db.fetch_all("SELECT * FROM policies LIMIT 100")
   ```

3. **Memory Leaks**

   ```python
   # Bad: Unbounded cache
   cache = {}

   # Good: Bounded cache with TTL
   from cachetools import TTLCache
   cache = TTLCache(maxsize=1000, ttl=300)
   ```

4. **Inefficient Serialization**

   ```python
   # Bad: Standard json
   import json
   data = json.dumps(large_object)

   # Good: Optimized orjson
   import orjson
   data = orjson.dumps(large_object)
   ```
