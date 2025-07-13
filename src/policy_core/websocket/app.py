# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""WebSocket application setup."""

import json
from typing import Any
from uuid import UUID, uuid4

from beartype import beartype
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware

from policy_core.core.result_types import Err, Ok, Result

from ..core.cache import get_cache
from ..core.config import get_settings
from ..core.database import get_database
from ..services.quote_service import QuoteService
from .handlers.admin_dashboard import AdminDashboardHandler
from .handlers.analytics import AnalyticsWebSocketHandler, DashboardConfig
from .handlers.notifications import NotificationHandler
from .handlers.quotes import CollaborativeEditRequest, QuoteWebSocketHandler
from .manager import ConnectionManager, MessageType, WebSocketMessage

# Create WebSocket app
websocket_app = FastAPI(
    title="PD Prime WebSocket API",
    description="Real-time WebSocket endpoints for quotes and analytics",
    version="1.0.0",
)


# Defer CORS setup to startup
@websocket_app.on_event("startup")
async def setup_cors() -> None:
    """Setup CORS middleware on startup when settings are available."""
    try:
        settings = get_settings()
        websocket_app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.api_cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    except Exception:
        # During testing, settings might not be available
        pass


# Initialize global instances
_manager: ConnectionManager | None = None
_quote_handler: QuoteWebSocketHandler | None = None
_analytics_handler: AnalyticsWebSocketHandler | None = None
_notification_handler: NotificationHandler | None = None
_admin_handler: AdminDashboardHandler | None = None


