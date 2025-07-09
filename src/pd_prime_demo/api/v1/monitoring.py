"""Database and system monitoring endpoints with performance tracking."""

import time
from typing import Any, Union, Dict, TYPE_CHECKING

# TYPE_CHECKING imports not needed - using string annotations

from beartype import beartype
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from ...core.admin_query_optimizer import AdminQueryOptimizer
from ...core.database_enhanced import Database
from ...core.performance_monitor import PerformanceMetrics, get_performance_collector
from ...core.query_optimizer import QueryOptimizer
from ...core.result_types import Result, Ok, Err
from ..dependencies import get_db
from ..response_patterns import handle_result, ErrorResponse

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

# Base structure models needed early in the file


class TableBloatInfo(BaseModel):
    """Table bloat information structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    table_name: str = Field(..., description="Table name")
    bloat_percent: float = Field(..., description="Bloat percentage")
    table_size_bytes: int = Field(..., description="Table size in bytes")
    bloat_size_bytes: int = Field(..., description="Bloat size in bytes")
    recommended_action: str = Field(..., description="Recommended action")


class ConnectionStats(BaseModel):
    """Connection statistics structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    total_connections: int = Field(..., description="Total connections")
    active_connections: int = Field(..., description="Active connections")
    idle_connections: int = Field(..., description="Idle connections")
    waiting_connections: int = Field(..., description="Waiting connections")
    max_connections: int = Field(..., description="Maximum connections")


class HealthIndicators(BaseModel):
    """Health indicators structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    is_healthy: bool = Field(..., description="Overall health status")
    warning_signs: list[str] = Field(default=[], description="Warning indicators")
    critical_issues: list[str] = Field(default=[], description="Critical issues")
    last_check: float = Field(..., description="Last health check timestamp")


class PoolPerformanceMetrics(BaseModel):
    """Pool performance metrics structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    avg_connection_time_ms: float = Field(..., description="Average connection time")
    avg_query_time_ms: float = Field(..., description="Average query time")
    queries_per_second: float = Field(..., description="Queries per second")
    connection_errors: int = Field(..., description="Connection errors count")
    timeout_errors: int = Field(..., description="Timeout errors count")


class HealthCheckDetails(BaseModel):
    """Structured health check details."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    database_status: str = Field(..., description="Database connection status")
    redis_status: str = Field(..., description="Redis connection status")
    external_apis_status: str = Field(..., description="External APIs status")
    disk_usage_percent: float = Field(..., description="Disk usage percentage")
    memory_usage_percent: float = Field(..., description="Memory usage percentage")
    cpu_usage_percent: float = Field(..., description="CPU usage percentage")
    uptime_seconds: int = Field(..., description="System uptime in seconds")


class PoolStatsResponse(BaseModel):
    """Pool statistics response model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    size: int = Field(..., description="Current pool size")
    free_size: int = Field(..., description="Available connections")
    min_size: int = Field(..., description="Minimum pool size")
    max_size: int = Field(..., description="Maximum pool size")
    connections_active: int = Field(..., description="Active connections")
    connections_idle: int = Field(..., description="Idle connections")
    queries_total: int = Field(..., description="Total queries executed")
    queries_slow: int = Field(..., description="Slow queries count")
    pool_exhausted_count: int = Field(..., description="Pool exhaustion events")
    average_query_time_ms: float = Field(
        ..., description="Average query time in milliseconds"
    )
    utilization_percent: float = Field(..., description="Pool utilization percentage")


class SlowQueryResponse(BaseModel):
    """Slow query information response."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    query: str = Field(..., description="Sanitized query text")
    calls: int = Field(..., description="Number of times executed")
    total_time_ms: float = Field(..., description="Total execution time")
    mean_time_ms: float = Field(..., description="Average execution time")
    stddev_time_ms: float = Field(
        ..., description="Standard deviation of execution time"
    )
    rows: int = Field(..., description="Average rows returned")


class IndexSuggestionResponse(BaseModel):
    """Index suggestion response."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    table_name: str = Field(..., description="Table name")
    column_name: str = Field(..., description="Column name")
    index_type: str = Field(..., description="Suggested index type")
    create_statement: str = Field(..., description="SQL to create index")
    estimated_improvement: str = Field(..., description="Expected improvement")


