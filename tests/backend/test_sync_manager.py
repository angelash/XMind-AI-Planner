"""Tests for cloud sync manager (GAP-06)."""
from __future__ import annotations

import time

import pytest

from app.services.sync_manager import (
    NodeChange,
    SyncConflict,
    SyncManager,
    get_sync_manager,
    reset_sync_manager,
)


class TestNodeChange:
    """Tests for NodeChange dataclass."""

    def test_node_change_creation(self):
        """Test creating a NodeChange instance."""
        old_content = {"id": "node-1", "text": "Old text"}
        new_content = {"id": "node-1", "text": "New text"}
        
        change = NodeChange(
            node_id="node-1",
            user_id="user-123",
            user_name="Test User",
            old_content=old_content,
            new_content=new_content,
        )
        
        assert change.node_id == "node-1"
        assert change.user_id == "user-123"
        assert change.user_name == "Test User"
        assert change.old_content == old_content
        assert change.new_content == new_content
        assert change.timestamp > 0
        assert change.conflict_resolved is False


class TestSyncConflict:
    """Tests for SyncConflict dataclass."""

    def test_sync_conflict_creation(self):
        """Test creating a SyncConflict instance."""
        users = [
            {"user_id": "user-1", "user_name": "User One", "timestamp": time.time() - 10},
            {"user_id": "user-2", "user_name": "User Two", "timestamp": time.time()},
        ]
        
        conflict = SyncConflict(
            node_id="node-1",
            conflicting_users=users,
        )
        
        assert conflict.node_id == "node-1"
        assert len(conflict.conflicting_users) == 2
        assert conflict.winning_user is None
        assert conflict.resolved_at is None


