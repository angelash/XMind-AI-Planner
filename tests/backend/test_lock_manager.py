"""Tests for node lock manager (LOCK-01)."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.lock_manager import (
    LOCK_TIMEOUT_SECONDS,
    LockManager,
    NodeLock,
    get_lock_manager,
    reset_lock_manager,
)


class TestNodeLock:
    """Tests for NodeLock dataclass."""

    def test_node_lock_creation(self):
        """Test creating a NodeLock instance."""
        lock = NodeLock(
            node_id="node-123",
            document_id="doc-456",
            user_id="user-789",
            user_name="Test User",
        )
        assert lock.node_id == "node-123"
        assert lock.document_id == "doc-456"
        assert lock.user_id == "user-789"
        assert lock.user_name == "Test User"
        assert lock.locked_at > 0
        assert lock.last_activity > 0

    def test_node_lock_is_expired(self):
        """Test lock expiration check."""
        lock = NodeLock(
            node_id="node-123",
            document_id="doc-456",
            user_id="user-789",
            user_name="Test User",
        )
        # Fresh lock should not be expired
        assert lock.is_expired() is False

    def test_node_lock_is_expired_true(self):
        """Test that expired lock is detected."""
        lock = NodeLock(
            node_id="node-123",
            document_id="doc-456",
            user_id="user-789",
            user_name="Test User",
            locked_at=1000.0,
            last_activity=1000.0,  # Old timestamp
        )
        # Set last_activity to be older than timeout
        lock.last_activity = time.time() - LOCK_TIMEOUT_SECONDS - 1
        assert lock.is_expired() is True

    def test_node_lock_refresh(self):
        """Test refreshing lock activity."""
        lock = NodeLock(
            node_id="node-123",
            document_id="doc-456",
            user_id="user-789",
            user_name="Test User",
        )
        old_activity = lock.last_activity
        time.sleep(0.01)  # Small delay
        lock.refresh()
        assert lock.last_activity > old_activity


class TestLockManager:
    """Tests for LockManager class."""

    @pytest.fixture
    def manager(self):
        """Create a fresh LockManager for each test."""
        reset_lock_manager()
        return LockManager()

    def test_get_instance_singleton(self):
        """Test that get_lock_manager returns singleton."""
        reset_lock_manager()
        manager1 = get_lock_manager()
        manager2 = get_lock_manager()
        assert manager1 is manager2

    def test_lock_node_success(self, manager):
        """Test successfully locking a node."""
        mock_broadcast = AsyncMock()
        manager._broadcast_lock_event = mock_broadcast

        async def run_test():
            result = await manager.lock_node(
                document_id="doc-123",
                node_id="node-456",
                user_id="user-789",
                user_name="Test User",
            )
            assert result["success"] is True
            assert result["node_id"] == "node-456"
            assert result["user_id"] == "user-789"
            assert "locked_at" in result
            mock_broadcast.assert_called_once()

        asyncio.run(run_test())

    def test_lock_node_already_locked_same_user(self, manager):
        """Test locking a node already locked by same user."""
        mock_broadcast = AsyncMock()
        manager._broadcast_lock_event = mock_broadcast

        async def run_test():
            # First lock
            await manager.lock_node("doc-123", "node-456", "user-789", "Test User")
            mock_broadcast.reset_mock()

            # Second lock from same user - should refresh
            result = await manager.lock_node(
                document_id="doc-123",
                node_id="node-456",
                user_id="user-789",
                user_name="Test User",
            )
            assert result["success"] is True
            # No broadcast for refresh
            mock_broadcast.assert_not_called()

        asyncio.run(run_test())

    def test_lock_node_already_locked_other_user(self, manager):
        """Test locking a node already locked by another user."""
        mock_broadcast = AsyncMock()
        manager._broadcast_lock_event = mock_broadcast

        async def run_test():
            # First lock by user 1
            await manager.lock_node("doc-123", "node-456", "user-1", "User One")
            mock_broadcast.reset_mock()

            # Second lock from user 2 - should fail
            result = await manager.lock_node(
                document_id="doc-123",
                node_id="node-456",
                user_id="user-2",
                user_name="User Two",
            )
            assert result["success"] is False
            assert result["locked_by"] == "user-1"
            assert result["locked_by_name"] == "User One"

        asyncio.run(run_test())

    def test_lock_node_expired_lock(self, manager):
        """Test that expired lock is replaced."""
        mock_broadcast = AsyncMock()
        manager._broadcast_lock_event = mock_broadcast

        async def run_test():
            # First lock
            result1 = await manager.lock_node("doc-123", "node-456", "user-1", "User One")
            # Manually expire the lock
            manager._locks["doc-123"]["node-456"].last_activity = time.time() - LOCK_TIMEOUT_SECONDS - 1
            mock_broadcast.reset_mock()

            # Second lock should succeed because first is expired
            result2 = await manager.lock_node(
                document_id="doc-123",
                node_id="node-456",
                user_id="user-2",
                user_name="User Two",
            )
            assert result2["success"] is True
            assert result2["user_id"] == "user-2"
            # Should broadcast unlock and lock
            assert mock_broadcast.call_count == 2

        asyncio.run(run_test())

    def test_unlock_node_success(self, manager):
        """Test successfully unlocking a node."""
        mock_broadcast = AsyncMock()
        manager._broadcast_lock_event = mock_broadcast

        async def run_test():
            # Lock first
            await manager.lock_node("doc-123", "node-456", "user-789", "Test User")
            mock_broadcast.reset_mock()

            # Unlock
            result = await manager.unlock_node("doc-123", "node-456", "user-789")
            assert result["success"] is True
            assert result["node_id"] == "node-456"
            mock_broadcast.assert_called_once()

        asyncio.run(run_test())

    def test_unlock_node_not_owner(self, manager):
        """Test unlocking a node locked by another user."""
        mock_broadcast = AsyncMock()
        manager._broadcast_lock_event = mock_broadcast

        async def run_test():
            # Lock by user 1
            await manager.lock_node("doc-123", "node-456", "user-1", "User One")

            # Try to unlock by user 2
            result = await manager.unlock_node("doc-123", "node-456", "user-2")
            assert result["success"] is False
            assert result["reason"] == "not_owner"

        asyncio.run(run_test())

    def test_unlock_node_not_locked(self, manager):
        """Test unlocking a node that isn't locked."""
        async def run_test():
            # First create a lock for the document so we get "not_locked" instead of "no_locks"
            await manager.lock_node("doc-123", "node-other", "user-1", "User One")
            result = await manager.unlock_node("doc-123", "node-456", "user-789")
            assert result["success"] is False
            assert result["reason"] == "not_locked"

        asyncio.run(run_test())

    def test_unlock_node_no_locks(self, manager):
        """Test unlocking when no locks exist for document."""
        async def run_test():
            result = await manager.unlock_node("doc-123", "node-456", "user-789")
            assert result["success"] is False
            assert result["reason"] == "no_locks"

        asyncio.run(run_test())

    def test_release_user_locks(self, manager):
        """Test releasing all locks for a user."""
        mock_broadcast = AsyncMock()
        manager._broadcast_lock_event = mock_broadcast

        async def run_test():
            # Lock multiple nodes for same user
            await manager.lock_node("doc-123", "node-1", "user-1", "User One")
            await manager.lock_node("doc-123", "node-2", "user-1", "User One")
            await manager.lock_node("doc-123", "node-3", "user-2", "User Two")

            # Release all locks for user 1
            released = await manager.release_user_locks("doc-123", "user-1")
            assert set(released) == {"node-1", "node-2"}

            # User 2's lock should still exist
            locks = manager.get_document_locks("doc-123")
            assert len(locks) == 1
            assert locks[0]["node_id"] == "node-3"

        asyncio.run(run_test())

    def test_release_user_locks_empty(self, manager):
        """Test releasing locks when user has none."""
        async def run_test():
            released = await manager.release_user_locks("doc-123", "user-789")
            assert released == []

        asyncio.run(run_test())

    def test_get_document_locks(self, manager):
        """Test getting all locks for a document."""
        async def run_test():
            # Lock multiple nodes
            await manager.lock_node("doc-123", "node-1", "user-1", "User One")
            await manager.lock_node("doc-123", "node-2", "user-2", "User Two")

            locks = manager.get_document_locks("doc-123")
            assert len(locks) == 2
            node_ids = {l["node_id"] for l in locks}
            assert node_ids == {"node-1", "node-2"}

        asyncio.run(run_test())

    def test_get_document_locks_empty(self, manager):
        """Test getting locks for document with none."""
        locks = manager.get_document_locks("doc-123")
        assert locks == []

    def test_get_document_locks_filters_expired(self, manager):
        """Test that get_document_locks filters expired locks."""
        async def run_test():
            # Lock a node
            await manager.lock_node("doc-123", "node-1", "user-1", "User One")
            # Expire it
            manager._locks["doc-123"]["node-1"].last_activity = time.time() - LOCK_TIMEOUT_SECONDS - 1

            locks = manager.get_document_locks("doc-123")
            assert locks == []

            # Lock should be cleaned up
            assert "node-1" not in manager._locks["doc-123"]

        asyncio.run(run_test())

    def test_cleanup_expired_locks(self, manager):
        """Test cleaning up expired locks."""
        async def run_test():
            # Lock two nodes
            await manager.lock_node("doc-123", "node-1", "user-1", "User One")
            await manager.lock_node("doc-123", "node-2", "user-2", "User Two")

            # Expire first lock
            manager._locks["doc-123"]["node-1"].last_activity = time.time() - LOCK_TIMEOUT_SECONDS - 1

            # Cleanup
            cleaned = await manager.cleanup_expired_locks()
            assert cleaned == 1

            # Only second lock should remain
            locks = manager.get_document_locks("doc-123")
            assert len(locks) == 1
            assert locks[0]["node_id"] == "node-2"

        asyncio.run(run_test())

    def test_multiple_documents(self, manager):
        """Test locking nodes across multiple documents."""
        async def run_test():
            await manager.lock_node("doc-1", "node-1", "user-1", "User One")
            await manager.lock_node("doc-2", "node-2", "user-1", "User One")

            locks1 = manager.get_document_locks("doc-1")
            locks2 = manager.get_document_locks("doc-2")

            assert len(locks1) == 1
            assert len(locks2) == 1

        asyncio.run(run_test())

    def test_user_locks_tracking(self, manager):
        """Test that user locks are tracked correctly."""
        async def run_test():
            await manager.lock_node("doc-123", "node-1", "user-1", "User One")
            await manager.lock_node("doc-123", "node-2", "user-1", "User One")

            assert "node-1" in manager._user_locks.get("user-1", [])
            assert "node-2" in manager._user_locks.get("user-1", [])

            # Unlock one
            await manager.unlock_node("doc-123", "node-1", "user-1")

            assert "node-1" not in manager._user_locks.get("user-1", [])
            assert "node-2" in manager._user_locks.get("user-1", [])

        asyncio.run(run_test())