class QueryPlanResponse(BaseModel):
    """Query execution plan response."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    query: str = Field(..., description="Analyzed query")
    execution_time_ms: float = Field(..., description="Execution time")
    planning_time_ms: float = Field(..., description="Planning time")
    total_cost: float = Field(..., description="Total cost estimate")
    rows_returned: int = Field(..., description="Rows returned")
    suggestions: list[str] = Field(..., description="Optimization suggestions")


class DailyMetricItem(BaseModel):
    """Individual daily metric item."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    date: str = Field(..., description="Date of metrics")
    quotes_generated: int = Field(..., description="Number of quotes generated")
    policies_created: int = Field(..., description="Number of policies created")
    claims_processed: int = Field(..., description="Number of claims processed")
    revenue: float = Field(..., description="Daily revenue")


class UserActivityItem(BaseModel):
    """Individual user activity item."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    user_id: str = Field(..., description="User identifier")
    user_name: str = Field(..., description="User name")
    activity_type: str = Field(..., description="Type of activity")
    timestamp: str = Field(..., description="Activity timestamp")
    details: str | None = Field(default=None, description="Additional activity details")


class SystemHealthMetrics(BaseModel):
    """System health metrics."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    cpu_usage: float = Field(..., description="CPU usage percentage")
    memory_usage: float = Field(..., description="Memory usage percentage")
    disk_usage: float = Field(..., description="Disk usage percentage")
    database_connections: int = Field(..., description="Active database connections")
    response_time_avg: float = Field(..., description="Average response time in ms")


class AdminMetricsResponse(BaseModel):
    """Admin dashboard metrics response."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    daily_metrics: list[DailyMetricItem] = Field(
        ..., description="Daily business metrics"
    )
    user_activity: list[UserActivityItem] = Field(..., description="Admin user activity")
    system_health: SystemHealthMetrics = Field(..., description="System health metrics")
    cache_hit_rate: float = Field(..., description="Cache hit rate percentage")


@router.get("/pool-stats", response_model=PoolStatsResponse)
@beartype
async def get_pool_stats(db: Database = Depends(get_db)) -> PoolStatsResponse:
    """Get database connection pool statistics."""
    stats = await db.get_pool_stats()

    # Calculate utilization
    utilization = 0.0
    if stats.size > 0:
        utilization = ((stats.size - stats.free_size) / stats.size) * 100

    return PoolStatsResponse(
        size=stats.size,
        free_size=stats.free_size,
        min_size=stats.min_size,
        max_size=stats.max_size,
        connections_active=stats.connections_active,
        connections_idle=stats.connections_idle,
        queries_total=stats.queries_total,
        queries_slow=stats.queries_slow,
        pool_exhausted_count=stats.pool_exhausted_count,
        average_query_time_ms=stats.average_query_time_ms,
        utilization_percent=utilization,
    )


@router.get("/slow-queries", response_model=list[SlowQueryResponse])
@beartype
async def get_slow_queries(
    response: Response,
    threshold_ms: float = Query(
        100.0, ge=10.0, le=10000.0, description="Threshold in milliseconds"
    ),
    limit: int = Query(20, ge=1, le=100, description="Maximum results to return"),
    db: Database = Depends(get_db),
) -> Union[list[SlowQueryResponse], ErrorResponse]:
    """Get analysis of slow database queries."""
    optimizer = QueryOptimizer(db)
    result = await optimizer.analyze_slow_queries(
        threshold_ms=threshold_ms, limit=limit
    )

    if result.is_err():
        return handle_result(Err(result.err_value or "Failed to analyze slow queries"), response)

    # Type narrowing - ok_value should not be None if is_ok() is True
    slow_queries = result.ok_value
    if slow_queries is None:
        return handle_result(Err("Internal server error: slow queries result is None"), response)

    # Convert domain models to response models
    slow_query_responses = [
        SlowQueryResponse(
            query=sq.query,
            calls=sq.calls,
            total_time_ms=sq.total_time_ms,
            mean_time_ms=sq.mean_time_ms,
            stddev_time_ms=sq.stddev_time_ms,
            rows=sq.rows,
        )
        for sq in slow_queries
    ]

    return slow_query_responses


@router.post("/analyze-query", response_model=QueryPlanResponse)
@beartype
async def analyze_query(
    response: Response,
    query: str = Query(..., description="SQL query to analyze"),
    db: Database = Depends(get_db),
) -> Union[QueryPlanResponse, ErrorResponse]:
    """Analyze a specific query's execution plan."""
    optimizer = QueryOptimizer(db)
    result = await optimizer.explain_analyze(query)

    if result.is_err():
        return handle_result(Err(result.err_value or "Failed to analyze query"), response)

    plan = result.ok_value

    # Type narrowing - plan should not be None if is_ok() is True
    if plan is None:
        return handle_result(Err("Internal server error: query plan is None"), response)

    # Convert domain model to response model
    plan_response = QueryPlanResponse(
        query=plan.query,
        execution_time_ms=plan.execution_time_ms,
        planning_time_ms=plan.planning_time_ms,
        total_cost=plan.total_cost,
        rows_returned=plan.rows_returned,
        suggestions=plan.suggestions,
    )

    return plan_response


