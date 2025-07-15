# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Real-time notification handler for push notifications and alerts."""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

from policy_core.core.database import Database
from policy_core.core.result_types import Err, Ok, Result

from ..manager import ConnectionManager, MessageType, WebSocketMessage
from ..message_models import Data, create_websocket_message_data


class NotificationConfig(BaseModel):
    """Configuration for notification delivery."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    notification_type: str = Field(..., min_length=1, max_length=50)
    priority: str = Field(..., pattern="^(low|normal|high|urgent)$")
    channel: str = Field(
        default="websocket", pattern="^(websocket|email|sms|push|in_app)$"
    )
    expires_at: datetime | None = Field(default=None)
    action_url: str | None = Field(default=None)
    requires_acknowledgment: bool = Field(default=False)


class NotificationData(BaseModel):
    """Notification payload data."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    title: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1)
    data: Data = Field(default_factory=dict)
    icon: str | None = Field(default=None)
    sound: str | None = Field(default=None)


class SystemAlert(BaseModel):
    """System-wide alert definition."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    alert_type: str = Field(..., min_length=1, max_length=50)
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    affected_systems: list[str] = Field(default_factory=list)
    estimated_resolution: datetime | None = Field(default=None)
    requires_action: bool = Field(default=False)


class NotificationHandler:
    """Handle real-time notifications and system alerts with no silent fallbacks."""

    def __init__(self, manager: ConnectionManager, db: Database) -> None:
        """Initialize notification handler."""
        self._manager = manager
        self._db = db

        # Notification queue management
        self._pending_notifications: dict[UUID, NotificationConfig] = {}
        self._notification_delivery_tasks: dict[str, asyncio.Task[None]] = {}

        # System alert tracking
        self._active_alerts: dict[str, SystemAlert] = {}

        # Delivery statistics
        self._delivery_stats = {
            "total_sent": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "acknowledgments_received": 0,
        }

    @beartype
    async def send_personal_notification(
        self,
        user_id: UUID,
        notification: NotificationData,
        config: NotificationConfig,
    ) -> Result[int, str]:
        """Send notification to a specific user with delivery tracking."""
        # Validate user exists and has active connections
        if user_id not in self._manager._user_connections:
            # Store in database for later delivery
            store_result = await self._store_notification_for_later(
                user_id, notification, config
            )
            if store_result.is_err():
                return Err(store_result.unwrap_err())
            return Ok(1)  # Stored for later delivery - count of 1

        # Create notification ID for tracking
        notification_id = UUID()
        self._pending_notifications[notification_id] = config

        # Build notification message
        notification_msg = WebSocketMessage(
            type=MessageType.NOTIFICATION_RECEIVED,
            data=create_websocket_message_data(
                notification_id=notification_id,
                payload={
                    "notification_type": config.notification_type,
                    "priority": config.priority,
                    "title": notification.title,
                    "message": notification.message,
                    "data": notification.data,
                    "icon": notification.icon,
                    "sound": notification.sound,
                    "action_url": config.action_url,
                    "requires_acknowledgment": config.requires_acknowledgment,
                    "expires_at": (
                        config.expires_at.isoformat() if config.expires_at else None
                    ),
                    "delivered_at": datetime.now().isoformat(),
                },
            ).model_dump(),
        )

        # Send to user
        send_result = await self._manager.send_to_user(user_id, notification_msg)

        if send_result.is_ok():
            self._delivery_stats["total_sent"] += 1
            if send_result.unwrap() > 0:
                self._delivery_stats["successful_deliveries"] += 1

                # Store successful delivery in database
                await self._record_notification_delivery(
                    notification_id, user_id, notification, config, "delivered"
                )

                # Set up expiration if needed
                if config.expires_at:
                    asyncio.create_task(
                        self._handle_notification_expiration(
                            notification_id, config.expires_at
                        )
                    )
            else:
                self._delivery_stats["failed_deliveries"] += 1
                await self._record_notification_delivery(
                    notification_id, user_id, notification, config, "failed"
                )
        else:
            self._delivery_stats["failed_deliveries"] += 1
            await self._record_notification_delivery(
                notification_id, user_id, notification, config, "failed"
            )

        return Ok(1)

    @beartype
    async def broadcast_system_alert(
        self,
        alert: SystemAlert,
        notification: NotificationData,
        target_roles: list[str] | None = None,
    ) -> Result[int, str]:
        """Broadcast system alert to all relevant users."""
        alert_id = (
            f"alert_{alert.alert_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        # Store alert
        self._active_alerts[alert_id] = alert

        # Build alert message
        alert_msg = WebSocketMessage(
            type=MessageType.SYSTEM_ALERT,
            data=create_websocket_message_data(
                alert_type=alert.alert_type,
                severity=alert.severity,
                payload={
                    "alert_id": alert_id,
                    "title": notification.title,
                    "message": notification.message,
                    "affected_systems": alert.affected_systems,
                    "requires_action": alert.requires_action,
                    "estimated_resolution": (
                        alert.estimated_resolution.isoformat()
                        if alert.estimated_resolution
                        else None
                    ),
                    "data": notification.data,
                    "icon": notification.icon or self._get_alert_icon(alert.severity),
                    "sound": notification.sound
                    or self._get_alert_sound(alert.severity),
                    "timestamp": datetime.now().isoformat(),
                },
            ).model_dump(),
        )

        # Determine target users
        if target_roles:
            # Send to users with specific roles
            target_users = await self._get_users_by_roles(target_roles)
            successful_sends = 0

            for user_id in target_users:
                send_result = await self._manager.send_to_user(user_id, alert_msg)
                if send_result.is_ok() and send_result.unwrap() > 0:
                    successful_sends += send_result.unwrap()
        else:
            # Broadcast to all connected users
            send_result = await self._manager.broadcast(alert_msg)
            successful_sends = send_result.unwrap() if send_result.is_ok() else 0

        # Record alert in database
        await self._record_system_alert(alert, notification, successful_sends)

        # Schedule alert cleanup if resolution time is known
        if alert.estimated_resolution:
            asyncio.create_task(
                self._cleanup_resolved_alert(alert_id, alert.estimated_resolution)
            )

        return Ok(successful_sends)

    @beartype
    async def send_quote_expiration_alert(
        self, quote_id: UUID, customer_user_id: UUID, expiration_time: datetime
    ) -> Result[int, str]:
        """Send quote expiration notification."""
        # Calculate time until expiration
        time_until_expiry = expiration_time - datetime.now()
        hours_until_expiry = int(time_until_expiry.total_seconds() / 3600)

        if hours_until_expiry <= 0:
            return Err("Quote has already expired")

        # Determine urgency
        if hours_until_expiry <= 1:
            priority = "urgent"
            title = "Quote Expires in 1 Hour"
        elif hours_until_expiry <= 24:
            priority = "high"
            title = f"Quote Expires in {hours_until_expiry} Hours"
        else:
            priority = "normal"
            title = f"Quote Expires in {hours_until_expiry // 24} Days"

        notification = NotificationData(
            title=title,
            message=f"Your insurance quote (ID: {str(quote_id)[:8]}) is expiring soon. Complete your purchase to lock in your rate.",
            data={
                "quote_id": str(quote_id),
                "expiration_time": expiration_time.isoformat(),
                "hours_remaining": hours_until_expiry,
            },
            icon="quote-expiring",
            sound="gentle" if priority == "normal" else "urgent",
        )

        config = NotificationConfig(
            notification_type="quote_expiring",
            priority=priority,
            expires_at=expiration_time,
            action_url=f"/quotes/{quote_id}",
            requires_acknowledgment=priority in ["high", "urgent"],
        )

        return await self.send_personal_notification(
            customer_user_id, notification, config
        )

    @beartype
    async def send_policy_renewal_reminder(
        self, policy_id: UUID, customer_user_id: UUID, renewal_date: datetime
    ) -> Result[int, str]:
        """Send policy renewal reminder."""
        days_until_renewal = (renewal_date - datetime.now()).days

        notification = NotificationData(
            title="Policy Renewal Due",
            message=f"Your insurance policy is up for renewal in {days_until_renewal} days. Review your coverage and renew to avoid a lapse.",
            data={
                "policy_id": str(policy_id),
                "renewal_date": renewal_date.isoformat(),
                "days_remaining": days_until_renewal,
            },
            icon="policy-renewal",
        )

        config = NotificationConfig(
            notification_type="policy_renewal",
            priority="high" if days_until_renewal <= 7 else "normal",
            action_url=f"/policies/{policy_id}/renew",
            requires_acknowledgment=days_until_renewal <= 3,
        )

        return await self.send_personal_notification(
            customer_user_id, notification, config
        )

    @beartype
    async def handle_notification_acknowledgment(
        self, connection_id: str, notification_id: UUID
    ) -> Result[None, str]:
        """Handle user acknowledgment of notification."""
        if notification_id not in self._pending_notifications:
            return Err(
                f"Notification {notification_id} not found or already acknowledged"
            )

        # Remove from pending
        self._pending_notifications.pop(notification_id)

        # Update statistics
        self._delivery_stats["acknowledgments_received"] += 1

        # Update database record
        await self._db.execute(
            """
            UPDATE notification_queue
            SET read_at = CURRENT_TIMESTAMP,
                status = 'acknowledged'
            WHERE id = $1
            """,
            notification_id,
        )

        # Send acknowledgment confirmation
        confirm_msg = WebSocketMessage(
            type=MessageType.NOTIFICATION_RECEIVED,
            data=create_websocket_message_data(
                notification_id=notification_id,
                payload={"acknowledged_at": datetime.now().isoformat()},
            ).model_dump(),
        )

        await self._manager.send_personal_message(connection_id, confirm_msg)
        return Ok(None)

    @beartype
    async def get_delivery_statistics(self) -> dict[str, Any]:
        """Get notification delivery statistics."""
        # Get database statistics
        db_stats = await self._db.fetchrow(
            """
            SELECT
                COUNT(*) as total_notifications,
                COUNT(*) FILTER (WHERE status = 'delivered') as delivered,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                COUNT(*) FILTER (WHERE read_at IS NOT NULL) as read,
                AVG(EXTRACT(EPOCH FROM (delivered_at - created_at))) as avg_delivery_time_seconds
            FROM notification_queue
            WHERE created_at > NOW() - INTERVAL '24 hours'
            """
        )

        return {
            "session_stats": self._delivery_stats,
            "daily_stats": dict(db_stats) if db_stats else {},
            "active_alerts": len(self._active_alerts),
            "pending_notifications": len(self._pending_notifications),
        }

    @beartype
    async def cleanup_connection(self, connection_id: str) -> None:
        """Clean up resources when connection is lost."""
        # Cancel any pending delivery tasks for this connection
        tasks_to_cancel = [
            key
            for key in self._notification_delivery_tasks.keys()
            if connection_id in key
        ]

        for task_key in tasks_to_cancel:
            if task_key in self._notification_delivery_tasks:
                self._notification_delivery_tasks[task_key].cancel()
                try:
                    await self._notification_delivery_tasks[task_key]
                except asyncio.CancelledError:
                    pass
                del self._notification_delivery_tasks[task_key]

    @beartype
    def _get_alert_icon(self, severity: str) -> str:
        """Get appropriate icon for alert severity."""
        icons = {
            "low": "info-circle",
            "medium": "exclamation-triangle",
            "high": "exclamation-circle",
            "critical": "times-circle",
        }
        return icons.get(severity, "info-circle")

    @beartype
    def _get_alert_sound(self, severity: str) -> str:
        """Get appropriate sound for alert severity."""
        sounds = {
            "low": "gentle",
            "medium": "attention",
            "high": "urgent",
            "critical": "alarm",
        }
        return sounds.get(severity, "gentle")

    @beartype
    async def _get_users_by_roles(self, roles: list[str]) -> list[UUID]:
        """Get users with specific roles."""
        # Query users with the specified roles
        rows = await self._db.fetch(
            """
            SELECT DISTINCT u.id
            FROM users u
            JOIN user_roles ur ON u.id = ur.user_id
            JOIN roles r ON ur.role_id = r.id
            WHERE r.name = ANY($1)
              AND u.is_active = true
            """,
            roles,
        )
        return [row["id"] for row in rows]

    @beartype
    async def _store_notification_for_later(
        self,
        user_id: UUID,
        notification: NotificationData,
        config: NotificationConfig,
    ) -> Result[None, str]:
        """Store notification in database for later delivery."""
        try:
            await self._db.execute(
                """
                INSERT INTO notification_queue
                (notification_type, priority, channel, user_id, title, message, data, action_url, status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending')
                """,
                config.notification_type,
                config.priority,
                config.channel,
                user_id,
                notification.title,
                notification.message,
                notification.data,
                config.action_url,
            )
            return Ok(None)
        except Exception as e:
            return Err(f"Failed to store notification: {str(e)}")

    @beartype
    async def _record_notification_delivery(
        self,
        notification_id: UUID,
        user_id: UUID,
        notification: NotificationData,
        config: NotificationConfig,
        status: str,
    ) -> None:
        """Record notification delivery in database."""
        try:
            await self._db.execute(
                """
                INSERT INTO notification_queue
                (id, notification_type, priority, channel, user_id, title, message, data,
                 action_url, status, delivered_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                        CASE WHEN $10 = 'delivered' THEN CURRENT_TIMESTAMP ELSE NULL END)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    delivered_at = EXCLUDED.delivered_at
                """,
                notification_id,
                config.notification_type,
                config.priority,
                config.channel,
                user_id,
                notification.title,
                notification.message,
                notification.data,
                config.action_url,
                status,
            )
        except Exception:
            # Non-critical error
            pass

    @beartype
    async def _record_system_alert(
        self,
        alert: SystemAlert,
        notification: NotificationData,
        recipients_count: int,
    ) -> None:
        """Record system alert in database."""
        try:
            await self._db.execute(
                """
                INSERT INTO system_alerts
                (alert_type, severity, message, details, resolved)
                VALUES ($1, $2, $3, $4, false)
                """,
                alert.alert_type,
                alert.severity,
                notification.message,
                {
                    "affected_systems": alert.affected_systems,
                    "recipients_count": recipients_count,
                    "notification_data": notification.data,
                },
            )
        except Exception:
            # Non-critical error
            pass

    async def _handle_notification_expiration(
        self, notification_id: UUID, expiration_time: datetime
    ) -> None:
        """Handle notification expiration."""
        wait_time = (expiration_time - datetime.now()).total_seconds()
        if wait_time > 0:
            await asyncio.sleep(wait_time)

        # Remove from pending if still there
        if notification_id in self._pending_notifications:
            del self._pending_notifications[notification_id]

        # Update database
        await self._db.execute(
            """
            UPDATE notification_queue
            SET status = 'expired'
            WHERE id = $1 AND status != 'acknowledged'
            """,
            notification_id,
        )

    async def _cleanup_resolved_alert(
        self, alert_id: str, resolution_time: datetime
    ) -> None:
        """Clean up resolved system alert."""
        wait_time = (resolution_time - datetime.now()).total_seconds()
        if wait_time > 0:
            await asyncio.sleep(wait_time)

        # Remove from active alerts
        if alert_id in self._active_alerts:
            alert = self._active_alerts.pop(alert_id)

            # Send resolution notification
            resolution_msg = WebSocketMessage(
                type=MessageType.SYSTEM_ALERT,
                data=create_websocket_message_data(
                    alert_type=alert.alert_type,
                    payload={
                        "alert_id": alert_id,
                        "resolved_at": datetime.now().isoformat(),
                    },
                ).model_dump(),
            )

            await self._manager.broadcast(resolution_msg)
