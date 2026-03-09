"""Agent conversation storage layer.

AG-02: 对话模型与 API
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
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
    # Enable foreign keys for cascade delete to work
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ============ Conversation CRUD ============

def _conversation_to_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "uuid": row["uuid"],
        "document_id": row["document_id"],
        "user_id": row["user_id"],
        "title": row["title"],
        "status": row["status"],
        "context_node_id": row["context_node_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_conversation(
    document_id: str,
    user_id: str,
    title: str | None = None,
    context_node_id: str | None = None,
) -> dict[str, Any]:
    """Create a new conversation for a document."""
    conversation_uuid = str(uuid4())
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO conversations(uuid, document_id, user_id, title, context_node_id)
            VALUES(?, ?, ?, ?, ?)
            """,
            (conversation_uuid, document_id, user_id, title, context_node_id),
        )
        row = conn.execute(
            "SELECT * FROM conversations WHERE uuid = ?",
            (conversation_uuid,),
        ).fetchone()
    if row is None:
        raise RuntimeError("created conversation cannot be loaded")
    return _conversation_to_payload(row)


def get_conversation(conversation_uuid: str) -> dict[str, Any] | None:
    """Get a conversation by UUID."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE uuid = ?",
            (conversation_uuid,),
        ).fetchone()
    if row is None:
        return None
    return _conversation_to_payload(row)


def get_conversation_by_id(conversation_id: int) -> dict[str, Any] | None:
    """Get a conversation by internal ID."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
    if row is None:
        return None
    return _conversation_to_payload(row)


def list_conversations(
    document_id: str,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List conversations for a document, optionally filtered by status."""
    with _connect() as conn:
        if status:
            rows = conn.execute(
                """
                SELECT * FROM conversations
                WHERE document_id = ? AND status = ?
                ORDER BY updated_at DESC
                """,
                (document_id, status),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM conversations
                WHERE document_id = ?
                ORDER BY updated_at DESC
                """,
                (document_id,),
            ).fetchall()
    return [_conversation_to_payload(row) for row in rows]


def update_conversation(
    conversation_uuid: str,
    updates: dict[str, Any],
) -> dict[str, Any] | None:
    """Update a conversation's fields."""
    current = get_conversation(conversation_uuid)
    if current is None:
        return None

    title = updates.get("title", current["title"])
    status = updates.get("status", current["status"])
    context_node_id = updates.get("context_node_id", current["context_node_id"])

    with _connect() as conn:
        conn.execute(
            """
            UPDATE conversations
            SET title = ?, status = ?, context_node_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE uuid = ?
            """,
            (title, status, context_node_id, conversation_uuid),
        )
    return get_conversation(conversation_uuid)


def delete_conversation(conversation_uuid: str) -> bool:
    """Delete a conversation (cascade deletes messages and modifications)."""
    with _connect() as conn:
        result = conn.execute(
            "DELETE FROM conversations WHERE uuid = ?",
            (conversation_uuid,),
        )
    return result.rowcount > 0


# ============ Message CRUD ============

def _message_to_payload(row: sqlite3.Row) -> dict[str, Any]:
    metadata = row["metadata"]
    return {
        "id": row["id"],
        "conversation_id": row["conversation_id"],
        "role": row["role"],
        "content": row["content"],
        "metadata": json.loads(metadata) if metadata else None,
        "created_at": row["created_at"],
    }


