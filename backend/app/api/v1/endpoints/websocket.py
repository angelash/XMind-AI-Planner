"""WebSocket endpoint for real-time document collaboration.

RT-01: WebSocket 连接管理
RT-02: 防抖保存与广播同步
LOCK-01: 节点锁定机制
GAP-06: 云端同步

Endpoint: /ws/documents/{document_id}

Features:
- Connection with JWT authentication
- Heartbeat mechanism (ping/pong)
- User presence tracking
- Message routing
- Document save with version tracking
- Node locking for collaborative editing
- Cloud sync with conflict detection and LWW resolution

Lock Feature (LOCK-01):
- Lock nodes on selection to prevent concurrent edits
- Broadcast lock state changes to all users
- Auto-release after 5 minutes of inactivity
- Release on deselection or disconnect

Cloud Sync Feature (GAP-06):
- Detects conflicts when multiple users edit same node simultaneously
- Last-Write-Wins (LWW) conflict resolution
- Notifies users when their changes are overwritten
- Tracks change history for conflict resolution
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
from app.services.lock_manager import get_lock_manager
from app.services.sync_manager import get_sync_manager
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
    """Handle document save request with cloud sync conflict resolution.
    
    Saves document content, detects conflicts, resolves with LWW,
    creates version, and notifies all users.
    
    GAP-06: 云端同步 - Conflict detection and LWW resolution
    
    Args:
        document_id: Document to save
        content: New document content
        user: User performing save
        websocket: WebSocket connection
        manager: Connection manager
    """
    sync_manager = get_sync_manager()
    
    # Get current document to detect changes
    doc = get_document(document_id)
    if doc is None:
        await websocket.send_json({
            "type": "save_error",
            "message": "Document not found",
        })
        return
    
    old_content = doc.get("content", {})
    
    # Extract modified nodes from content diff
    modified_nodes = _extract_modified_nodes(old_content, content)
    
    # Check for conflicts on modified nodes
    conflict_notifications = []
    for node_id, node_content in modified_nodes.items():
        conflict = sync_manager.detect_conflict(
            document_id, node_id, user["id"], user["display_name"]
        )
        if conflict:
            # Resolve conflict with LWW
            resolved_content, notification = sync_manager.resolve_conflict_lww(
                conflict, document_id, node_content, user["id"], user["display_name"]
            )
            # Update the content with the winning version
            content = _update_node_in_content(content, node_id, resolved_content)
            conflict_notifications.append(notification)
        else:
            # Record the change
            sync_manager.record_change(
                document_id, node_id, user["id"], user["display_name"],
                None, node_content
            )
    
    # Update document
    updated = update_document(document_id, {"content": content})
    if updated is None:
        await websocket.send_json({
            "type": "save_error",
            "message": "Failed to update document",
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
        "conflicts": conflict_notifications if conflict_notifications else None,
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
    
    # Clear pending changes after successful save
    sync_manager.clear_pending_changes(document_id)


def _extract_modified_nodes(
    old_content: dict[str, Any],
    new_content: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Extract modified nodes from content diff.
    
    Args:
        old_content: Previous document content
        new_content: New document content
        
    Returns:
        Dict mapping node_id -> node_content
    """
    modified = {}
    
    def collect_nodes(node: dict[str, Any], nodes_dict: dict[str, dict[str, Any]]) -> None:
        """Recursively collect all nodes."""
        node_id = node.get("id")
        if node_id:
            nodes_dict[node_id] = node
        children = node.get("children", [])
        if isinstance(children, list):
            for child in children:
                collect_nodes(child, nodes_dict)
    
    # Collect all nodes from both versions
    old_nodes = {}
    new_nodes = {}
    
    topic_old = old_content.get("topic")
    topic_new = new_content.get("topic")
    
    if topic_old:
        collect_nodes(topic_old, old_nodes)
    if topic_new:
        collect_nodes(topic_new, new_nodes)
    
    # Find modified nodes (different content in new version)
    for node_id, new_node in new_nodes.items():
        if node_id in old_nodes:
            old_node = old_nodes[node_id]
            # Compare key fields
            if (new_node.get("text") != old_node.get("text") or
                new_node.get("memo") != old_node.get("memo")):
                modified[node_id] = new_node
        else:
            # New node added
            modified[node_id] = new_node
    
    return modified