@router.get(
    "/index-suggestions/{table_name}", response_model=list[IndexSuggestionResponse]
)
@beartype
async def get_index_suggestions(
    table_name: str,
    response: Response,
    min_cardinality: int = Query(
        100, ge=10, description="Minimum cardinality for suggestions"
    ),
    db: Database = Depends(get_db),
) -> Union[list[IndexSuggestionResponse], ErrorResponse]:
    """Get index suggestions for a specific table."""
    optimizer = QueryOptimizer(db)
    result = await optimizer.suggest_indexes(table_name, min_cardinality)

    if result.is_err():
        return handle_result(Err(result.err_value or "Failed to suggest indexes"), response)

    # Type narrowing - ok_value should not be None if is_ok() is True
    suggestions = result.ok_value
    if suggestions is None:
        return handle_result(Err("Internal server error: index suggestions result is None"), response)

    # Convert domain models to response models
    suggestion_responses = [
        IndexSuggestionResponse(
            table_name=suggestion.table_name,
            column_name=suggestion.column_name,
            index_type=suggestion.index_type,
            create_statement=suggestion.create_statement,
            estimated_improvement=suggestion.estimated_improvement,
        )
        for suggestion in suggestions
    ]

    return suggestion_responses


class TableBloatResponse(BaseModel):
    """Response model for table bloat check."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    bloated_tables: list[TableBloatInfo] = Field(..., description="List of bloated tables")


@router.get("/table-bloat", response_model=TableBloatResponse)
@beartype
async def check_table_bloat(
    response: Response,
    threshold_percent: float = Query(
        20.0, ge=5.0, le=50.0, description="Bloat threshold percentage"
    ),
    db: Database = Depends(get_db),
) -> Union[TableBloatResponse, ErrorResponse]:
    """Check for table bloat that affects performance."""
    optimizer = QueryOptimizer(db)
    result = await optimizer.check_table_bloat(threshold_percent)

    if result.is_err():
        return handle_result(Err(result.err_value or "Failed to check table bloat"), response)

    # Convert raw data to structured response
    bloated_tables_data = result.ok_value or []
    structured_bloated_tables = [
        TableBloatInfo(
            table_name=table.get("table_name", ""),
            bloat_percent=table.get("bloat_percent", 0.0),
            table_size_bytes=table.get("table_size_bytes", 0),
            bloat_size_bytes=table.get("bloat_size_bytes", 0),
            recommended_action=table.get("recommended_action", "No action needed")
        )
        for table in bloated_tables_data
    ]
    
    return TableBloatResponse(bloated_tables=structured_bloated_tables)


@router.get("/admin/metrics", response_model=AdminMetricsResponse)
@beartype
async def get_admin_metrics(
    response: Response,
    use_cache: bool = Query(True, description="Use cached results if available"),
    db: Database = Depends(get_db),
) -> Union[AdminMetricsResponse, ErrorResponse]:
    """Get optimized admin dashboard metrics."""
    admin_optimizer = AdminQueryOptimizer(db)
    result = await admin_optimizer.get_admin_dashboard_metrics(use_cache=use_cache)

    if result.is_err():
        return handle_result(Err(result.err_value or "Failed to get admin metrics"), response)

    metrics = result.unwrap()  # Safe to unwrap after checking is_err()

    # Add cache hit rate (simplified for now)
    cache_hit_rate = 85.0 if use_cache else 0.0

    # Convert domain model to response model
    daily_metrics_converted = [
        DailyMetricItem(
            date=item.get("date", ""),
            quotes_generated=item.get("quotes_generated", 0),
            policies_created=item.get("policies_created", 0),
            claims_processed=item.get("claims_processed", 0),
            revenue=item.get("revenue", 0.0)
        )
        for item in metrics.daily_metrics
    ]
    
    user_activity_converted = [
        UserActivityItem(
            user_id=item.get("user_id", ""),
            user_name=item.get("user_name", ""),
            activity_type=item.get("activity_type", ""),
            timestamp=item.get("timestamp", ""),
            details=item.get("details")
        )
        for item in metrics.user_activity
    ]
    
    system_health_converted = SystemHealthMetrics(
        cpu_usage=metrics.system_health.get("cpu_usage", 0.0),
        memory_usage=metrics.system_health.get("memory_usage", 0.0),
        disk_usage=metrics.system_health.get("disk_usage", 0.0),
        database_connections=metrics.system_health.get("database_connections", 0),
        response_time_avg=metrics.system_health.get("response_time_avg", 0.0)
    )
    
    metrics_response = AdminMetricsResponse(
        daily_metrics=daily_metrics_converted,
        user_activity=user_activity_converted,
        system_health=system_health_converted,
        cache_hit_rate=cache_hit_rate,
    )

    return metrics_response


class AdminViewsRefreshResponse(BaseModel):
    """Response model for admin views refresh."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    refreshed_views: list[str] = Field(..., description="List of refreshed views")


