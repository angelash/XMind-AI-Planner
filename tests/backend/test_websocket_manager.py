"""Tests for WebSocket connection management (RT-01)."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.services.websocket_manager import (
    ConnectionManager,
    ConnectionInfo,
    HeartbeatMessage,
    get_connection_manager,
    reset_connection_manager,
)


class TestConnectionInfo:
    """Tests for ConnectionInfo dataclass."""

    def test_connection_info_creation(self):
        """Test creating a ConnectionInfo instance."""
        info = ConnectionInfo(
            document_id="doc-123",
            user_id="user-456",
            user_name="Test User",
        )
        assert info.document_id == "doc-123"
        assert info.user_id == "user-456"
        assert info.user_name == "Test User"
        assert info.connected_at > 0


class TestConnectionManager:
    """Tests for ConnectionManager class."""

    @pytest.fixture
    def manager(self):
        """Create a fresh ConnectionManager for each test."""
        reset_connection_manager()
        return ConnectionManager()

    def test_get_instance_singleton(self):
        """Test that get_connection_manager returns singleton."""
        reset_connection_manager()
        manager1 = get_connection_manager()
        manager2 = get_connection_manager()
        assert manager1 is manager2

    def test_connect(self, manager):
        """Test connecting a WebSocket client."""
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        async def run_test():
            await manager.connect(mock_ws, "doc-123", "user-456", "Test User")
            assert "doc-123" in manager.active_connections
            assert len(manager.active_connections["doc-123"]) == 1

        asyncio.run(run_test())

    def test_disconnect(self, manager):
        """Test disconnecting a WebSocket client."""
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        async def run_test():
            await manager.connect(mock_ws, "doc-123", "user-456", "Test User")
            manager.disconnect(mock_ws, "doc-123")
            assert "doc-123" not in manager.active_connections

        asyncio.run(run_test())

    def test_disconnect_last_client_removes_document(self, manager):
        """Test that document key is removed when last client disconnects."""
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        async def run_test():
            await manager.connect(mock_ws, "doc-123", "user-456", "Test User")
            manager.disconnect(mock_ws, "doc-123")
            assert "doc-123" not in manager.active_connections

        asyncio.run(run_test())

    def test_multiple_clients_same_document(self, manager):
        """Test multiple clients connecting to same document."""
        mock_ws1 = MagicMock()
        mock_ws1.accept = AsyncMock()
        mock_ws1.send_json = AsyncMock()
        mock_ws2 = MagicMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_json = AsyncMock()

        async def run_test():
            await manager.connect(mock_ws1, "doc-123", "user-1", "User One")
            await manager.connect(mock_ws2, "doc-123", "user-2", "User Two")
            assert len(manager.active_connections["doc-123"]) == 2

        asyncio.run(run_test())

    def test_get_document_users(self, manager):
        """Test getting list of users connected to a document."""
        mock_ws1 = MagicMock()
        mock_ws1.accept = AsyncMock()
        mock_ws1.send_json = AsyncMock()
        mock_ws2 = MagicMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_json = AsyncMock()

        async def run_test():
            await manager.connect(mock_ws1, "doc-123", "user-1", "User One")
            await manager.connect(mock_ws2, "doc-123", "user-2", "User Two")
            users = manager.get_document_users("doc-123")
            assert len(users) == 2
            user_names = [u["user_name"] for u in users]
            assert "User One" in user_names
            assert "User Two" in user_names

        asyncio.run(run_test())

    def test_get_document_users_empty(self, manager):
        """Test getting users for document with no connections."""
        users = manager.get_document_users("doc-999")
        assert users == []

    def test_broadcast_to_document(self, manager):
        """Test broadcasting message to all clients in a document."""
        mock_ws1 = MagicMock()
        mock_ws1.accept = AsyncMock()
        mock_ws1.send_json = AsyncMock()
        mock_ws2 = MagicMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_json = AsyncMock()

        async def run_test():
            await manager.connect(mock_ws1, "doc-123", "user-1", "User One")
            await manager.connect(mock_ws2, "doc-123", "user-2", "User Two")
            # Reset mocks to clear the join broadcast calls
            mock_ws1.send_json.reset_mock()
            mock_ws2.send_json.reset_mock()
            message = {"type": "update", "data": "test"}
            await manager.broadcast_to_document("doc-123", message, exclude_user=None)
            mock_ws1.send_json.assert_called_once_with(message)
            mock_ws2.send_json.assert_called_once_with(message)

        asyncio.run(run_test())

    def test_broadcast_with_exclude(self, manager):
        """Test broadcasting with user exclusion."""
        mock_ws1 = MagicMock()
        mock_ws1.accept = AsyncMock()
        mock_ws1.send_json = AsyncMock()
        mock_ws2 = MagicMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_json = AsyncMock()

        async def run_test():
            await manager.connect(mock_ws1, "doc-123", "user-1", "User One")
            await manager.connect(mock_ws2, "doc-123", "user-2", "User Two")
            # Reset mocks to clear the join broadcast calls
            mock_ws1.send_json.reset_mock()
            mock_ws2.send_json.reset_mock()
            message = {"type": "update", "data": "test"}
            await manager.broadcast_to_document("doc-123", message, exclude_user="user-1")
            mock_ws1.send_json.assert_not_called()
            mock_ws2.send_json.assert_called_once_with(message)

        asyncio.run(run_test())

    def test_send_to_user(self, manager):
        """Test sending message to specific user."""
        mock_ws = MagicMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        async def run_test():
            await manager.connect(mock_ws, "doc-123", "user-1", "User One")
            # Reset mock to clear join broadcast
            mock_ws.send_json.reset_mock()
            message = {"type": "ping"}
            result = await manager.send_to_user("doc-123", "user-1", message)
            assert result is True
            mock_ws.send_json.assert_called_once_with(message)

        asyncio.run(run_test())

    def test_send_to_user_not_found(self, manager):
        """Test sending message to non-existent user."""
        async def run_test():
            message = {"type": "ping"}
            result = await manager.send_to_user("doc-123", "user-999", message)
            assert result is False

        asyncio.run(run_test())


class TestWebSocketEndpoint:
    """Tests for WebSocket API endpoint."""

    @pytest.fixture
    def app(self):
        """Create test FastAPI app with WebSocket endpoint."""
        from app.api.v1.endpoints.websocket import router as ws_router
        
        app = FastAPI()
        app.include_router(ws_router, tags=['websocket'])
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_websocket_endpoint_exists(self, app):
        """Test that WebSocket endpoint is registered."""
        routes = [route.path for route in app.routes]
        assert any('/ws/documents/{document_id}' in str(route) for route in app.routes)


class TestHeartbeat:
    """Tests for WebSocket heartbeat mechanism."""

    def test_heartbeat_message_format(self):
        """Test that heartbeat response has correct format."""
        msg = HeartbeatMessage()
        assert msg.type == "pong"
        assert msg.timestamp > 0

    def test_heartbeat_serialization(self):
        """Test heartbeat message serialization."""
        msg = HeartbeatMessage()
        data = msg.model_dump()
        assert data["type"] == "pong"
        assert "timestamp" in data