def create_message(
    conversation_id: int,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a new message in a conversation."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO messages(conversation_id, role, content, metadata)
            VALUES(?, ?, ?, ?)
            """,
            (conversation_id, role, content, json.dumps(metadata) if metadata else None),
        )
        # Update conversation's updated_at
        conn.execute(
            """
            UPDATE conversations SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (conversation_id,),
        )
        row = conn.execute(
            """
            SELECT * FROM messages
            WHERE conversation_id = ? AND id = last_insert_rowid()
            """,
            (conversation_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError("created message cannot be loaded")
    return _message_to_payload(row)


def list_messages(conversation_id: int) -> list[dict[str, Any]]:
    """List all messages in a conversation, ordered by creation time."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
            """,
            (conversation_id,),
        ).fetchall()
    return [_message_to_payload(row) for row in rows]


def get_message(message_id: int) -> dict[str, Any] | None:
    """Get a specific message by ID."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM messages WHERE id = ?",
            (message_id,),
        ).fetchone()
    if row is None:
        return None
    return _message_to_payload(row)


# ============ Node Modification CRUD ============

def _modification_to_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "conversation_id": row["conversation_id"],
        "message_id": row["message_id"],
        "node_id": row["node_id"],
        "modification_type": row["modification_type"],
        "before_value": json.loads(row["before_value"]) if row["before_value"] else None,
        "after_value": json.loads(row["after_value"]) if row["after_value"] else None,
        "status": row["status"],
        "created_at": row["created_at"],
    }


def create_modification(
    conversation_id: int,
    message_id: int,
    node_id: str,
    modification_type: str,
    before_value: dict[str, Any] | None = None,
    after_value: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a node modification record."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO node_modifications(
                conversation_id, message_id, node_id, modification_type,
                before_value, after_value
            )
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id, message_id, node_id, modification_type,
                json.dumps(before_value) if before_value else None,
                json.dumps(after_value) if after_value else None,
            ),
        )
        row = conn.execute(
            """
            SELECT * FROM node_modifications
            WHERE conversation_id = ? AND id = last_insert_rowid()
            """,
            (conversation_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError("created modification cannot be loaded")
    return _modification_to_payload(row)


def list_modifications(conversation_id: int, status: str | None = None) -> list[dict[str, Any]]:
    """List modifications for a conversation, optionally filtered by status."""
    with _connect() as conn:
        if status:
            rows = conn.execute(
                """
                SELECT * FROM node_modifications
                WHERE conversation_id = ? AND status = ?
                ORDER BY created_at ASC
                """,
                (conversation_id, status),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM node_modifications
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                """,
                (conversation_id,),
            ).fetchall()
    return [_modification_to_payload(row) for row in rows]


def get_modification(modification_id: int) -> dict[str, Any] | None:
    """Get a specific modification by ID."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM node_modifications WHERE id = ?",
            (modification_id,),
        ).fetchone()
    if row is None:
        return None
    return _modification_to_payload(row)


def update_modification_status(
    modification_id: int,
    status: str,
) -> dict[str, Any] | None:
    """Update a modification's status (accepted/rejected)."""
    with _connect() as conn:
        result = conn.execute(
            """
            UPDATE node_modifications SET status = ?
            WHERE id = ?
            """,
            (status, modification_id),
        )
        if result.rowcount == 0:
            return None
    return get_modification(modification_id)


def batch_update_modifications_status(
    conversation_id: int,
    message_id: int | None = None,
    status: str = "accepted",
) -> int:
    """Batch update modifications status for a conversation or message.

    Returns the number of modifications updated.
    """
    with _connect() as conn:
        if message_id is not None:
            result = conn.execute(
                """
                UPDATE node_modifications SET status = ?
                WHERE conversation_id = ? AND message_id = ? AND status = 'pending'
                """,
                (status, conversation_id, message_id),
            )
        else:
            result = conn.execute(
                """
                UPDATE node_modifications SET status = ?
                WHERE conversation_id = ? AND status = 'pending'
                """,
                (status, conversation_id),
            )
    return result.rowcount


def count_pending_modifications(conversation_id: int) -> int:
    """Count pending modifications for a conversation."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) as count FROM node_modifications
            WHERE conversation_id = ? AND status = 'pending'
            """,
            (conversation_id,),
        ).fetchone()
    return row["count"] if row else 0


# ============ Conversation with Messages ============

def get_conversation_with_messages(conversation_uuid: str) -> dict[str, Any] | None:
    """Get a conversation with all its messages and pending modifications."""
    conversation = get_conversation(conversation_uuid)
    if conversation is None:
        return None

    conversation_id = conversation["id"]
    messages = list_messages(conversation_id)
    pending_modifications = list_modifications(conversation_id, status="pending")

    return {
        **conversation,
        "messages": messages,
        "pending_modifications": pending_modifications,
    }
