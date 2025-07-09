"""Real-time quote updates handler."""

import asyncio
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

from pd_prime_demo.core.result_types import Err, Ok, Result

from ...services.quote_service import QuoteService
from ..manager import ConnectionManager, MessageType, WebSocketMessage
from ..message_models import (  # Auto-generated models
    Any],
    BaseModelConfig,
    DetailsData,
    """Structured,
    ...models.base,
    :,
    @beartype,
    class,
    dict[str,
    from,
    import,
    model,
    replacing,
    usage.""",
)

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class FieldLocksMapping(BaseModelConfig):
    """Structured model replacing dict[str, str] usage."""

    key: str = Field(..., min_length=1, description="Mapping key")
    value: str = Field(..., min_length=1, description="Mapping value")

    create_websocket_message_data,
)


class QuoteUpdateData(BaseModel):
    """Data structure for quote updates."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    update_type: str = Field(..., min_length=1, max_length=50)
    field: str | None = Field(default=None)
    old_value: Any = Field(default=None)
    new_value: Any = Field(default=None)
    updated_by: str | None = Field(default=None)
    calculation_progress: float | None = Field(default=None, ge=0, le=100)
    stage: str | None = Field(default=None)


class CollaborativeEditRequest(BaseModel):
    """Request for collaborative quote editing."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    quote_id: UUID = Field(...)
    field: str = Field(..., min_length=1, max_length=100)
    value: Any = Field(...)


