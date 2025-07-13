# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Enhanced message models for WebSocket communication."""

from datetime import datetime
from enum import Enum
from typing import Any, Union
from uuid import UUID

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field, ValidationError, validator

from policy_core.core.result_types import Err, Ok, Result
from policy_core.models.base import BaseModelConfig

# Auto-generated models


@beartype
class PayloadData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class VData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class Data(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class ValuesData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class ByStateCounts(BaseModelConfig):
    """Structured model for state-based count data."""

    # Auto-generated - customize based on usage
    total: int = Field(default=0, ge=0, description="Total count")
    ca: int = Field(default=0, ge=0, description="California count")
    tx: int = Field(default=0, ge=0, description="Texas count")
    ny: int = Field(default=0, ge=0, description="New York count")
    fl: int = Field(default=0, ge=0, description="Florida count")
    other: int = Field(default=0, ge=0, description="Other states count")


@beartype
class ConnectionLimitsCounts(BaseModelConfig):
    """Structured model replacing dict[str, int] usage.

    Provides backward-compat keys ``max_connections`` and ``current_connections`` used by
    ConnectionManager welcome messages.
    """

    max_connections: int | None = Field(
        default=None,
        ge=0,
        description="Maximum concurrent connections allowed by server",
    )
    current_connections: int | None = Field(
        default=None,
        ge=0,
        description="Current active WebSocket connections on server",
    )
    total: int | None = Field(
        default=None,
        ge=0,
        description="Total connections (legacy metric, may match current_connections)",
    )


@beartype
class DetailsData(BaseModelConfig):
    """Structured model for detailed data usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


# WebSocket-specific models to replace dict usage


class MessagePriorityLevel(str, Enum):
    """Message priority levels for WebSocket message handling."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class MessagePriorityHandling(BaseModel):
    """Message priority handling configuration."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    level: MessagePriorityLevel = Field(..., description="Priority level")
    queue_size: int = Field(..., ge=1, le=10000, description="Maximum queue size")
    processing_rate: float = Field(
        ..., ge=0.1, le=1000.0, description="Messages per second"
    )
    drop_count: int = Field(default=0, ge=0, description="Number of dropped messages")


class WebSocketMessageData(BaseModel):
    """Structured message data to replace dict[str, Any] usage."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Core message fields
    connection_id: str | None = Field(default=None, description="Target connection ID")
    user_id: UUID | None = Field(default=None, description="User identifier")
    room_id: str | None = Field(default=None, description="Room identifier")

    # Message content
    action: str | None = Field(default=None, description="Action type")
    payload: PayloadData = Field(
        default_factory=PayloadData, description="Message payload"
    )

    # System fields
    server_time: datetime | None = Field(default=None, description="Server timestamp")
    client_time: datetime | None = Field(default=None, description="Client timestamp")

    # Status and metadata
    status: str | None = Field(default=None, description="Message status")
    error: str | None = Field(default=None, description="Error message")
    event: str | None = Field(default=None, description="Event type")

    # Collaboration fields
    quote_id: UUID | None = Field(default=None, description="Quote identifier")
    field: str | None = Field(default=None, description="Field name")
    value: Any | None = Field(default=None, description="Field value")
    old_status: str | None = Field(default=None, description="Previous status")
    new_status: str | None = Field(default=None, description="New status")

    # Analytics fields
    dashboard_type: str | None = Field(default=None, description="Dashboard type")
    metrics: list[str] | None = Field(default=None, description="Metrics list")
    funnel_steps: list[str] | None = Field(default=None, description="Funnel steps")

    # Notification fields
    notification_id: UUID | None = Field(default=None, description="Notification ID")

    # Admin fields
    alert_type: str | None = Field(default=None, description="Alert type")
    severity: str | None = Field(default=None, description="Alert severity")

    # Connection management
    member_count: int | None = Field(
        default=None, ge=0, description="Room member count"
    )
    connection_limits: ConnectionLimitsCounts | None = Field(
        default=None, description="Connection limits"
    )
    capabilities: dict[str, bool] | None = Field(
        default=None, description="Connection capabilities"
    )

    # Binary transfer
    file_id: UUID | None = Field(default=None, description="File identifier")
    filename: str | None = Field(default=None, description="File name")
    content_type: str | None = Field(default=None, description="Content type")
    size_bytes: int | None = Field(default=None, ge=0, description="Size in bytes")

    @validator("payload")
    @classmethod
    @beartype
    def validate_payload_size(cls, v: PayloadData) -> PayloadData:
        """Validate payload size to prevent oversized messages."""
        import json

        data_size = len(json.dumps(v, default=str))
        if data_size > 512 * 1024:  # 512KB limit for payload
            raise ValueError(f"Payload too large: {data_size} bytes (max 512KB)")
        return v


class ConnectionCapabilities(BaseModel):
    """Connection capabilities to replace client_capabilities dict."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Core WebSocket capabilities
    rooms: bool = Field(default=True, description="Room subscription support")
    message_sequencing: bool = Field(
        default=True, description="Message sequencing support"
    )
    binary_messages: bool = Field(default=True, description="Binary message support")
    message_priorities: bool = Field(
        default=True, description="Message priority support"
    )
    backpressure_detection: bool = Field(
        default=True, description="Backpressure detection"
    )

    # Advanced features
    collaborative_editing: bool = Field(
        default=False, description="Collaborative editing support"
    )
    real_time_analytics: bool = Field(default=False, description="Real-time analytics")
    file_transfer: bool = Field(default=False, description="File transfer support")
    compression: bool = Field(default=False, description="Message compression")

    # Protocol features
    heartbeat_interval: int = Field(
        default=30, ge=5, le=300, description="Heartbeat interval (seconds)"
    )
    max_message_size: int = Field(
        default=1024 * 1024, ge=1024, description="Max message size (bytes)"
    )
    protocol_version: str = Field(default="1.0", description="Protocol version")

    @beartype
    def supports_feature(self, feature: str) -> bool:
        """Check if a specific feature is supported."""
        return getattr(self, feature, False)


class BackpressureMetrics(BaseModel):
    """Backpressure metrics to replace nested dict metrics."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Queue depth metrics by priority
    critical_queue_depth: int = Field(
        default=0, ge=0, description="Critical priority queue depth"
    )
    high_queue_depth: int = Field(
        default=0, ge=0, description="High priority queue depth"
    )
    normal_queue_depth: int = Field(
        default=0, ge=0, description="Normal priority queue depth"
    )
    low_queue_depth: int = Field(
        default=0, ge=0, description="Low priority queue depth"
    )

    # Processing rates by priority (messages per second)
    critical_processing_rate: float = Field(
        default=0.0, ge=0.0, description="Critical priority processing rate"
    )
    high_processing_rate: float = Field(
        default=0.0, ge=0.0, description="High priority processing rate"
    )
    normal_processing_rate: float = Field(
        default=0.0, ge=0.0, description="Normal priority processing rate"
    )
    low_processing_rate: float = Field(
        default=0.0, ge=0.0, description="Low priority processing rate"
    )

    # Drop counts by priority
    critical_drop_count: int = Field(
        default=0, ge=0, description="Critical priority drop count"
    )
    high_drop_count: int = Field(
        default=0, ge=0, description="High priority drop count"
    )
    normal_drop_count: int = Field(
        default=0, ge=0, description="Normal priority drop count"
    )
    low_drop_count: int = Field(default=0, ge=0, description="Low priority drop count")

    # Overall metrics
    total_queue_depth: int = Field(default=0, ge=0, description="Total queue depth")
    overall_processing_rate: float = Field(
        default=0.0, ge=0.0, description="Overall processing rate"
    )
    total_drop_count: int = Field(default=0, ge=0, description="Total drop count")
    backpressure_level: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Backpressure level (0-1)"
    )

    @beartype
    def get_queue_depth_by_priority(self, priority: MessagePriorityLevel) -> int:
        """Get queue depth for a specific priority level."""
        mapping = {
            MessagePriorityLevel.CRITICAL: self.critical_queue_depth,
            MessagePriorityLevel.HIGH: self.high_queue_depth,
            MessagePriorityLevel.NORMAL: self.normal_queue_depth,
            MessagePriorityLevel.LOW: self.low_queue_depth,
        }
        return mapping.get(priority, 0)

    @beartype
    def get_processing_rate_by_priority(self, priority: MessagePriorityLevel) -> float:
        """Get processing rate for a specific priority level."""
        mapping = {
            MessagePriorityLevel.CRITICAL: self.critical_processing_rate,
            MessagePriorityLevel.HIGH: self.high_processing_rate,
            MessagePriorityLevel.NORMAL: self.normal_processing_rate,
            MessagePriorityLevel.LOW: self.low_processing_rate,
        }
        return mapping.get(priority, 0.0)

    @beartype
    def is_under_pressure(self) -> bool:
        """Check if system is under backpressure."""
        return self.backpressure_level > 0.7


