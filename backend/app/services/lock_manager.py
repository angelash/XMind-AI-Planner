"""Node lock manager for collaborative editing.

LOCK-01: 节点锁定机制

Provides node-level locking to prevent concurrent editing conflicts:
- Lock on node selection
- Lock broadcast to other users
- Auto-release after inactivity (5 minutes)
- Release on deselection
- Release on disconnect
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from app.services.websocket_manager import get_connection_manager


# Lock timeout in seconds (5 minutes)
LOCK_TIMEOUT_SECONDS = 300


@dataclass
class NodeLock:
    """Represents a lock on a node."""
    node_id: str
    document_id: str
    user_id: str
    user_name: str
    locked_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    
    def is_expired(self) -> bool:
        """Check if lock has expired due to inactivity."""
        return time.time() - self.last_activity > LOCK_TIMEOUT_SECONDS
    
    def refresh(self) -> None:
        """Refresh the lock's activity timestamp."""
        self.last_activity = time.time()


class LockManager:
    """Manages node locks for collaborative editing.
    
    Features:
    - Lock nodes on selection
    - Broadcast lock state changes
    - Auto-release after inactivity
    - Release on disconnect
    """
    
    def __init__(self):
        # document_id -> {node_id: NodeLock}
        self._locks: dict[str, dict[str, NodeLock]] = {}
        # user_id -> list of node_ids they have locked
        self._user_locks: dict[str, list[str]] = {}
    
    @property
    def locks(self) -> dict[str, dict[str, NodeLock]]:
        """Return all locks for testing."""
        return self._locks
    
    async def lock_node(
        self,
        document_id: str,
        node_id: str,
        user_id: str,
        user_name: str,
    ) -> dict[str, Any]:
        """Lock a node for a user.
        
        Args:
            document_id: Document containing the node
            node_id: Node to lock
            user_id: User requesting the lock
            user_name: Display name of the user
            
        Returns:
            Result dict with success status and lock info
        """
        if document_id not in self._locks:
            self._locks[document_id] = {}
        
        locks = self._locks[document_id]
        
        # Check if node is already locked
        if node_id in locks:
            existing_lock = locks[node_id]
            # Check if lock is expired
            if existing_lock.is_expired():
                # Release expired lock
                await self._release_lock(document_id, node_id)
            elif existing_lock.user_id == user_id:
                # Same user - refresh the lock
                existing_lock.refresh()
                return {
                    "success": True,
                    "node_id": node_id,
                    "user_id": user_id,
                    "locked_at": existing_lock.locked_at,
                    "last_activity": existing_lock.last_activity,
                }
            else:
                # Locked by another user
                return {
                    "success": False,
                    "node_id": node_id,
                    "locked_by": existing_lock.user_id,
                    "locked_by_name": existing_lock.user_name,
                    "locked_at": existing_lock.locked_at,
                }
        
        # Create new lock
        lock = NodeLock(
            node_id=node_id,
            document_id=document_id,
            user_id=user_id,
            user_name=user_name,
        )
        locks[node_id] = lock
        
        # Track user locks
        if user_id not in self._user_locks:
            self._user_locks[user_id] = []
        if node_id not in self._user_locks[user_id]:
            self._user_locks[user_id].append(node_id)
        
        # Broadcast lock event
        await self._broadcast_lock_event(document_id, lock, "node_locked")
        
        return {
            "success": True,
            "node_id": node_id,
            "user_id": user_id,
            "locked_at": lock.locked_at,
        }
    
    async def unlock_node(
        self,
        document_id: str,
        node_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Unlock a node.
        
        Args:
            document_id: Document containing the node
            node_id: Node to unlock
            user_id: User releasing the lock
            
        Returns:
            Result dict with success status
        """
        if document_id not in self._locks:
            return {"success": False, "reason": "no_locks"}
        
        locks = self._locks[document_id]
        
        if node_id not in locks:
            return {"success": False, "reason": "not_locked"}
        
        lock = locks[node_id]
        
        # Only the lock owner can unlock
        if lock.user_id != user_id:
            return {
                "success": False,
                "reason": "not_owner",
                "locked_by": lock.user_id,
            }
        
        # Release the lock
        await self._release_lock(document_id, node_id)
        
        return {"success": True, "node_id": node_id}
    
    async def release_user_locks(
        self,
        document_id: str,
        user_id: str,
    ) -> list[str]:
        """Release all locks held by a user in a document.
        
        Called when user disconnects or switches documents.
        
        Args:
            document_id: Document to release locks in
            user_id: User whose locks to release
            
        Returns:
            List of released node IDs
        """
        if document_id not in self._locks:
            return []
        
        released = []
        locks = self._locks[document_id]
        
        # Find all locks by this user
        nodes_to_release = [
            node_id for node_id, lock in locks.items()
            if lock.user_id == user_id
        ]
        
        for node_id in nodes_to_release:
            await self._release_lock(document_id, node_id)
            released.append(node_id)
        
        return released
    
    def get_document_locks(self, document_id: str) -> list[dict[str, Any]]:
        """Get all active locks for a document.
        
        Args:
            document_id: Document to query
            
        Returns:
            List of lock info dicts
        """
        if document_id not in self._locks:
            return []
        
        # Filter out expired locks
        locks = self._locks[document_id]
        active_locks = []
        expired_nodes = []
        
        for node_id, lock in locks.items():
            if lock.is_expired():
                expired_nodes.append(node_id)
            else:
                active_locks.append({
                    "node_id": node_id,
                    "user_id": lock.user_id,
                    "user_name": lock.user_name,
                    "locked_at": lock.locked_at,
                })
        
        # Clean up expired locks (sync, will be broadcast by next caller)
        for node_id in expired_nodes:
            del locks[node_id]
        
        return active_locks
    
    async def cleanup_expired_locks(self) -> int:
        """Clean up all expired locks across all documents.
        
        Returns:
            Number of locks cleaned up
        """
        cleaned = 0
        for document_id in list(self._locks.keys()):
            locks = self._locks[document_id]
            expired = [
                node_id for node_id, lock in locks.items()
                if lock.is_expired()
            ]
            for node_id in expired:
                await self._release_lock(document_id, node_id)
                cleaned += 1
        return cleaned
    
    async def _release_lock(self, document_id: str, node_id: str) -> None:
        """Internal method to release a lock."""
        if document_id not in self._locks:
            return
        
        locks = self._locks[document_id]
        if node_id not in locks:
            return
        
        lock = locks.pop(node_id)
        
        # Remove from user locks
        if lock.user_id in self._user_locks:
            if node_id in self._user_locks[lock.user_id]:
                self._user_locks[lock.user_id].remove(node_id)
        
        # Broadcast unlock event
        await self._broadcast_lock_event(document_id, lock, "node_unlocked")
        
        # Clean up empty document entries
        if not locks:
            del self._locks[document_id]
    
    async def _broadcast_lock_event(
        self,
        document_id: str,
        lock: NodeLock,
        event_type: str,
    ) -> None:
        """Broadcast lock state change to document users."""
        manager = get_connection_manager()
        message = {
            "type": event_type,
            "node_id": lock.node_id,
            "user_id": lock.user_id,
            "user_name": lock.user_name,
            "timestamp": time.time(),
        }
        await manager.broadcast_to_document(
            document_id,
            message,
            exclude_user=None,  # Notify everyone including lock owner
        )


# Singleton instance
_manager: LockManager | None = None


def get_lock_manager() -> LockManager:
    """Get the singleton LockManager instance."""
    global _manager
    if _manager is None:
        _manager = LockManager()
    return _manager


def reset_lock_manager() -> None:
    """Reset the singleton LockManager (for testing)."""
    global _manager
    _manager = None