class TestSyncManager:
    """Tests for SyncManager class."""

    @pytest.fixture
    def manager(self):
        """Create a fresh SyncManager for each test."""
        reset_sync_manager()
        return SyncManager()

    def test_get_instance_singleton(self):
        """Test that get_sync_manager returns singleton."""
        reset_sync_manager()
        manager1 = get_sync_manager()
        manager2 = get_sync_manager()
        assert manager1 is manager2

    def test_record_change(self, manager):
        """Test recording a node change."""
        old_content = {"id": "node-1", "text": "Old"}
        new_content = {"id": "node-1", "text": "New"}
        
        change = manager.record_change(
            document_id="doc-123",
            node_id="node-1",
            user_id="user-456",
            user_name="Test User",
            old_content=old_content,
            new_content=new_content,
        )
        
        assert change.node_id == "node-1"
        assert change.user_id == "user-456"
        
        # Verify it's in pending changes
        pending = manager.get_pending_changes("doc-123")
        assert "node-1" in pending
        assert pending["node-1"] is change

    def test_get_pending_changes_for_document(self, manager):
        """Test getting all pending changes for a document."""
        manager.record_change(
            "doc-123", "node-1", "user-1", "User One",
            None, {"id": "node-1", "text": "A"}
        )
        manager.record_change(
            "doc-123", "node-2", "user-1", "User One",
            None, {"id": "node-2", "text": "B"}
        )
        
        changes = manager.get_pending_changes("doc-123")
        assert len(changes) == 2
        assert "node-1" in changes
        assert "node-2" in changes

    def test_get_pending_changes_for_node(self, manager):
        """Test getting pending changes for a specific node."""
        manager.record_change(
            "doc-123", "node-1", "user-1", "User One",
            None, {"id": "node-1", "text": "A"}
        )
        manager.record_change(
            "doc-123", "node-2", "user-1", "User One",
            None, {"id": "node-2", "text": "B"}
        )
        
        node_changes = manager.get_pending_changes("doc-123", "node-1")
        assert isinstance(node_changes, NodeChange)
        assert node_changes.node_id == "node-1"

    def test_get_pending_changes_empty_document(self, manager):
        """Test getting pending changes for non-existent document."""
        changes = manager.get_pending_changes("doc-999")
        assert changes == {}

    def test_get_pending_changes_empty_node(self, manager):
        """Test getting pending changes for non-existent node."""
        manager.record_change(
            "doc-123", "node-1", "user-1", "User One",
            None, {"id": "node-1", "text": "A"}
        )
        
        node_changes = manager.get_pending_changes("doc-123", "node-999")
        assert node_changes == []

    def test_detect_conflict_different_users(self, manager):
        """Test conflict detection when different users edit same node."""
        # User 1 edits node-1
        manager.record_change(
            "doc-123", "node-1", "user-1", "User One",
            None, {"id": "node-1", "text": "User 1's edit"}
        )
        
        # User 2 tries to edit same node
        conflict = manager.detect_conflict(
            "doc-123", "node-1", "user-2", "User Two"
        )
        
        assert conflict is not None
        assert conflict.node_id == "node-1"
        assert len(conflict.conflicting_users) == 2
        user_ids = [u["user_id"] for u in conflict.conflicting_users]
        assert "user-1" in user_ids
        assert "user-2" in user_ids

    def test_detect_conflict_same_user_no_conflict(self, manager):
        """Test that same user editing same node is not a conflict."""
        manager.record_change(
            "doc-123", "node-1", "user-1", "User One",
            None, {"id": "node-1", "text": "First edit"}
        )
        
        conflict = manager.detect_conflict(
            "doc-123", "node-1", "user-1", "User One"
        )
        
        assert conflict is None

    def test_detect_conflict_no_pending_change(self, manager):
        """Test conflict detection when no pending change exists."""
        conflict = manager.detect_conflict(
            "doc-123", "node-1", "user-1", "User One"
        )
        
        assert conflict is None

    def test_resolve_conflict_lww_current_user_wins(self, manager):
        """Test LWW resolution when current user has latest timestamp."""
        users = [
            {"user_id": "user-1", "user_name": "User One", "timestamp": time.time() - 10},
            {"user_id": "user-2", "user_name": "User Two", "timestamp": time.time()},
        ]
        
        conflict = SyncConflict(
            node_id="node-1",
            conflicting_users=users,
        )
        
        new_content = {"id": "node-1", "text": "User 2's edit"}
        
        winner_content, notification = manager.resolve_conflict_lww(
            conflict, "doc-123", new_content, "user-2", "User Two"
        )
        
        assert winner_content == new_content
        assert notification["type"] == "conflict_lost"
        assert notification["winner"]["user_id"] == "user-2"
        assert conflict.winning_user == users[1]

    def test_resolve_conflict_lww_other_user_wins(self, manager):
        """Test LWW resolution when other user has latest timestamp."""
        users = [
            {"user_id": "user-1", "user_name": "User One", "timestamp": time.time()},
            {"user_id": "user-2", "user_name": "User Two", "timestamp": time.time() - 10},
        ]
        
        conflict = SyncConflict(
            node_id="node-1",
            conflicting_users=users,
        )
        
        new_content = {"id": "node-1", "text": "User 2's edit"}
        
        winner_content, notification = manager.resolve_conflict_lww(
            conflict, "doc-123", new_content, "user-2", "User Two"
        )
        
        # User 2's content should be replaced (fallback since doc doesn't exist)
        assert notification["type"] == "conflict_lost"
        assert notification["winner"]["user_id"] == "user-1"
        assert conflict.winning_user == users[0]

    def test_clear_pending_changes_document(self, manager):
        """Test clearing all pending changes for a document."""
        manager.record_change("doc-123", "node-1", "user-1", "User One", None, {})
        manager.record_change("doc-123", "node-2", "user-1", "User One", None, {})
        
        assert len(manager.get_pending_changes("doc-123")) == 2
        
        manager.clear_pending_changes("doc-123")
        
        assert manager.get_pending_changes("doc-123") == {}

    def test_clear_pending_changes_node(self, manager):
        """Test clearing pending change for specific node."""
        manager.record_change("doc-123", "node-1", "user-1", "User One", None, {})
        manager.record_change("doc-123", "node-2", "user-1", "User One", None, {})
        
        assert len(manager.get_pending_changes("doc-123")) == 2
        
        manager.clear_pending_changes("doc-123", "node-1")
        
        changes = manager.get_pending_changes("doc-123")
        assert "node-1" not in changes
        assert "node-2" in changes

    def test_get_conflicts_empty(self, manager):
        """Test getting conflicts for document with no conflicts."""
        conflicts = manager.get_conflicts("doc-123")
        assert conflicts == []

    def test_clear_old_conflicts(self, manager):
        """Test clearing old conflicts from history."""
        # Create some conflicts
        users = [{"user_id": "u1", "user_name": "U1", "timestamp": time.time()}]
        conflict = SyncConflict(node_id="n1", conflicting_users=users)
        conflict.resolved_at = time.time() - 7200  # 2 hours ago
        
        if "doc-123" not in manager._conflicts:
            manager._conflicts["doc-123"] = []
        manager._conflicts["doc-123"].append(conflict)
        
        # Clear conflicts older than 1 hour
        manager.clear_old_conflicts("doc-123", older_than_seconds=3600)
        
        conflicts = manager.get_conflicts("doc-123")
        assert len(conflicts) == 0

    def test_clear_old_conflicts_keeps_recent(self, manager):
        """Test that recent conflicts are not cleared."""
        users = [{"user_id": "u1", "user_name": "U1", "timestamp": time.time()}]
        conflict = SyncConflict(node_id="n1", conflicting_users=users)
        conflict.resolved_at = time.time() - 600  # 10 minutes ago
        
        if "doc-123" not in manager._conflicts:
            manager._conflicts["doc-123"] = []
        manager._conflicts["doc-123"].append(conflict)
        
        # Clear conflicts older than 1 hour
        manager.clear_old_conflicts("doc-123", older_than_seconds=3600)
        
        conflicts = manager.get_conflicts("doc-123")
        assert len(conflicts) == 1
