"""File tree management service for project workspaces."""
from __future__ import annotations

from pathlib import Path
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
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _to_item_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "parent_id": row["parent_id"],
        "name": row["name"],
        "type": row["type"],
        "path": row["path"],
        "content": row["content"] if "content" in row.keys() else "",
        "sort_order": row["sort_order"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "created_by": row["created_by"],
    }


def list_file_tree_items(project_id: str, parent_id: str | None = None) -> list[dict[str, Any]]:
    """List file tree items in a project, optionally filtered by parent."""
    with _connect() as conn:
        if parent_id is None:
            # List root items (parent_id is NULL)
            rows = conn.execute(
                """
                SELECT id, project_id, parent_id, name, type, path, content, sort_order,
                       created_at, updated_at, created_by
                FROM file_tree_items
                WHERE project_id = ? AND parent_id IS NULL
                ORDER BY type = 'folder' DESC, sort_order ASC, name ASC
                """,
                (project_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, project_id, parent_id, name, type, path, content, sort_order,
                       created_at, updated_at, created_by
                FROM file_tree_items
                WHERE project_id = ? AND parent_id = ?
                ORDER BY type = 'folder' DESC, sort_order ASC, name ASC
                """,
                (project_id, parent_id),
            ).fetchall()
    return [_to_item_payload(row) for row in rows]


def get_file_tree_item(item_id: str) -> dict[str, Any] | None:
    """Get a single file tree item by ID."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, project_id, parent_id, name, type, path, content, sort_order,
                   created_at, updated_at, created_by
            FROM file_tree_items
            WHERE id = ?
            """,
            (item_id,),
        ).fetchone()
    if row is None:
        return None
    return _to_item_payload(row)


def get_file_tree_item_by_path(project_id: str, path: str) -> dict[str, Any] | None:
    """Get a file tree item by its path."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, project_id, parent_id, name, type, path, content, sort_order,
                   created_at, updated_at, created_by
            FROM file_tree_items
            WHERE project_id = ? AND path = ?
            """,
            (project_id, path),
        ).fetchone()
    if row is None:
        return None
    return _to_item_payload(row)


def create_file_tree_item(
    project_id: str,
    name: str,
    item_type: str,
    parent_id: str | None = None,
    created_by: str | None = None,
    sort_order: int = 0,
    content: str = "",
) -> dict[str, Any]:
    """Create a new file or folder in the file tree."""
    if not name or not name.strip():
        raise ValueError("name is required")

    name = name.strip()
    item_type = item_type.strip().lower()
    if item_type not in {"folder", "file"}:
        raise ValueError("type must be 'folder' or 'file'")

    # Compute path based on parent
    if parent_id is None:
        path = f"/{name}"
    else:
        parent = get_file_tree_item(parent_id)
        if parent is None:
            raise ValueError("parent not found")
        if parent["type"] != "folder":
            raise ValueError("parent must be a folder")
        if parent["project_id"] != project_id:
            raise ValueError("parent does not belong to this project")
        path = f"{parent['path']}/{name}"

    # Check for duplicate path
    existing = get_file_tree_item_by_path(project_id, path)
    if existing is not None:
        raise ValueError(f"an item with path '{path}' already exists")

    item_id = str(uuid4())

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO file_tree_items(id, project_id, parent_id, name, type, path, content, sort_order, created_by)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (item_id, project_id, parent_id, name, item_type, path, content, sort_order, created_by),
        )

    item = get_file_tree_item(item_id)
    if item is None:
        raise RuntimeError("created item cannot be loaded")
    return item


def update_file_tree_item(
    item_id: str,
    name: str | None = None,
    sort_order: int | None = None,
) -> dict[str, Any] | None:
    """Update a file tree item's name and/or sort order."""
    item = get_file_tree_item(item_id)
    if item is None:
        return None

    new_name = name.strip() if name else item["name"]
    new_sort_order = sort_order if sort_order is not None else item["sort_order"]

    if not new_name:
        raise ValueError("name cannot be empty")

    # If name changed, update path and all children's paths
    if new_name != item["name"]:
        with _connect() as conn:
            # Compute new path
            if item["parent_id"] is None:
                new_path = f"/{new_name}"
            else:
                parent = get_file_tree_item(item["parent_id"])
                if parent is None:
                    raise RuntimeError("parent not found")
                new_path = f"{parent['path']}/{new_name}"

            # Check for duplicate path
            existing = get_file_tree_item_by_path(item["project_id"], new_path)
            if existing is not None and existing["id"] != item_id:
                raise ValueError(f"an item with path '{new_path}' already exists")

            # Update this item
            conn.execute(
                """
                UPDATE file_tree_items
                SET name = ?, path = ?, sort_order = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_name, new_path, new_sort_order, item_id),
            )

            # Update all children paths (recursive)
            _update_children_paths(conn, item_id, item["path"], new_path)
    else:
        with _connect() as conn:
            conn.execute(
                """
                UPDATE file_tree_items
                SET sort_order = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_sort_order, item_id),
            )

    return get_file_tree_item(item_id)


def _update_children_paths(
    conn: sqlite3.Connection,
    parent_id: str,
    old_parent_path: str,
    new_parent_path: str,
) -> None:
    """Recursively update children's paths when parent path changes."""
    children = conn.execute(
        "SELECT id, path FROM file_tree_items WHERE parent_id = ?",
        (parent_id,),
    ).fetchall()

    for child in children:
        old_path = child["path"]
        new_path = old_path.replace(old_parent_path, new_parent_path, 1)
        conn.execute(
            "UPDATE file_tree_items SET path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (new_path, child["id"]),
        )
        # Recursively update grandchildren
        _update_children_paths(conn, child["id"], old_path, new_path)


def delete_file_tree_item(item_id: str) -> bool:
    """Delete a file tree item. Folders are deleted recursively."""
    with _connect() as conn:
        result = conn.execute(
            "DELETE FROM file_tree_items WHERE id = ?",
            (item_id,),
        )
    return result.rowcount > 0


def move_file_tree_item(item_id: str, new_parent_id: str | None) -> dict[str, Any] | None:
    """Move a file tree item to a new parent."""
    item = get_file_tree_item(item_id)
    if item is None:
        return None

    # Compute new path
    if new_parent_id is None:
        new_path = f"/{item['name']}"
    else:
        new_parent = get_file_tree_item(new_parent_id)
        if new_parent is None:
            raise ValueError("new parent not found")
        if new_parent["type"] != "folder":
            raise ValueError("new parent must be a folder")
        if new_parent["project_id"] != item["project_id"]:
            raise ValueError("new parent does not belong to this project")
        new_path = f"{new_parent['path']}/{item['name']}"

    # Check for duplicate path
    existing = get_file_tree_item_by_path(item["project_id"], new_path)
    if existing is not None and existing["id"] != item_id:
        raise ValueError(f"an item with path '{new_path}' already exists")

    # Prevent moving a folder into itself or its descendants
    if item["type"] == "folder" and new_path.startswith(item["path"] + "/"):
        raise ValueError("cannot move a folder into itself or its descendants")

    old_path = item["path"]

    with _connect() as conn:
        conn.execute(
            """
            UPDATE file_tree_items
            SET parent_id = ?, path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_parent_id, new_path, item_id),
        )

        # Update all children paths
        _update_children_paths(conn, item_id, old_path, new_path)

    return get_file_tree_item(item_id)


def get_file_tree(project_id: str) -> list[dict[str, Any]]:
    """Get the complete file tree for a project as a nested structure."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, project_id, parent_id, name, type, path, content, sort_order,
                   created_at, updated_at, created_by
            FROM file_tree_items
            WHERE project_id = ?
            ORDER BY type = 'folder' DESC, sort_order ASC, name ASC
            """,
            (project_id,),
        ).fetchall()

    items = [_to_item_payload(row) for row in rows]
    return _build_tree(items)


def update_file_tree_item_content(item_id: str, content: str) -> dict[str, Any] | None:
    """Update the content of a file tree item."""
    item = get_file_tree_item(item_id)
    if item is None:
        return None
    
    if item["type"] != "file":
        raise ValueError("can only update content of files, not folders")

    with _connect() as conn:
        conn.execute(
            """
            UPDATE file_tree_items
            SET content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (content, item_id),
        )

    return get_file_tree_item(item_id)


def _build_tree(items: list[dict[str, Any]], parent_id: str | None = None) -> list[dict[str, Any]]:
    """Build a nested tree structure from flat items."""
    result = []
    for item in items:
        if item["parent_id"] == parent_id:
            children = _build_tree(items, item["id"])
            node = {**item, "children": children}
            result.append(node)
    return result
