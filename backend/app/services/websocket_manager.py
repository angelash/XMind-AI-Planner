"""WebSocket connection manager for real-time collaboration.

RT-01: WebSocket 连接管理

Provides connection lifecycle management for document collaboration:
- Connect/disconnect handling
- Per-document connection tracking
- User presence tracking
- Message broadcasting
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket


@dataclass
class ConnectionInfo:
    """Information about a WebSocket connection."""
    document_id: str
    user_id: str
    user_name: str
    connected_at: float = field(default_factory=time.time)


class HeartbeatMessage:
    """Heartbeat response message."""
    type: str = "pong"
    timestamp: float
    
    def __init__(self):
        self.timestamp = time.time()
    
    def model_dump(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "timestamp": self.timestamp,
        }


class ConnectionManager:
    """Manages WebSocket connections for document collaboration.
    
    Tracks connections per document and provides:
    - Connection lifecycle management
    - User presence tracking
    - Message broadcasting within documents
    """
    
    def __init__(self):
        # document_id -> {websocket: ConnectionInfo}
        self._connections: dict[str, dict[WebSocket, ConnectionInfo]] = {}
        # user_id -> websocket mapping for direct messaging
        self._user_connections: dict[str, dict[str, WebSocket]] = {}  # doc_id -> {user_id -> ws}
    
    @property
    def active_connections(self) -> dict[str, dict[WebSocket, ConnectionInfo]]:
        """Return active connections for testing."""
        return self._connections
    
    async def connect(
        self,
        websocket: WebSocket,
        document_id: str,
        user_id: str,
        user_name: str,
    ) -> None:
        """Accept and register a new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            document_id: Document being accessed
            user_id: User identifier
            user_name: Display name for presence
        """
        await websocket.accept()
        
        info = ConnectionInfo(
            document_id=document_id,
            user_id=user_id,
            user_name=user_name,
        )
        
        if document_id not in self._connections:
            self._connections[document_id] = {}
        self._connections[document_id][websocket] = info
        
        # Track by user for direct messaging
        if document_id not in self._user_connections:
            self._user_connections[document_id] = {}
        self._user_connections[document_id][user_id] = websocket
        
        # Notify others in the document
        await self._broadcast_user_joined(document_id, user_id, user_name)
    
    def disconnect(self, websocket: WebSocket, document_id: str) -> None:
        """Remove a WebSocket connection.
        
        Args:
            websocket: The WebSocket to disconnect
            document_id: Document being accessed
        """
        if document_id in self._connections:
            info = self._connections[document_id].pop(websocket, None)
            if info:
                # Remove from user connections
                if document_id in self._user_connections:
                    self._user_connections[document_id].pop(info.user_id, None)
            
            # Clean up empty document entries
            if not self._connections[document_id]:
                del self._connections[document_id]
                if document_id in self._user_connections:
                    del self._user_connections[document_id]
    
    def get_document_users(self, document_id: str) -> list[dict[str, Any]]:
        """Get list of users connected to a document.
        
        Args:
            document_id: Document to query
            
        Returns:
            List of user info dicts with user_id, user_name, connected_at
        """
        if document_id not in self._connections:
            return []
        
        users = []
        seen = set()
        for info in self._connections[document_id].values():
            if info.user_id not in seen:
                seen.add(info.user_id)
                users.append({
                    "user_id": info.user_id,
                    "user_name": info.user_name,
                    "connected_at": info.connected_at,
                })
        return users
    
    async def broadcast_to_document(
        self,
        document_id: str,
        message: dict[str, Any],
        exclude_user: str | None = None,
    ) -> None:
        """Broadcast a message to all connections in a document.
        
        Args:
            document_id: Target document
            message: Message to broadcast
            exclude_user: Optional user_id to exclude from broadcast
        """
        if document_id not in self._connections:
            return
        
        disconnected = []
        for ws, info in self._connections[document_id].items():
            if exclude_user and info.user_id == exclude_user:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(ws)
        
        # Clean up disconnected WebSockets
        for ws in disconnected:
            self.disconnect(ws, document_id)
    
    async def send_to_user(
        self,
        document_id: str,
        user_id: str,
        message: dict[str, Any],
    ) -> bool:
        """Send a message to a specific user in a document.
        
        Args:
            document_id: Target document
            user_id: Target user
            message: Message to send
            
        Returns:
            True if message was sent, False if user not found
        """
        if document_id not in self._user_connections:
            return False
        if user_id not in self._user_connections[document_id]:
            return False
        
        ws = self._user_connections[document_id][user_id]
        try:
            await ws.send_json(message)
            return True
        except Exception:
            self.disconnect(ws, document_id)
            return False
    
    async def _broadcast_user_joined(
        self,
        document_id: str,
        user_id: str,
        user_name: str,
    ) -> None:
        """Broadcast user join notification to document."""
        message = {
            "type": "user_joined",
            "user_id": user_id,
            "user_name": user_name,
            "users": self.get_document_users(document_id),
        }
        await self.broadcast_to_document(document_id, message, exclude_user=user_id)
    
    async def broadcast_user_left(
        self,
        document_id: str,
        user_id: str,
        user_name: str,
    ) -> None:
        """Broadcast user leave notification to document."""
        message = {
            "type": "user_left",
            "user_id": user_id,
            "user_name": user_name,
            "users": self.get_document_users(document_id),
        }
        await self.broadcast_to_document(document_id, message)


# Singleton instance
_manager: ConnectionManager | None = None


def get_connection_manager() -> ConnectionManager:
    """Get the singleton ConnectionManager instance."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager


def reset_connection_manager() -> None:
    """Reset the singleton ConnectionManager (for testing)."""
    global _manager
    _manager = None
