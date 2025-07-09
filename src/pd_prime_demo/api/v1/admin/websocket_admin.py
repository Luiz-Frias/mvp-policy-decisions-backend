"""Admin WebSocket API endpoints for real-time monitoring and control."""

from datetime import datetime
from typing import Any
from uuid import UUID

from beartype import beartype
from fastapi import (
    APIRouter,
    Depends,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, ConfigDict, Field

from ....models.admin import AdminUser
from ....websocket.handlers.admin_dashboard import AdminDashboardHandler
from ....websocket.manager import ConnectionManager, MessageType, WebSocketMessage
from ...response_patterns import ErrorResponse


class AdminWebSocketConfig(BaseModel):
    """Configuration for admin WebSocket sessions."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    dashboard_type: str = Field(..., pattern="^(system|activity|performance|alerts)$")
    update_interval: int = Field(default=5, ge=1, le=60)
    filters: dict[str, Any] = Field(default_factory=dict)
    metrics: list[str] = Field(default_factory=list)
    alert_levels: list[str] = Field(
        default_factory=lambda: ["medium", "high", "critical"]
    )


class AdminDashboardStats(BaseModel):
    """Admin dashboard statistics response."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    active_admin_connections: int = Field(ge=0)
    total_websocket_connections: int = Field(ge=0)
    system_health_status: str = Field(...)
    active_alerts: int = Field(ge=0)
    pending_notifications: int = Field(ge=0)


router = APIRouter(prefix="/websocket", tags=["Admin WebSocket"])


def get_admin_dashboard_handler() -> AdminDashboardHandler:
    """Get admin dashboard handler dependency."""
    # This would be injected in production
    # For now, using a placeholder
    from ....core.cache import get_cache
    from ....core.database_enhanced import get_database

    cache = get_cache()
    database = get_database()
    manager = ConnectionManager(cache, database)
    return AdminDashboardHandler(manager, database, cache)


def get_current_admin_user() -> AdminUser:
    """Get current admin user dependency."""
    # This would check JWT tokens in production
    # For now, return a demo admin user
    return AdminUser(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        email="admin@demo.com",
        role_id=UUID("00000000-0000-0000-0000-000000000002"),  # Required field
        is_super_admin=True,  # Grant super admin for demo user
        full_name="Demo Admin",  # Required field
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@router.websocket("/admin-dashboard")
async def admin_dashboard_websocket(
    websocket: WebSocket,
    dashboard_handler: AdminDashboardHandler = Depends(get_admin_dashboard_handler),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> None:
    """WebSocket endpoint for admin real-time dashboards."""
    await websocket.accept()

    connection_id = f"admin_{admin_user.id}_{id(websocket)}"

    try:
        # Send welcome message
        welcome_msg = WebSocketMessage(
            type=MessageType.CONNECTION,
            data={
                "connection_id": connection_id,
                "admin_user": {
                    "id": str(admin_user.id),
                    "email": admin_user.email,
                    "role": "super_admin" if admin_user.is_super_admin else "admin",
                    "permissions": admin_user.effective_permissions,
                },
                "capabilities": [
                    "system_monitoring",
                    "user_activity_tracking",
                    "performance_monitoring",
                    "alert_management",
                ],
            },
        )
        await websocket.send_json(welcome_msg.model_dump())

        while True:
            try:
                data = await websocket.receive_json()
                message_type = data.get("type")

                if message_type == "start_system_monitoring":
                    config = data.get("config", {})
                    await dashboard_handler.start_system_monitoring(
                        connection_id, admin_user.id, config
                    )
                    # System monitoring started successfully

                elif message_type == "start_user_activity":
                    filters = data.get("filters", {})
                    await dashboard_handler.start_user_activity_monitoring(
                        connection_id, admin_user.id, filters
                    )
                    # User activity monitoring started successfully

                elif message_type == "start_performance_monitoring":
                    metrics = data.get("metrics", [])
                    await dashboard_handler.start_performance_monitoring(
                        connection_id, admin_user.id, metrics
                    )
                    # Performance monitoring started successfully

                elif message_type == "ping":
                    pong_msg = WebSocketMessage(
                        type=MessageType.PONG, data={"timestamp": data.get("timestamp")}
                    )
                    await websocket.send_json(pong_msg.model_dump())

                else:
                    error_msg = WebSocketMessage(
                        type=MessageType.ERROR,
                        data={
                            "error": f"Unknown message type: {message_type}",
                            "supported_types": [
                                "start_system_monitoring",
                                "start_user_activity",
                                "start_performance_monitoring",
                                "ping",
                            ],
                        },
                    )
                    await websocket.send_json(error_msg.model_dump())

            except WebSocketDisconnect:
                break
            except Exception as e:
                error_msg = WebSocketMessage(
                    type=MessageType.ERROR,
                    data={
                        "error": f"Processing error: {str(e)}",
                        "fatal": True,
                    },
                )
                await websocket.send_json(error_msg.model_dump())
                break

    except WebSocketDisconnect:
        pass
    finally:
        await dashboard_handler.handle_admin_disconnect(connection_id)


@router.get("/stats", response_model=AdminDashboardStats)
@beartype
async def get_admin_dashboard_stats(
    response: Response,
    admin_user: AdminUser = Depends(get_current_admin_user),
    dashboard_handler: AdminDashboardHandler = Depends(get_admin_dashboard_handler),
) -> AdminDashboardStats | ErrorResponse:
    """Get current admin dashboard statistics."""
    if "analytics:read" not in admin_user.effective_permissions:
        response.status_code = status.HTTP_403_FORBIDDEN
        return ErrorResponse(error="Insufficient permissions for dashboard statistics")

    # Get statistics from handler
    stats = await dashboard_handler._collect_system_metrics()

    if stats.is_err():
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ErrorResponse(error=stats.unwrap_err())

    metrics = stats.unwrap()

    websocket_metrics = metrics.get("websockets", {})
    if websocket_metrics is None:
        websocket_metrics = {}

    return AdminDashboardStats(
        active_admin_connections=len(dashboard_handler._active_streams),
        total_websocket_connections=websocket_metrics.get("total_connections", 0),
        system_health_status=metrics.get("health_status", "unknown"),
        active_alerts=len(dashboard_handler._active_streams),  # Simplified
        pending_notifications=0,  # Would come from notification handler
    )


@router.post("/broadcast-alert")
@beartype
async def broadcast_admin_alert(
    alert_type: str,
    message: str,
    response: Response,
    severity: str = "medium",
    data: dict[str, Any] | None = None,
    admin_user: AdminUser = Depends(get_current_admin_user),
    dashboard_handler: AdminDashboardHandler = Depends(get_admin_dashboard_handler),
) -> dict[str, str] | ErrorResponse:
    """Broadcast alert to all admin dashboard users."""
    if "system:manage" not in admin_user.effective_permissions:
        response.status_code = status.HTTP_403_FORBIDDEN
        return ErrorResponse(error="Insufficient permissions to broadcast alerts")

    result = await dashboard_handler.broadcast_admin_alert(
        alert_type, message, severity, data
    )

    if result.is_err():
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ErrorResponse(error=result.unwrap_err())

    return {
        "status": "success",
        "message": f"Alert '{alert_type}' broadcast successfully",
    }


@router.get("/connection-health")
@beartype
async def get_websocket_connection_health(
    response: Response,
    admin_user: AdminUser = Depends(get_current_admin_user),
    dashboard_handler: AdminDashboardHandler = Depends(get_admin_dashboard_handler),
) -> dict[str, Any] | ErrorResponse:
    """Get WebSocket connection health metrics."""
    if "performance:read" not in admin_user.effective_permissions:
        response.status_code = status.HTTP_403_FORBIDDEN
        return ErrorResponse(
            error="Insufficient permissions for connection health metrics"
        )

    # Get connection health from manager
    stats = await dashboard_handler._manager.get_connection_stats()

    return {
        "status": "healthy" if stats["utilization"] < 0.8 else "warning",
        "metrics": stats,
        "recommendations": _get_health_recommendations(stats),
    }


@beartype
def _get_health_recommendations(stats: dict[str, Any]) -> list[str]:
    """Generate health recommendations based on current metrics."""
    recommendations = []

    utilization = stats.get("utilization", 0)
    if utilization > 0.9:
        recommendations.append(
            "Consider scaling WebSocket servers - utilization above 90%"
        )
    elif utilization > 0.7:
        recommendations.append("Monitor connection growth - utilization above 70%")

    largest_room = stats.get("largest_room", 0)
    if largest_room > 1000:
        recommendations.append("Large rooms detected - consider room partitioning")

    total_rooms = stats.get("total_rooms", 0)
    if total_rooms > 10000:
        recommendations.append("High room count - consider room cleanup strategy")

    if not recommendations:
        recommendations.append("System is operating within normal parameters")

    return recommendations


@router.get("/active-sessions")
@beartype
async def get_active_admin_sessions(
    response: Response,
    admin_user: AdminUser = Depends(get_current_admin_user),
    dashboard_handler: AdminDashboardHandler = Depends(get_admin_dashboard_handler),
) -> dict[str, Any] | ErrorResponse:
    """Get information about active admin WebSocket sessions."""
    if "audit:read" not in admin_user.effective_permissions:
        response.status_code = status.HTTP_403_FORBIDDEN
        return ErrorResponse(error="Insufficient permissions for session information")

    active_sessions = []
    for stream_key in dashboard_handler._active_streams.keys():
        # Parse stream key to extract connection info
        parts = stream_key.split("_")
        session_info = {
            "stream_key": stream_key,
            "stream_type": parts[0] if parts else "unknown",
            "connection_id": "_".join(parts[1:]) if len(parts) > 1 else "unknown",
            "status": "active",
        }
        active_sessions.append(session_info)

    return {
        "active_sessions": active_sessions,
        "total_count": len(active_sessions),
        "session_types": list({s["stream_type"] for s in active_sessions}),
    }