class ConnectionState(str, Enum):
    """Connection state enumeration."""

    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    IDLE = "idle"
    ACTIVE = "active"
    DEGRADED = "degraded"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class WebSocketConnectionMetadata(BaseModel):
    """WebSocket connection metadata to replace connection metadata dicts."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Connection identity
    connection_id: str = Field(
        ..., min_length=1, max_length=100, description="Connection identifier"
    )
    user_id: UUID | None = Field(default=None, description="User identifier")

    # Connection details
    ip_address: str | None = Field(default=None, description="Client IP address")
    user_agent: str | None = Field(default=None, description="Client user agent")

    # Timestamps
    connected_at: datetime = Field(
        default_factory=datetime.now, description="Connection timestamp"
    )
    last_activity: datetime = Field(
        default_factory=datetime.now, description="Last activity timestamp"
    )

    # Connection state
    state: ConnectionState = Field(
        default=ConnectionState.CONNECTING, description="Connection state"
    )
    protocol_version: str = Field(default="1.0", description="Protocol version")

    # Capabilities and configuration
    capabilities: ConnectionCapabilities = Field(
        default_factory=ConnectionCapabilities, description="Client capabilities"
    )

    # Performance metrics
    rate_limit_remaining: int = Field(
        default=1000, ge=0, description="Remaining rate limit"
    )
    backpressure_level: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Backpressure level"
    )

    # Room subscriptions
    subscribed_rooms: set[str] = Field(
        default_factory=set, description="Subscribed rooms"
    )

    # Statistics
    messages_sent: int = Field(default=0, ge=0, description="Messages sent count")
    messages_received: int = Field(
        default=0, ge=0, description="Messages received count"
    )
    bytes_sent: int = Field(default=0, ge=0, description="Bytes sent")
    bytes_received: int = Field(default=0, ge=0, description="Bytes received")

    @beartype
    def is_healthy(self) -> bool:
        """Check if connection is in healthy state."""
        return self.state in {
            ConnectionState.CONNECTED,
            ConnectionState.AUTHENTICATED,
            ConnectionState.ACTIVE,
        }

    @beartype
    def needs_attention(self) -> bool:
        """Check if connection needs attention."""
        return self.state in {
            ConnectionState.DEGRADED,
            ConnectionState.IDLE,
            ConnectionState.ERROR,
        }

    @beartype
    def is_rate_limited(self) -> bool:
        """Check if connection is rate limited."""
        return self.rate_limit_remaining <= 0

    @beartype
    def has_backpressure(self) -> bool:
        """Check if connection has backpressure."""
        return self.backpressure_level > 0.7

    @beartype
    def is_subscribed_to_room(self, room_id: str) -> bool:
        """Check if connection is subscribed to a room."""
        return room_id in self.subscribed_rooms


class MessageValidationMixin:
    """Mixin for common message validation patterns."""

    @validator("*", pre=True)
    @classmethod
    @beartype
    def strip_whitespace(cls, v: Any) -> Any:
        """Strip whitespace from string values."""
        if isinstance(v, str):
            return v.strip()
        return v


class QuoteMessage(BaseModel, MessageValidationMixin):
    """Message model for quote-related operations."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    quote_id: UUID = Field(..., description="Quote identifier")
    action: str = Field(
        ..., pattern="^(subscribe|unsubscribe|update|edit|status_change)$"
    )
    data: WebSocketMessageData = Field(
        default_factory=WebSocketMessageData, description="Structured message data"
    )

    @validator("data")
    @classmethod
    def validate_data_by_action(
        cls, v: WebSocketMessageData, values: ValuesData
    ) -> WebSocketMessageData:
        """Validate data based on action type."""
        action = values.get("action")

        if action == "edit":
            if not v.field or v.value is None:
                raise ValueError(
                    "Field 'field' and 'value' are required for edit action"
                )

        elif action == "status_change":
            if not v.old_status or not v.new_status:
                raise ValueError(
                    "Fields 'old_status' and 'new_status' are required for status_change action"
                )

        return v


