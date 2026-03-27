"""
Tests for Agent Conversation Model and API (AG-02)

AG-02 should provide:
- Conversation CRUD (create, read, update, delete)
- Message management within conversations
- Node modification tracking with status (pending/accepted/rejected)
- Batch modification status updates
"""

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest


# ============ Conversation Store Tests ============

@pytest.fixture
def temp_db(monkeypatch):
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        # Set environment variable for database path
        monkeypatch.setenv("DB_PATH", str(db_path))

        # Clear settings cache to pick up new DB path
        from app.core.settings import get_settings
        get_settings.cache_clear()

        yield db_path


def test_conversation_migration_tables_exist(temp_db):
    """Migration 0008 should create conversations, messages, and node_modifications tables."""
    # Trigger migration by calling any production code
    from app.services.document_store import create_document
    create_document("Trigger Migration", {"id": "root", "text": "Root"}, "user-1")

    # Now check the tables exist
    conn = sqlite3.connect(temp_db)
    conn.row_factory = sqlite3.Row

    # Check conversations table exists
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('conversations', 'messages', 'node_modifications')"
    ).fetchall()
    table_names = {row["name"] for row in tables}

    assert "conversations" in table_names, f"Expected 'conversations' table, got: {table_names}"
    assert "messages" in table_names, f"Expected 'messages' table, got: {table_names}"
    assert "node_modifications" in table_names, f"Expected 'node_modifications' table, got: {table_names}"

    conn.close()


def test_conversation_store_create(temp_db):
    """Conversation store should create a new conversation."""
    from app.services.conversation_store import create_conversation, get_conversation

    # First create a document (required for foreign key)
    from app.services.document_store import create_document

    doc = create_document("Test Document", {"id": "root", "text": "Root"}, "user-1")

    # Create conversation
    conversation = create_conversation(
        document_id=doc["id"],
        user_id="user-1",
        title="Test Conversation",
        context_node_id="node-1",
    )

    assert conversation["uuid"] is not None
    assert conversation["document_id"] == doc["id"]
    assert conversation["user_id"] == "user-1"
    assert conversation["title"] == "Test Conversation"
    assert conversation["status"] == "active"
    assert conversation["context_node_id"] == "node-1"


def test_conversation_store_list(temp_db):
    """Conversation store should list conversations for a document."""
    from app.services.conversation_store import create_conversation, list_conversations
    from app.services.document_store import create_document

    doc = create_document("Test Document", {"id": "root", "text": "Root"}, "user-1")

    # Create multiple conversations
    conv1 = create_conversation(doc["id"], "user-1", "Conv 1")
    conv2 = create_conversation(doc["id"], "user-1", "Conv 2")

    # Update one to closed status
    from app.services.conversation_store import update_conversation
    update_conversation(conv1["uuid"], {"status": "closed"})

    # List all
    all_convos = list_conversations(doc["id"])
    assert len(all_convos) == 2

    # List by status
    active_convos = list_conversations(doc["id"], status="active")
    assert len(active_convos) == 1
    assert active_convos[0]["uuid"] == conv2["uuid"]

    closed_convos = list_conversations(doc["id"], status="closed")
    assert len(closed_convos) == 1
    assert closed_convos[0]["uuid"] == conv1["uuid"]


def test_conversation_store_update(temp_db):
    """Conversation store should update conversation fields."""
    from app.services.conversation_store import create_conversation, update_conversation, get_conversation
    from app.services.document_store import create_document

    doc = create_document("Test Document", {"id": "root", "text": "Root"}, "user-1")
    conv = create_conversation(doc["id"], "user-1", "Original Title")

    # Update title
    updated = update_conversation(conv["uuid"], {"title": "New Title"})
    assert updated["title"] == "New Title"

    # Update status
    updated = update_conversation(conv["uuid"], {"status": "closed"})
    assert updated["status"] == "closed"

    # Update context node
    updated = update_conversation(conv["uuid"], {"context_node_id": "node-new"})
    assert updated["context_node_id"] == "node-new"


def test_conversation_store_delete(temp_db):
    """Conversation store should delete a conversation."""
    from app.services.conversation_store import create_conversation, delete_conversation, get_conversation
    from app.services.document_store import create_document

    doc = create_document("Test Document", {"id": "root", "text": "Root"}, "user-1")
    conv = create_conversation(doc["id"], "user-1", "To Delete")

    # Delete
    success = delete_conversation(conv["uuid"])
    assert success is True

    # Verify deleted
    result = get_conversation(conv["uuid"])
    assert result is None


def test_message_store_create(temp_db):
    """Message store should create messages in a conversation."""
    from app.services.conversation_store import create_conversation, create_message, list_messages
    from app.services.document_store import create_document

    doc = create_document("Test Document", {"id": "root", "text": "Root"}, "user-1")
    conv = create_conversation(doc["id"], "user-1", "Test")

    # Create user message
    msg1 = create_message(conv["id"], "user", "Hello AI")

    assert msg1["conversation_id"] == conv["id"]
    assert msg1["role"] == "user"
    assert msg1["content"] == "Hello AI"

    # Create assistant message
    msg2 = create_message(conv["id"], "assistant", "Hello! How can I help?")
    assert msg2["role"] == "assistant"

    # List messages
    messages = list_messages(conv["id"])
    assert len(messages) == 2


def test_message_with_metadata(temp_db):
    """Messages can include metadata JSON."""
    from app.services.conversation_store import create_conversation, create_message, get_message
    from app.services.document_store import create_document

    doc = create_document("Test Document", {"id": "root", "text": "Root"}, "user-1")
    conv = create_conversation(doc["id"], "user-1", "Test")

    metadata = {"node_changes": 3, "tokens": 150}
    msg = create_message(conv["id"], "assistant", "Response", metadata=metadata)

    assert msg["metadata"]["node_changes"] == 3
    assert msg["metadata"]["tokens"] == 150


