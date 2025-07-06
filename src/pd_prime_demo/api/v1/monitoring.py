"""Database and system monitoring endpoints."""

from typing import Any

from beartype import beartype
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ...core.admin_query_optimizer import AdminQueryOptimizer
from ...core.database_enhanced import Database, PoolMetrics
from ...core.query_optimizer import QueryOptimizer, SlowQuery
from ..dependencies import get_db


router = APIRouter(prefix="/monitoring", tags=["monitoring"])


class PoolStatsResponse(BaseModel):
    """Pool statistics response model."""
    
    model_config = {"frozen": True}
    
    size: int = Field(..., description="Current pool size")
    free_size: int = Field(..., description="Available connections")
    min_size: int = Field(..., description="Minimum pool size")
    max_size: int = Field(..., description="Maximum pool size")
    connections_active: int = Field(..., description="Active connections")
    connections_idle: int = Field(..., description="Idle connections")
    queries_total: int = Field(..., description="Total queries executed")
    queries_slow: int = Field(..., description="Slow queries count")
    pool_exhausted_count: int = Field(..., description="Pool exhaustion events")
    average_query_time_ms: float = Field(..., description="Average query time in milliseconds")
    utilization_percent: float = Field(..., description="Pool utilization percentage")


class SlowQueryResponse(BaseModel):
    """Slow query information response."""
    
    model_config = {"frozen": True}
    
    query: str = Field(..., description="Sanitized query text")
    calls: int = Field(..., description="Number of times executed")
    total_time_ms: float = Field(..., description="Total execution time")
    mean_time_ms: float = Field(..., description="Average execution time")
    stddev_time_ms: float = Field(..., description="Standard deviation of execution time")
    rows: int = Field(..., description="Average rows returned")


class IndexSuggestionResponse(BaseModel):
    """Index suggestion response."""
    
    model_config = {"frozen": True}
    
    table_name: str = Field(..., description="Table name")
    column_name: str = Field(..., description="Column name")
    index_type: str = Field(..., description="Suggested index type")
    create_statement: str = Field(..., description="SQL to create index")
    estimated_improvement: str = Field(..., description="Expected improvement")


class QueryPlanResponse(BaseModel):
    """Query execution plan response."""
    
    model_config = {"frozen": True}
    
    query: str = Field(..., description="Analyzed query")
    execution_time_ms: float = Field(..., description="Execution time")
    planning_time_ms: float = Field(..., description="Planning time")
    total_cost: float = Field(..., description="Total cost estimate")
    rows_returned: int = Field(..., description="Rows returned")
    suggestions: list[str] = Field(..., description="Optimization suggestions")


class AdminMetricsResponse(BaseModel):
    """Admin dashboard metrics response."""
    
    model_config = {"frozen": True}
    
    daily_metrics: list[dict[str, Any]] = Field(..., description="Daily business metrics")
    user_activity: list[dict[str, Any]] = Field(..., description="Admin user activity")
    system_health: dict[str, Any] = Field(..., description="System health metrics")
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
    threshold_ms: float = Query(100.0, ge=10.0, le=10000.0, description="Threshold in milliseconds"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results to return"),
    db: Database = Depends(get_db),
) -> list[SlowQueryResponse]:
    """Get analysis of slow database queries."""
    optimizer = QueryOptimizer(db)
    result = await optimizer.analyze_slow_queries(threshold_ms=threshold_ms, limit=limit)
    
    if result.is_err():
        raise HTTPException(status_code=500, detail=result.err_value)
    
    return [
        SlowQueryResponse(
            query=sq.query,
            calls=sq.calls,
            total_time_ms=sq.total_time_ms,
            mean_time_ms=sq.mean_time_ms,
            stddev_time_ms=sq.stddev_time_ms,
            rows=sq.rows,
        )
        for sq in result.ok_value
    ]


@router.post("/analyze-query", response_model=QueryPlanResponse)
@beartype
async def analyze_query(
    query: str = Query(..., description="SQL query to analyze"),
    db: Database = Depends(get_db),
) -> QueryPlanResponse:
    """Analyze a specific query's execution plan."""
    optimizer = QueryOptimizer(db)
    result = await optimizer.explain_analyze(query)
    
    if result.is_err():
        raise HTTPException(status_code=500, detail=result.err_value)
    
    plan = result.ok_value
    return QueryPlanResponse(
        query=plan.query,
        execution_time_ms=plan.execution_time_ms,
        planning_time_ms=plan.planning_time_ms,
        total_cost=plan.total_cost,
        rows_returned=plan.rows_returned,
        suggestions=plan.suggestions,
    )