@beartype
def get_manager() -> ConnectionManager:
    """Get WebSocket connection manager instance."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager(get_cache(), get_database())
    return _manager


@beartype
def get_quote_handler() -> QuoteWebSocketHandler:
    """Get quote WebSocket handler instance."""
    global _quote_handler
    if _quote_handler is None:
        # Initialize quote service
        db = get_database()
        cache = get_cache()
        quote_service = QuoteService(db, cache)

        _quote_handler = QuoteWebSocketHandler(get_manager(), quote_service)
    return _quote_handler


@beartype
def get_analytics_handler() -> AnalyticsWebSocketHandler:
    """Get analytics WebSocket handler instance."""
    global _analytics_handler
    if _analytics_handler is None:
        _analytics_handler = AnalyticsWebSocketHandler(get_manager(), get_database())
    return _analytics_handler


@beartype
def get_notification_handler() -> NotificationHandler:
    """Get notification WebSocket handler instance."""
    global _notification_handler
    if _notification_handler is None:
        _notification_handler = NotificationHandler(get_manager(), get_database())
    return _notification_handler


@beartype
def get_admin_handler() -> AdminDashboardHandler:
    """Get admin dashboard WebSocket handler instance."""
    global _admin_handler
    if _admin_handler is None:
        _admin_handler = AdminDashboardHandler(
            get_manager(), get_database(), get_cache()
        )
    return _admin_handler


@websocket_app.on_event("startup")
async def startup() -> None:
    """Start WebSocket manager and handlers."""
    manager = get_manager()
    await manager.start()


@websocket_app.on_event("shutdown")
async def shutdown() -> None:
    """Stop WebSocket manager and cleanup."""
    manager = get_manager()
    await manager.stop()


@beartype
async def send_error_message(
    manager: ConnectionManager, connection_id: str, error: str
) -> None:
    """Helper function to send error messages with proper format."""
    error_msg = WebSocketMessage(type=MessageType.ERROR, data={"error": error})
    await manager.send_personal_message(connection_id, error_msg)


@beartype
async def validate_websocket_token(token: str | None) -> Result[UUID | None, str]:
    """Validate WebSocket authentication token."""
    if not token:
        # Allow anonymous connections for demo
        return Ok(None)

    # In production, validate JWT token
    # For now, accept any non-empty token as demo user
    if token == "demo":
        return Ok(UUID("00000000-0000-0000-0000-000000000000"))

    try:
        # Try to parse as UUID for testing
        user_id = UUID(token)
        return Ok(user_id)
    except ValueError:
        return Err("Invalid authentication token format")


@websocket_app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = None,
) -> None:
    """Main WebSocket endpoint with explicit error handling."""
    connection_id = str(uuid4())
    manager = get_manager()
    quote_handler = get_quote_handler()
    analytics_handler = get_analytics_handler()
    notification_handler = get_notification_handler()
    admin_handler = get_admin_handler()

    # Validate token
    auth_result = await validate_websocket_token(token)
    if auth_result.is_err():
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason=auth_result.unwrap_err()
        )
        return

    user_id = auth_result.unwrap()

    # Accept connection
    connect_result = await manager.connect(
        websocket,
        connection_id,
        user_id=user_id,
        metadata={
            "ip_address": websocket.client.host if websocket.client else None,
            "user_agent": websocket.headers.get("user-agent"),
        },
    )

    if connect_result.is_err():
        await websocket.close(
            code=status.WS_1013_TRY_AGAIN_LATER,
            reason=(connect_result.unwrap_err() or "Connection failed")[
                :123
            ],  # Reason limited to 123 bytes
        )
        return

    try:
        while True:
            # Receive message
            try:
                raw_data = await websocket.receive_text()
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                error_msg = WebSocketMessage(
                    type=MessageType.ERROR,
                    data={
                        "error": "Invalid JSON format",
                        "received": (
                            raw_data[:100] if "raw_data" in locals() else "unknown"
                        ),
                    },
                )
                await manager.send_personal_message(connection_id, error_msg)
                continue
            except ValueError:
                # WebSocket closed or invalid data
                break

            # Handle base message types
            message_type = data.get("type")

            if message_type in ["ping", "subscribe", "unsubscribe"]:
                # Base manager handles these
                await manager.handle_message(connection_id, data)

            # Quote-specific messages
            elif message_type == "quote_subscribe":
                quote_id = data.get("quote_id")
                if not quote_id:
                    error_msg = WebSocketMessage(
                        type=MessageType.ERROR,
                        data={"error": "quote_id required for quote_subscribe"},
                    )
                    await manager.send_personal_message(connection_id, error_msg)
                    continue

                try:
                    quote_uuid = UUID(quote_id)
                    await quote_handler.handle_quote_subscribe(
                        connection_id, quote_uuid
                    )
                except ValueError:
                    error_msg = WebSocketMessage(
                        type=MessageType.ERROR,
                        data={"error": f"Invalid quote_id format: {quote_id}"},
                    )
                    await manager.send_personal_message(connection_id, error_msg)

            elif message_type == "quote_unsubscribe":
                quote_id = data.get("quote_id")
                if quote_id:
                    try:
                        quote_uuid = UUID(quote_id)
                        await quote_handler.handle_quote_unsubscribe(
                            connection_id, quote_uuid
                        )
                    except ValueError:
                        pass  # Ignore invalid UUID on unsubscribe

            elif message_type == "quote_edit":
                try:
                    edit_request = CollaborativeEditRequest(**data.get("data", {}))
                    await quote_handler.handle_collaborative_edit(
                        connection_id, edit_request
                    )
                except Exception as e:
                    await send_error_message(
                        manager, connection_id, f"Invalid edit request: {str(e)}"
                    )

            elif message_type == "field_focus":
                quote_id = data.get("quote_id")
                field = data.get("field")
                focused = data.get("focused", False)

                if quote_id and field:
                    try:
                        quote_uuid = UUID(quote_id)
                        await quote_handler.handle_field_focus(
                            connection_id, quote_uuid, field, focused
                        )
                    except ValueError:
                        pass

            elif message_type == "cursor_position":
                quote_id = data.get("quote_id")
                field = data.get("field")
                position = data.get("position", 0)

                if quote_id and field and isinstance(position, int):
                    try:
                        quote_uuid = UUID(quote_id)
                        await quote_handler.handle_cursor_position(
                            connection_id, quote_uuid, field, position
                        )
                    except ValueError:
                        pass

            # Analytics messages
            elif message_type == "start_analytics":
                dashboard_type = data.get("dashboard_type")
                if not dashboard_type:
                    await send_error_message(
                        manager, connection_id, "dashboard_type required for analytics"
                    )
                    continue

                try:
                    config = DashboardConfig(
                        dashboard_type=dashboard_type,
                        update_interval=data.get("update_interval", 5),
                        filters=data.get("filters", {}),
                        metrics=data.get("metrics", []),
                        time_range_hours=data.get("time_range_hours", 24),
                    )
                    await analytics_handler.start_analytics_stream(
                        connection_id, config
                    )
                except Exception as e:
                    await send_error_message(
                        manager, connection_id, f"Invalid analytics config: {str(e)}"
                    )

            elif message_type == "stop_analytics":
                dashboard_type = data.get("dashboard_type")
                if dashboard_type:
                    await analytics_handler.stop_analytics_stream(
                        connection_id, dashboard_type
                    )

            # Notification messages
            elif message_type == "notification_acknowledge":
                notification_id = data.get("notification_id")
                if notification_id:
                    try:
                        notification_uuid = UUID(notification_id)
                        await notification_handler.handle_notification_acknowledgment(
                            connection_id, notification_uuid
                        )
                    except ValueError:
                        await send_error_message(
                            manager,
                            connection_id,
                            f"Invalid notification_id format: {notification_id}",
                        )

            # Admin dashboard messages
            elif message_type == "start_admin_monitoring":
                if not user_id:
                    await send_error_message(
                        manager,
                        connection_id,
                        "Authentication required for admin monitoring",
                    )
                    continue

                dashboard_config = data.get("config", {})
                await admin_handler.start_system_monitoring(
                    connection_id, user_id, dashboard_config
                )

            elif message_type == "start_user_activity":
                if not user_id:
                    await send_error_message(
                        manager,
                        connection_id,
                        "Authentication required for user activity monitoring",
                    )
                    continue

                filters = data.get("filters", {})
                await admin_handler.start_user_activity_monitoring(
                    connection_id, user_id, filters
                )

            elif message_type == "start_performance_monitoring":
                if not user_id:
                    await send_error_message(
                        manager,
                        connection_id,
                        "Authentication required for performance monitoring",
                    )
                    continue

                metrics = data.get("metrics", [])
                await admin_handler.start_performance_monitoring(
                    connection_id, user_id, metrics
                )

            else:
                # Unknown message type
                error_msg = WebSocketMessage(
                    type=MessageType.ERROR,
                    data={
                        "error": f"Unknown message type: {message_type}",
                        "supported_types": [
                            "ping",
                            "subscribe",
                            "unsubscribe",
                            "quote_subscribe",
                            "quote_unsubscribe",
                            "quote_edit",
                            "field_focus",
                            "cursor_position",
                            "start_analytics",
                            "stop_analytics",
                            "notification_acknowledge",
                            "start_admin_monitoring",
                            "start_user_activity",
                            "start_performance_monitoring",
                        ],
                    },
                )
                await manager.send_personal_message(connection_id, error_msg)

    except WebSocketDisconnect:
        pass  # Normal disconnection
    except Exception as e:
        # Unexpected error
        try:
            error_msg = WebSocketMessage(
                type=MessageType.ERROR,
                data={
                    "error": f"Unexpected error: {str(e)}",
                    "fatal": True,
                },
            )
            await manager.send_personal_message(connection_id, error_msg)
        except Exception:
            pass  # Connection already broken
    finally:
        # Cleanup
        await quote_handler.cleanup_connection(connection_id)
        await analytics_handler.cleanup_connection(connection_id)
        await notification_handler.cleanup_connection(connection_id)
        await admin_handler.handle_admin_disconnect(connection_id)
        await manager.disconnect(connection_id, "Connection closed")


@websocket_app.get("/health")
async def websocket_health() -> dict[str, Any]:
    """WebSocket service health check."""
    manager = get_manager()
    stats = await manager.get_connection_stats()

    return {
        "status": "healthy",
        "service": "websocket",
        "stats": stats,
    }


# Export the app
__all__ = ["websocket_app"]
