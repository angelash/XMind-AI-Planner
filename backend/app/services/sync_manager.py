"""Cloud sync manager with conflict detection and resolution.

GAP-06: 云端同步

Provides cloud sync functionality with:
- Conflict detection when multiple users edit simultaneously
- Last-Write-Wins (LWW) conflict resolution
- Change tracking
- Conflict notifications to users

This is a foundation for more sophisticated OT/CRDT handling in GAP-07.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.services.document_store import get_document, update_document


@dataclass
class NodeChange:
    """Tracks changes to a specific node."""
    node_id: str
    user_id: str
    user_name: str
    old_content: dict[str, Any] | None
    new_content: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    conflict_resolved: bool = False


@dataclass
class SyncConflict:
    """Represents a detected conflict."""
    node_id: str
    conflicting_users: list[dict[str, str]]  # [{user_id, user_name, timestamp}]
    winning_user: dict[str, str] | None = None  # LWW winner
    resolved_at: float | None = None


class SyncManager:
    """Manages cloud sync with conflict detection and resolution.
    
    Tracks document changes and provides:
    - Conflict detection (same node edited by multiple users)
    - LWW conflict resolution
    - Change history
    - Conflict notifications
    """
    
    def __init__(self):
        # document_id -> {node_id: NodeChange}
        self._pending_changes: dict[str, dict[str, NodeChange]] = {}
        # document_id -> list of SyncConflict
        self._conflicts: dict[str, list[SyncConflict]] = {}
    
    def get_pending_changes(
        self,
        document_id: str,
        node_id: str | None = None,
    ) -> dict[str, NodeChange] | list[NodeChange]:
        """Get pending changes for a document or specific node.
        
        Args:
            document_id: Document to query
            node_id: Optional node to filter
            
        Returns:
            All pending changes, or list for specific node
        """
        if document_id not in self._pending_changes:
            return {} if node_id is None else []
        
        changes = self._pending_changes[document_id]
        if node_id:
            return changes.get(node_id, [])
        return changes
    
    def record_change(
        self,
        document_id: str,
        node_id: str,
        user_id: str,
        user_name: str,
        old_content: dict[str, Any] | None,
        new_content: dict[str, Any],
    ) -> NodeChange:
        """Record a node change and check for conflicts.
        
        Args:
            document_id: Document being edited
            node_id: Node that was changed
            user_id: User making the change
            user_name: Display name
            old_content: Content before change
            new_content: Content after change
            
        Returns:
            The NodeChange that was recorded
        """
        change = NodeChange(
            node_id=node_id,
            user_id=user_id,
            user_name=user_name,
            old_content=old_content,
            new_content=new_content,
        )
        
        if document_id not in self._pending_changes:
            self._pending_changes[document_id] = {}
        
        self._pending_changes[document_id][node_id] = change
        
        return change
    
    def detect_conflict(
        self,
        document_id: str,
        node_id: str,
        user_id: str,
        user_name: str,
    ) -> SyncConflict | None:
        """Detect if there's a conflict on a node.
        
        Args:
            document_id: Document to check
            node_id: Node to check
            user_id: User attempting to edit
            user_name: Display name
            
        Returns:
            SyncConflict if conflict detected, None otherwise
        """
        if document_id not in self._pending_changes:
            return None
        
        changes = self._pending_changes[document_id]
        if node_id not in changes:
            return None
        
        existing_change = changes[node_id]
        
        # No conflict if same user
        if existing_change.user_id == user_id:
            return None
        
        # Conflict detected: different user edited same node
        conflict = SyncConflict(
            node_id=node_id,
            conflicting_users=[
                {
                    "user_id": existing_change.user_id,
                    "user_name": existing_change.user_name,
                    "timestamp": existing_change.timestamp,
                },
                {
                    "user_id": user_id,
                    "user_name": user_name,
                    "timestamp": time.time(),
                },
            ],
        )
        
        return conflict
    
    def resolve_conflict_lww(
        self,
        conflict: SyncConflict,
        document_id: str,
        new_content: dict[str, Any],
        user_id: str,
        user_name: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Resolve conflict using Last-Write-Wins (LWW) strategy.
        
        Args:
            conflict: The conflict to resolve
            document_id: Document being edited
            new_content: New content being saved
            user_id: User saving now
            user_name: Display name
            
        Returns:
            Tuple of (winning_content, loser_notification_data)
        """
        # LWW: Latest timestamp wins
        latest = max(conflict.conflicting_users, key=lambda u: u["timestamp"])
        
        winner_user_id = latest["user_id"]
        
        if winner_user_id == user_id:
            # Current user wins - their content is applied
            winner_content = new_content
            loser_notification = {
                "type": "conflict_lost",
                "node_id": conflict.node_id,
                "winner": {
                    "user_id": user_id,
                    "user_name": user_name,
                    "timestamp": time.time(),
                },
                "reason": "Your changes were overwritten by a later edit",
            }
        else:
            # Someone else wins - load their content from database
            doc = get_document(document_id)
            if doc is None:
                # Fallback: use current content
                winner_content = new_content
            else:
                # Extract node content from document
                winner_content = self._extract_node_content(doc.get("content", {}), conflict.node_id)
                if winner_content is None:
                    # Fallback: use current content
                    winner_content = new_content
            
            # Notify current user they lost
            loser_notification = {
                "type": "conflict_lost",
                "node_id": conflict.node_id,
                "winner": latest,
                "reason": "Your changes were overwritten by a later edit",
            }
        
        # Update conflict with winner info
        conflict.winning_user = latest
        conflict.resolved_at = time.time()
        
        # Store conflict for reference
        if document_id not in self._conflicts:
            self._conflicts[document_id] = []
        self._conflicts[document_id].append(conflict)
        
        return winner_content, loser_notification
    
    def _extract_node_content(
        self,
        doc_content: dict[str, Any],
        node_id: str,
    ) -> dict[str, Any] | None:
        """Extract a specific node's content from document.
        
        Args:
            doc_content: Full document content
            node_id: Node ID to extract
            
        Returns:
            Node content dict or None if not found
        """
        def find_node(node: dict[str, Any], target_id: str) -> dict[str, Any] | None:
            """Recursively find a node by ID."""
            if node.get("id") == target_id:
                return node
            children = node.get("children", [])
            if isinstance(children, list):
                for child in children:
                    result = find_node(child, target_id)
                    if result:
                        return result
            return None
        
        # MindElixir format: root is under "topic"
        topic = doc_content.get("topic")
        if not topic:
            return None
        
        return find_node(topic, node_id)
    
    def clear_pending_changes(
        self,
        document_id: str,
        node_id: str | None = None,
    ) -> None:
        """Clear pending changes after save.
        
        Args:
            document_id: Document to clear
            node_id: Optional specific node to clear
        """
        if document_id not in self._pending_changes:
            return
        
        if node_id:
            self._pending_changes[document_id].pop(node_id, None)
        else:
            self._pending_changes[document_id].clear()
    
    def get_conflicts(
        self,
        document_id: str,
    ) -> list[SyncConflict]:
        """Get conflict history for a document.
        
        Args:
            document_id: Document to query
            
        Returns:
            List of SyncConflict objects
        """
        return self._conflicts.get(document_id, [])
    
    def clear_old_conflicts(
        self,
        document_id: str,
        older_than_seconds: float = 3600,  # 1 hour default
    ) -> None:
        """Clear old conflicts from history.
        
        Args:
            document_id: Document to clean
            older_than_seconds: Remove conflicts older than this
        """
        if document_id not in self._conflicts:
            return
        
        now = time.time()
        self._conflicts[document_id] = [
            c for c in self._conflicts[document_id]
            if c.resolved_at and (now - c.resolved_at) < older_than_seconds
        ]


# Singleton instance
_manager: SyncManager | None = None


def get_sync_manager() -> SyncManager:
    """Get the singleton SyncManager instance."""
    global _manager
    if _manager is None:
        _manager = SyncManager()
    return _manager


def reset_sync_manager() -> None:
    """Reset the singleton SyncManager (for testing)."""
    global _manager
    _manager = None
