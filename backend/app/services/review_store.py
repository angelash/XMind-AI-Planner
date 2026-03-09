"""Review workflow store for pending changes.

REVIEW-01: 审核流程后端

Provides CRUD operations for pending change requests:
- Submit changes for review
- List pending changes
- Approve/reject changes
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.settings import get_settings
from app.db.config import DEFAULT_MIGRATIONS_DIR
from app.db.migrate import run_migrations


def _db_path() -> Path:
    settings = get_settings()
    path = settings.db_path_abs
    run_migrations(path, DEFAULT_MIGRATIONS_DIR)
    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


@dataclass
class PendingChange:
    """Represents a pending change awaiting review."""
    id: int | None = None
    document_id: str = ""
    node_id: str = ""
    change_type: str = "update"  # create, update, delete
    before_content: dict[str, Any] | None = None
    after_content: dict[str, Any] | None = None
    submitted_by: str = ""
    submitted_at: str = ""
    status: str = "pending"  # pending, approved, rejected
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    review_comment: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "node_id": self.node_id,
            "change_type": self.change_type,
            "before_content": self.before_content,
            "after_content": self.after_content,
            "submitted_by": self.submitted_by,
            "submitted_at": self.submitted_at,
            "status": self.status,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "review_comment": self.review_comment,
        }


def _row_to_change(row: sqlite3.Row) -> PendingChange:
    return PendingChange(
        id=row["id"],
        document_id=row["document_id"],
        node_id=row["node_id"],
        change_type=row["change_type"],
        before_content=json.loads(row["before_content"]) if row["before_content"] else None,
        after_content=json.loads(row["after_content"]) if row["after_content"] else None,
        submitted_by=row["submitted_by"],
        submitted_at=row["submitted_at"],
        status=row["status"],
        reviewed_by=row["reviewed_by"],
        reviewed_at=row["reviewed_at"],
        review_comment=row["review_comment"],
    )


def submit_change(
    document_id: str,
    node_id: str,
    change_type: str,
    submitted_by: str,
    before_content: dict[str, Any] | None = None,
    after_content: dict[str, Any] | None = None,
) -> PendingChange:
    """Submit a change for review.

    Args:
        document_id: Document containing the node
        node_id: Node being changed
        change_type: Type of change (create, update, delete)
        submitted_by: User ID of submitter
        before_content: Node state before change (null for create)
        after_content: Node state after change (null for delete)

    Returns:
        The created PendingChange

    Raises:
        ValueError: If validation fails or pending change already exists
    """
    if change_type not in ("create", "update", "delete"):
        raise ValueError(f"invalid change_type: {change_type}")

    with _connect() as conn:
        # Check for existing pending change on same node
        existing = conn.execute(
            "SELECT id FROM pending_changes WHERE document_id = ? AND node_id = ? AND status = 'pending'",
            (document_id, node_id),
        ).fetchone()
        if existing:
            raise ValueError(f"pending change already exists for node {node_id}")

        conn.execute(
            """
            INSERT INTO pending_changes (
                document_id, node_id, change_type,
                before_content, after_content, submitted_by
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,
                node_id,
                change_type,
                json.dumps(before_content) if before_content else None,
                json.dumps(after_content) if after_content else None,
                submitted_by,
            ),
        )
        change_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    return get_change_by_id(change_id)


def get_change_by_id(change_id: int) -> PendingChange | None:
    """Get a pending change by ID."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM pending_changes WHERE id = ?",
            (change_id,),
        ).fetchone()
    if row is None:
        return None
    return _row_to_change(row)


def list_pending_changes(
    document_id: str | None = None,
    status: str = "pending",
    submitted_by: str | None = None,
) -> list[PendingChange]:
    """List pending changes with optional filters.

    Args:
        document_id: Filter by document
        status: Filter by status (pending, approved, rejected)
        submitted_by: Filter by submitter

    Returns:
        List of matching PendingChange objects
    """
    query = "SELECT * FROM pending_changes WHERE 1=1"
    params: list[Any] = []

    if document_id:
        query += " AND document_id = ?"
        params.append(document_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    if submitted_by:
        query += " AND submitted_by = ?"
        params.append(submitted_by)

    query += " ORDER BY submitted_at DESC"

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()

    return [_row_to_change(row) for row in rows]


def approve_change(
    change_id: int,
    reviewed_by: str,
    review_comment: str | None = None,
) -> PendingChange | None:
    """Approve a pending change.

    Args:
        change_id: ID of the change to approve
        reviewed_by: User ID of reviewer
        review_comment: Optional comment

    Returns:
        Updated PendingChange or None if not found
    """
    now = datetime.now(UTC).isoformat()
    with _connect() as conn:
        result = conn.execute(
            """
            UPDATE pending_changes
            SET status = 'approved',
                reviewed_by = ?,
                reviewed_at = ?,
                review_comment = ?
            WHERE id = ? AND status = 'pending'
            """,
            (reviewed_by, now, review_comment, change_id),
        )
        if result.rowcount == 0:
            return None

    return get_change_by_id(change_id)


def reject_change(
    change_id: int,
    reviewed_by: str,
    review_comment: str | None = None,
) -> PendingChange | None:
    """Reject a pending change.

    Args:
        change_id: ID of the change to reject
        reviewed_by: User ID of reviewer
        review_comment: Optional comment

    Returns:
        Updated PendingChange or None if not found
    """
    now = datetime.now(UTC).isoformat()
    with _connect() as conn:
        result = conn.execute(
            """
            UPDATE pending_changes
            SET status = 'rejected',
                reviewed_by = ?,
                reviewed_at = ?,
                review_comment = ?
            WHERE id = ? AND status = 'pending'
            """,
            (reviewed_by, now, review_comment, change_id),
        )
        if result.rowcount == 0:
            return None

    return get_change_by_id(change_id)


def batch_approve(
    document_id: str,
    reviewed_by: str,
    change_ids: list[int] | None = None,
) -> list[PendingChange]:
    """Approve multiple pending changes at once.

    Args:
        document_id: Document to approve changes for
        reviewed_by: User ID of reviewer
        change_ids: Specific change IDs to approve (all pending if None)

    Returns:
        List of approved PendingChange objects
    """
    approved: list[PendingChange] = []

    with _connect() as conn:
        if change_ids:
            for change_id in change_ids:
                change = approve_change(change_id, reviewed_by)
                if change:
                    approved.append(change)
        else:
            # Approve all pending changes for document
            rows = conn.execute(
                "SELECT id FROM pending_changes WHERE document_id = ? AND status = 'pending'",
                (document_id,),
            ).fetchall()
            for row in rows:
                change = approve_change(row["id"], reviewed_by)
                if change:
                    approved.append(change)

    return approved


def delete_change(change_id: int) -> bool:
    """Delete a pending change (for cleanup or cancellation)."""
    with _connect() as conn:
        result = conn.execute(
            "DELETE FROM pending_changes WHERE id = ?",
            (change_id,),
        )
    return result.rowcount > 0


def get_pending_count(document_id: str) -> int:
    """Get count of pending changes for a document."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as count FROM pending_changes WHERE document_id = ? AND status = 'pending'",
            (document_id,),
        ).fetchone()
    return row["count"] if row else 0