def _update_node_in_content(
    content: dict[str, Any],
    node_id: str,
    new_node_content: dict[str, Any],
) -> dict[str, Any]:
    """Update a specific node in document content.
    
    Args:
        content: Document content
        node_id: Node to update
        new_node_content: New node content
        
    Returns:
        Updated content dict
    """
    def update_node(node: dict[str, Any], target_id: str, new_content: dict[str, Any]) -> bool:
        """Recursively update a node by ID. Returns True if updated."""
        if node.get("id") == target_id:
            # Update text and memo
            if "text" in new_content:
                node["text"] = new_content["text"]
            if "memo" in new_content:
                node["memo"] = new_content["memo"]
            return True
        
        children = node.get("children", [])
        if isinstance(children, list):
            for child in children:
                if update_node(child, target_id, new_content):
                    return True
        return False
    
    topic = content.get("topic")
    if topic:
        update_node(topic, node_id, new_node_content)
    
    return content


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
    3. Server sends initial state (user list, locks, content)
    4. Client/server exchange messages
    5. Server sends heartbeat every 30 seconds
    6. On disconnect, server notifies other users and releases locks
    
    Message types (client -> server):
    - {"type": "ping"} -> Heartbeat request
    - {"type": "update", "content": {...}} -> Document update (broadcast only)
    - {"type": "save", "content": {...}} -> Document save (persist + broadcast)
    - {"type": "cursor", "node_id": "..."} -> Cursor position
    - {"type": "lock_node", "node_id": "..."} -> Request node lock
    - {"type": "unlock_node", "node_id": "..."} -> Release node lock
    - {"type": "get_locks"} -> Get all locks for document
    
    Message types (server -> client):
    - {"type": "pong", "timestamp": ...} -> Heartbeat response
    - {"type": "connected", ...} -> Connection confirmed
    - {"type": "user_joined", ...} -> User joined notification
    - {"type": "user_left", ...} -> User left notification
    - {"type": "update", ...} -> Document update broadcast
    - {"type": "save_ok", ...} -> Save confirmation (to saver)
    - {"type": "document_saved", ...} -> Save notification (to others)
    - {"type": "cursor", ...} -> Cursor position broadcast
    - {"type": "node_locked", ...} -> Node locked notification
    - {"type": "node_unlocked", ...} -> Node unlocked notification
    - {"type": "lock_result", ...} -> Lock operation result
    - {"type": "locks", ...} -> Current locks for document
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
    lock_manager = get_lock_manager()
    await manager.connect(websocket, document_id, user["id"], user["display_name"])
    
    # Send initial state
    await websocket.send_json({
        "type": "connected",
        "document_id": document_id,
        "users": manager.get_document_users(document_id),
        "locks": lock_manager.get_document_locks(document_id),
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
                elif msg_type == "lock_node":
                    # Lock a node for editing
                    node_id = message.get("node_id")
                    if node_id:
                        result = await lock_manager.lock_node(
                            document_id=document_id,
                            node_id=node_id,
                            user_id=user["id"],
                            user_name=user["display_name"],
                        )
                        await websocket.send_json({
                            "type": "lock_result",
                            "success": result["success"],
                            "node_id": node_id,
                            **result,
                        })
                elif msg_type == "unlock_node":
                    # Unlock a node
                    node_id = message.get("node_id")
                    if node_id:
                        result = await lock_manager.unlock_node(
                            document_id=document_id,
                            node_id=node_id,
                            user_id=user["id"],
                        )
                        await websocket.send_json({
                            "type": "lock_result",
                            "success": result["success"],
                            "node_id": node_id,
                            **result,
                        })
                elif msg_type == "get_locks":
                    # Get all locks for the document
                    locks = lock_manager.get_document_locks(document_id)
                    await websocket.send_json({
                        "type": "locks",
                        "document_id": document_id,
                        "locks": locks,
                    })
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
        # Release all locks held by this user
        released = await lock_manager.release_user_locks(document_id, user["id"])
        # Notify other users
        await manager.broadcast_user_left(document_id, user["id"], user["display_name"])