def test_modification_create(temp_db):
    """Node modification records should be created correctly."""
    from app.services.conversation_store import (
        create_conversation, create_message, create_modification, list_modifications
    )
    from app.services.document_store import create_document

    doc = create_document("Test Document", {"id": "root", "text": "Root"}, "user-1")
    conv = create_conversation(doc["id"], "user-1", "Test")
    msg = create_message(conv["id"], "assistant", "AI response with modifications")

    # Create a modification
    mod = create_modification(
        conversation_id=conv["id"],
        message_id=msg["id"],
        node_id="node-1",
        modification_type="update",
        before_value={"text": "Old text"},
        after_value={"text": "New text"},
    )

    assert mod["node_id"] == "node-1"
    assert mod["modification_type"] == "update"
    assert mod["before_value"]["text"] == "Old text"
    assert mod["after_value"]["text"] == "New text"
    assert mod["status"] == "pending"


def test_modification_status_update(temp_db):
    """Modification status should be updatable."""
    from app.services.conversation_store import (
        create_conversation, create_message, create_modification, update_modification_status
    )
    from app.services.document_store import create_document

    doc = create_document("Test Document", {"id": "root", "text": "Root"}, "user-1")
    conv = create_conversation(doc["id"], "user-1", "Test")
    msg = create_message(conv["id"], "assistant", "Response")
    mod = create_modification(conv["id"], msg["id"], "node-1", "update")

    # Accept modification
    updated = update_modification_status(mod["id"], "accepted")
    assert updated["status"] == "accepted"

    # Reject modification
    mod2 = create_modification(conv["id"], msg["id"], "node-2", "create")
    updated2 = update_modification_status(mod2["id"], "rejected")
    assert updated2["status"] == "rejected"


def test_batch_modification_update(temp_db):
    """Batch update should update all pending modifications."""
    from app.services.conversation_store import (
        create_conversation, create_message, create_modification,
        batch_update_modifications_status, list_modifications, count_pending_modifications
    )
    from app.services.document_store import create_document

    doc = create_document("Test Document", {"id": "root", "text": "Root"}, "user-1")
    conv = create_conversation(doc["id"], "user-1", "Test")
    msg = create_message(conv["id"], "assistant", "Response")

    # Create multiple modifications
    create_modification(conv["id"], msg["id"], "node-1", "update")
    create_modification(conv["id"], msg["id"], "node-2", "create")
    create_modification(conv["id"], msg["id"], "node-3", "delete")

    # Verify all pending
    assert count_pending_modifications(conv["id"]) == 3

    # Accept all
    count = batch_update_modifications_status(conv["id"], status="accepted")
    assert count == 3

    # Verify no pending
    assert count_pending_modifications(conv["id"]) == 0

    # All should be accepted
    mods = list_modifications(conv["id"])
    assert all(m["status"] == "accepted" for m in mods)


def test_batch_modification_by_message(temp_db):
    """Batch update can target specific message's modifications."""
    from app.services.conversation_store import (
        create_conversation, create_message, create_modification,
        batch_update_modifications_status, list_modifications
    )
    from app.services.document_store import create_document

    doc = create_document("Test Document", {"id": "root", "text": "Root"}, "user-1")
    conv = create_conversation(doc["id"], "user-1", "Test")

    msg1 = create_message(conv["id"], "assistant", "Response 1")
    msg2 = create_message(conv["id"], "assistant", "Response 2")

    # Create modifications for each message
    create_modification(conv["id"], msg1["id"], "node-1", "update")
    create_modification(conv["id"], msg2["id"], "node-2", "create")

    # Accept only msg1's modifications
    count = batch_update_modifications_status(conv["id"], message_id=msg1["id"], status="accepted")
    assert count == 1

    # Verify
    mods = list_modifications(conv["id"])
    for m in mods:
        if m["message_id"] == msg1["id"]:
            assert m["status"] == "accepted"
        else:
            assert m["status"] == "pending"


def test_conversation_cascade_delete(temp_db):
    """Deleting a conversation should cascade delete messages and modifications."""
    from app.services.conversation_store import (
        create_conversation, create_message, create_modification,
        delete_conversation, list_messages, list_modifications
    )
    from app.services.document_store import create_document

    doc = create_document("Test Document", {"id": "root", "text": "Root"}, "user-1")
    conv = create_conversation(doc["id"], "user-1", "Test")
    msg = create_message(conv["id"], "assistant", "Response")
    create_modification(conv["id"], msg["id"], "node-1", "update")

    # Delete conversation
    delete_conversation(conv["uuid"])

    # Verify cascade delete
    # Note: SQLite cascade should handle this, but we verify by checking
    # that the data is gone
    messages = list_messages(conv["id"])
    modifications = list_modifications(conv["id"])

    # Both should be empty after cascade delete
    assert len(messages) == 0
    assert len(modifications) == 0


def test_conversation_with_messages(temp_db):
    """get_conversation_with_messages should return full conversation data."""
    from app.services.conversation_store import (
        create_conversation, create_message, create_modification,
        get_conversation_with_messages
    )
    from app.services.document_store import create_document

    doc = create_document("Test Document", {"id": "root", "text": "Root"}, "user-1")
    conv = create_conversation(doc["id"], "user-1", "Test")

    msg1 = create_message(conv["id"], "user", "Hello")
    msg2 = create_message(conv["id"], "assistant", "Hi there!")
    create_modification(conv["id"], msg2["id"], "node-1", "update")

    # Get full conversation
    result = get_conversation_with_messages(conv["uuid"])

    assert result is not None
    assert len(result["messages"]) == 2
    assert len(result["pending_modifications"]) == 1