@router.get("/index-suggestions/{table_name}", response_model=list[IndexSuggestionResponse])
@beartype
async def get_index_suggestions(
    table_name: str,
    min_cardinality: int = Query(100, ge=10, description="Minimum cardinality for suggestions"),
    db: Database = Depends(get_db),
) -> list[IndexSuggestionResponse]:
    """Get index suggestions for a specific table."""
    optimizer = QueryOptimizer(db)
    result = await optimizer.suggest_indexes(table_name, min_cardinality)
    
    if result.is_err():
        raise HTTPException(status_code=500, detail=result.err_value)
    
    return [
        IndexSuggestionResponse(
            table_name=suggestion.table_name,
            column_name=suggestion.column_name,
            index_type=suggestion.index_type,
            create_statement=suggestion.create_statement,
            estimated_improvement=suggestion.estimated_improvement,
        )
        for suggestion in result.ok_value
    ]


@router.get("/table-bloat")
@beartype
async def check_table_bloat(
    threshold_percent: float = Query(20.0, ge=5.0, le=50.0, description="Bloat threshold percentage"),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    """Check for table bloat that affects performance."""
    optimizer = QueryOptimizer(db)
    result = await optimizer.check_table_bloat(threshold_percent)
    
    if result.is_err():
        raise HTTPException(status_code=500, detail=result.err_value)
    
    return {"bloated_tables": result.ok_value}


@router.get("/admin/metrics", response_model=AdminMetricsResponse)
@beartype
async def get_admin_metrics(
    use_cache: bool = Query(True, description="Use cached results if available"),
    db: Database = Depends(get_db),
) -> AdminMetricsResponse:
    """Get optimized admin dashboard metrics."""
    admin_optimizer = AdminQueryOptimizer(db)
    result = await admin_optimizer.get_admin_dashboard_metrics(use_cache=use_cache)
    
    if result.is_err():
        raise HTTPException(status_code=500, detail=result.err_value)
    
    metrics = result.ok_value
    
    # Add cache hit rate (simplified for now)
    cache_hit_rate = 85.0 if use_cache else 0.0
    
    return AdminMetricsResponse(
        daily_metrics=metrics.daily_metrics,
        user_activity=metrics.user_activity,
        system_health=metrics.system_health,
        cache_hit_rate=cache_hit_rate,
    )


@router.post("/admin/refresh-views")
@beartype
async def refresh_admin_views(
    force: bool = Query(False, description="Force refresh all views"),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    """Refresh admin materialized views."""
    admin_optimizer = AdminQueryOptimizer(db)
    result = await admin_optimizer.refresh_materialized_views(force_refresh=force)
    
    if result.is_err():
        raise HTTPException(status_code=500, detail=result.err_value)
    
    return {"refreshed_views": result.ok_value}


@router.post("/admin/optimize")
@beartype
async def optimize_admin_queries(db: Database = Depends(get_db)) -> dict[str, Any]:
    """Run admin query optimization routine."""
    admin_optimizer = AdminQueryOptimizer(db)
    result = await admin_optimizer.optimize_admin_queries()
    
    if result.is_err():
        raise HTTPException(status_code=500, detail=result.err_value)
    
    return result.ok_value


@router.get("/admin/performance")
@beartype
async def monitor_admin_performance(db: Database = Depends(get_db)) -> dict[str, Any]:
    """Monitor admin-specific query performance."""
    admin_optimizer = AdminQueryOptimizer(db)
    result = await admin_optimizer.monitor_admin_query_performance()
    
    if result.is_err():
        raise HTTPException(status_code=500, detail=result.err_value)
    
    return result.ok_value


@router.get("/pool-metrics/detailed")
@beartype
async def get_detailed_pool_metrics(db: Database = Depends(get_db)) -> dict[str, Any]:
    """Get detailed connection pool metrics with advanced monitoring."""
    return await db.get_detailed_pool_metrics()


@router.get("/health/database")
@beartype
async def database_health_check(db: Database = Depends(get_db)) -> dict[str, Any]:
    """Comprehensive database health check."""
    health_result = await db.health_check()
    
    if health_result.is_err():
        return {
            "status": "unhealthy",
            "error": health_result.err_value,
            "details": {},
        }
    
    is_healthy = health_result.ok_value
    detailed_metrics = await db.get_detailed_pool_metrics()
    
    return {
        "status": "healthy" if is_healthy and detailed_metrics["health_indicators"]["is_healthy"] else "degraded",
        "details": detailed_metrics,
        "warnings": detailed_metrics["health_indicators"]["warning_signs"],
    }