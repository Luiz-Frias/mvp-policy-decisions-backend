# Database Optimization Guide

## Overview

This guide covers the database optimization strategies implemented for handling 10,000 concurrent users in the PD Prime Demo system.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Application   │     │   Application   │     │   Application   │
│   Instance 1    │     │   Instance 2    │     │   Instance N    │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┴───────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │      PgBouncer          │
                    │  (Connection Pooler)    │
                    └────────────┬────────────┘
                                 │
                ┌────────────────┴────────────────┐
                │                                 │
        ┌───────┴────────┐              ┌────────┴────────┐
        │  PostgreSQL    │              │  Read Replica   │
        │   Primary      │◄─────────────│  (Optional)     │
        └────────────────┘              └─────────────────┘
```

## Connection Pool Configuration

### Application-Level Pooling (asyncpg)

The enhanced database module (`database_enhanced.py`) implements intelligent connection pooling:

```python
# Capacity-based configuration
min_connections = calculate_min_connections(expected_rps=1000)  # ~20 connections
max_connections = calculate_max_connections(
    db_max_connections=100,
    app_instances=5,
    safety_margin=0.8
)  # ~16 connections per instance
```

Key features:
- **Dynamic pool sizing** based on expected load
- **Read replica support** for query distribution
- **Admin pool** for complex analytical queries
- **Connection health monitoring** with metrics
- **Automatic retry** with exponential backoff

### PgBouncer Configuration

PgBouncer acts as a connection multiplexer between applications and PostgreSQL:

```ini
# Transaction pooling for OLTP workload
pool_mode = transaction
max_client_conn = 10000
default_pool_size = 25

# Optimized for 10k users across 5 app instances
# Each instance: 2000 users / 25 pool size = 80 users per connection
```

## Query Optimization

### 1. Query Optimizer (`query_optimizer.py`)

Provides tools for identifying and fixing performance issues:

- **EXPLAIN ANALYZE** integration
- **Slow query detection** using pg_stat_statements
- **Index suggestions** based on table statistics
- **Table bloat detection**

### 2. Admin Query Optimizer (`admin_query_optimizer.py`)

Specialized optimization for admin dashboards:

- **Materialized views** for complex aggregations
- **Automatic refresh scheduling**
- **Dedicated connection pool** for admin queries
- **Result caching** with Redis

### 3. Prepared Statements

Common queries are prepared at connection initialization:

```python
# Prepared statements for performance
"get_quote_by_id": "SELECT * FROM quotes WHERE id = $1"
"get_customer_policies": "SELECT * FROM policies WHERE customer_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3"
```

## Monitoring

### Database Health Monitoring Script

Run periodic health checks:

```bash
python scripts/monitor_db_health.py
```

Monitors:
- Connection pool utilization
- Query performance metrics
- Cache hit rates
- Replication lag
- Index usage
- Table bloat

### API Monitoring Endpoints

Real-time monitoring via REST API:

- `GET /api/v1/monitoring/pool-stats` - Connection pool statistics
- `GET /api/v1/monitoring/slow-queries` - Slow query analysis
- `POST /api/v1/monitoring/analyze-query` - Analyze specific query
- `GET /api/v1/monitoring/admin/metrics` - Admin dashboard metrics

## Setup Instructions

### 1. Install PgBouncer

```bash
# Ubuntu/Debian
sudo apt-get install pgbouncer

# RHEL/CentOS
sudo yum install pgbouncer
```

### 2. Configure PgBouncer

```bash
# Copy configuration
sudo cp config/pgbouncer.ini /etc/pgbouncer/

# Create user list from example
sudo cp config/pgbouncer_userlist.txt.example /etc/pgbouncer/userlist.txt
# Edit userlist.txt with proper password hashes

# Set permissions
sudo chown pgbouncer:pgbouncer /etc/pgbouncer/*
sudo chmod 640 /etc/pgbouncer/userlist.txt
```

### 3. Configure PostgreSQL

Add to `postgresql.conf`:

```ini
# Connection settings
max_connections = 200
shared_buffers = 256MB

# Performance settings
effective_cache_size = 4GB
work_mem = 4MB
maintenance_work_mem = 64MB
random_page_cost = 1.1  # For SSD

# Enable pg_stat_statements
shared_preload_libraries = 'pg_stat_statements'
pg_stat_statements.track = all
```

### 4. Start Services

```bash
# Start PgBouncer
sudo systemctl enable pgbouncer
sudo systemctl start pgbouncer

# Verify
psql -h localhost -p 6432 -U pgbouncer_stats -d pgbouncer -c "SHOW STATS"
```

### 5. Configure Application

Update environment variables:

```bash
# Main database (through PgBouncer)
DATABASE_URL=postgresql://app_user:password@localhost:6432/pd_prime_demo

# Optional read replica
DATABASE_READ_URL=postgresql://app_readonly:password@read-replica:5432/pd_prime_demo

# Pool configuration
DATABASE_POOL_MIN=5
DATABASE_POOL_MAX=20
DATABASE_POOL_TIMEOUT=10.0
DATABASE_MAX_CONNECTIONS=100
```

## Performance Tuning Checklist

### Database Level

- [ ] Enable pg_stat_statements extension
- [ ] Configure shared_buffers (25% of RAM)
- [ ] Set effective_cache_size (75% of RAM)
- [ ] Adjust work_mem based on query complexity
- [ ] Enable parallel query execution
- [ ] Configure autovacuum aggressively

### Application Level

- [ ] Use connection pooling (asyncpg + PgBouncer)
- [ ] Implement query result caching
- [ ] Use prepared statements for common queries
- [ ] Batch similar operations
- [ ] Use read replicas for read-heavy operations

### Query Level

- [ ] Add appropriate indexes
- [ ] Use EXPLAIN ANALYZE for slow queries
- [ ] Avoid N+1 query patterns
- [ ] Use materialized views for complex aggregations
- [ ] Implement pagination for large result sets

### Monitoring

- [ ] Set up continuous health monitoring
- [ ] Configure alerts for pool exhaustion
- [ ] Track slow query trends
- [ ] Monitor replication lag
- [ ] Review index usage regularly

## Troubleshooting

### Connection Pool Exhaustion

```bash
# Check PgBouncer stats
psql -h localhost -p 6432 -U pgbouncer_stats -d pgbouncer -c "SHOW POOLS"

# Check application pool stats
curl http://localhost:8000/api/v1/monitoring/pool-stats
```

### Slow Queries

```bash
# Find slow queries
curl http://localhost:8000/api/v1/monitoring/slow-queries?threshold_ms=1000

# Analyze specific query
curl -X POST http://localhost:8000/api/v1/monitoring/analyze-query \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT * FROM quotes WHERE status = $1"}'
```

### High Replication Lag

```sql
-- Check replication status
SELECT client_addr, state, sync_state,
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS lag_bytes
FROM pg_stat_replication;
```

## Best Practices

1. **Never use default pool sizes** - Calculate based on expected load
2. **Monitor continuously** - Set up alerts before issues occur
3. **Test under load** - Verify configuration with realistic traffic
4. **Plan for peaks** - Size pools for peak traffic, not average
5. **Use read replicas** - Distribute read load across multiple databases
6. **Cache aggressively** - Reduce database load with intelligent caching
7. **Optimize queries** - Fix slow queries before adding resources

## References

- [PgBouncer Documentation](https://www.pgbouncer.org/)
- [PostgreSQL Connection Pooling](https://wiki.postgresql.org/wiki/Connection_Pooling)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
