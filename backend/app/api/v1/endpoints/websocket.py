"""WebSocket endpoint for real-time document collaboration.

RT-01: WebSocket 连接管理

Endpoint: /ws/documents/{document_id}

Features:
- Connection with JWT authentication
- Heartbeat mechanism (ping/pong)
- User presence tracking
- Message routing
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import (
    APIRouter,
    Cookie,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from app.core.auth_token import decode_jwt
from app.core.settings import get_settings
from app.services.document_store import get_document
from app.services.user_store import get_user_by_id
from app.services.websocket_manager import get_connection_manager

router = APIRouter()

# Heartbeat interval in seconds
HEARTBEAT_INTERVAL = 30
# Maximum missed heartbeats before disconnect
MAX_MISSED_HEARTBEATS = 3


async def get_user_from_token(token: str | None) -> dict[str, str] | None:
    """Validate JWT token and return user info.
    
    Args:
        token: JWT token string
        
    Returns:
        User info dict or None if invalid
    """
    if not token:
        return None
    
    settings = get_settings()
    payload = decode_jwt(token, settings.auth_jwt_secret)
    if payload is None:
        return None
    
    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        return None
    
    user = get_user_by_id(user_id)
    if user is None:
        return None
    
    return {
        "id": user["id"],
        "staff_no": user["staff_no"],
        "display_name": user["display_name"],
        "role": user["role"],
    }


@router.websocket("/ws/documents/{document_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    document_id: str,
    token: str | None = Query(default=None),
):
    """WebSocket endpoint for real-time document collaboration.
    
    Connection flow:
    1. Client connects with document_id and JWT token (query param)
    2. Server validates token and document access
    3. Server sends initial state (user list)
    4. Client/server exchange messages
    5. Server sends heartbeat every 30 seconds
    6. On disconnect, server notifies other users
    
    Message types (client -> server):
    - {"type": "ping"} -> Heartbeat request
    - {"type": "update", "content": {...}} -> Document update
    - {"type": "cursor", "node_id": "..."} -> Cursor position
    
    Message types (server -> client):
    - {"type": "pong", "timestamp": ...} -> Heartbeat response
    - {"type": "user_joined", "user_id": ..., "user_name": ..., "users": [...]}
    - {"type": "user_left", "user_id": ..., "user_name": ..., "users": [...]}
    - {"type": "update", "user_id": ..., "content": {...}}
    - {"type": "error", "message": ...}
    """
    # Authenticate user
    user = await get_user_from_token(token)
    if user is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return
    
    # Verify document access
    document = get_document(document_id)
    if document is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Document not found")
        return
    
    # Check access rights
    is_admin = user["role"] in {"admin", "reviewer"}
    is_owner = document.get("owner_id") == user["id"]
    
    # Check project membership if document is in a project
    if document.get("project_id") is not None:
        if not is_admin and not is_owner:
            from app.services.project_store import is_project_member
            if not is_project_member(document["project_id"], user["id"]):
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Access denied")
                return
    elif not is_admin and not is_owner:
        # Personal workspace document
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Access denied")
        return
    
    # Register connection
    manager = get_connection_manager()
    await manager.connect(websocket, document_id, user["id"], user["display_name"])
    
    # Send initial state
    await websocket.send_json({
        "type": "connected",
        "document_id": document_id,
        "users": manager.get_document_users(document_id),
    })
    
    try:
        # Main message loop
        while True:
            try:
                # Wait for messages with timeout for heartbeat
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=HEARTBEAT_INTERVAL,
                )
                
                # Parse message
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON",
                    })
                    continue
                
                # Handle message types
                msg_type = message.get("type")
                
                if msg_type == "ping":
                    # Heartbeat response
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": time.time(),
                    })
                elif msg_type == "update":
                    # Document update - broadcast to others
                    content = message.get("content", {})
                    await manager.broadcast_to_document(
                        document_id,
                        {
                            "type": "update",
                            "user_id": user["id"],
                            "user_name": user["display_name"],
                            "content": content,
                            "timestamp": time.time(),
                        },
                        exclude_user=user["id"],
                    )
                elif msg_type == "cursor":
                    # Cursor position - broadcast to others
                    node_id = message.get("node_id")
                    if node_id:
                        await manager.broadcast_to_document(
                            document_id,
                            {
                                "type": "cursor",
                                "user_id": user["id"],
                                "user_name": user["display_name"],
                                "node_id": node_id,
                            },
                            exclude_user=user["id"],
                        )
                else:
                    # Unknown message type
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                    })
                    
            except asyncio.TimeoutError:
                # Send heartbeat if no message received
                await websocket.send_json({
                    "type": "ping",
                    "timestamp": time.time(),
                })
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        # Log error but don't crash
        print(f"WebSocket error: {e}")
    finally:
        # Clean up connection
        manager.disconnect(websocket, document_id)
        await manager.broadcast_user_left(document_id, user["id"], user["display_name"])
