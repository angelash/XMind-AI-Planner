from __future__ import annotations

import json
from pathlib import Path
import secrets
import sqlite3
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


def _to_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "content": json.loads(row["content_json"]),
        "owner_id": row["owner_id"],
        "project_id": row["project_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_documents(owner_id: str | None = None, project_id: str | None = None) -> list[dict[str, Any]]:
    """List documents, optionally filtered by owner_id or project_id.
    
    For project documents, use project_id filter.
    For personal workspace documents, use owner_id filter with project_id=None.
    """
    with _connect() as conn:
        if project_id is not None:
            # List project documents
            rows = conn.execute(
                """
                SELECT id, title, content_json, owner_id, project_id, created_at, updated_at
                FROM documents
                WHERE project_id = ?
                ORDER BY updated_at DESC, created_at DESC, id DESC
                """,
                (project_id,),
            ).fetchall()
        elif owner_id is not None:
            # List personal workspace documents (owner_id match AND project_id IS NULL)
            rows = conn.execute(
                """
                SELECT id, title, content_json, owner_id, project_id, created_at, updated_at
                FROM documents
                WHERE owner_id = ? AND project_id IS NULL
                ORDER BY updated_at DESC, created_at DESC, id DESC
                """,
                (owner_id,),
            ).fetchall()
        else:
            # List all documents (admin view)
            rows = conn.execute(
                """
                SELECT id, title, content_json, owner_id, project_id, created_at, updated_at
                FROM documents
                ORDER BY updated_at DESC, created_at DESC, id DESC
                """
            ).fetchall()
    return [_to_payload(row) for row in rows]


def get_document(document_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, title, content_json, owner_id, project_id, created_at, updated_at
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()
    if row is None:
        return None
    return _to_payload(row)


def create_document(title: str, content: dict[str, Any], owner_id: str | None, project_id: str | None = None) -> dict[str, Any]:
    document_id = str(uuid4())
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO documents(id, title, content_json, owner_id, project_id)
            VALUES(?, ?, ?, ?, ?)
            """,
            (document_id, title, json.dumps(content, ensure_ascii=False), owner_id, project_id),
        )
    document = get_document(document_id)
    if document is None:
        raise RuntimeError("created document cannot be loaded")
    return document


def _update_document_internal(document_id: str, title: str, content: dict[str, Any], owner_id: str | None, project_id: str | None) -> dict[str, Any] | None:
    """Internal function to update document without creating version."""
    with _connect() as conn:
        conn.execute(
            """
            UPDATE documents
            SET title = ?, content_json = ?, owner_id = ?, project_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (title, json.dumps(content, ensure_ascii=False), owner_id, project_id, document_id),
        )
    return get_document(document_id)


def update_document(document_id: str, updates: dict[str, Any], changed_by: str | None = None) -> dict[str, Any] | None:
    """Update a document and automatically create a version history entry."""
    current = get_document(document_id)
    if current is None:
        return None

    title = updates.get("title", current["title"])
    content = updates.get("content", current["content"])
    owner_id = updates.get("owner_id", current["owner_id"])
    project_id = updates.get("project_id", current["project_id"])

    updated = _update_document_internal(document_id, title, content, owner_id, project_id)
    if updated is None:
        return None

    # Create version history entry
    create_document_version(document_id, title, content, changed_by)

    return updated


def delete_document(document_id: str) -> bool:
    with _connect() as conn:
        result = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    return result.rowcount > 0


def _to_share_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "token": row["token"],
        "document_id": row["document_id"],
        "is_editable": bool(row["is_editable"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "document": {
            "id": row["doc_id"],
            "title": row["doc_title"],
            "content": json.loads(row["doc_content_json"]),
            "owner_id": row["doc_owner_id"],
            "created_at": row["doc_created_at"],
            "updated_at": row["doc_updated_at"],
        },
    }


def create_or_refresh_share(document_id: str, is_editable: bool = True) -> dict[str, Any] | None:
    if get_document(document_id) is None:
        return None

    token = secrets.token_urlsafe(24)
    with _connect() as conn:
        conn.execute("DELETE FROM shares WHERE document_id = ?", (document_id,))
        conn.execute(
            """
            INSERT INTO shares(token, document_id, is_editable)
            VALUES(?, ?, ?)
            """,
            (token, document_id, 1 if is_editable else 0),
        )
    return get_share(token)


def get_share(token: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                s.token,
                s.document_id,
                s.is_editable,
                s.created_at,
                s.updated_at,
                d.id AS doc_id,
                d.title AS doc_title,
                d.content_json AS doc_content_json,
                d.owner_id AS doc_owner_id,
                d.created_at AS doc_created_at,
                d.updated_at AS doc_updated_at
            FROM shares s
            JOIN documents d ON d.id = s.document_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
    if row is None:
        return None
    return _to_share_payload(row)


def update_share_document(token: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    share = get_share(token)
    if share is None:
        return None
    if not share["is_editable"]:
        raise PermissionError("share is read only")

    updated = update_document(share["document_id"], updates)
    if updated is None:
        return None

    with _connect() as conn:
        conn.execute(
            """
            UPDATE shares
            SET updated_at = CURRENT_TIMESTAMP
            WHERE token = ?
            """,
            (token,),
        )
    return get_share(token)


# Version history functions

MAX_VERSIONS_PER_DOCUMENT = 50


def _to_version_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "document_id": row["document_id"],
        "version_number": row["version_number"],
        "title": row["title"],
        "content": json.loads(row["content_json"]),
        "changed_by": row["changed_by"],
        "summary": row["summary"],
        "created_at": row["created_at"],
    }


def list_document_versions(document_id: str) -> list[dict[str, Any]]:
    """List all versions for a document, newest first."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, document_id, version_number, title, content_json, changed_by, summary, created_at
            FROM document_versions
            WHERE document_id = ?
            ORDER BY version_number DESC
            """,
            (document_id,),
        ).fetchall()
    return [_to_version_payload(row) for row in rows]


def get_document_version(document_id: str, version_id: str) -> dict[str, Any] | None:
    """Get a specific version of a document."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, document_id, version_number, title, content_json, changed_by, summary, created_at
            FROM document_versions
            WHERE id = ? AND document_id = ?
            """,
            (version_id, document_id),
        ).fetchone()
    if row is None:
        return None
    return _to_version_payload(row)


def create_document_version(
    document_id: str,
    title: str,
    content: dict[str, Any],
    changed_by: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """Create a new version for a document.

    Automatically assigns version_number and cleans up old versions.
    """
    with _connect() as conn:
        # Get next version number
        row = conn.execute(
            """
            SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version
            FROM document_versions
            WHERE document_id = ?
            """,
            (document_id,),
        ).fetchone()
        next_version = row["next_version"] if row else 1

        version_id = str(uuid4())
        conn.execute(
            """
            INSERT INTO document_versions(id, document_id, version_number, title, content_json, changed_by, summary)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (version_id, document_id, next_version, title, json.dumps(content, ensure_ascii=False), changed_by, summary),
        )

        # Clean up old versions if exceeding limit
        conn.execute(
            """
            DELETE FROM document_versions
            WHERE document_id = ? AND version_number <= (
                SELECT MAX(version_number) - ? FROM document_versions WHERE document_id = ?
            )
            """,
            (document_id, MAX_VERSIONS_PER_DOCUMENT, document_id),
        )

    version = get_document_version(document_id, version_id)
    if version is None:
        raise RuntimeError("created version cannot be loaded")
    return version


def rollback_to_version(document_id: str, version_id: str, changed_by: str | None = None) -> dict[str, Any] | None:
    """Rollback document to a specific version.

    Creates a new version with the old content before applying.
    """
    # Get the version to rollback to
    version = get_document_version(document_id, version_id)
    if version is None:
        return None

    # Get current document state
    current = get_document(document_id)
    if current is None:
        return None

    # Create a version of current state before rollback
    create_document_version(
        document_id,
        current["title"],
        current["content"],
        changed_by,
        "Auto-saved before rollback",
    )

    # Update document to the version content (without creating version)
    updated = _update_document_internal(document_id, version["title"], version["content"], current["owner_id"], current["project_id"])
    if updated is None:
        return None

    # Create a version for the rollback
    create_document_version(
        document_id,
        version["title"],
        version["content"],
        changed_by,
        f"Rolled back to version {version['version_number']}",
    )

    return updated


def move_document_to_project(document_id: str, project_id: str | None, moved_by: str | None = None) -> dict[str, Any] | None:
    """Move a document to a project workspace or back to personal workspace.

    Args:
        document_id: The document to move
        project_id: Target project ID, or None to move to personal workspace
        moved_by: User who initiated the move

    Returns:
        Updated document or None if not found
    """
    current = get_document(document_id)
    if current is None:
        return None

    # Create a version before moving
    create_document_version(
        document_id,
        current["title"],
        current["content"],
        moved_by,
        f"Moved to {'personal workspace' if project_id is None else f'project {project_id}'}",
    )

    # Update the document's project_id
    updated = _update_document_internal(
        document_id,
        current["title"],
        current["content"],
        current["owner_id"],
        project_id,
    )

    return updated


# Node association functions

def _find_node_in_tree(node: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    """Recursively find a node in the tree by ID.

    Args:
        node: Current node to search
        node_id: Target node ID

    Returns:
        Found node or None
    """
    if node.get("id") == node_id:
        return node
    for child in node.get("children", []):
        found = _find_node_in_tree(child, node_id)
        if found:
            return found
    return None


def _deep_copy_node(node: dict[str, Any]) -> dict[str, Any]:
    """Deep copy a node, generating new IDs.

    Args:
        node: Node to copy

    Returns:
        Deep copy with new IDs
    """
    import copy
    new_node = copy.deepcopy(node)
    # Generate new IDs
    new_node["id"] = f"node-{str(uuid4())[:8]}"
    if "children" in new_node:
        new_node["children"] = [_deep_copy_node(child) for child in new_node["children"]]
    return new_node


def export_subtree_as_document(
    document_id: str,
    node_id: str,
    clear_original_children: bool = False,
    changed_by: str | None = None,
) -> dict[str, Any] | None:
    """Export a node subtree as a new document and link it to the original node.

    Args:
        document_id: Source document ID
        node_id: Node to export (becomes root of new document)
        clear_original_children: If True, remove children from original node
        changed_by: User who initiated the export

    Returns:
        Dict with new_document_id and exported_node_id, or None if not found
    """
    current = get_document(document_id)
    if current is None:
        return None

    content = current["content"]
    node_data = content.get("nodeData", {})
    
    # Find the node to export
    target_node = _find_node_in_tree(node_data, node_id)
    if target_node is None:
        return None

    # Deep copy the subtree
    exported_subtree = _deep_copy_node(target_node)
    exported_subtree["root"] = True

    # Create new document with the subtree
    new_title = f"{target_node.get('topic', 'Exported')} - 子图"
    new_doc = create_document(
        new_title,
        {"nodeData": exported_subtree},
        current.get("owner_id"),
        current.get("project_id"),
    )

    # Update original node to have linkedDocId
    def update_node_link(node: dict[str, Any]) -> bool:
        if node.get("id") == node_id:
            node["linkedDocId"] = new_doc["id"]
            if clear_original_children:
                node["children"] = []
            return True
        for child in node.get("children", []):
            if update_node_link(child):
                return True
        return False

    update_node_link(node_data)

    # Update the original document
    update_document(document_id, {"content": content}, changed_by)

    return {
        "new_document_id": new_doc["id"],
        "exported_node_id": node_id,
    }


def recall_association(
    document_id: str,
    node_id: str,
    changed_by: str | None = None,
) -> dict[str, Any] | None:
    """Recall (merge) an associated mind map back into the node.

    Args:
        document_id: Source document ID
        node_id: Node with linkedDocId to recall
        changed_by: User who initiated the recall

    Returns:
        Dict with merged_count, or None if not found/not linked
    """
    current = get_document(document_id)
    if current is None:
        return None

    content = current["content"]
    node_data = content.get("nodeData", {})

    # Find the node
    target_node = _find_node_in_tree(node_data, node_id)
    if target_node is None:
        return None

    linked_doc_id = target_node.get("linkedDocId")
    if not linked_doc_id:
        return None

    # Get the linked document
    linked_doc = get_document(linked_doc_id)
    if linked_doc is None:
        return None

    # Get children from linked document
    linked_node_data = linked_doc.get("content", {}).get("nodeData", {})
    linked_children = linked_node_data.get("children", [])

    # Deep copy children to avoid reference issues
    import copy
    merged_children = copy.deepcopy(linked_children)

    # Merge children into the target node
    existing_children = target_node.get("children", [])
    target_node["children"] = existing_children + merged_children

    # Clear linkedDocId
    del target_node["linkedDocId"]

    # Update the document
    update_document(document_id, {"content": content}, changed_by)

    return {
        "merged_count": len(merged_children),
        "node_id": node_id,
    }


def bind_link(
    document_id: str,
    node_id: str,
    linked_doc_id: str,
    changed_by: str | None = None,
) -> dict[str, Any] | None:
    """Bind an existing document to a node via linkedDocId.

    Args:
        document_id: Source document ID
        node_id: Node to link
        linked_doc_id: Document to link to
        changed_by: User who initiated the binding

    Returns:
        Updated document or None if not found
    """
    current = get_document(document_id)
    if current is None:
        return None

    # Verify linked document exists
    linked_doc = get_document(linked_doc_id)
    if linked_doc is None:
        return None

    content = current["content"]
    node_data = content.get("nodeData", {})

    # Find the node
    target_node = _find_node_in_tree(node_data, node_id)
    if target_node is None:
        return None

    # Set linkedDocId
    target_node["linkedDocId"] = linked_doc_id

    # Update the document
    return update_document(document_id, {"content": content}, changed_by)
