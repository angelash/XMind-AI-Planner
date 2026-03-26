"""Tests for OT manager (GAP-07)."""
from __future__ import annotations

import time

import pytest

from app.services.ot_manager import (
    Operation,
    OpType,
    OTManager,
    get_ot_manager,
    reset_ot_manager,
)


class TestOperation:
    """Tests for Operation dataclass."""

    def test_create_edit_operation(self):
        """Test creating an EDIT operation."""
        op = Operation(
            op_type=OpType.EDIT,
            node_id="node-1",
            user_id="user-123",
            user_name="Test User",
            document_id="doc-456",
            old_text="Old",
            new_text="New",
        )

        assert op.op_type == OpType.EDIT
        assert op.node_id == "node-1"
        assert op.user_id == "user-123"
        assert op.old_text == "Old"
        assert op.new_text == "New"

    def test_create_insert_operation(self):
        """Test creating an INSERT operation."""
        op = Operation(
            op_type=OpType.INSERT,
            node_id="new-node",
            user_id="user-123",
            user_name="Test User",
            document_id="doc-456",
            parent_id="parent-1",
            insert_index=0,
        )

        assert op.op_type == OpType.INSERT
        assert op.parent_id == "parent-1"
        assert op.insert_index == 0

    def test_create_delete_operation(self):
        """Test creating a DELETE operation."""
        deleted_content = {"id": "node-1", "text": "To delete"}
        op = Operation(
            op_type=OpType.DELETE,
            node_id="node-1",
            user_id="user-123",
            user_name="Test User",
            document_id="doc-456",
            deleted_content=deleted_content,
        )

        assert op.op_type == OpType.DELETE
        assert op.deleted_content == deleted_content

    def test_create_move_operation(self):
        """Test creating a MOVE operation."""
        op = Operation(
            op_type=OpType.MOVE,
            node_id="node-1",
            user_id="user-123",
            user_name="Test User",
            document_id="doc-456",
            old_parent_id="parent-1",
            new_parent_id="parent-2",
            old_index=0,
            new_index=1,
        )

        assert op.op_type == OpType.MOVE
        assert op.old_parent_id == "parent-1"
        assert op.new_parent_id == "parent-2"
        assert op.old_index == 0
        assert op.new_index == 1

    def test_operation_to_dict(self):
        """Test operation serialization to dict."""
        op = Operation(
            op_type=OpType.EDIT,
            node_id="node-1",
            user_id="user-123",
            user_name="Test User",
            document_id="doc-456",
            old_text="Old",
            new_text="New",
        )

        data = op.to_dict()
        assert data["op_type"] == "edit"
        assert data["node_id"] == "node-1"
        assert data["old_text"] == "Old"
        assert data["new_text"] == "New"

    def test_operation_from_dict(self):
        """Test operation deserialization from dict."""
        data = {
            "op_type": "edit",
            "node_id": "node-1",
            "user_id": "user-123",
            "user_name": "Test User",
            "document_id": "doc-456",
            "timestamp": time.time(),
            "old_text": "Old",
            "new_text": "New",
        }

        op = Operation.from_dict(data)
        assert op.op_type == OpType.EDIT
        assert op.node_id == "node-1"
        assert op.old_text == "Old"
        assert op.new_text == "New"


