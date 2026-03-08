from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
from typing import Any
from uuid import uuid4

from app.core.settings import get_settings
from app.db.config import DEFAULT_MIGRATIONS_DIR
from app.db.migrate import run_migrations


ADMIN_STAFF_NO = 'admin'
ADMIN_DISPLAY_NAME = 'Administrator'


def _db_path() -> Path:
    settings = get_settings()
    path = settings.db_path_abs
    run_migrations(path, DEFAULT_MIGRATIONS_DIR)
    return path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _to_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        'id': row['id'],
        'staff_no': row['staff_no'],
        'display_name': row['display_name'],
        'role': row['role'],
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            '''
            SELECT id, staff_no, display_name, role, created_at, updated_at
            FROM users
            WHERE id = ?
            ''',
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return _to_payload(row)


def get_user_by_staff_no(staff_no: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            '''
            SELECT id, staff_no, display_name, role, created_at, updated_at
            FROM users
            WHERE staff_no = ?
            ''',
            (staff_no,),
        ).fetchone()
    if row is None:
        return None
    return _to_payload(row)


def ensure_default_admin() -> None:
    settings = get_settings()
    admin_hash = hash_password(settings.admin_password)

    with _connect() as conn:
        current = conn.execute(
            'SELECT id FROM users WHERE staff_no = ?',
            (ADMIN_STAFF_NO,),
        ).fetchone()
        if current is None:
            conn.execute(
                '''
                INSERT INTO users(id, staff_no, display_name, role, password_hash)
                VALUES(?, ?, ?, ?, ?)
                ''',
                (str(uuid4()), ADMIN_STAFF_NO, ADMIN_DISPLAY_NAME, 'admin', admin_hash),
            )
            return

        conn.execute(
            '''
            UPDATE users
            SET password_hash = ?, role = 'admin', updated_at = CURRENT_TIMESTAMP
            WHERE staff_no = ?
            ''',
            (admin_hash, ADMIN_STAFF_NO),
        )


def verify_admin_password(password: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            'SELECT password_hash FROM users WHERE staff_no = ?',
            (ADMIN_STAFF_NO,),
        ).fetchone()
    if row is None:
        return False
    return hash_password(password) == row['password_hash']


def ensure_employee_user(staff_no: str) -> dict[str, Any]:
    existing = get_user_by_staff_no(staff_no)
    if existing is not None:
        return existing

    display_name = f'员工 {staff_no}'
    user_id = str(uuid4())
    with _connect() as conn:
        conn.execute(
            '''
            INSERT INTO users(id, staff_no, display_name, role)
            VALUES(?, ?, ?, 'employee')
            ''',
            (user_id, staff_no, display_name),
        )

    created = get_user_by_id(user_id)
    if created is None:
        raise RuntimeError('created user cannot be loaded')
    return created


def _validate_role(role: str) -> str:
    role = role.strip()
    if role not in {"employee", "reviewer", "admin"}:
        raise ValueError("invalid role")
    return role


def list_users() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, staff_no, display_name, role, created_at, updated_at FROM users ORDER BY staff_no"
        ).fetchall()
    return [_to_payload(row) for row in rows]


def create_user(staff_no: str, display_name: str, role: str = "employee") -> dict[str, Any]:
    staff_no = staff_no.strip()
    display_name = display_name.strip()
    if not staff_no:
        raise ValueError("staff_no is required")
    if not display_name:
        raise ValueError("display_name is required")
    role = _validate_role(role)

    user_id = str(uuid4())
    with _connect() as conn:
        conn.execute(
            "INSERT INTO users(id, staff_no, display_name, role) VALUES(?, ?, ?, ?)",
            (user_id, staff_no, display_name, role),
        )

    created = get_user_by_id(user_id)
    if created is None:
        raise RuntimeError("created user cannot be loaded")
    return created


def update_user(staff_no: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    current = get_user_by_staff_no(staff_no)
    if current is None:
        return None

    display_name = updates.get("display_name", current["display_name"])
    role = updates.get("role", current["role"])

    if display_name is None or not str(display_name).strip():
        raise ValueError("display_name is required")

    if role is None:
        role = current["role"]
    role = _validate_role(str(role))

    with _connect() as conn:
        conn.execute(
            "UPDATE users SET display_name = ?, role = ?, updated_at = CURRENT_TIMESTAMP WHERE staff_no = ?",
            (str(display_name).strip(), role, staff_no),
        )

    return get_user_by_staff_no(staff_no)


def delete_user(staff_no: str) -> bool:
    with _connect() as conn:
        result = conn.execute("DELETE FROM users WHERE staff_no = ?", (staff_no,))
    return result.rowcount > 0


def set_user_role(staff_no: str, role: str) -> None:
    """Update user's role. Used by tests and admin tools."""

    role = _validate_role(role)
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE staff_no = ?",
            (role, staff_no),
        )