class TestLockManagerBroadcast:
    """Tests for lock broadcast integration."""

    @pytest.fixture
    def manager(self):
        """Create a fresh LockManager for each test."""
        reset_lock_manager()
        manager = LockManager()
        # Mock the broadcast
        manager._broadcast_lock_event = AsyncMock()
        return manager

    def test_lock_broadcasts_event(self, manager):
        """Test that locking a node broadcasts an event."""
        async def run_test():
            await manager.lock_node("doc-123", "node-456", "user-1", "User One")
            manager._broadcast_lock_event.assert_called_once()
            call_args = manager._broadcast_lock_event.call_args
            assert call_args[0][0] == "doc-123"
            assert call_args[0][2] == "node_locked"

        asyncio.run(run_test())

    def test_unlock_broadcasts_event(self, manager):
        """Test that unlocking a node broadcasts an event."""
        async def run_test():
            await manager.lock_node("doc-123", "node-456", "user-1", "User One")
            manager._broadcast_lock_event.reset_mock()

            await manager.unlock_node("doc-123", "node-456", "user-1")
            manager._broadcast_lock_event.assert_called_once()
            call_args = manager._broadcast_lock_event.call_args
            assert call_args[0][0] == "doc-123"
            assert call_args[0][2] == "node_unlocked"

        asyncio.run(run_test())