class TestOTManager:
    """Tests for OTManager class."""

    @pytest.fixture
    def manager(self):
        """Create a fresh OTManager for each test."""
        reset_ot_manager()
        return OTManager()

    def test_get_instance_singleton(self):
        """Test that get_ot_manager returns singleton."""
        reset_ot_manager()
        manager1 = get_ot_manager()
        manager2 = get_ot_manager()
        assert manager1 is manager2

    def test_record_operation(self, manager):
        """Test recording an operation."""
        op = Operation(
            op_type=OpType.EDIT,
            node_id="node-1",
            user_id="user-123",
            user_name="Test User",
            document_id="doc-456",
            old_text="Old",
            new_text="New",
        )

        manager.record_operation(op)

        history = manager.get_operation_history("doc-456")
        assert len(history) == 1
        assert history[0] is op

    def test_get_operation_history_empty(self, manager):
        """Test getting history for document with no operations."""
        history = manager.get_operation_history("doc-999")
        assert history == []

    def test_transform_no_base_ops(self, manager):
        """Test transforming operations with no base operations."""
        op = Operation(
            op_type=OpType.EDIT,
            node_id="node-1",
            user_id="user-123",
            user_name="Test User",
            document_id="doc-456",
        )

        transformed = manager.transform_operations([op], [])
        assert len(transformed) == 1
        assert transformed[0] is op

    def test_transform_different_nodes(self, manager):
        """Test transforming operations on different nodes."""
        op1 = Operation(
            op_type=OpType.EDIT,
            node_id="node-1",
            user_id="user-123",
            user_name="Test User",
            document_id="doc-456",
            old_text="Old",
            new_text="New",
        )
        base_op = Operation(
            op_type=OpType.EDIT,
            node_id="node-2",  # Different node
            user_id="user-789",
            user_name="Other User",
            document_id="doc-456",
        )

        transformed = manager.transform_operations([op1], [base_op])
        assert len(transformed) == 1
        assert transformed[0] is op1

    def test_transform_edit_edit_lww(self, manager):
        """Test EDIT vs EDIT transformation with LWW."""
        base_op = Operation(
            op_type=OpType.EDIT,
            node_id="node-1",
            user_id="user-1",
            user_name="User One",
            document_id="doc-456",
            timestamp=time.time(),
            old_text="A",
            new_text="B",
        )
        op = Operation(
            op_type=OpType.EDIT,
            node_id="node-1",
            user_id="user-2",
            user_name="User Two",
            document_id="doc-456",
            timestamp=time.time() + 1,  # Later
            old_text="B",
            new_text="C",
        )

        transformed = manager.transform_operations([op], [base_op])
        assert len(transformed) == 1
        assert transformed[0] is op  # Later op wins

    def test_transform_edit_edit_earlier_cancelled(self, manager):
        """Test that earlier EDIT is cancelled by later EDIT."""
        now = time.time()
        base_op = Operation(
            op_type=OpType.EDIT,
            node_id="node-1",
            user_id="user-1",
            user_name="User One",
            document_id="doc-456",
            timestamp=now + 1,  # Later
            old_text="A",
            new_text="B",
        )
        op = Operation(
            op_type=OpType.EDIT,
            node_id="node-1",
            user_id="user-2",
            user_name="User Two",
            document_id="doc-456",
            timestamp=now,  # Earlier
            old_text="A",
            new_text="C",
        )

        transformed = manager.transform_operations([op], [base_op])
        assert len(transformed) == 0  # Earlier op cancelled

    def test_transform_delete_wins_over_edit(self, manager):
        """Test that DELETE wins over EDIT."""
        base_op = Operation(
            op_type=OpType.DELETE,
            node_id="node-1",
            user_id="user-1",
            user_name="User One",
            document_id="doc-456",
            deleted_content={"id": "node-1"},
        )
        op = Operation(
            op_type=OpType.EDIT,
            node_id="node-1",
            user_id="user-2",
            user_name="User Two",
            document_id="doc-456",
            old_text="Old",
            new_text="New",
        )

        transformed = manager.transform_operations([op], [base_op])
        assert len(transformed) == 0  # EDIT cancelled by DELETE

    def test_transform_edit_after_delete_cancelled(self, manager):
        """Test that EDIT after DELETE is cancelled."""
        op = Operation(
            op_type=OpType.EDIT,
            node_id="node-1",
            user_id="user-1",
            user_name="User One",
            document_id="doc-456",
        )
        base_op = Operation(
            op_type=OpType.DELETE,
            node_id="node-1",
            user_id="user-2",
            user_name="User Two",
            document_id="doc-456",
            deleted_content={"id": "node-1"},
        )

        transformed = manager.transform_operations([op], [base_op])
        assert len(transformed) == 0

    def test_transform_insert_insert_adjusts_index(self, manager):
        """Test that INSERT adjusts index based on other INSERT."""
        now = time.time()
        base_op = Operation(
            op_type=OpType.INSERT,
            node_id="node-A",
            user_id="user-1",
            user_name="User One",
            document_id="doc-456",
            parent_id="parent-1",
            insert_index=0,
            timestamp=now + 1,  # Later
        )
        op = Operation(
            op_type=OpType.INSERT,
            node_id="node-B",
            user_id="user-2",
            user_name="User Two",
            document_id="doc-456",
            parent_id="parent-1",
            insert_index=0,  # Same position
            timestamp=now,  # Earlier
        )

        transformed = manager.transform_operations([op], [base_op])
        assert len(transformed) == 1
        assert transformed[0].insert_index == 1  # Adjusted

    def test_transform_insert_insert_different_parents(self, manager):
        """Test INSERT on different parents doesn't conflict."""
        base_op = Operation(
            op_type=OpType.INSERT,
            node_id="node-A",
            user_id="user-1",
            user_name="User One",
            document_id="doc-456",
            parent_id="parent-1",
            insert_index=0,
        )
        op = Operation(
            op_type=OpType.INSERT,
            node_id="node-B",
            user_id="user-2",
            user_name="User Two",
            document_id="doc-456",
            parent_id="parent-2",  # Different parent
            insert_index=0,
        )

        transformed = manager.transform_operations([op], [base_op])
        assert len(transformed) == 1
        assert transformed[0].insert_index == 0  # Not adjusted

    def test_transform_insert_after_delete_parent(self, manager):
        """Test INSERT after DELETE of parent is cancelled."""
        now = time.time()
        base_op = Operation(
            op_type=OpType.DELETE,
            node_id="parent-1",
            user_id="user-1",
            user_name="User One",
            document_id="doc-456",
            timestamp=now + 1,  # Later
            deleted_content={"id": "parent-1"},
        )
        op = Operation(
            op_type=OpType.INSERT,
            node_id="new-node",
            user_id="user-2",
            user_name="User Two",
            document_id="doc-456",
            parent_id="parent-1",  # Deleted parent
            insert_index=0,
            timestamp=now,  # Earlier
        )

        transformed = manager.transform_operations([op], [base_op])
        assert len(transformed) == 0

    def test_transform_move_deleted_node_cancelled(self, manager):
        """Test MOVE of deleted node is cancelled."""
        base_op = Operation(
            op_type=OpType.DELETE,
            node_id="node-1",
            user_id="user-1",
            user_name="User One",
            document_id="doc-456",
            deleted_content={"id": "node-1"},
        )
        op = Operation(
            op_type=OpType.MOVE,
            node_id="node-1",  # Deleted node
            user_id="user-2",
            user_name="User Two",
            document_id="doc-456",
            old_parent_id="parent-1",
            new_parent_id="parent-2",
            old_index=0,
            new_index=0,
        )

        transformed = manager.transform_operations([op], [base_op])
        assert len(transformed) == 0

    def test_transform_move_to_deleted_parent_cancelled(self, manager):
        """Test MOVE to deleted parent is cancelled."""
        now = time.time()
        base_op = Operation(
            op_type=OpType.DELETE,
            node_id="parent-2",
            user_id="user-1",
            user_name="User One",
            document_id="doc-456",
            timestamp=now + 1,  # Later
            deleted_content={"id": "parent-2"},
        )
        op = Operation(
            op_type=OpType.MOVE,
            node_id="node-1",
            user_id="user-2",
            user_name="User Two",
            document_id="doc-456",
            old_parent_id="parent-1",
            new_parent_id="parent-2",  # Deleted parent
            old_index=0,
            new_index=0,
            timestamp=now,  # Earlier
        )

        transformed = manager.transform_operations([op], [base_op])
        assert len(transformed) == 0

    def test_transform_move_move_lww(self, manager):
        """Test MOVE vs MOVE with LWW."""
        base_op = Operation(
            op_type=OpType.MOVE,
            node_id="node-1",
            user_id="user-1",
            user_name="User One",
            document_id="doc-456",
            old_parent_id="parent-1",
            new_parent_id="parent-2",
            old_index=0,
            new_index=0,
            timestamp=time.time(),
        )
        op = Operation(
            op_type=OpType.MOVE,
            node_id="node-1",
            user_id="user-2",
            user_name="User Two",
            document_id="doc-456",
            old_parent_id="parent-1",
            new_parent_id="parent-3",
            old_index=0,
            new_index=0,
            timestamp=time.time() + 1,  # Later
        )

        transformed = manager.transform_operations([op], [base_op])
        assert len(transformed) == 1
        assert transformed[0] is op  # Later move wins

    def test_get_operation_history_with_filter(self, manager):
        """Test filtering operation history by timestamp."""
        now = time.time()
        op1 = Operation(
            op_type=OpType.EDIT,
            node_id="node-1",
            user_id="user-1",
            user_name="User One",
            document_id="doc-456",
            timestamp=now - 10,
        )
        op2 = Operation(
            op_type=OpType.EDIT,
            node_id="node-2",
            user_id="user-2",
            user_name="User Two",
            document_id="doc-456",
            timestamp=now - 5,
        )
        op3 = Operation(
            op_type=OpType.EDIT,
            node_id="node-3",
            user_id="user-3",
            user_name="User Three",
            document_id="doc-456",
            timestamp=now,
        )

        manager.record_operation(op1)
        manager.record_operation(op2)
        manager.record_operation(op3)

        # Get operations from last 3 seconds
        recent = manager.get_operation_history("doc-456", since_timestamp=now - 3)
        assert len(recent) == 1
        assert recent[0].node_id == "node-3"

    def test_clear_old_operations(self, manager):
        """Test clearing old operations."""
        now = time.time()
        op1 = Operation(
            op_type=OpType.EDIT,
            node_id="node-1",
            user_id="user-1",
            user_name="User One",
            document_id="doc-456",
            timestamp=now - 7200,  # 2 hours ago
        )
        op2 = Operation(
            op_type=OpType.EDIT,
            node_id="node-2",
            user_id="user-2",
            user_name="User Two",
            document_id="doc-456",
            timestamp=now - 600,  # 10 minutes ago
        )

        manager.record_operation(op1)
        manager.record_operation(op2)

        manager.clear_old_operations("doc-456", older_than_seconds=3600)

        history = manager.get_operation_history("doc-456")
        assert len(history) == 1
        assert history[0].node_id == "node-2"

    def test_manager_create_edit_operation(self, manager):
        """Test convenience method for creating EDIT operations."""
        op = manager.create_edit_operation(
            document_id="doc-456",
            node_id="node-1",
            user_id="user-123",
            user_name="Test User",
            old_text="Old",
            new_text="New",
        )

        assert op.op_type == OpType.EDIT
        assert op.node_id == "node-1"