class QuoteWebSocketHandler:
    """Handle real-time quote operations with no silent fallbacks."""

    def __init__(
        self,
        manager: ConnectionManager,
        quote_service: QuoteService,
    ) -> None:
        """Initialize quote handler."""
        self._manager = manager
        self._quote_service = quote_service

        # Track active quote editing sessions
        self._active_quote_sessions: dict[UUID, set[str]] = {}

        # Collaborative editing locks
        self._field_locks: FieldLocksMapping = {}  # field_key -> connection_id

        # Message deduplication
        self._recent_updates: dict[str, datetime] = {}

    @beartype
    async def handle_quote_subscribe(
        self, connection_id: str, quote_id: UUID
    ) -> Result[None, str]:
        """Subscribe to real-time quote updates with explicit validation."""
        # Validate quote exists and user has access
        quote_result = await self._quote_service.get_quote(quote_id)
        if quote_result.is_err():
            error_msg = WebSocketMessage(
                type=MessageType.SUBSCRIPTION_ERROR,
                data=create_websocket_message_data(
                    error=f"Cannot subscribe to quote {quote_id}: {quote_result.unwrap_err()}",
                    quote_id=quote_id,
                ).model_dump(),
            )
            await self._manager.send_personal_message(connection_id, error_msg)
            return Err(f"Quote subscription failed: {quote_result.unwrap_err()}")

        quote = quote_result.unwrap()
        if not quote:
            error_msg = WebSocketMessage(
                type=MessageType.SUBSCRIPTION_ERROR,
                data=create_websocket_message_data(
                    error=f"Quote {quote_id} not found",
                    quote_id=quote_id,
                ).model_dump(),
            )
            await self._manager.send_personal_message(connection_id, error_msg)
            return Err(f"Quote {quote_id} not found")

        # Subscribe to quote room
        room_id = f"quote:{quote_id}"
        subscribe_result = await self._manager.subscribe_to_room(connection_id, room_id)
        if subscribe_result.is_err():
            return subscribe_result

        # Track active session
        if quote_id not in self._active_quote_sessions:
            self._active_quote_sessions[quote_id] = set()
        self._active_quote_sessions[quote_id].add(connection_id)

        # Send current quote state
        state_msg = WebSocketMessage(
            type=MessageType.QUOTE_STATE,
            data=create_websocket_message_data(
                quote_id=quote_id,
                payload={
                    "quote": quote.model_dump(mode="json"),
                    "active_editors": len(self._active_quote_sessions[quote_id]),
                    "your_connection_id": connection_id,
                },
            ).model_dump(),
        )
        await self._manager.send_personal_message(connection_id, state_msg)

        # Notify others of new editor
        join_msg = WebSocketMessage(
            type=MessageType.ROOM_EVENT,
            data=create_websocket_message_data(
                quote_id=quote_id,
                connection_id=connection_id,
                payload={"active_editors": len(self._active_quote_sessions[quote_id])},
            ).model_dump(),
        )
        await self._manager.send_to_room(room_id, join_msg, exclude=[connection_id])

        return Ok(None)

    @beartype
    async def handle_quote_unsubscribe(
        self, connection_id: str, quote_id: UUID
    ) -> Result[None, str]:
        """Unsubscribe from quote updates."""
        room_id = f"quote:{quote_id}"

        # Remove from active sessions
        if quote_id in self._active_quote_sessions:
            self._active_quote_sessions[quote_id].discard(connection_id)
            if not self._active_quote_sessions[quote_id]:
                del self._active_quote_sessions[quote_id]

        # Release any field locks
        locked_fields = [
            field
            for field, owner in self._field_locks.items()
            if owner == connection_id and field.startswith(f"{quote_id}:")
        ]
        for field in locked_fields:
            del self._field_locks[field]
            # Notify about lock release
            unlock_msg = WebSocketMessage(
                type=MessageType.FIELD_UNLOCKED,
                data=create_websocket_message_data(
                    quote_id=quote_id,
                    field=field.split(":", 1)[1],
                ).model_dump(),
            )
            await self._manager.send_to_room(room_id, unlock_msg)

        # Unsubscribe from room
        unsubscribe_result = await self._manager.unsubscribe_from_room(
            connection_id, room_id
        )

        # Notify others of editor leaving
        if quote_id in self._active_quote_sessions:
            leave_msg = WebSocketMessage(
                type=MessageType.ROOM_EVENT,
                data=create_websocket_message_data(
                    quote_id=quote_id,
                    connection_id=connection_id,
                    payload={
                        "active_editors": len(self._active_quote_sessions[quote_id])
                    },
                ).model_dump(),
            )
            await self._manager.send_to_room(room_id, leave_msg)

        return unsubscribe_result

    @beartype
    async def broadcast_quote_update(
        self, quote_id: UUID, update_data: QuoteUpdateData
    ) -> Result[int, str]:
        """Broadcast quote update to all subscribers with deduplication."""
        # Deduplication check
        dedup_key = f"{quote_id}:{update_data.update_type}:{update_data.field}"
        now = datetime.now()

        if dedup_key in self._recent_updates:
            last_update = self._recent_updates[dedup_key]
            if (now - last_update).total_seconds() < 0.5:  # 500ms deduplication window
                return Ok(0)  # Skip duplicate update

        self._recent_updates[dedup_key] = now

        # Clean old deduplication entries
        cutoff = now - timedelta(seconds=5)
        self._recent_updates = {
            k: v for k, v in self._recent_updates.items() if v > cutoff
        }

        room_id = f"quote:{quote_id}"

        message = WebSocketMessage(
            type=MessageType.QUOTE_UPDATE,
            data=create_websocket_message_data(
                quote_id=quote_id,
                payload={"update": update_data.model_dump(exclude_none=True)},
            ).model_dump(),
        )

        return await self._manager.send_to_room(room_id, message)

    @beartype
    async def handle_collaborative_edit(
        self, connection_id: str, edit_request: CollaborativeEditRequest
    ) -> Result[None, str]:
        """Handle collaborative quote editing with field-level locking."""
        quote_id = edit_request.quote_id
        field = edit_request.field
        field_key = f"{quote_id}:{field}"

        # Check field lock
        if (
            field_key in self._field_locks
            and self._field_locks[field_key] != connection_id
        ):
            lock_owner = self._field_locks[field_key]
            error_msg = WebSocketMessage(
                type=MessageType.EDIT_REJECTED,
                data=create_websocket_message_data(
                    error=f"Field '{field}' is currently being edited by another user",
                    field=field,
                    payload={"locked_by": lock_owner},
                ).model_dump(),
            )
            await self._manager.send_personal_message(connection_id, error_msg)
            return Err(f"Field {field} is locked by connection {lock_owner}")

        # Validate edit permission
        metadata = self._manager._connection_metadata.get(connection_id)
        if not metadata or not metadata.user_id:
            return Err("User authentication required for editing")

        # Apply optimistic lock
        self._field_locks[field_key] = connection_id
        lock_msg = WebSocketMessage(
            type=MessageType.FIELD_LOCKED,
            data=create_websocket_message_data(
                quote_id=quote_id,
                field=field,
                payload={"locked_by": connection_id},
            ).model_dump(),
        )
        room_id = f"quote:{quote_id}"
        await self._manager.send_to_room(room_id, lock_msg, exclude=[connection_id])

        # Validate and apply edit
        # Note: Actual quote update would go through quote service
        # For now, just broadcast the change
        update_data = QuoteUpdateData(
            update_type="field_edit",
            field=field,
            new_value=edit_request.value,
            updated_by=str(metadata.user_id),
        )

        broadcast_result = await self.broadcast_quote_update(quote_id, update_data)

        # Release lock after short delay (allows for rapid edits)
        asyncio.create_task(self._auto_release_lock(field_key, connection_id, 2.0))

        if broadcast_result.is_ok():
            return Ok(None)
        else:
            return Err(broadcast_result.unwrap_err())

    @beartype
    async def stream_calculation_progress(
        self,
        quote_id: UUID,
        progress: float,
        stage: str,
        details: DetailsData | None = None,
    ) -> Result[int, str]:
        """Stream calculation progress to subscribers."""
        if not 0 <= progress <= 100:
            return Err(
                f"Invalid progress value: {progress}. Must be between 0 and 100."
            )

        room_id = f"quote:{quote_id}"

        progress_msg = WebSocketMessage(
            type=MessageType.CALCULATION_PROGRESS,
            data=create_websocket_message_data(
                quote_id=quote_id,
                payload={
                    "progress": progress,
                    "stage": stage,
                    "details": details or {},
                    "completed": progress >= 100,
                },
            ).model_dump(),
        )

        return await self._manager.send_to_room(room_id, progress_msg)

    @beartype
    async def notify_quote_status_change(
        self,
        quote_id: UUID,
        old_status: str,
        new_status: str,
        reason: str | None = None,
    ) -> Result[int, str]:
        """Notify subscribers of quote status changes."""
        room_id = f"quote:{quote_id}"

        status_msg = WebSocketMessage(
            type=MessageType.QUOTE_STATUS_CHANGED,
            data=create_websocket_message_data(
                quote_id=quote_id,
                old_status=old_status,
                new_status=new_status,
                payload={
                    "reason": reason,
                    "timestamp": datetime.now().isoformat(),
                },
            ).model_dump(),
        )

        return await self._manager.send_to_room(room_id, status_msg)

    @beartype
    async def handle_field_focus(
        self, connection_id: str, quote_id: UUID, field: str, focused: bool
    ) -> Result[None, str]:
        """Handle field focus events for collaborative awareness."""
        room_id = f"quote:{quote_id}"

        # Get user info
        metadata = self._manager._connection_metadata.get(connection_id)
        user_id = (
            str(metadata.user_id) if metadata and metadata.user_id else "anonymous"
        )

        focus_msg = WebSocketMessage(
            type=MessageType.FIELD_FOCUS,
            data=create_websocket_message_data(
                quote_id=quote_id,
                field=field,
                user_id=metadata.user_id if metadata else None,
                connection_id=connection_id,
                payload={"focused": focused, "user_id": user_id},
            ).model_dump(),
        )

        # Broadcast to others
        await self._manager.send_to_room(room_id, focus_msg, exclude=[connection_id])
        return Ok(None)

    @beartype
    async def handle_cursor_position(
        self, connection_id: str, quote_id: UUID, field: str, position: int
    ) -> Result[None, str]:
        """Handle cursor position updates for real-time collaboration."""
        # Validate position
        if position < 0:
            return Err("Cursor position cannot be negative")

        room_id = f"quote:{quote_id}"

        # Get user info
        metadata = self._manager._connection_metadata.get(connection_id)
        user_id = (
            str(metadata.user_id) if metadata and metadata.user_id else "anonymous"
        )

        cursor_msg = WebSocketMessage(
            type=MessageType.CURSOR_POSITION,
            data=create_websocket_message_data(
                quote_id=quote_id,
                field=field,
                user_id=metadata.user_id if metadata else None,
                connection_id=connection_id,
                payload={"position": position, "user_id": user_id},
            ).model_dump(),
        )

        # Broadcast to others (high frequency, exclude sender)
        await self._manager.send_to_room(room_id, cursor_msg, exclude=[connection_id])
        return Ok(None)

    async def _auto_release_lock(
        self, field_key: str, connection_id: str, delay: float
    ) -> None:
        """Automatically release field lock after delay."""
        await asyncio.sleep(delay)
        if (
            field_key in self._field_locks
            and self._field_locks[field_key] == connection_id
        ):
            del self._field_locks[field_key]

            # Parse field key
            quote_id, field = field_key.split(":", 1)
            room_id = f"quote:{quote_id}"

            unlock_msg = WebSocketMessage(
                type=MessageType.FIELD_UNLOCKED,
                data=create_websocket_message_data(
                    quote_id=UUID(quote_id),
                    field=field,
                ).model_dump(),
            )
            await self._manager.send_to_room(room_id, unlock_msg)

    @beartype
    async def cleanup_connection(self, connection_id: str) -> None:
        """Clean up resources when a connection is lost."""
        # Release all field locks held by this connection
        locked_fields = [
            field
            for field, owner in self._field_locks.items()
            if owner == connection_id
        ]

        for field_key in locked_fields:
            del self._field_locks[field_key]
            quote_id, field = field_key.split(":", 1)

            unlock_msg = WebSocketMessage(
                type=MessageType.FIELD_UNLOCKED,
                data=create_websocket_message_data(
                    quote_id=UUID(quote_id),
                    field=field,
                    payload={"reason": "connection_lost"},
                ).model_dump(),
            )
            room_id = f"quote:{quote_id}"
            await self._manager.send_to_room(room_id, unlock_msg)

        # Remove from all active sessions
        for quote_id_uuid in list(self._active_quote_sessions.keys()):
            if connection_id in self._active_quote_sessions[quote_id_uuid]:
                await self.handle_quote_unsubscribe(connection_id, quote_id_uuid)
