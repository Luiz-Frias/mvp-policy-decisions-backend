"""Unit tests for WebSocket Manager functionality."""

import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import WebSocket
from starlette.websockets import WebSocketState

from src.pd_prime_demo.websocket.manager import (
    ConnectionManager,
    WebSocketMessage,
    ConnectionMetadata,
)


def create_mock_websocket():
    """Create a properly mocked WebSocket that passes beartype validation."""
    # Create a mock that inherits from WebSocket to satisfy beartype
    mock = MagicMock(spec=WebSocket)
    mock.is_connected = True
    mock.messages_sent = []
    mock.client = MagicMock()
    mock.client.host = "127.0.0.1"
    mock.headers = {"user-agent": "test"}
    mock.state = WebSocketState.CONNECTED
    
    # Setup async methods
    async def mock_accept():
        mock.state = WebSocketState.CONNECTED
    
    async def mock_send_json(data):
        if not mock.is_connected:
            raise Exception("Connection closed")
        mock.messages_sent.append(data)
    
    async def mock_close(code=1000, reason=""):
        mock.is_connected = False
        mock.state = WebSocketState.DISCONNECTED
    
    mock.accept = mock_accept
    mock.send_json = mock_send_json
    mock.close = mock_close
    
    return mock


class MockCache:
    """Mock cache for testing."""
    
    def __init__(self):
        self.data = {}
    
    async def sadd(self, key: str, value: str):
        """Mock sadd."""
        if key not in self.data:
            self.data[key] = set()
        self.data[key].add(value)
    
    async def srem(self, key: str, value: str):
        """Mock srem."""
        if key in self.data:
            self.data[key].discard(value)
    
    async def setex(self, key: str, ttl: int, value: str):
        """Mock setex."""
        self.data[key] = value


class MockDatabase:
    """Mock database for testing."""
    
    def __init__(self):
        self.executed_queries = []
    
    async def execute(self, query: str, *args):
        """Mock execute."""
        self.executed_queries.append((query, args))
    
    async def fetchrow(self, query: str, *args):
        """Mock fetchrow."""
        return None
    
    async def fetch(self, query: str, *args):
        """Mock fetch."""
        return []


@pytest.fixture
def mock_cache():
    """Mock cache instance."""
    return MockCache()


@pytest.fixture
def mock_db():
    """Mock database instance."""
    return MockDatabase()


@pytest.fixture
def connection_manager(mock_cache, mock_db):
    """Create connection manager with mocks."""
    # Mock the monitoring to avoid import issues
    manager = ConnectionManager(mock_cache, mock_db)
    manager._monitor = AsyncMock()
    return manager