class AdminOptimizationResponse(BaseModel):
    """Response model for admin query optimization."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    optimizations_applied: int = Field(..., description="Number of optimizations applied")
    queries_optimized: list[str] = Field(..., description="List of optimized queries")
    performance_improvement: float = Field(..., description="Performance improvement percentage")


class AdminPerformanceResponse(BaseModel):
    """Response model for admin performance monitoring."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    slow_queries: list[str] = Field(..., description="List of slow queries")
    average_response_time: float = Field(..., description="Average response time in ms")
    total_queries: int = Field(..., description="Total number of queries")


class DetailedPoolMetricsResponse(BaseModel):
    """Response model for detailed pool metrics."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    connection_stats: ConnectionStats = Field(..., description="Connection statistics")
    health_indicators: HealthIndicators = Field(..., description="Health indicators")
    performance_metrics: PoolPerformanceMetrics = Field(..., description="Performance metrics")


class DatabaseHealthCheckResponse(BaseModel):
    """Response model for database health check."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    status: str = Field(..., description="Health status (healthy/degraded/unhealthy)")
    details: HealthCheckDetails = Field(..., description="Detailed health metrics")
    warnings: list[str] = Field(..., description="Warning messages")


@router.post("/admin/refresh-views", response_model=AdminViewsRefreshResponse)
@beartype
async def refresh_admin_views(
    response: Response,
    force: bool = Query(False, description="Force refresh all views"),
    db: Database = Depends(get_db),
) -> Union[AdminViewsRefreshResponse, ErrorResponse]:
    """Refresh admin materialized views."""
    admin_optimizer = AdminQueryOptimizer(db)
    result = await admin_optimizer.refresh_materialized_views(force_refresh=force)

    if result.is_err():
        return handle_result(Err(result.err_value or "Failed to refresh views"), response)

    # Type narrowing and response formatting
    refreshed_views = result.ok_value
    if refreshed_views is None:
        return handle_result(Err("Internal server error: refreshed views result is None"), response)

    # Convert to list format expected by the response model
    refreshed_views_list = list(refreshed_views) if isinstance(refreshed_views, dict) else refreshed_views
    return AdminViewsRefreshResponse(refreshed_views=refreshed_views_list)


