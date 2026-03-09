"""Commit workspace service.

AUTO-04: 提交工作区与合并区

Provides a staging area for AI-generated changes from dev tasks.
Changes are stored in the workspace and can be reviewed before
being merged into the actual document.

Workflow:
1. AI task generates changes → create workspace entry with snapshots
2. User reviews the proposed changes (before/after)
3. User either merges (applies changes) or discards
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from app.core.settings import get_settings
from app.db.config import DEFAULT_MIGRATIONS_DIR
from app.db.migrate import run_migrations
from app.services.document_store import get_document, update_document


class WorkspaceStatus:
    """Workspace status constants."""
    PENDING = "pending"
    MERGED = "merged"
    DISCARDED = "discarded"


def _db_path() -> Path:
    settings = get_settings()
    path = settings.db_path_abs
    run_migrations(path, DEFAULT_MIGRATIONS_DIR)
    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _to_workspace_payload(row: sqlite3.Row) -> dict[str, Any]:
    """Convert database row to API response."""
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "document_id": row["document_id"],
        "snapshot_before": json.loads(row["snapshot_before"]) if row["snapshot_before"] else None,
        "snapshot_after": json.loads(row["snapshot_after"]) if row["snapshot_after"] else None,
        "changes_summary": row["changes_summary"],
        "status": row["status"],
        "created_by": row["created_by"],
        "merged_by": row["merged_by"],
        "created_at": row["created_at"],
        "merged_at": row["merged_at"],
    }


def list_commit_workspaces(
    document_id: str | None = None,
    task_id: str | None = None,
    status: str | None = None,
    created_by: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List commit workspaces with optional filters.

    Args:
        document_id: Filter by document
        task_id: Filter by dev task
        status: Filter by status (pending, merged, discarded)
        created_by: Filter by creator
        limit: Maximum number of results

    Returns:
        List of workspace entries
    """
    with _connect() as conn:
        query = "SELECT * FROM commit_workspace WHERE 1=1"
        params: list[Any] = []

        if document_id is not None:
            query += " AND document_id = ?"
            params.append(document_id)
        if task_id is not None:
            query += " AND task_id = ?"
            params.append(task_id)
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        if created_by is not None:
            query += " AND created_by = ?"
            params.append(created_by)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
    return [_to_workspace_payload(row) for row in rows]


def get_commit_workspace(workspace_id: str) -> dict[str, Any] | None:
    """Get a single commit workspace by ID.

    Args:
        workspace_id: Workspace ID

    Returns:
        Workspace entry or None if not found
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM commit_workspace WHERE id = ?",
            (workspace_id,),
        ).fetchone()
    if row is None:
        return None
    return _to_workspace_payload(row)


def get_pending_workspace_for_document(document_id: str) -> dict[str, Any] | None:
    """Get the pending workspace for a document.

    There should be at most one pending workspace per document.

    Args:
        document_id: Document ID

    Returns:
        Pending workspace or None
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM commit_workspace WHERE document_id = ? AND status = ? ORDER BY created_at DESC LIMIT 1",
            (document_id, WorkspaceStatus.PENDING),
        ).fetchone()
    if row is None:
        return None
    return _to_workspace_payload(row)


def create_commit_workspace(
    task_id: str,
    document_id: str,
    snapshot_before: dict[str, Any] | None,
    snapshot_after: dict[str, Any],
    changes_summary: str,
    created_by: str,
) -> dict[str, Any]:
    """Create a new commit workspace entry.

    Args:
        task_id: Dev task ID that generated the changes
        document_id: Target document ID
        snapshot_before: Document state before changes (null if new document)
        snapshot_after: Proposed document state after changes
        changes_summary: Human-readable summary of changes
        created_by: User ID who initiated the task

    Returns:
        Created workspace entry

    Raises:
        ValueError: If document doesn't exist or there's already a pending workspace
    """
    # Verify document exists
    document = get_document(document_id)
    if document is None:
        raise ValueError(f"Document not found: {document_id}")

    # Check for existing pending workspace
    existing = get_pending_workspace_for_document(document_id)
    if existing is not None:
        raise ValueError(f"Document already has a pending workspace: {existing['id']}")

    workspace_id = str(uuid4())

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO commit_workspace(id, task_id, document_id, snapshot_before, snapshot_after, changes_summary, created_by)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workspace_id,
                task_id,
                document_id,
                json.dumps(snapshot_before, ensure_ascii=False) if snapshot_before else None,
                json.dumps(snapshot_after, ensure_ascii=False),
                changes_summary,
                created_by,
            ),
        )

    workspace = get_commit_workspace(workspace_id)
    if workspace is None:
        raise RuntimeError("Created workspace cannot be loaded")
    return workspace


