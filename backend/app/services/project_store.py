"""Project workspace and member management service."""
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
    return conn


def _to_project_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"] or "",
        "created_by": row["created_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _to_member_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "user_id": row["user_id"],
        "user_staff_no": row["user_staff_no"],
        "user_display_name": row["user_display_name"],
        "role": row["role"],
        "joined_at": row["joined_at"],
    }


# Project CRUD

def list_projects(user_id: str | None = None) -> list[dict[str, Any]]:
    """List all projects (admin) or user's projects (member)."""
    with _connect() as conn:
        if user_id is None:
            # List all projects
            rows = conn.execute(
                """
                SELECT id, name, description, created_by, created_at, updated_at
                FROM projects
                ORDER BY updated_at DESC, created_at DESC
                """
            ).fetchall()
        else:
            # List projects where user is a member
            rows = conn.execute(
                """
                SELECT DISTINCT p.id, p.name, p.description, p.created_by, p.created_at, p.updated_at
                FROM projects p
                JOIN project_members pm ON p.id = pm.project_id
                WHERE pm.user_id = ?
                ORDER BY p.updated_at DESC, p.created_at DESC
                """,
                (user_id,),
            ).fetchall()
    return [_to_project_payload(row) for row in rows]


def get_project(project_id: str) -> dict[str, Any] | None:
    """Get a single project by ID."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, name, description, created_by, created_at, updated_at
            FROM projects
            WHERE id = ?
            """,
            (project_id,),
        ).fetchone()
    if row is None:
        return None
    return _to_project_payload(row)


def create_project(name: str, created_by: str, description: str = "") -> dict[str, Any]:
    """Create a new project. Creator becomes the owner."""
    if not name or not name.strip():
        raise ValueError("project name is required")

    project_id = str(uuid4())
    member_id = str(uuid4())

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO projects(id, name, description, created_by)
            VALUES(?, ?, ?, ?)
            """,
            (project_id, name.strip(), description.strip(), created_by),
        )
        # Add creator as owner
        conn.execute(
            """
            INSERT INTO project_members(id, project_id, user_id, role)
            VALUES(?, ?, ?, 'owner')
            """,
            (member_id, project_id, created_by),
        )

    project = get_project(project_id)
    if project is None:
        raise RuntimeError("created project cannot be loaded")
    return project


def update_project(project_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update project name and/or description."""
    current = get_project(project_id)
    if current is None:
        return None

    name = updates.get("name", current["name"])
    description = updates.get("description", current["description"])

    if not name or not name.strip():
        raise ValueError("project name is required")

    with _connect() as conn:
        conn.execute(
            """
            UPDATE projects
            SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (name.strip(), description.strip() if description else "", project_id),
        )

    return get_project(project_id)


def delete_project(project_id: str) -> bool:
    """Delete a project (cascade deletes members)."""
    with _connect() as conn:
        result = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return result.rowcount > 0


# Member management

def list_project_members(project_id: str) -> list[dict[str, Any]]:
    """List all members of a project."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT pm.id, pm.project_id, pm.user_id, pm.role, pm.joined_at,
                   u.staff_no AS user_staff_no, u.display_name AS user_display_name
            FROM project_members pm
            JOIN users u ON u.id = pm.user_id
            WHERE pm.project_id = ?
            ORDER BY pm.role = 'owner' DESC, pm.role = 'admin' DESC, pm.joined_at ASC
            """,
            (project_id,),
        ).fetchall()
    return [_to_member_payload(row) for row in rows]


def get_project_member(project_id: str, user_id: str) -> dict[str, Any] | None:
    """Get a specific project member."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT pm.id, pm.project_id, pm.user_id, pm.role, pm.joined_at,
                   u.staff_no AS user_staff_no, u.display_name AS user_display_name
            FROM project_members pm
            JOIN users u ON u.id = pm.user_id
            WHERE pm.project_id = ? AND pm.user_id = ?
            """,
            (project_id, user_id),
        ).fetchone()
    if row is None:
        return None
    return _to_member_payload(row)


def add_project_member(project_id: str, user_id: str, role: str = "member") -> dict[str, Any]:
    """Add a user to a project."""
    if get_project(project_id) is None:
        raise ValueError("project not found")

    existing = get_project_member(project_id, user_id)
    if existing is not None:
        raise ValueError("user is already a member")

    role = role.strip()
    if role not in {"owner", "admin", "member"}:
        raise ValueError("invalid role: must be owner, admin, or member")

    member_id = str(uuid4())
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO project_members(id, project_id, user_id, role)
            VALUES(?, ?, ?, ?)
            """,
            (member_id, project_id, user_id, role),
        )
        # Update project updated_at
        conn.execute(
            "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (project_id,),
        )

    member = get_project_member(project_id, user_id)
    if member is None:
        raise RuntimeError("created member cannot be loaded")
    return member


def update_project_member_role(project_id: str, user_id: str, role: str) -> dict[str, Any] | None:
    """Update a member's role in a project."""
    member = get_project_member(project_id, user_id)
    if member is None:
        return None

    role = role.strip()
    if role not in {"owner", "admin", "member"}:
        raise ValueError("invalid role: must be owner, admin, or member")

    with _connect() as conn:
        conn.execute(
            """
            UPDATE project_members SET role = ? WHERE project_id = ? AND user_id = ?
            """,
            (role, project_id, user_id),
        )
        conn.execute(
            "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (project_id,),
        )

    return get_project_member(project_id, user_id)


def remove_project_member(project_id: str, user_id: str) -> bool:
    """Remove a member from a project."""
    with _connect() as conn:
        result = conn.execute(
            "DELETE FROM project_members WHERE project_id = ? AND user_id = ?",
            (project_id, user_id),
        )
        if result.rowcount > 0:
            conn.execute(
                "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (project_id,),
            )
            return True
    return False


def is_project_member(project_id: str, user_id: str) -> bool:
    """Check if a user is a member of a project."""
    return get_project_member(project_id, user_id) is not None


def is_project_admin(project_id: str, user_id: str) -> bool:
    """Check if a user is an admin or owner of a project."""
    member = get_project_member(project_id, user_id)
    return member is not None and member["role"] in {"owner", "admin"}