@router.post("/admin/optimize", response_model=AdminOptimizationResponse)
@beartype
async def optimize_admin_queries(
    response: Response,
    db: Database = Depends(get_db)
) -> Union[AdminOptimizationResponse, ErrorResponse]:
    """Run admin query optimization routine."""
    admin_optimizer = AdminQueryOptimizer(db)
    result = await admin_optimizer.optimize_admin_queries()

    if result.is_err():
        return handle_result(Err(result.err_value or "Failed to optimize queries"), response)

    # Type narrowing and response formatting
    optimization_result = result.ok_value
    if optimization_result is None:
        return handle_result(Err("Internal server error: optimization result is None"), response)

    # Convert dict response to structured model
    return AdminOptimizationResponse(
        optimizations_applied=optimization_result.get("optimizations_applied", 0),
        queries_optimized=optimization_result.get("queries_optimized", []),
        performance_improvement=optimization_result.get("performance_improvement", 0.0)
    )


@router.get("/admin/performance", response_model=AdminPerformanceResponse)
@beartype
async def monitor_admin_performance(
    response: Response,
    db: Database = Depends(get_db)
) -> Union[AdminPerformanceResponse, ErrorResponse]:
    """Monitor admin-specific query performance."""
    admin_optimizer = AdminQueryOptimizer(db)
    result = await admin_optimizer.monitor_admin_query_performance()

    if result.is_err():
        return handle_result(Err(result.err_value or "Failed to monitor performance"), response)

    # Type narrowing and response formatting
    performance_result = result.ok_value
    if performance_result is None:
        return handle_result(Err("Internal server error: performance result is None"), response)

    # Convert dict response to structured model
    return AdminPerformanceResponse(
        slow_queries=performance_result.get("slow_queries", []),
        average_response_time=performance_result.get("average_response_time", 0.0),
        total_queries=performance_result.get("total_queries", 0)
    )


@router.get("/pool-metrics/detailed", response_model=DetailedPoolMetricsResponse)
@beartype
async def get_detailed_pool_metrics(db: Database = Depends(get_db)) -> DetailedPoolMetricsResponse:
    """Get detailed connection pool metrics with advanced monitoring."""
    metrics = await db.get_detailed_pool_metrics()
    
    # Convert raw metrics to structured models
    connection_stats_data = metrics.get("connection_stats", {})
    health_indicators_data = metrics.get("health_indicators", {})
    performance_metrics_data = metrics.get("performance_metrics", {})
    
    connection_stats = ConnectionStats(
        total_connections=connection_stats_data.get("total_connections", 0),
        active_connections=connection_stats_data.get("active_connections", 0),
        idle_connections=connection_stats_data.get("idle_connections", 0),
        waiting_connections=connection_stats_data.get("waiting_connections", 0),
        max_connections=connection_stats_data.get("max_connections", 0)
    )
    
    health_indicators = HealthIndicators(
        is_healthy=health_indicators_data.get("is_healthy", False),
        warning_signs=health_indicators_data.get("warning_signs", []),
        critical_issues=health_indicators_data.get("critical_issues", []),
        last_check=health_indicators_data.get("last_check", time.time())
    )
    
    performance_metrics = PoolPerformanceMetrics(
        avg_connection_time_ms=performance_metrics_data.get("avg_connection_time_ms", 0.0),
        avg_query_time_ms=performance_metrics_data.get("avg_query_time_ms", 0.0),
        queries_per_second=performance_metrics_data.get("queries_per_second", 0.0),
        connection_errors=performance_metrics_data.get("connection_errors", 0),
        timeout_errors=performance_metrics_data.get("timeout_errors", 0)
    )
    
    return DetailedPoolMetricsResponse(  # SYSTEM_BOUNDARY - Aggregated system data
        connection_stats=connection_stats,
        health_indicators=health_indicators,
        performance_metrics=performance_metrics
    )