def merge_commit_workspace(
    workspace_id: str,
    merged_by: str,
) -> dict[str, Any]:
    """Merge a pending workspace into the document.

    This applies the proposed changes to the document.

    Args:
        workspace_id: Workspace ID
        merged_by: User ID who approved the merge

    Returns:
        Updated workspace entry

    Raises:
        ValueError: If workspace not found or not in pending status
    """
    workspace = get_commit_workspace(workspace_id)
    if workspace is None:
        raise ValueError(f"Workspace not found: {workspace_id}")

    if workspace["status"] != WorkspaceStatus.PENDING:
        raise ValueError(f"Workspace is not in pending status: {workspace['status']}")

    # Apply changes to document
    snapshot_after = workspace["snapshot_after"]
    document = update_document(
        workspace["document_id"],
        {"content": snapshot_after},
        changed_by=merged_by,
    )
    if document is None:
        raise ValueError(f"Failed to update document: {workspace['document_id']}")

    # Update workspace status
    with _connect() as conn:
        conn.execute(
            """
            UPDATE commit_workspace
            SET status = ?, merged_by = ?, merged_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (WorkspaceStatus.MERGED, merged_by, workspace_id),
        )

    updated = get_commit_workspace(workspace_id)
    if updated is None:
        raise RuntimeError("Updated workspace cannot be loaded")
    return updated


def discard_commit_workspace(
    workspace_id: str,
    discarded_by: str,
) -> dict[str, Any]:
    """Discard a pending workspace without applying changes.

    Args:
        workspace_id: Workspace ID
        discarded_by: User ID who discarded

    Returns:
        Updated workspace entry

    Raises:
        ValueError: If workspace not found or not in pending status
    """
    workspace = get_commit_workspace(workspace_id)
    if workspace is None:
        raise ValueError(f"Workspace not found: {workspace_id}")

    if workspace["status"] != WorkspaceStatus.PENDING:
        raise ValueError(f"Workspace is not in pending status: {workspace['status']}")

    # Update workspace status
    with _connect() as conn:
        conn.execute(
            """
            UPDATE commit_workspace
            SET status = ?, merged_by = ?, merged_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (WorkspaceStatus.DISCARDED, discarded_by, workspace_id),
        )

    updated = get_commit_workspace(workspace_id)
    if updated is None:
        raise RuntimeError("Updated workspace cannot be loaded")
    return updated


def get_workspace_diff(workspace_id: str) -> dict[str, Any] | None:
    """Get a diff summary for a workspace.

    Returns the before/after snapshots and a list of changed nodes.

    Args:
        workspace_id: Workspace ID

    Returns:
        Diff summary or None if workspace not found
    """
    workspace = get_commit_workspace(workspace_id)
    if workspace is None:
        return None

    before = workspace["snapshot_before"] or {}
    after = workspace["snapshot_after"] or {}

    # Simple diff: collect all node IDs from both snapshots
    before_nodes = _collect_nodes(before)
    after_nodes = _collect_nodes(after)

    added_ids = set(after_nodes.keys()) - set(before_nodes.keys())
    removed_ids = set(before_nodes.keys()) - set(after_nodes.keys())
    common_ids = set(before_nodes.keys()) & set(after_nodes.keys())

    # Check for modified nodes
    modified_ids = set()
    for node_id in common_ids:
        if before_nodes[node_id] != after_nodes[node_id]:
            modified_ids.add(node_id)

    return {
        "workspace_id": workspace_id,
        "document_id": workspace["document_id"],
        "added": [{"id": nid, "text": after_nodes[nid].get("text")} for nid in sorted(added_ids)],
        "removed": [{"id": nid, "text": before_nodes[nid].get("text")} for nid in sorted(removed_ids)],
        "modified": [{"id": nid, "text": after_nodes[nid].get("text")} for nid in sorted(modified_ids)],
        "stats": {
            "added_count": len(added_ids),
            "removed_count": len(removed_ids),
            "modified_count": len(modified_ids),
        },
    }


def _collect_nodes(root: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Collect all nodes from a document tree into a flat dict.

    Args:
        root: Root node of document tree

    Returns:
        Dict mapping node ID to node data
    """
    nodes = {}

    def _traverse(node: dict[str, Any]) -> None:
        node_id = node.get("id")
        if node_id:
            # Store a simplified version (without children to avoid nested comparison)
            nodes[node_id] = {
                "id": node_id,
                "text": node.get("text"),
                "expanded": node.get("expanded"),
                "style": node.get("style"),
            }
        for child in node.get("children") or []:
            _traverse(child)

    _traverse(root)
    return nodes
