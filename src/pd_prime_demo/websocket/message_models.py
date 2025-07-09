"""Enhanced message models for WebSocket communication."""

from datetime import datetime
from typing import Any, Union
from uuid import UUID

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field, validator


class MessageValidationMixin:
    """Mixin for common message validation patterns."""

    @validator("*", pre=True)
    @classmethod
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
    data: dict[str, Any] = Field(default_factory=dict)

    @validator("data")
    @classmethod
    def validate_data_by_action(
        cls, v: dict[str, Any], values: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate data based on action type."""
        action = values.get("action")

        if action == "edit":
            required_fields = ["field", "value"]
            for field in required_fields:
                if field not in v:
                    raise ValueError(f"Field '{field}' is required for edit action")

        elif action == "status_change":
            required_fields = ["old_status", "new_status"]
            for field in required_fields:
                if field not in v:
                    raise ValueError(
                        f"Field '{field}' is required for status_change action"
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
    data: dict[str, Any] = Field(default_factory=dict)
    permissions: list[str] | None = Field(
        default=None, description="Required permissions"
    )

    @validator("room_id")
    @classmethod
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
    config: dict[str, Any] = Field(default_factory=dict)

    @validator("config")
    @classmethod
    def validate_config_by_dashboard_type(
        cls, v: dict[str, Any], values: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate config based on dashboard type."""
        dashboard_type = values.get("dashboard_type")

        if dashboard_type == "conversion":
            # Validate conversion funnel config
            if "funnel_steps" in v and not isinstance(v["funnel_steps"], list):
                raise ValueError("funnel_steps must be a list")

        elif dashboard_type == "performance":
            # Validate performance metrics config
            if "metrics" in v and not isinstance(v["metrics"], list):
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
    config: dict[str, Any] = Field(default_factory=dict)
    permissions: list[str] = Field(default_factory=list)

    @validator("permissions")
    @classmethod
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
    def validate_chunk_consistency(cls, v: int, values: dict[str, Any]) -> int:
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
def validate_message_data(message_type: str, data: dict[str, Any]) -> MessageType:
    """Validate message data based on type."""
    if message_type not in MESSAGE_TYPE_REGISTRY:
        raise ValueError(f"Unknown message type: {message_type}")

    model_class = MESSAGE_TYPE_REGISTRY[message_type]
    validated_model = model_class(**data)
    return validated_model


@beartype
def get_supported_message_types() -> list[str]:
    """Get list of supported message types."""
    return list(MESSAGE_TYPE_REGISTRY.keys())