class RoomMessage(BaseModel, MessageValidationMixin):
    """Message model for room management operations."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    room_id: str = Field(..., min_length=1, max_length=200, pattern="^[a-zA-Z0-9:_-]+$")
    action: str = Field(..., pattern="^(join|leave|message|event)$")
    data: WebSocketMessageData = Field(
        default_factory=WebSocketMessageData, description="Structured message data"
    )
    permissions: list[str] | None = Field(
        default=None, description="Required permissions"
    )

    @validator("room_id")
    @classmethod
    @beartype
    def validate_room_id_format(cls, v: str) -> str:
        """Validate room ID format and extract type."""
        parts = v.split(":")
        if len(parts) < 2:
            raise ValueError("Room ID must be in format 'type:identifier'")

        room_type = parts[0]
        allowed_types = ["quote", "policy", "admin", "analytics", "notification"]
        if room_type not in allowed_types:
            raise ValueError(
                f"Room type '{room_type}' not allowed. Must be one of {allowed_types}"
            )

        return v


class AnalyticsMessage(BaseModel, MessageValidationMixin):
    """Message model for analytics operations."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    dashboard_type: str = Field(
        ..., pattern="^(conversion|performance|user_activity|system_health)$"
    )
    action: str = Field(..., pattern="^(start|stop|update|filter)$")
    config: WebSocketMessageData = Field(
        default_factory=WebSocketMessageData, description="Dashboard configuration"
    )

    @validator("config")
    @classmethod
    def validate_config_by_dashboard_type(
        cls, v: WebSocketMessageData, values: ValuesData
    ) -> WebSocketMessageData:
        """Validate config based on dashboard type."""
        dashboard_type = values.get("dashboard_type")

        if dashboard_type == "conversion":
            # Validate conversion funnel config
            if v.funnel_steps is not None and not isinstance(v.funnel_steps, list):
                raise ValueError("funnel_steps must be a list")

        elif dashboard_type == "performance":
            # Validate performance metrics config
            if v.metrics is not None and not isinstance(v.metrics, list):
                raise ValueError("metrics must be a list")

        return v


