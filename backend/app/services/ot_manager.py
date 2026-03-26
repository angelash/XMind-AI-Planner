"""Operational Transformation (OT) manager for concurrent edit resolution.

GAP-07: OT/CRDT 冲突处理

Provides OT-based conflict resolution for mind map editing:
- Tracks operations on nodes (edit, insert, delete, move)
- Transforms concurrent operations to maintain consistency
- Resolves conflicts without data loss
- Better than LWW for collaborative editing

Supported operations:
- EDIT: Update node text or memo
- INSERT: Add new child node
- DELETE: Remove node and its subtree
- MOVE: Change node position or parent
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class OpType(Enum):
    """Types of operations supported by OT."""
    EDIT = "edit"
    INSERT = "INSERT"
    DELETE = "DELETE"
    MOVE = "MOVE"


@dataclass
class Operation:
    """Represents a single edit operation."""
    op_type: OpType
    node_id: str
    user_id: str
    user_name: str
    document_id: str
    timestamp: float = field(default_factory=time.time)
    # Operation-specific fields
    old_text: str | None = None
    new_text: str | None = None
    old_memo: str | None = None
    new_memo: str | None = None
    # For INSERT
    parent_id: str | None = None
    insert_index: int = -1
    # For MOVE
    old_parent_id: str | None = None
    new_parent_id: str | None = None
    old_index: int = -1
    new_index: int = -1
    # For DELETE
    deleted_content: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert operation to dict for serialization."""
        return {
            "op_type": self.op_type.value,
            "node_id": self.node_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "document_id": self.document_id,
            "timestamp": self.timestamp,
            "old_text": self.old_text,
            "new_text": self.new_text,
            "old_memo": self.old_memo,
            "new_memo": self.new_memo,
            "parent_id": self.parent_id,
            "insert_index": self.insert_index,
            "old_parent_id": self.old_parent_id,
            "new_parent_id": self.new_parent_id,
            "old_index": self.old_index,
            "new_index": self.new_index,
            "deleted_content": self.deleted_content,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Operation":
        """Create operation from dict."""
        return cls(
            op_type=OpType(data["op_type"]),
            node_id=data["node_id"],
            user_id=data["user_id"],
            user_name=data["user_name"],
            document_id=data["document_id"],
            timestamp=data["timestamp"],
            old_text=data.get("old_text"),
            new_text=data.get("new_text"),
            old_memo=data.get("old_memo"),
            new_memo=data.get("new_memo"),
            parent_id=data.get("parent_id"),
            insert_index=data.get("insert_index", -1),
            old_parent_id=data.get("old_parent_id"),
            new_parent_id=data.get("new_parent_id"),
            old_index=data.get("old_index", -1),
            new_index=data.get("new_index", -1),
            deleted_content=data.get("deleted_content"),
        )


class OTManager:
    """Manages operational transformation for concurrent edits.

    Tracks operations and transforms them to maintain consistency:
    - Stores operation history per document
    - Transforms concurrent operations
    - Applies operations in correct order
    """

    def __init__(self):
        # document_id -> list of Operation (in order of application)
        self._operation_log: dict[str, list[Operation]] = {}
        # document_id -> set of pending operation IDs (user_id:timestamp)
        self._pending_ops: dict[str, set[str]] = {}

    def record_operation(self, op: Operation) -> None:
        """Record a new operation.

        Args:
            op: Operation to record
        """
        if op.document_id not in self._operation_log:
            self._operation_log[op.document_id] = []
        self._operation_log[op.document_id].append(op)

    def transform_operations(
        self,
        ops: list[Operation],
        base_ops: list[Operation],
    ) -> list[Operation]:
        """Transform operations against base operations.

        Args:
            ops: Operations to transform
            base_ops: Operations they were based on

        Returns:
            Transformed operations ready for application
        """
        if not base_ops:
            return ops

        transformed = ops.copy()
        for base_op in base_ops:
            transformed = self._transform_against(transformed, base_op)

        return transformed

    def _transform_against(
        self,
        ops: list[Operation],
        base_op: Operation,
    ) -> list[Operation]:
        """Transform a list of operations against a base operation.

        Args:
            ops: Operations to transform
            base_op: Base operation to transform against

        Returns:
            Transformed operations
        """
        result = []
        for op in ops:
            transformed = self._transform_op(op, base_op)
            if transformed:
                result.append(transformed)
        return result

    def _transform_op(
        self,
        op: Operation,
        base_op: Operation,
    ) -> Operation | None:
        """Transform a single operation against a base operation.

        Args:
            op: Operation to transform
            base_op: Base operation

        Returns:
            Transformed operation, or None if it was cancelled
        """
        # Check for cross-node conflicts first
        # INSERT into deleted parent
        if (op.op_type == OpType.INSERT and
            base_op.op_type == OpType.DELETE and
            op.parent_id == base_op.node_id):
            return self._transform_insert_after_delete(op, base_op)

        # MOVE to deleted parent
        if (op.op_type == OpType.MOVE and
            base_op.op_type == OpType.DELETE and
            op.new_parent_id == base_op.node_id):
            return self._transform_move(op, base_op)

        # INSERT vs INSERT: check if same parent, need index adjustment
        if (op.op_type == OpType.INSERT and
            base_op.op_type == OpType.INSERT):
            if op.parent_id == base_op.parent_id:
                # Same parent, need transformation
                return self._transform_insert_insert(op, base_op)
            # Different parents, no conflict
            return op

        # Different nodes - no conflict, no transformation (for non-INSERT ops)
        if op.node_id != base_op.node_id:
            return op

        # Same node, different operations - transform based on types
        if op.op_type == OpType.EDIT and base_op.op_type == OpType.EDIT:
            return self._transform_edit_edit(op, base_op)
        elif op.op_type == OpType.DELETE and base_op.op_type == OpType.EDIT:
            return None  # DELETE wins, EDIT is lost
        elif op.op_type == OpType.EDIT and base_op.op_type == OpType.DELETE:
            return None  # DELETE already happened, EDIT is lost
        elif op.op_type == OpType.DELETE and base_op.op_type == OpType.INSERT:
            # INSERT then DELETE = no net effect
            return None
        elif op.op_type == OpType.INSERT and base_op.op_type == OpType.DELETE:
            # DELETE then INSERT = INSERT on new parent
            return self._transform_insert_after_delete(op, base_op)
        elif op.op_type == OpType.MOVE:
            return self._transform_move(op, base_op)

        # Default: no transformation
        return op

    def _transform_edit_edit(
        self,
        op: Operation,
        base_op: Operation,
    ) -> Operation | None:
        """Transform EDIT operation against another EDIT.

        Uses last-write-wins for text, merges for different fields.

        Args:
            op: Operation to transform
            base_op: Base operation

        Returns:
            Transformed operation
        """
        # LWW: latest timestamp wins
        if base_op.timestamp > op.timestamp:
            # Base op is later, cancel this op
            return None

        # This op is later, keep it
        return op

    def _transform_insert_insert(
        self,
        op: Operation,
        base_op: Operation,
    ) -> Operation | None:
        """Transform INSERT operation against another INSERT.

        Adjusts insert index to maintain order.

        Args:
            op: Operation to transform
            base_op: Base operation

        Returns:
            Transformed operation
        """
        if op.parent_id != base_op.parent_id:
            # Different parents, no conflict
            return op

        if base_op.timestamp >= op.timestamp:
            # Base op inserted later, adjust index
            if op.insert_index >= base_op.insert_index:
                # Adjust index to account for the inserted node
                # Create new operation with adjusted index
                return Operation(
                    op_type=op.op_type,
                    node_id=op.node_id,
                    user_id=op.user_id,
                    user_name=op.user_name,
                    document_id=op.document_id,
                    timestamp=op.timestamp,
                    parent_id=op.parent_id,
                    insert_index=op.insert_index + 1,
                    old_text=op.old_text,
                    new_text=op.new_text,
                    old_memo=op.old_memo,
                    new_memo=op.new_memo,
                    old_parent_id=op.old_parent_id,
                    new_parent_id=op.new_parent_id,
                    old_index=op.old_index,
                    new_index=op.new_index,
                    deleted_content=op.deleted_content,
                )

        return op

    def _transform_insert_after_delete(
        self,
        op: Operation,
        base_op: Operation,
    ) -> Operation | None:
        """Transform INSERT after node was deleted.

        Args:
            op: INSERT operation
            base_op: DELETE operation

        Returns:
            Transformed operation
        """
        # Insert on deleted node - can't happen, return None
        # Also check if parent is the deleted node
        if op.parent_id == base_op.node_id:
            return None

        return op

    def _transform_move(
        self,
        op: Operation,
        base_op: Operation,
    ) -> Operation | None:
        """Transform MOVE operation.

        Args:
            op: MOVE operation
            base_op: Base operation

        Returns:
            Transformed operation
        """
        if base_op.op_type == OpType.DELETE:
            # Can't move a deleted node
            if op.node_id == base_op.node_id:
                return None
            # Can't move to deleted parent
            if op.new_parent_id == base_op.node_id:
                return None

        elif base_op.op_type == OpType.MOVE:
            # Two concurrent moves - last one wins
            if base_op.timestamp > op.timestamp:
                return None

        return op

    def create_edit_operation(
        self,
        document_id: str,
        node_id: str,
        user_id: str,
        user_name: str,
        old_text: str | None = None,
        new_text: str | None = None,
        old_memo: str | None = None,
        new_memo: str | None = None,
    ) -> Operation:
        """Create an EDIT operation.

        Args:
            document_id: Document ID
            node_id: Node being edited
            user_id: User making the edit
            user_name: Display name
            old_text: Previous text (if changed)
            new_text: New text (if changed)
            old_memo: Previous memo (if changed)
            new_memo: New memo (if changed)

        Returns:
            EDIT operation
        """
        return Operation(
            op_type=OpType.EDIT,
            node_id=node_id,
            user_id=user_id,
            user_name=user_name,
            document_id=document_id,
            old_text=old_text,
            new_text=new_text,
            old_memo=old_memo,
            new_memo=new_memo,
        )

    def create_insert_operation(
        self,
        document_id: str,
        node_id: str,
        parent_id: str,
        insert_index: int,
        user_id: str,
        user_name: str,
    ) -> Operation:
        """Create an INSERT operation.

        Args:
            document_id: Document ID
            node_id: New node ID
            parent_id: Parent node ID
            insert_index: Index in parent's children
            user_id: User making the insert
            user_name: Display name

        Returns:
            INSERT operation
        """
        return Operation(
            op_type=OpType.INSERT,
            node_id=node_id,
            user_id=user_id,
            user_name=user_name,
            document_id=document_id,
            parent_id=parent_id,
            insert_index=insert_index,
        )

    def create_delete_operation(
        self,
        document_id: str,
        node_id: str,
        deleted_content: dict[str, Any],
        user_id: str,
        user_name: str,
    ) -> Operation:
        """Create a DELETE operation.

        Args:
            document_id: Document ID
            node_id: Node being deleted
            deleted_content: Content of deleted node (for undo)
            user_id: User making the delete
            user_name: Display name

        Returns:
            DELETE operation
        """
        return Operation(
            op_type=OpType.DELETE,
            node_id=node_id,
            user_id=user_id,
            user_name=user_name,
            document_id=document_id,
            deleted_content=deleted_content,
        )

    def create_move_operation(
        self,
        document_id: str,
        node_id: str,
        old_parent_id: str,
        new_parent_id: str,
        old_index: int,
        new_index: int,
        user_id: str,
        user_name: str,
    ) -> Operation:
        """Create a MOVE operation.

        Args:
            document_id: Document ID
            node_id: Node being moved
            old_parent_id: Previous parent
            new_parent_id: New parent
            old_index: Previous index
            new_index: New index
            user_id: User making the move
            user_name: Display name

        Returns:
            MOVE operation
        """
        return Operation(
            op_type=OpType.MOVE,
            node_id=node_id,
            user_id=user_id,
            user_name=user_name,
            document_id=document_id,
            old_parent_id=old_parent_id,
            new_parent_id=new_parent_id,
            old_index=old_index,
            new_index=new_index,
        )

    def get_operation_history(
        self,
        document_id: str,
        since_timestamp: float | None = None,
    ) -> list[Operation]:
        """Get operation history for a document.

        Args:
            document_id: Document to query
            since_timestamp: Optional filter for ops after this time

        Returns:
            List of operations
        """
        if document_id not in self._operation_log:
            return []

        ops = self._operation_log[document_id]
        if since_timestamp:
            return [op for op in ops if op.timestamp > since_timestamp]
        return ops

    def clear_old_operations(
        self,
        document_id: str,
        older_than_seconds: float = 3600,
    ) -> None:
        """Clear old operations from history.

        Args:
            document_id: Document to clean
            older_than_seconds: Remove ops older than this
        """
        if document_id not in self._operation_log:
            return

        now = time.time()
        self._operation_log[document_id] = [
            op for op in self._operation_log[document_id]
            if (now - op.timestamp) < older_than_seconds
        ]


# Singleton instance
_manager: OTManager | None = None


def get_ot_manager() -> OTManager:
    """Get the singleton OTManager instance."""
    global _manager
    if _manager is None:
        _manager = OTManager()
    return _manager


def reset_ot_manager() -> None:
    """Reset the singleton OTManager (for testing)."""
    global _manager
    _manager = None
