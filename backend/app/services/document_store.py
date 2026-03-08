from __future__ import annotations

import json
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


def _to_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "content": json.loads(row["content_json"]),
        "owner_id": row["owner_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_documents() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, title, content_json, owner_id, created_at, updated_at
            FROM documents
            ORDER BY updated_at DESC, created_at DESC, id DESC
            """
        ).fetchall()
    return [_to_payload(row) for row in rows]


def get_document(document_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, title, content_json, owner_id, created_at, updated_at
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()
    if row is None:
        return None
    return _to_payload(row)


def create_document(title: str, content: dict[str, Any], owner_id: str | None) -> dict[str, Any]:
    document_id = str(uuid4())
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO documents(id, title, content_json, owner_id)
            VALUES(?, ?, ?, ?)
            """,
            (document_id, title, json.dumps(content, ensure_ascii=False), owner_id),
        )
    document = get_document(document_id)
    if document is None:
        raise RuntimeError("created document cannot be loaded")
    return document


def update_document(document_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    current = get_document(document_id)
    if current is None:
        return None

    title = updates.get("title", current["title"])
    content = updates.get("content", current["content"])
    owner_id = updates.get("owner_id", current["owner_id"])

    with _connect() as conn:
        conn.execute(
            """
            UPDATE documents
            SET title = ?, content_json = ?, owner_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (title, json.dumps(content, ensure_ascii=False), owner_id, document_id),
        )
    return get_document(document_id)


def delete_document(document_id: str) -> bool:
    with _connect() as conn:
        result = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
    return result.rowcount > 0