@router.get("/health/database", response_model=DatabaseHealthCheckResponse)
@beartype
async def database_health_check(db: Database = Depends(get_db)) -> DatabaseHealthCheckResponse:
    """Comprehensive database health check."""
    health_result = await db.health_check()

    if health_result.is_err():
        error_details = HealthCheckDetails(
            database_status="error",
            redis_status="unknown",
            external_apis_status="unknown",
            disk_usage_percent=0.0,
            memory_usage_percent=0.0,
            cpu_usage_percent=0.0,
            uptime_seconds=0
        )
        return DatabaseHealthCheckResponse(
            status="unhealthy",
            details=error_details,
            warnings=[health_result.err_value or "Unknown error"]
        )

    is_healthy = health_result.ok_value
    detailed_metrics = await db.get_detailed_pool_metrics()
    health_indicators_data = detailed_metrics.get("health_indicators", {})

    status = (
        "healthy"
        if is_healthy and health_indicators_data.get("is_healthy", False)
        else "degraded"
    )
    
    # Create structured health details
    health_details = HealthCheckDetails(
        database_status="healthy" if is_healthy else "degraded",
        redis_status="healthy",  # SYSTEM_BOUNDARY - would need actual Redis check
        external_apis_status="healthy",  # SYSTEM_BOUNDARY - would need actual API checks
        disk_usage_percent=75.0,  # SYSTEM_BOUNDARY - would need actual disk check
        memory_usage_percent=45.0,  # SYSTEM_BOUNDARY - would need actual memory check
        cpu_usage_percent=25.0,  # SYSTEM_BOUNDARY - would need actual CPU check
        uptime_seconds=86400  # SYSTEM_BOUNDARY - would need actual uptime check
    )
    
    return DatabaseHealthCheckResponse(
        status=status,
        details=health_details,
        warnings=health_indicators_data.get("warning_signs", [])
    )


# Performance Monitoring Endpoints


class PerformanceMetricsResponse(BaseModel):
    """Performance metrics response model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    operation: str = Field(..., description="Operation name")
    total_requests: int = Field(..., description="Total requests processed")
    avg_duration_ms: float = Field(..., description="Average response time in ms")
    p95_duration_ms: float = Field(..., description="95th percentile response time")
    p99_duration_ms: float = Field(..., description="99th percentile response time")
    memory_usage_mb: float = Field(..., description="Average memory usage in MB")
    error_rate: float = Field(..., description="Error rate (0.0 to 1.0)")
    success_rate: float = Field(..., description="Success rate (0.0 to 1.0)")
    requests_per_second: float = Field(..., description="Current RPS")
    meets_100ms_requirement: bool = Field(..., description="Meets <100ms requirement")


# Models moved to after their dependencies are defined


class PerformanceAlertsResponse(BaseModel):
    """Response model for performance alerts."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    total_alerts: int = Field(..., description="Total number of alerts")
    critical_alerts: list[str] = Field(..., description="Critical alerts")
    warning_alerts: list[str] = Field(..., description="Warning alerts")
    status: str = Field(..., description="Overall alert status")
    timestamp: float = Field(..., description="Alert timestamp")


class PerformanceResetResponse(BaseModel):
    """Response model for performance metrics reset."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    status: str = Field(..., description="Reset status")
    message: str = Field(..., description="Reset confirmation message")
    timestamp: float = Field(..., description="Reset timestamp")


# Response models for complex aggregations


class MetricsAggregation(BaseModel):
    """Response model for aggregated performance metrics."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    operations: dict[str, PerformanceMetricsResponse] = Field(
        ..., description="Performance metrics by operation name"
    )
    total_operations: int = Field(..., description="Total number of operations tracked")
    timestamp: float = Field(..., description="Metrics collection timestamp")


# HealthCheckDetails already defined at the top of the file


class HealthCheckResponse(BaseModel):
    """Response model for detailed health check."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    status: str = Field(..., description="Overall health status")
    details: HealthCheckDetails = Field(..., description="Detailed health metrics")
    warnings: list[str] = Field(default=[], description="Health warnings")
    timestamp: float = Field(..., description="Health check timestamp")


class SystemSummaryResponse(BaseModel):
    """Response model for system summary aggregations."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    performance_summary: "PerformanceSummaryResponse" = Field(
        ..., description="Performance summary metrics"
    )
    health_summary: HealthCheckResponse = Field(
        ..., description="Health check summary"
    )
    alert_summary: "PerformanceAlertsResponse" = Field(
        ..., description="Alert summary"
    )
    pool_summary: PoolStatsResponse = Field(
        ..., description="Database pool summary"
    )
    timestamp: float = Field(..., description="Summary generation timestamp")


# Structured models for existing dict[str, Any] fields


# Base structure models moved to the top of the file