class NotificationMessage(BaseModel, MessageValidationMixin):
    """Message model for notification operations."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    notification_id: UUID = Field(..., description="Notification identifier")
    action: str = Field(..., pattern="^(acknowledge|dismiss|mark_read)$")
    timestamp: datetime = Field(default_factory=datetime.now)


class AdminMessage(BaseModel, MessageValidationMixin):
    """Message model for admin operations."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    action: str = Field(
        ...,
        pattern="^(start_monitoring|stop_monitoring|user_activity|performance|system_health)$",
    )
    config: WebSocketMessageData = Field(
        default_factory=WebSocketMessageData, description="Admin configuration"
    )
    permissions: list[str] = Field(default_factory=list)

    @validator("permissions")
    @classmethod
    @beartype
    def validate_admin_permissions(cls, v: list[str]) -> list[str]:
        """Validate admin permissions."""
        allowed_permissions = [
            "admin.system.monitor",
            "admin.user.activity",
            "admin.performance.view",
            "admin.connections.manage",
        ]

        for permission in v:
            if permission not in allowed_permissions:
                raise ValueError(f"Permission '{permission}' not allowed")

        return v


class BinaryMessage(BaseModel, MessageValidationMixin):
    """Message model for binary data transfers."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    file_id: UUID = Field(..., description="File identifier")
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(
        ...,
        pattern="^[a-zA-Z0-9][a-zA-Z0-9!#$&\\-\\^_]*\\/[a-zA-Z0-9][a-zA-Z0-9!#$&\\-\\^_]*$",
    )
    size_bytes: int = Field(..., ge=1, le=10 * 1024 * 1024)  # Max 10MB
    chunk_index: int = Field(default=0, ge=0)
    total_chunks: int = Field(default=1, ge=1)

    @validator("total_chunks")
    @classmethod
    @beartype
    def validate_chunk_consistency(cls, v: int, values: ValuesData) -> int:
        """Validate chunk consistency."""
        chunk_index = values.get("chunk_index", 0)
        if chunk_index >= v:
            raise ValueError("chunk_index must be less than total_chunks")
        return v


# Union type for all message types
MessageType = Union[
    QuoteMessage,
    RoomMessage,
    AnalyticsMessage,
    NotificationMessage,
    AdminMessage,
    BinaryMessage,
]

# Message type registry for validation
MESSAGE_TYPE_REGISTRY = {
    "quote_subscribe": QuoteMessage,
    "quote_unsubscribe": QuoteMessage,
    "quote_edit": QuoteMessage,
    "quote_status_change": QuoteMessage,
    "subscribe": RoomMessage,
    "unsubscribe": RoomMessage,
    "room_message": RoomMessage,
    "start_analytics": AnalyticsMessage,
    "stop_analytics": AnalyticsMessage,
    "notification_acknowledge": NotificationMessage,
    "start_admin_monitoring": AdminMessage,
    "start_user_activity": AdminMessage,
    "start_performance_monitoring": AdminMessage,
    "binary_upload": BinaryMessage,
    "binary_download": BinaryMessage,
}


@beartype
def validate_message_data(message_type: str, data: Data) -> MessageType:
    """Validate message data based on type."""
    if message_type not in MESSAGE_TYPE_REGISTRY:
        raise ValueError(f"Unknown message type: {message_type}")

    model_class = MESSAGE_TYPE_REGISTRY[message_type]
    validated_model = model_class(**data)
    # Type casting is safe here because we know the model_class creates
    # instances of the correct type from the MessageType union
    return validated_model  # type: ignore[no-any-return]


@beartype
def get_supported_message_types() -> list[str]:
    """Get list of supported message types."""
    return list(MESSAGE_TYPE_REGISTRY.keys())


# ---------------------------------------------------------------------------
# LEGACY_INPUT_BOUNDARY
# TODO: delete when all callers provide ConnectionLimitsCounts / ConnectionCapabilities
# Helpers to convert loose dict inputs into strict models for backward compatibility.
# ---------------------------------------------------------------------------


@beartype
def _to_connection_limits_counts(
    data: ConnectionLimitsCounts | dict[str, Any] | None,
) -> Result[ConnectionLimitsCounts | None, str]:
    """Convert dict to ConnectionLimitsCounts where necessary."""

    if data is None or isinstance(data, ConnectionLimitsCounts):
        return Ok(data)

    if isinstance(data, dict):
        try:
            return Ok(ConnectionLimitsCounts.model_validate(data))
        except ValidationError as exc:  # type: ignore[name-defined]
            return Err(f"Invalid connection_limits: {exc}")

    return Err(
        "Unsupported connection_limits type. Expected ConnectionLimitsCounts, dict, or None."
    )


@beartype
def _to_connection_capabilities(
    data: ConnectionCapabilities | dict[str, Any] | None,
) -> Result[ConnectionCapabilities | None, str]:
    """Convert dict to ConnectionCapabilities while filtering unknown fields."""

    if data is None or isinstance(data, ConnectionCapabilities):
        return Ok(data)

    if isinstance(data, dict):
        try:
            allowed_keys = ConnectionCapabilities.model_fields.keys()
            filtered = {k: v for k, v in data.items() if k in allowed_keys}
            return Ok(ConnectionCapabilities.model_validate(filtered))
        except ValidationError as exc:  # type: ignore[name-defined]
            return Err(f"Invalid connection_capabilities: {exc}")

    return Err(
        "Unsupported capabilities type. Expected ConnectionCapabilities, dict, or None."
    )


@beartype
def create_websocket_message_data(
    *,
    connection_id: str | None = None,
    user_id: UUID | None = None,
    room_id: str | None = None,
    action: str | None = None,
    payload: PayloadData | dict[str, Any] | None = None,
    connection_limits: ConnectionLimitsCounts | dict[str, int] | None = None,
    capabilities: ConnectionCapabilities | dict[str, bool] | None = None,
    **kwargs: Any,
) -> WebSocketMessageData:
    """Helper function to create WebSocketMessageData instances accepting legacy dicts."""

    # Convert payload
    payload_model = (
        payload
        if isinstance(payload, PayloadData)
        else PayloadData.model_validate(payload or {})
    )

    # Convert connection_limits
    limits_result = _to_connection_limits_counts(connection_limits)
    if limits_result.is_err():
        raise ValueError(limits_result.unwrap_err())
    limits_model = limits_result.unwrap()

    # Capabilities remain a simple dict in WebSocketMessageData; allow both dict and model
    if isinstance(capabilities, ConnectionCapabilities):
        capabilities_dict = capabilities.model_dump()
    else:
        capabilities_dict = capabilities

    return WebSocketMessageData(
        connection_id=connection_id,
        user_id=user_id,
        room_id=room_id,
        action=action,
        payload=payload_model,
        connection_limits=limits_model,
        capabilities=capabilities_dict,
        **kwargs,
    )


@beartype
def create_connection_capabilities(
    *,
    collaborative_editing: bool = False,
    real_time_analytics: bool = False,
    file_transfer: bool = False,
    compression: bool = False,
    capabilities: ConnectionCapabilities | dict[str, Any] | None = None,
    **kwargs: Any,
) -> ConnectionCapabilities:
    """Helper function to create ConnectionCapabilities instances or validate provided dict."""

    if capabilities is not None:
        result = _to_connection_capabilities(capabilities)
        if result.is_err():
            raise ValueError(result.unwrap_err())
        return result.unwrap() or ConnectionCapabilities()

    return ConnectionCapabilities(
        collaborative_editing=collaborative_editing,
        real_time_analytics=real_time_analytics,
        file_transfer=file_transfer,
        compression=compression,
        **kwargs,
    )


@beartype
def create_backpressure_metrics(
    queue_depths: dict[MessagePriorityLevel, int] | None = None,
    processing_rates: dict[MessagePriorityLevel, float] | None = None,
    drop_counts: dict[MessagePriorityLevel, int] | None = None,
    backpressure_level: float = 0.0,
) -> BackpressureMetrics:
    """Helper function to create BackpressureMetrics instances."""
    queue_depths = queue_depths or {}
    processing_rates = processing_rates or {}
    drop_counts = drop_counts or {}

    return BackpressureMetrics(
        critical_queue_depth=queue_depths.get(MessagePriorityLevel.CRITICAL, 0),
        high_queue_depth=queue_depths.get(MessagePriorityLevel.HIGH, 0),
        normal_queue_depth=queue_depths.get(MessagePriorityLevel.NORMAL, 0),
        low_queue_depth=queue_depths.get(MessagePriorityLevel.LOW, 0),
        critical_processing_rate=processing_rates.get(
            MessagePriorityLevel.CRITICAL, 0.0
        ),
        high_processing_rate=processing_rates.get(MessagePriorityLevel.HIGH, 0.0),
        normal_processing_rate=processing_rates.get(MessagePriorityLevel.NORMAL, 0.0),
        low_processing_rate=processing_rates.get(MessagePriorityLevel.LOW, 0.0),
        critical_drop_count=drop_counts.get(MessagePriorityLevel.CRITICAL, 0),
        high_drop_count=drop_counts.get(MessagePriorityLevel.HIGH, 0),
        normal_drop_count=drop_counts.get(MessagePriorityLevel.NORMAL, 0),
        low_drop_count=drop_counts.get(MessagePriorityLevel.LOW, 0),
        backpressure_level=backpressure_level,
    )


@beartype
def create_connection_metadata(
    connection_id: str,
    user_id: UUID | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    capabilities: ConnectionCapabilities | dict[str, Any] | None = None,
    **kwargs: Any,
) -> WebSocketConnectionMetadata:
    """Helper to create WebSocketConnectionMetadata accepting dict capabilities."""

    result = _to_connection_capabilities(capabilities)
    if result.is_err():
        raise ValueError(result.unwrap_err())

    return WebSocketConnectionMetadata(
        connection_id=connection_id,
        user_id=user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        capabilities=result.unwrap() or ConnectionCapabilities(),
        **kwargs,
    )
