"""WebSocket connection and room management."""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

from beartype import beartype
from fastapi import WebSocket
from pydantic import BaseModel, ConfigDict, Field

from ..core.cache import Cache
from ..core.database import Database
from ..services.result import Err, Ok, Result
from .monitoring import WebSocketMonitor


class WebSocketMessage(BaseModel):
    """WebSocket message structure."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: str = Field(..., min_length=1, max_length=50)
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    sequence: int | None = Field(default=None, ge=0)


class ConnectionMetadata(BaseModel):
    """Metadata for a WebSocket connection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connection_id: str = Field(..., min_length=1, max_length=100)
    user_id: UUID | None = Field(default=None)
    ip_address: str | None = Field(default=None)
    user_agent: str | None = Field(default=None)
    connected_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)


class ConnectionManager:
    """Manage WebSocket connections and rooms with no silent fallbacks."""

    def __init__(self, cache: Cache, db: Database) -> None:
        """Initialize connection manager."""
        self._cache = cache
        self._db = db

        # Active connections by connection ID
        self._connections: dict[str, WebSocket] = {}

        # User to connection mapping
        self._user_connections: dict[UUID, set[str]] = {}

        # Room subscriptions
        self._room_subscriptions: dict[str, set[str]] = {}

        # Connection metadata
        self._connection_metadata: dict[str, ConnectionMetadata] = {}

        # Message sequence tracking per connection
        self._message_sequences: dict[str, int] = {}

        # Heartbeat tracking
        self._last_ping: dict[str, datetime] = {}

        # Performance monitoring
        self._monitor = WebSocketMonitor(cache, db)

        # Background tasks
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._health_monitor_task: asyncio.Task[None] | None = None

        # Connection pool monitoring
        self._active_connection_count = 0
        self._max_connections_allowed = 10000

    async def start(self) -> None:
        """Start background tasks."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._health_monitor_task = asyncio.create_task(self._health_monitoring_loop())
        await self._monitor.start_monitoring()

    async def stop(self) -> None:
        """Stop background tasks and close all connections."""
        # Stop monitoring first
        await self._monitor.stop_monitoring()

        # Cancel background tasks
        for task in [self._heartbeat_task, self._health_monitor_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close all connections
        for conn_id in list(self._connections.keys()):
            await self.disconnect(conn_id, "Server shutdown")

    @beartype
    async def connect(
        self,
        websocket: WebSocket,
        connection_id: str,
        user_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Result[None, str]:
        """Accept and register a new WebSocket connection with explicit validation."""
        # Check connection limits
        if self._active_connection_count >= self._max_connections_allowed:
            return Err(
                f"Connection limit reached: {self._max_connections_allowed}. "
                "Required action: Contact admin to increase connection pool. "
                "System cannot accept new connections until existing ones disconnect."
            )

        # Validate connection ID uniqueness
        if connection_id in self._connections:
            return Err(
                f"Connection ID {connection_id} already exists. "
                "Required action: Generate a unique connection ID. "
                "System requires all connection IDs to be globally unique."
            )

        # Validate user permissions if user_id provided
        if user_id:
            permission_check = await self._validate_user_permissions(user_id)
            if permission_check.is_err():
                return permission_check

        try:
            await websocket.accept()
        except Exception as e:
            return Err(
                f"Failed to accept WebSocket connection: {str(e)}. "
                "Required action: Check network configuration and client compatibility. "
                "WebSocket handshake must complete successfully."
            )

        # Create connection metadata
        conn_metadata = ConnectionMetadata(
            connection_id=connection_id,
            user_id=user_id,
            ip_address=metadata.get("ip_address") if metadata else None,
            user_agent=metadata.get("user_agent") if metadata else None,
        )

        # Store connection
        self._connections[connection_id] = websocket
        self._connection_metadata[connection_id] = conn_metadata
        self._last_ping[connection_id] = datetime.now()
        self._message_sequences[connection_id] = 0
        self._active_connection_count += 1

        # Map user to connection
        if user_id:
            if user_id not in self._user_connections:
                self._user_connections[user_id] = set()
            self._user_connections[user_id].add(connection_id)

        # Store in database for distributed systems
        store_result = await self._store_connection(conn_metadata)
        if store_result.is_err():
            # Roll back local state
            del self._connections[connection_id]
            del self._connection_metadata[connection_id]
            del self._last_ping[connection_id]
            del self._message_sequences[connection_id]
            self._active_connection_count -= 1
            if user_id and user_id in self._user_connections:
                self._user_connections[user_id].discard(connection_id)
            return store_result

        # Send welcome message with explicit connection state
        welcome_msg = WebSocketMessage(
            type="connection",
            data={
                "status": "connected",
                "connection_id": connection_id,
                "server_time": datetime.now().isoformat(),
                "connection_limits": {
                    "max_connections": self._max_connections_allowed,
                    "current_connections": self._active_connection_count,
                },
                "capabilities": {
                    "rooms": True,
                    "message_sequencing": True,
                    "heartbeat_interval": 30,
                },
            },
            sequence=self._get_next_sequence(connection_id),
        )

        send_result = await self.send_personal_message(connection_id, welcome_msg)
        if send_result.is_err():
            # Connection failed immediately
            await self.disconnect(connection_id, "Initial message send failed")
            return send_result

        # Record successful connection in monitoring
        await self._monitor.record_connection_established(
            connection_id, user_id, metadata
        )

        return Ok(None)

    @beartype
    async def disconnect(
        self,
        connection_id: str,
        reason: str = "Unknown",
        skip_notification: bool = False,
    ) -> Result[None, str]:
        """Disconnect and cleanup a WebSocket connection with explicit tracking."""
        if connection_id not in self._connections:
            return Err(
                f"Connection {connection_id} not found in active pool. "
                "Required action: Check connection state in admin dashboard. "
                "System cannot disconnect non-existent connections."
            )

        # Get metadata
        metadata = self._connection_metadata.get(connection_id)
        if not metadata:
            return Err(
                f"Connection metadata for {connection_id} is missing. "
                "This indicates a critical state inconsistency. "
                "Required action: Alert system administrator immediately."
            )

        # Notify user of impending disconnection (unless skipping due to send failure)
        if not skip_notification and "Send failed" not in reason:
            disconnect_msg = WebSocketMessage(
                type="disconnecting",
                data={
                    "reason": reason,
                    "connection_id": connection_id,
                    "final_sequence": self._message_sequences.get(connection_id, 0),
                },
            )
            # Try to send, but don't create recursive disconnect if this fails
            try:
                websocket = self._connections[connection_id]
                await websocket.send_json(disconnect_msg.model_dump())
            except Exception:
                # Connection already broken, proceed with cleanup
                pass

        # Remove from user connections
        if metadata.user_id:
            if metadata.user_id in self._user_connections:
                self._user_connections[metadata.user_id].discard(connection_id)
                if not self._user_connections[metadata.user_id]:
                    del self._user_connections[metadata.user_id]

        # Remove from all rooms and notify room members
        for room_id in list(self._room_subscriptions.keys()):
            if connection_id in self._room_subscriptions[room_id]:
                await self._leave_room_internal(connection_id, room_id)

        # Close WebSocket
        websocket = self._connections[connection_id]
        try:
            await websocket.close(
                code=1000, reason=reason[:123]
            )  # Reason limited to 123 bytes
        except Exception:
            # Connection already closed
            pass

        # Cleanup local state
        del self._connections[connection_id]
        del self._connection_metadata[connection_id]
        self._last_ping.pop(connection_id, None)
        self._message_sequences.pop(connection_id, None)
        self._active_connection_count -= 1

        # Remove from database
        await self._remove_connection(connection_id)

        # Record disconnection in monitoring
        await self._monitor.record_connection_closed(connection_id, reason)

        return Ok(None)

    @beartype
    async def subscribe_to_room(
        self, connection_id: str, room_id: str
    ) -> Result[None, str]:
        """Subscribe a connection to a room with explicit permission validation."""
        if connection_id not in self._connections:
            return Err(
                f"Connection {connection_id} not found. "
                "Required action: Establish connection before subscribing to rooms. "
                "System requires active connection for room subscriptions."
            )

        # Validate room access permissions
        metadata = self._connection_metadata.get(connection_id)
        if metadata and metadata.user_id:
            permission_result = await self._validate_room_access(
                metadata.user_id, room_id
            )
            if permission_result.is_err():
                return permission_result

        # Check if already subscribed
        if (
            room_id in self._room_subscriptions
            and connection_id in self._room_subscriptions[room_id]
        ):
            return Ok(None)  # Already subscribed, idempotent operation

        # Subscribe to room
        if room_id not in self._room_subscriptions:
            self._room_subscriptions[room_id] = set()

        self._room_subscriptions[room_id].add(connection_id)

        # Store subscription in cache for distributed systems
        cache_result = await self._cache_room_subscription(room_id, connection_id, True)
        if cache_result.is_err():
            # Roll back
            self._room_subscriptions[room_id].discard(connection_id)
            return cache_result

        # Get room member count
        member_count = len(self._room_subscriptions[room_id])

        # Notify room of new member
        join_msg = WebSocketMessage(
            type="room_event",
            data={
                "event": "member_joined",
                "room_id": room_id,
                "connection_id": connection_id,
                "user_id": (
                    str(metadata.user_id) if metadata and metadata.user_id else None
                ),
                "member_count": member_count,
            },
        )

        await self.send_to_room(room_id, join_msg, exclude=[connection_id])

        # Confirm subscription to the joining member
        confirm_msg = WebSocketMessage(
            type="room_subscribed",
            data={
                "room_id": room_id,
                "member_count": member_count,
            },
            sequence=self._get_next_sequence(connection_id),
        )

        await self.send_personal_message(connection_id, confirm_msg)

        # Record room subscription in monitoring
        await self._monitor.record_room_subscription(connection_id, room_id, True)

        return Ok(None)

    @beartype
    async def unsubscribe_from_room(
        self, connection_id: str, room_id: str
    ) -> Result[None, str]:
        """Unsubscribe a connection from a room."""
        if connection_id not in self._connections:
            return Err(
                f"Connection {connection_id} not found. "
                "Cannot unsubscribe from room without active connection."
            )

        # Check if subscribed
        if (
            room_id not in self._room_subscriptions
            or connection_id not in self._room_subscriptions[room_id]
        ):
            return Ok(None)  # Not subscribed, idempotent operation

        await self._leave_room_internal(connection_id, room_id)

        # Record room unsubscription in monitoring
        await self._monitor.record_room_subscription(connection_id, room_id, False)

        return Ok(None)

    @beartype
    async def send_personal_message(
        self, connection_id: str, message: WebSocketMessage
    ) -> Result[None, str]:
        """Send a message to a specific connection with guaranteed delivery tracking."""
        if connection_id not in self._connections:
            return Err(
                f"Connection {connection_id} not found. "
                "Cannot send message to non-existent connection."
            )

        websocket = self._connections[connection_id]

        # Set sequence number if not provided
        if message.sequence is None:
            message = message.model_copy(
                update={"sequence": self._get_next_sequence(connection_id)}
            )

        try:
            message_data = message.model_dump()
            await websocket.send_json(message_data)

            # Record message sending in monitoring
            message_size = len(str(message_data))
            await self._monitor.record_message_sent(connection_id, message_size)

            # Update last activity
            if connection_id in self._connection_metadata:
                self._connection_metadata[connection_id] = self._connection_metadata[
                    connection_id
                ].model_copy(update={"last_activity": datetime.now()})
            return Ok(None)
        except Exception as e:
            # Connection failed, disconnect (skip notification to prevent recursion)
            await self.disconnect(
                connection_id, f"Send failed: {str(e)}", skip_notification=True
            )
            return Err(
                f"Failed to send message to connection {connection_id}: {str(e)}. "
                "Connection has been terminated."
            )

    @beartype
    async def send_to_user(
        self, user_id: UUID, message: WebSocketMessage
    ) -> Result[int, str]:
        """Send a message to all connections of a user. Returns number of successful sends."""
        if user_id not in self._user_connections:
            return Ok(0)  # No connections for user

        successful_sends = 0
        failed_connections = []

        for conn_id in list(self._user_connections[user_id]):
            result = await self.send_personal_message(conn_id, message)
            if result.is_ok():
                successful_sends += 1
            else:
                failed_connections.append(conn_id)

        # Report if some sends failed
        if failed_connections:
            return Ok(successful_sends)  # Partial success is still Ok

        return Ok(successful_sends)

    @beartype
    async def send_to_room(
        self,
        room_id: str,
        message: WebSocketMessage,
        exclude: list[str] | None = None,
    ) -> Result[int, str]:
        """Send a message to all connections in a room. Returns number of successful sends."""
        if room_id not in self._room_subscriptions:
            return Ok(0)  # No subscribers in room

        exclude = exclude or []
        successful_sends = 0
        failed_connections = []

        for conn_id in list(self._room_subscriptions[room_id]):
            if conn_id not in exclude:
                result = await self.send_personal_message(conn_id, message)
                if result.is_ok():
                    successful_sends += 1
                else:
                    failed_connections.append(conn_id)

        return Ok(successful_sends)

    @beartype
    async def broadcast(
        self,
        message: WebSocketMessage,
        exclude: list[str] | None = None,
    ) -> Result[int, str]:
        """Broadcast a message to all connections. Use sparingly."""
        exclude = exclude or []
        successful_sends = 0

        for conn_id in list(self._connections.keys()):
            if conn_id not in exclude:
                result = await self.send_personal_message(conn_id, message)
                if result.is_ok():
                    successful_sends += 1

        return Ok(successful_sends)

    @beartype
    async def handle_message(
        self, connection_id: str, raw_message: dict[str, Any]
    ) -> Result[None, str]:
        """Handle incoming WebSocket message with explicit validation."""
        # Validate connection exists
        if connection_id not in self._connections:
            return Err(
                f"Connection {connection_id} not found. "
                "Cannot process messages from non-existent connections."
            )

        # Validate message structure
        if "type" not in raw_message:
            error_msg = WebSocketMessage(
                type="error",
                data={
                    "error": "Message validation error: 'type' field is required.",
                    "required_fields": ["type"],
                    "received_fields": list(raw_message.keys()),
                },
                sequence=self._get_next_sequence(connection_id),
            )
            await self.send_personal_message(connection_id, error_msg)
            return Err("Invalid message structure: missing 'type' field")

        message_type = raw_message.get("type")

        # Update last activity
        self._last_ping[connection_id] = datetime.now()

        # Handle different message types
        if message_type == "ping":
            pong_msg = WebSocketMessage(
                type="pong",
                data={
                    "client_time": raw_message.get("timestamp"),
                    "server_time": datetime.now().isoformat(),
                },
                sequence=self._get_next_sequence(connection_id),
            )
            return await self.send_personal_message(connection_id, pong_msg)

        elif message_type == "subscribe":
            room_id = raw_message.get("room_id")
            if not room_id:
                return Err(
                    "Subscribe message missing room_id. "
                    "Required action: Include 'room_id' in subscribe messages."
                )
            return await self.subscribe_to_room(connection_id, room_id)

        elif message_type == "unsubscribe":
            room_id = raw_message.get("room_id")
            if not room_id:
                return Err(
                    "Unsubscribe message missing room_id. "
                    "Required action: Include 'room_id' in unsubscribe messages."
                )
            return await self.unsubscribe_from_room(connection_id, room_id)

        else:
            # Unknown message type - no silent fallback
            error_msg = WebSocketMessage(
                type="error",
                data={
                    "error": f"Unknown message type: {message_type}",
                    "supported_types": ["ping", "subscribe", "unsubscribe"],
                },
                sequence=self._get_next_sequence(connection_id),
            )
            await self.send_personal_message(connection_id, error_msg)
            return Err(f"Unknown message type: {message_type}")

    @beartype
    async def get_connection_stats(self) -> dict[str, Any]:
        """Get current connection statistics."""
        room_sizes = {
            room_id: len(members)
            for room_id, members in self._room_subscriptions.items()
        }

        return {
            "total_connections": self._active_connection_count,
            "max_connections": self._max_connections_allowed,
            "utilization": self._active_connection_count
            / self._max_connections_allowed,
            "unique_users": len(self._user_connections),
            "total_rooms": len(self._room_subscriptions),
            "room_sizes": room_sizes,
            "largest_room": max(room_sizes.values()) if room_sizes else 0,
        }

    @beartype
    async def get_performance_metrics(self) -> dict[str, Any]:
        """Get comprehensive performance metrics including monitoring data."""
        basic_stats = await self.get_connection_stats()
        monitoring_summary = await self._monitor.get_metrics_summary()

        return {
            **basic_stats,
            "monitoring": monitoring_summary,
        }

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats and check connection health."""
        while True:
            try:
                await asyncio.sleep(30)  # 30 second intervals

                now = datetime.now()
                disconnected = []

                # Check all connections
                for conn_id, last_ping in list(self._last_ping.items()):
                    # If no ping in 90 seconds, consider dead
                    if (now - last_ping).total_seconds() > 90:
                        disconnected.append(conn_id)
                    else:
                        # Send heartbeat
                        heartbeat_msg = WebSocketMessage(
                            type="heartbeat",
                            data={
                                "server_time": now.isoformat(),
                                "connection_healthy": True,
                            },
                            sequence=self._get_next_sequence(conn_id),
                        )
                        await self.send_personal_message(conn_id, heartbeat_msg)

                # Disconnect dead connections
                for conn_id in disconnected:
                    await self.disconnect(conn_id, "Heartbeat timeout")

            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue
                pass

    async def _health_monitoring_loop(self) -> None:
        """Monitor overall system health and alert on issues."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute

                stats = await self.get_connection_stats()

                # Check for concerning patterns
                if stats["utilization"] > 0.9:
                    # Alert admins about high connection usage
                    alert_msg = WebSocketMessage(
                        type="system_alert",
                        data={
                            "alert_type": "high_connection_usage",
                            "message": f"Connection pool at {stats['utilization']*100:.1f}% capacity",
                            "severity": "warning",
                            "stats": stats,
                        },
                    )
                    # Send to admin room
                    await self.send_to_room("admin:monitoring", alert_msg)

            except asyncio.CancelledError:
                break
            except Exception:
                pass

    @beartype
    def _get_next_sequence(self, connection_id: str) -> int:
        """Get next message sequence number for a connection."""
        if connection_id not in self._message_sequences:
            self._message_sequences[connection_id] = 0

        self._message_sequences[connection_id] += 1
        return self._message_sequences[connection_id]

    @beartype
    async def _leave_room_internal(self, connection_id: str, room_id: str) -> None:
        """Internal method to handle leaving a room."""
        self._room_subscriptions[room_id].discard(connection_id)
        if not self._room_subscriptions[room_id]:
            del self._room_subscriptions[room_id]

        # Remove from cache
        await self._cache_room_subscription(room_id, connection_id, False)

        # Get remaining member count
        member_count = len(self._room_subscriptions.get(room_id, set()))

        # Notify room of member leaving
        metadata = self._connection_metadata.get(connection_id)
        leave_msg = WebSocketMessage(
            type="room_event",
            data={
                "event": "member_left",
                "room_id": room_id,
                "connection_id": connection_id,
                "user_id": (
                    str(metadata.user_id) if metadata and metadata.user_id else None
                ),
                "member_count": member_count,
            },
        )
        await self.send_to_room(room_id, leave_msg)

    @beartype
    async def _validate_user_permissions(self, user_id: UUID) -> Result[None, str]:
        """Validate user has permission to connect via WebSocket."""
        # In production, check user status, subscription, etc.
        # For now, allow all authenticated users
        return Ok(None)

    @beartype
    async def _validate_room_access(
        self, user_id: UUID, room_id: str
    ) -> Result[None, str]:
        """Validate user has permission to access a specific room."""
        # Room access patterns:
        # - quote:{quote_id} - user must own quote or be assigned agent
        # - policy:{policy_id} - user must own policy or have admin access
        # - admin:* - user must have admin role
        # - analytics:* - user must have analytics permission

        if room_id.startswith("admin:"):
            # Check admin permissions
            # For now, simplified check
            return Ok(None)

        if room_id.startswith("quote:"):
            # Extract quote ID and check ownership
            # For now, allow access
            return Ok(None)

        # Default allow for demo
        return Ok(None)

    @beartype
    async def _cache_room_subscription(
        self, room_id: str, connection_id: str, subscribe: bool
    ) -> Result[None, str]:
        """Cache room subscription for distributed systems."""
        try:
            cache_key = f"ws:room:{room_id}:members"
            if subscribe:
                await self._cache.sadd(cache_key, connection_id)
            else:
                await self._cache.srem(cache_key, connection_id)
            return Ok(None)
        except Exception as e:
            return Err(f"Failed to update room cache: {str(e)}")

    @beartype
    async def _store_connection(
        self, metadata: ConnectionMetadata
    ) -> Result[None, str]:
        """Store connection info in database."""
        try:
            await self._db.execute(
                """
                INSERT INTO websocket_connections
                (connection_id, user_id, ip_address, user_agent, connected_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (connection_id) DO NOTHING
                """,
                metadata.connection_id,
                metadata.user_id,
                metadata.ip_address,
                metadata.user_agent,
                metadata.connected_at,
            )
            return Ok(None)
        except Exception as e:
            return Err(f"Failed to store connection in database: {str(e)}")

    @beartype
    async def _remove_connection(self, connection_id: str) -> Result[None, str]:
        """Remove connection from database."""
        try:
            await self._db.execute(
                """
                UPDATE websocket_connections
                SET disconnected_at = $2
                WHERE connection_id = $1
                """,
                connection_id,
                datetime.now(),
            )
            return Ok(None)
        except Exception:
            # Non-critical error, connection already cleaned up locally
            return Ok(None)