@pytest.mark.unit
@pytest.mark.asyncio
class TestConnectionManager:
    """Test ConnectionManager functionality."""

    async def test_websocket_message_validation(self):
        """Test WebSocket message validation."""
        # Valid message
        msg = WebSocketMessage(
            type="test",
            data={"key": "value"},
            timestamp=datetime.now()
        )
        assert msg.type == "test"
        assert msg.data == {"key": "value"}

    async def test_connection_lifecycle(self, connection_manager):
        """Test connection establishment and cleanup."""
        websocket = create_mock_websocket()
        connection_id = "test_conn_1"
        user_id = uuid4()

        # Test connection
        result = await connection_manager.connect(
            websocket,
            connection_id,
            user_id=user_id,
            metadata={"ip_address": "127.0.0.1"}
        )

        assert result.is_ok()
        assert connection_id in connection_manager._connections
        assert user_id in connection_manager._user_connections
        assert len(websocket.messages_sent) > 0  # Welcome message
        
        # Verify welcome message
        welcome_msg = websocket.messages_sent[0]
        assert welcome_msg["type"] == "connection"
        assert welcome_msg["data"]["status"] == "connected"

        # Test disconnection
        disconnect_result = await connection_manager.disconnect(connection_id, "test")
        assert disconnect_result.is_ok()
        assert connection_id not in connection_manager._connections

    async def test_duplicate_connection_rejection(self, connection_manager):
        """Test that duplicate connection IDs are rejected."""
        websocket1 = create_mock_websocket()
        websocket2 = create_mock_websocket()
        connection_id = "duplicate_conn"

        # First connection should succeed
        result1 = await connection_manager.connect(websocket1, connection_id)
        assert result1.is_ok()

        # Second connection with same ID should fail
        result2 = await connection_manager.connect(websocket2, connection_id)
        assert result2.is_err()
        assert "already exists" in result2.unwrap_err()

    async def test_room_subscription(self, connection_manager):
        """Test room subscription functionality."""
        websocket = create_mock_websocket()
        connection_id = "test_conn_room"
        room_id = "test_room"

        # Connect first
        await connection_manager.connect(websocket, connection_id)

        # Subscribe to room
        sub_result = await connection_manager.subscribe_to_room(connection_id, room_id)
        assert sub_result.is_ok()
        assert room_id in connection_manager._room_subscriptions
        assert connection_id in connection_manager._room_subscriptions[room_id]

        # Unsubscribe from room
        unsub_result = await connection_manager.unsubscribe_from_room(connection_id, room_id)
        assert unsub_result.is_ok()

    async def test_message_sending(self, connection_manager):
        """Test message sending functionality."""
        websocket = create_mock_websocket()
        connection_id = "test_conn_msg"

        await connection_manager.connect(websocket, connection_id)

        # Send a test message
        test_msg = WebSocketMessage(type="test", data={"content": "hello"})
        result = await connection_manager.send_personal_message(connection_id, test_msg)
        
        assert result.is_ok()
        assert len(websocket.messages_sent) >= 2  # Welcome + test message

        # Find the test message
        test_message_sent = None
        for msg in websocket.messages_sent:
            if msg.get("type") == "test":
                test_message_sent = msg
                break

        assert test_message_sent is not None
        assert test_message_sent["data"]["content"] == "hello"

    async def test_room_broadcasting(self, connection_manager):
        """Test broadcasting to room members."""
        # Create multiple connections
        connections = []
        connection_ids = []
        room_id = "broadcast_room"

        for i in range(3):
            websocket = create_mock_websocket()
            connection_id = f"conn_{i}"
            
            await connection_manager.connect(websocket, connection_id)
            await connection_manager.subscribe_to_room(connection_id, room_id)
            
            connections.append(websocket)
            connection_ids.append(connection_id)

        # Broadcast message to room
        broadcast_msg = WebSocketMessage(type="broadcast", data={"message": "hello room"})
        result = await connection_manager.send_to_room(room_id, broadcast_msg)
        
        assert result.is_ok()
        assert result.unwrap() == 3  # Should send to all 3 connections

        # Verify all connections received the message
        for websocket in connections:
            broadcast_received = any(
                msg.get("type") == "broadcast" for msg in websocket.messages_sent
            )
            assert broadcast_received

    async def test_connection_limit_enforcement(self, connection_manager):
        """Test connection limit enforcement."""
        # Set a low limit for testing
        connection_manager._max_connections_allowed = 2

        connections = []
        for i in range(3):
            websocket = create_mock_websocket()
            connection_id = f"limit_conn_{i}"
            
            result = await connection_manager.connect(websocket, connection_id)
            
            if i < 2:
                assert result.is_ok()
                connections.append((websocket, connection_id))
            else:
                assert result.is_err()
                assert "Connection limit reached" in result.unwrap_err()

        # Cleanup
        for websocket, connection_id in connections:
            await connection_manager.disconnect(connection_id, "test cleanup")

    async def test_message_sequencing(self, connection_manager):
        """Test message sequence numbering."""
        websocket = create_mock_websocket()
        connection_id = "seq_test_conn"

        await connection_manager.connect(websocket, connection_id)

        # Send multiple messages
        for i in range(3):
            msg = WebSocketMessage(type="test", data={"number": i})
            await connection_manager.send_personal_message(connection_id, msg)

        # Check sequence numbers are incrementing
        sequences = []
        for msg in websocket.messages_sent:
            if "sequence" in msg:
                sequences.append(msg["sequence"])

        # Should have at least welcome message + 3 test messages with sequences
        assert len(sequences) >= 4
        
        # Sequences should be incrementing
        for i in range(1, len(sequences)):
            assert sequences[i] > sequences[i-1]

    async def test_error_handling_invalid_connection(self, connection_manager):
        """Test error handling for invalid connection operations."""
        # Try to send message to non-existent connection
        msg = WebSocketMessage(type="test", data={})
        result = await connection_manager.send_personal_message("invalid_conn", msg)
        assert result.is_err()

        # Try to subscribe non-existent connection to room
        sub_result = await connection_manager.subscribe_to_room("invalid_conn", "room")
        assert sub_result.is_err()

    async def test_ping_pong_handling(self, connection_manager):
        """Test ping/pong message handling."""
        websocket = create_mock_websocket()
        connection_id = "ping_test_conn"

        await connection_manager.connect(websocket, connection_id)

        # Send ping message
        ping_data = {"type": "ping", "timestamp": "2024-01-01T00:00:00Z"}
        result = await connection_manager.handle_message(connection_id, ping_data)
        
        assert result.is_ok()

        # Should receive pong response
        pong_received = any(
            msg.get("type") == "pong" for msg in websocket.messages_sent
        )
        assert pong_received

    async def test_connection_stats(self, connection_manager):
        """Test connection statistics reporting."""
        # Create some connections and rooms
        for i in range(3):
            websocket = create_mock_websocket()
            connection_id = f"stats_conn_{i}"
            
            await connection_manager.connect(websocket, connection_id)
            await connection_manager.subscribe_to_room(connection_id, f"room_{i}")

        stats = await connection_manager.get_connection_stats()
        
        assert stats["total_connections"] == 3
        assert stats["unique_users"] == 0  # No users specified
        assert stats["total_rooms"] == 3
        assert "utilization" in stats

    async def test_failed_connection_cleanup(self, connection_manager):
        """Test cleanup when connection fails."""
        websocket = create_mock_websocket()
        connection_id = "fail_test_conn"

        # Simulate connection failure by making websocket reject send
        websocket.is_connected = False

        # Connection should fail during welcome message
        result = await connection_manager.connect(websocket, connection_id)
        
        # Should handle the failure gracefully
        assert result.is_err()
        assert connection_id not in connection_manager._connections


if __name__ == "__main__":
    pytest.main([__file__, "-v"])