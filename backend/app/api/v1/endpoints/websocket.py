"""WebSocket endpoint for real-time document collaboration.

RT-01: WebSocket 连接管理
RT-02: 防抖保存与广播同步

Endpoint: /ws/documents/{document_id}

Features:
- Connection with JWT authentication
- Heartbeat mechanism (ping/pong)
- User presence tracking
- Message routing
- Document save with version tracking
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
from app.services.document_store import (
    create_document_version,
    get_document,
    update_document,
)
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


async def handle_save(
    document_id: str,
    content: dict[str, Any],
    user: dict[str, str],
    websocket: WebSocket,
    manager: Any,
) -> None:
    """Handle document save request.
    
    Saves document content, creates version, and notifies all users.
    
    Args:
        document_id: Document to save
        content: New document content
        user: User performing save
        websocket: WebSocket connection
        manager: Connection manager
    """
    # Update document
    updated = update_document(document_id, {"content": content})
    if updated is None:
        await websocket.send_json({
            "type": "save_error",
            "message": "Document not found",
        })
        return
    
    # Create version
    version = create_document_version(
        document_id=document_id,
        title=updated.get("title", ""),
        content=content,
        changed_by=user["id"],
        summary=f"Saved via WebSocket by {user['display_name']}",
    )
    
    # Send save confirmation to the user who saved
    await websocket.send_json({
        "type": "save_ok",
        "document_id": document_id,
        "version_id": version.get("id"),
        "version_number": version.get("version_number"),
        "timestamp": time.time(),
    })
    
    # Broadcast save notification to other users
    await manager.broadcast_to_document(
        document_id,
        {
            "type": "document_saved",
            "user_id": user["id"],
            "user_name": user["display_name"],
            "version_number": version.get("version_number"),
            "timestamp": time.time(),
        },
        exclude_user=user["id"],
    )


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
    - {"type": "update", "content": {...}} -> Document update (broadcast only)
    - {"type": "save", "content": {...}} -> Document save (persist + broadcast)
    - {"type": "cursor", "node_id": "..."} -> Cursor position
    
    Message types (server -> client):
    - {"type": "pong", "timestamp": ...} -> Heartbeat response
    - {"type": "connected", ...} -> Connection confirmed
    - {"type": "user_joined", ...} -> User joined notification
    - {"type": "user_left", ...} -> User left notification
    - {"type": "update", ...} -> Document update broadcast
    - {"type": "save_ok", ...} -> Save confirmation (to saver)
    - {"type": "document_saved", ...} -> Save notification (to others)
    - {"type": "cursor", ...} -> Cursor position broadcast
    - {"type": "error", ...} -> Error message
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
        "content": document.get("content", {}),
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
                elif msg_type == "save":
                    # Document save - persist and broadcast
                    content = message.get("content", {})
                    await handle_save(document_id, content, user, websocket, manager)
                elif msg_type == "update":
                    # Document update - broadcast to others (no save)
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