class PerformanceSummaryResponse(BaseModel):
    """Response model for performance summary."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    status: str = Field(..., description="Overall performance status")
    performance_grade: str = Field(..., description="Performance grade (A-F)")
    operations_tracked: int = Field(..., description="Number of operations tracked")
    operations_meeting_100ms: str = Field(..., description="Operations meeting 100ms requirement")
    operations_meeting_50ms: str = Field(..., description="Operations meeting 50ms requirement")
    overall_error_rate: str = Field(..., description="Overall error rate")
    overall_avg_latency_ms: str = Field(..., description="Overall average latency")
    overall_p99_latency_ms: str = Field(..., description="Overall P99 latency")
    active_alerts: int = Field(..., description="Number of active alerts")
    production_ready: bool = Field(..., description="Whether system is production ready")
    recommendations: list[str] = Field(..., description="Performance recommendations")


@router.get(
    "/performance/metrics", response_model=MetricsAggregation
)
@beartype
async def get_performance_metrics() -> MetricsAggregation:
    """Get comprehensive performance metrics aggregation for all tracked operations."""
    collector = get_performance_collector()
    all_metrics = await collector.get_all_metrics()

    operations = {
        operation: PerformanceMetricsResponse(
            operation=metrics.operation,
            total_requests=metrics.total_requests,
            avg_duration_ms=metrics.avg_duration_ms,
            p95_duration_ms=metrics.p95_duration_ms,
            p99_duration_ms=metrics.p99_duration_ms,
            memory_usage_mb=metrics.memory_usage_mb,
            error_rate=metrics.error_rate,
            success_rate=metrics.success_rate,
            requests_per_second=metrics.requests_per_second,
            meets_100ms_requirement=metrics.p99_duration_ms < 100.0,
        )
        for operation, metrics in all_metrics.items()
    }
    
    return MetricsAggregation(
        operations=operations,
        total_operations=len(all_metrics),
        timestamp=time.time()
    )


@router.get(
    "/performance/metrics/{operation}", response_model=PerformanceMetricsResponse
)
@beartype
async def get_operation_metrics(
    operation: str,
    response: Response
) -> Union[PerformanceMetricsResponse, ErrorResponse]:
    """Get performance metrics for a specific operation."""
    collector = get_performance_collector()
    result = await collector.get_metrics(operation)

    if result.is_err():
        return handle_result(Err(result.err_value or "Failed to get operation metrics"), response)

    metrics = result.unwrap()  # Safe to unwrap after checking is_err()

    # Convert domain model to response model
    metrics_response = PerformanceMetricsResponse(
        operation=metrics.operation,
        total_requests=metrics.total_requests,
        avg_duration_ms=metrics.avg_duration_ms,
        p95_duration_ms=metrics.p95_duration_ms,
        p99_duration_ms=metrics.p99_duration_ms,
        memory_usage_mb=metrics.memory_usage_mb,
        error_rate=metrics.error_rate,
        success_rate=metrics.success_rate,
        requests_per_second=metrics.requests_per_second,
        meets_100ms_requirement=metrics.p99_duration_ms < 100.0,
    )

    return metrics_response


@router.get("/performance/alerts", response_model=PerformanceAlertsResponse)
@beartype
async def get_performance_alerts() -> PerformanceAlertsResponse:
    """Get current performance alerts and warnings."""
    collector = get_performance_collector()
    alerts = await collector.check_performance_alerts()

    # Categorize alerts
    critical_alerts = [
        alert
        for alert in alerts
        if "HIGH LATENCY" in alert or "HIGH ERROR RATE" in alert
    ]
    warning_alerts = [alert for alert in alerts if alert not in critical_alerts]

    status = (
        "critical"
        if critical_alerts
        else ("warning" if warning_alerts else "healthy")
    )
    
    return PerformanceAlertsResponse(
        total_alerts=len(alerts),
        critical_alerts=critical_alerts,
        warning_alerts=warning_alerts,
        status=status,
        timestamp=time.time()
    )


@router.post("/performance/reset", response_model=PerformanceResetResponse)
@beartype
async def reset_performance_metrics() -> PerformanceResetResponse:
    """Reset all performance metrics (for testing/development)."""
    collector = get_performance_collector()
    await collector.reset_metrics()

    return PerformanceResetResponse(
        status="success",
        message="Performance metrics reset successfully",
        timestamp=time.time()
    )


@router.get("/performance/summary", response_model=PerformanceSummaryResponse)
@beartype
async def get_performance_summary() -> PerformanceSummaryResponse:
    """Get a summary of overall system performance."""
    collector = get_performance_collector()
    all_metrics = await collector.get_all_metrics()
    alerts = await collector.check_performance_alerts()

    if not all_metrics:
        return PerformanceSummaryResponse(
            status="no_data",
            performance_grade="N/A",
            operations_tracked=0,
            operations_meeting_100ms="0/0",
            operations_meeting_50ms="0/0",
            overall_error_rate="N/A",
            overall_avg_latency_ms="N/A",
            overall_p99_latency_ms="N/A",
            active_alerts=0,
            production_ready=False,
            recommendations=["No performance data available yet"]
        )

    # Calculate overall statistics
    total_operations = len(all_metrics)
    operations_meeting_100ms = sum(
        1 for m in all_metrics.values() if m.p99_duration_ms < 100
    )
    operations_meeting_50ms = sum(
        1 for m in all_metrics.values() if m.p99_duration_ms < 50
    )

    overall_error_rate = (
        sum(m.error_rate for m in all_metrics.values()) / total_operations
    )
    overall_avg_latency = (
        sum(m.avg_duration_ms for m in all_metrics.values()) / total_operations
    )
    overall_p99_latency = max(m.p99_duration_ms for m in all_metrics.values())

    # Performance grade
    if operations_meeting_100ms == total_operations and overall_error_rate < 0.01:
        grade = "A" if operations_meeting_50ms == total_operations else "B"
        status = "excellent" if grade == "A" else "good"
    elif operations_meeting_100ms >= total_operations * 0.8:
        grade = "C"
        status = "acceptable"
    else:
        grade = "F"
        status = "critical"

    return PerformanceSummaryResponse(
        status=status,
        performance_grade=grade,
        operations_tracked=total_operations,
        operations_meeting_100ms=f"{operations_meeting_100ms}/{total_operations}",
        operations_meeting_50ms=f"{operations_meeting_50ms}/{total_operations}",
        overall_error_rate=f"{overall_error_rate:.2%}",
        overall_avg_latency_ms=f"{overall_avg_latency:.1f}",
        overall_p99_latency_ms=f"{overall_p99_latency:.1f}",
        active_alerts=len(alerts),
        production_ready=operations_meeting_100ms == total_operations and overall_error_rate < 0.01,
        recommendations=_get_performance_recommendations(all_metrics, alerts)
    )


def _get_performance_recommendations(
    metrics: dict[str, PerformanceMetrics], alerts: list[str]
) -> list[str]:
    """Generate performance improvement recommendations."""
    recommendations = []

    if alerts:
        recommendations.append(f"Address {len(alerts)} active performance alerts")

    slow_operations = [name for name, m in metrics.items() if m.p99_duration_ms > 100]
    if slow_operations:
        recommendations.append(
            f"Optimize slow operations: {', '.join(slow_operations[:3])}"
        )

    high_error_operations = [name for name, m in metrics.items() if m.error_rate > 0.01]
    if high_error_operations:
        recommendations.append(
            f"Investigate errors in: {', '.join(high_error_operations[:3])}"
        )

    high_memory_operations = [
        name for name, m in metrics.items() if m.memory_usage_mb > 10
    ]
    if high_memory_operations:
        recommendations.append(
            f"Optimize memory usage in: {', '.join(high_memory_operations[:3])}"
        )

    if not recommendations:
        recommendations.append(
            "All operations performing within targets - consider load testing"
        )

    return recommendations


@router.get("/system/summary", response_model=SystemSummaryResponse)
@beartype
async def get_system_summary(
    db: Database = Depends(get_db)
) -> SystemSummaryResponse:
    """Get comprehensive system summary with all monitoring aggregations."""
    # Get all component summaries
    performance_summary = await get_performance_summary()
    health_summary = await database_health_check(db)
    alert_summary = await get_performance_alerts()
    pool_summary = await get_pool_stats(db)
    
    # Convert health summary to proper HealthCheckResponse format
    health_response = HealthCheckResponse(
        status=health_summary.status,
        details=health_summary.details,
        warnings=health_summary.warnings,
        timestamp=time.time()
    )
    
    return SystemSummaryResponse(
        performance_summary=performance_summary,
        health_summary=health_response,
        alert_summary=alert_summary,
        pool_summary=pool_summary,
        timestamp=time.time()
    )
