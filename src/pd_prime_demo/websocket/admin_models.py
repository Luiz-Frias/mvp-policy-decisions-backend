# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Admin dashboard specific models for WebSocket handlers."""

from datetime import datetime
from typing import Any
from uuid import UUID

from beartype import beartype
from pydantic import Field

from pd_prime_demo.models.base import BaseModelConfig


@beartype
class SystemHealthStatus(BaseModelConfig):
    """System health status model."""

    status: str = Field(..., pattern="^(healthy|degraded|critical)$")
    timestamp: datetime
    database: "DatabaseStats"
    websockets: "WebSocketStats"
    cache: "CacheStats"
    errors: "ErrorStats"


@beartype
class DatabasePoolStats(BaseModelConfig):
    """Database connection pool statistics."""

    active_connections: int = Field(default=0, ge=0)
    idle_connections: int = Field(default=0, ge=0)
    total_connections: int = Field(default=0, ge=0)
    longest_connection_seconds: float | None = Field(default=None, ge=0)


@beartype
class DatabasePerformanceStats(BaseModelConfig):
    """Database query performance statistics."""

    avg_query_time_ms: float | None = Field(default=None, ge=0)
    max_query_time_ms: float | None = Field(default=None, ge=0)
    total_queries: int | None = Field(default=None, ge=0)


@beartype
class DatabaseStats(BaseModelConfig):
    """Complete database statistics."""

    pool: DatabasePoolStats
    performance: DatabasePerformanceStats
    status: str = Field(..., pattern="^(healthy|warning|critical)$")


@beartype
class WebSocketStats(BaseModelConfig):
    """WebSocket connection statistics."""

    active_connections: int = Field(default=0, ge=0)
    total_connections: int = Field(default=0, ge=0)
    utilization: float = Field(default=0.0, ge=0.0, le=1.0)
    rooms_count: int = Field(default=0, ge=0)
    messages_per_second: float = Field(default=0.0, ge=0)


@beartype
class CacheStats(BaseModelConfig):
    """Redis cache statistics."""

    connected_clients: int = Field(default=0, ge=0)
    used_memory_mb: float = Field(default=0.0, ge=0)
    hit_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    total_keys: int = Field(default=0, ge=0)
    status: str = Field(..., pattern="^(healthy|warning|critical)$")


@beartype
class ErrorCount(BaseModelConfig):
    """Error count by type."""

    error_type: str
    count: int = Field(..., ge=0)
    last_occurrence: datetime


@beartype
class ErrorTrend(BaseModelConfig):
    """Error trend statistics."""

    last_5min: int = Field(default=0, ge=0)
    last_hour: int = Field(default=0, ge=0)
    last_24h: int = Field(default=0, ge=0)


@beartype
class ErrorStats(BaseModelConfig):
    """Complete error statistics."""

    by_type: list[ErrorCount]
    trend: ErrorTrend
    circuit_breakers: dict[str, str]  # service_name -> status


@beartype
class UserActivity(BaseModelConfig):
    """User activity log entry."""

    id: UUID
    admin_user_id: UUID
    email: str
    action: str
    resource_type: str
    resource_id: str | None = None
    status: str
    created_at: datetime
    ip_address: str | None = None


@beartype
class ApiResponseTimes(BaseModelConfig):
    """API response time statistics."""

    avg: float | None = Field(default=None, ge=0)
    p50: float | None = Field(default=None, ge=0)
    p95: float | None = Field(default=None, ge=0)
    p99: float | None = Field(default=None, ge=0)


@beartype
class QuoteCalculationTimes(BaseModelConfig):
    """Quote calculation time statistics."""

    avg: float | None = Field(default=None, ge=0)
    min: float | None = Field(default=None, ge=0)
    max: float | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)


@beartype
class ErrorRates(BaseModelConfig):
    """API error rate statistics."""

    errors: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)
    error_rate: float = Field(default=0.0, ge=0.0, le=1.0)


@beartype
class PerformanceMetrics(BaseModelConfig):
    """Complete performance metrics."""

    api_response_times: ApiResponseTimes | None = None
    quote_calculation_times: QuoteCalculationTimes | None = None
    active_sessions: int | None = None
    error_rates: ErrorRates | None = None
    timestamp: datetime


@beartype
class AdminAlertData(BaseModelConfig):
    """Admin alert data payload."""

    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    requires_action: bool = Field(default=False)


@beartype
class FiltersData(BaseModelConfig):
    """Filter data for admin queries."""

    action: str | None = None
    resource_type: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    user_id: UUID | None = None
    severity: str | None = None


# Type aliases for clarity
DbStatsData = DatabaseStats
WsStatsData = WebSocketStats
CacheStatsData = CacheStats
ErrorStatsData = ErrorStats
