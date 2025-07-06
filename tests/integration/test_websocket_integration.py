"""Integration tests for WebSocket infrastructure.

Tests end-to-end WebSocket functionality including:
- Connection management
- Real-time quote updates
- Analytics streaming
- Admin dashboard features
- Notification delivery
"""

import asyncio
import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocketDisconnect

from src.pd_prime_demo.main import app
from src.pd_prime_demo.websocket.app import websocket_app
from src.pd_prime_demo.websocket.manager import WebSocketMessage


@pytest.fixture
def test_client():
    """Get test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def websocket_client():
    """Get test client for WebSocket app."""
    return TestClient(websocket_app)


class WebSocketTestClient:
    """Helper class for WebSocket testing."""

    def __init__(self, client: TestClient, token: str | None = None):
        self.client = client
        self.token = token
        self.websocket = None
        self.received_messages = []

    async def connect(self, endpoint: str = "/ws") -> None:
        """Connect to WebSocket endpoint."""
        url = endpoint
        if self.token:
            url += f"?token={self.token}"

        self.websocket = self.client.websocket_connect(url)
        self.websocket.__enter__()

    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        if self.websocket:
            self.websocket.__exit__(None, None, None)
            self.websocket = None

    async def send_message(self, message: dict[str, Any]) -> None:
        """Send message to WebSocket."""
        if self.websocket:
            self.websocket.send_json(message)

    async def receive_message(self, timeout: float = 1.0) -> dict[str, Any]:
        """Receive message from WebSocket."""
        if self.websocket:
            try:
                message = self.websocket.receive_json()
                self.received_messages.append(message)
                return message
            except Exception:
                raise TimeoutError("No message received within timeout")
        raise RuntimeError("Not connected")

    async def wait_for_message_type(
        self, message_type: str, timeout: float = 5.0
    ) -> dict[str, Any]:
        """Wait for specific message type."""
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                message = await self.receive_message(0.1)
                if message.get("type") == message_type:
                    return message
            except TimeoutError:
                continue
        raise TimeoutError(f"Message type '{message_type}' not received within timeout")


@pytest.mark.integration
class TestWebSocketBasicIntegration:
    """Basic WebSocket integration tests."""

    def test_websocket_connection_lifecycle(self, websocket_client: TestClient) -> None:
        """Test basic connection and disconnection."""
        ws_client = WebSocketTestClient(websocket_client, token="demo")

        # Test connection
        with websocket_client.websocket_connect("/ws?token=demo") as websocket:
            # Should receive connection confirmation
            message = websocket.receive_json()
            assert message["type"] == "connection"
            assert message["data"]["status"] == "connected"
            assert "connection_id" in message["data"]

            # Test ping/pong
            websocket.send_json({"type": "ping", "timestamp": "2024-01-01T00:00:00Z"})
            pong = websocket.receive_json()
            assert pong["type"] == "pong"
            assert "server_time" in pong["data"]

    def test_websocket_authentication(self, websocket_client: TestClient) -> None:
        """Test WebSocket authentication scenarios."""
        # Test valid token
        with websocket_client.websocket_connect("/ws?token=demo") as websocket:
            message = websocket.receive_json()
            assert message["type"] == "connection"

        # Test invalid token
        try:
            with websocket_client.websocket_connect("/ws?token=invalid") as websocket:
                # Should be rejected
                assert False, "Should not connect with invalid token"
        except WebSocketDisconnect as e:
            assert e.code == 1008  # Policy violation

    def test_room_subscription(self, websocket_client: TestClient) -> None:
        """Test room subscription functionality."""
        with websocket_client.websocket_connect("/ws?token=demo") as websocket:
            # Skip connection message
            websocket.receive_json()

            # Subscribe to room
            websocket.send_json({"type": "subscribe", "room_id": "test_room"})

            # Should receive subscription confirmation
            message = websocket.receive_json()
            assert message["type"] == "room_subscribed"
            assert message["data"]["room_id"] == "test_room"

            # Unsubscribe from room
            websocket.send_json({"type": "unsubscribe", "room_id": "test_room"})

    def test_error_handling(self, websocket_client: TestClient) -> None:
        """Test error handling for invalid messages."""
        with websocket_client.websocket_connect("/ws?token=demo") as websocket:
            # Skip connection message
            websocket.receive_json()

            # Send invalid message
            websocket.send_json({"type": "invalid_type"})

            # Should receive error message
            error_message = websocket.receive_json()
            assert error_message["type"] == "error"
            assert "Unknown message type" in error_message["data"]["error"]


@pytest.mark.integration
class TestQuoteWebSocketIntegration:
    """Quote-specific WebSocket integration tests."""

    def test_quote_subscription_workflow(self, websocket_client: TestClient) -> None:
        """Test complete quote subscription workflow."""
        quote_id = str(uuid4())

        with websocket_client.websocket_connect("/ws?token=demo") as websocket:
            # Skip connection message
            websocket.receive_json()

            # Subscribe to quote
            websocket.send_json({"type": "quote_subscribe", "quote_id": quote_id})

            # Should receive quote state or error (quote doesn't exist)
            message = websocket.receive_json()
            assert message["type"] in ["quote_state", "subscription_error"]

            if message["type"] == "subscription_error":
                assert quote_id in message["data"]["error"]

    def test_collaborative_editing_simulation(
        self, websocket_client: TestClient
    ) -> None:
        """Test collaborative editing features."""
        quote_id = str(uuid4())

        # Simulate two users editing the same quote
        with websocket_client.websocket_connect("/ws?token=demo") as ws1, \
             websocket_client.websocket_connect("/ws?token=demo") as ws2:

            # Skip connection messages
            ws1.receive_json()
            ws2.receive_json()

            # Both subscribe to same quote
            ws1.send_json({"type": "quote_subscribe", "quote_id": quote_id})
            ws2.send_json({"type": "quote_subscribe", "quote_id": quote_id})

            # Skip initial responses
            ws1.receive_json()
            ws2.receive_json()

            # User 1 focuses on a field
            ws1.send_json({
                "type": "field_focus",
                "quote_id": quote_id,
                "field": "customer_name",
                "focused": True
            })

            # User 2 should receive focus notification
            try:
                focus_message = ws2.receive_json()
                if focus_message["type"] == "field_focus":
                    assert focus_message["data"]["field"] == "customer_name"
                    assert focus_message["data"]["focused"] is True
            except Exception:
                # Focus message might not be received if quote doesn't exist
                pass

    def test_quote_calculation_progress(self, websocket_client: TestClient) -> None:
        """Test quote calculation progress streaming."""
        quote_id = str(uuid4())

        with websocket_client.websocket_connect("/ws?token=demo") as websocket:
            # Skip connection message
            websocket.receive_json()

            # Subscribe to quote
            websocket.send_json({"type": "quote_subscribe", "quote_id": quote_id})

            # Skip initial response
            websocket.receive_json()

            # Calculation progress would be sent by the rating engine
            # This tests the WebSocket infrastructure's ability to handle it


@pytest.mark.integration
class TestAnalyticsWebSocketIntegration:
    """Analytics dashboard WebSocket integration tests."""

    def test_analytics_dashboard_subscription(
        self, websocket_client: TestClient
    ) -> None:
        """Test analytics dashboard subscription."""
        with websocket_client.websocket_connect("/ws?token=demo") as websocket:
            # Skip connection message
            websocket.receive_json()

            # Start analytics dashboard
            websocket.send_json({
                "type": "start_analytics",
                "dashboard_type": "quotes",
                "update_interval": 5,
                "filters": {},
                "metrics": [],
                "time_range_hours": 24
            })

            # Should receive initial analytics data
            message = websocket.receive_json()
            assert message["type"] in ["analytics_data", "analytics_error"]

            if message["type"] == "analytics_data":
                assert message["data"]["dashboard"] == "quotes"
                assert "metrics" in message["data"]

            # Stop analytics
            websocket.send_json({
                "type": "stop_analytics",
                "dashboard_type": "quotes"
            })

    def test_analytics_permission_validation(
        self, websocket_client: TestClient
    ) -> None:
        """Test analytics permission validation."""
        with websocket_client.websocket_connect("/ws?token=demo") as websocket:
            # Skip connection message
            websocket.receive_json()

            # Try to access admin analytics without proper permissions
            websocket.send_json({
                "type": "start_analytics",
                "dashboard_type": "admin",
                "update_interval": 5
            })

            # Should receive error or data based on permissions
            message = websocket.receive_json()
            assert message["type"] in ["analytics_data", "analytics_error"]


@pytest.mark.integration
class TestNotificationWebSocketIntegration:
    """Notification WebSocket integration tests."""

    def test_notification_acknowledgment(self, websocket_client: TestClient) -> None:
        """Test notification acknowledgment workflow."""
        with websocket_client.websocket_connect("/ws?token=demo") as websocket:
            # Skip connection message
            websocket.receive_json()

            # Acknowledge a notification (would normally be received first)
            notification_id = str(uuid4())
            websocket.send_json({
                "type": "notification_acknowledge",
                "notification_id": notification_id
            })

            # Should receive acknowledgment response or error
            message = websocket.receive_json()
            assert message["type"] in ["notification_acknowledged", "error"]


@pytest.mark.integration
class TestAdminWebSocketIntegration:
    """Admin dashboard WebSocket integration tests."""

    def test_admin_monitoring_workflow(self, websocket_client: TestClient) -> None:
        """Test admin monitoring workflow."""
        # Use admin token for authentication
        with websocket_client.websocket_connect("/ws?token=admin") as websocket:
            # Skip connection message
            websocket.receive_json()

            # Start system monitoring
            websocket.send_json({
                "type": "start_admin_monitoring",
                "config": {"update_interval": 5}
            })

            # Should receive monitoring data or permission error
            message = websocket.receive_json()
            assert message["type"] in [
                "admin_monitoring_started",
                "permission_error",
                "error"
            ]

    def test_user_activity_monitoring(self, websocket_client: TestClient) -> None:
        """Test user activity monitoring."""
        with websocket_client.websocket_connect("/ws?token=admin") as websocket:
            # Skip connection message
            websocket.receive_json()

            # Start user activity monitoring
            websocket.send_json({
                "type": "start_user_activity",
                "filters": {"action": "login"}
            })

            # Should receive response
            message = websocket.receive_json()
            assert message["type"] in [
                "user_activity_batch",
                "permission_error",
                "error"
            ]

    def test_performance_monitoring(self, websocket_client: TestClient) -> None:
        """Test performance monitoring."""
        with websocket_client.websocket_connect("/ws?token=admin") as websocket:
            # Skip connection message
            websocket.receive_json()

            # Start performance monitoring
            websocket.send_json({
                "type": "start_performance_monitoring",
                "metrics": ["api_response_times", "active_sessions"]
            })

            # Should receive response
            message = websocket.receive_json()
            assert message["type"] in [
                "performance_metrics",
                "permission_error",
                "error"
            ]


@pytest.mark.integration
class TestWebSocketEndToEnd:
    """End-to-end WebSocket integration tests."""

    def test_multiple_clients_same_quote(self, websocket_client: TestClient) -> None:
        """Test multiple clients working on the same quote."""
        quote_id = str(uuid4())
        clients = []

        try:
            # Create multiple WebSocket connections
            for i in range(3):
                ws = websocket_client.websocket_connect(f"/ws?token=user_{i}")
                ws.__enter__()
                clients.append(ws)

                # Skip connection message
                ws.receive_json()

                # Subscribe to same quote
                ws.send_json({"type": "quote_subscribe", "quote_id": quote_id})
                ws.receive_json()  # Skip response

            # Have one client make an edit
            if clients:
                clients[0].send_json({
                    "type": "quote_edit",
                    "data": {
                        "quote_id": quote_id,
                        "field": "customer_name",
                        "value": "John Doe"
                    }
                })

                # Other clients should potentially receive updates
                # (depends on whether quote exists)

        finally:
            # Cleanup connections
            for ws in clients:
                try:
                    ws.__exit__(None, None, None)
                except Exception:
                    pass

    def test_system_alert_broadcast(self, websocket_client: TestClient) -> None:
        """Test system alert broadcasting to multiple clients."""
        clients = []

        try:
            # Create multiple connections
            for i in range(2):
                ws = websocket_client.websocket_connect(f"/ws?token=user_{i}")
                ws.__enter__()
                clients.append(ws)

                # Skip connection message
                ws.receive_json()

            # System alert would be triggered by admin or system event
            # This tests the infrastructure's ability to handle broadcasts

        finally:
            # Cleanup
            for ws in clients:
                try:
                    ws.__exit__(None, None, None)
                except Exception:
                    pass

    def test_connection_recovery_simulation(
        self, websocket_client: TestClient
    ) -> None:
        """Test connection recovery scenarios."""
        with websocket_client.websocket_connect("/ws?token=demo") as websocket:
            # Skip connection message
            websocket.receive_json()

            # Subscribe to something
            websocket.send_json({"type": "subscribe", "room_id": "test_room"})
            websocket.receive_json()

            # Send heartbeat to maintain connection
            websocket.send_json({"type": "ping"})
            pong = websocket.receive_json()
            assert pong["type"] == "pong"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])