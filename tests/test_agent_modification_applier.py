"""
Tests for AG-03: Diff + Keep/Undo

AG-03 should provide:
- Apply modification to document content (keep/accept)
- Revert modification from document content (undo/reject)
- Batch apply/revert operations
- Modification state validation
"""

import os
import tempfile
import sqlite3
from pathlib import Path

import pytest


# ============ Test Fixtures ============

@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        # Run migrations manually
        migrations_dir = Path(__file__).resolve().parent.parent / "backend" / "app" / "db" / "migrations"

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")

        # Run all migrations
        for migration_file in sorted(migrations_dir.glob("*.sql")):
            sql = migration_file.read_text(encoding="utf-8")
            conn.executescript(sql)

        conn.close()

        # Set environment variable for database path
        old_env = os.environ.get("XMIND_DB_PATH")
        os.environ["XMIND_DB_PATH"] = str(db_path)

        yield db_path

        # Cleanup
        if old_env is not None:
            os.environ["XMIND_DB_PATH"] = old_env
        else:
            os.environ.pop("XMIND_DB_PATH", None)


@pytest.fixture
def sample_document(temp_db):
    """Create a sample document with mind map content."""
    from app.services.document_store import create_document

    content = {
        "id": "root",
        "text": "Project Plan",
        "children": [
            {
                "id": "node-1",
                "text": "Phase 1",
                "children": [
                    {"id": "node-1-1", "text": "Task A"},
                    {"id": "node-1-2", "text": "Task B"},
                ]
            },
            {
                "id": "node-2",
                "text": "Phase 2",
                "children": []
            }
        ]
    }
    doc = create_document("Test Document", content, "user-1")
    return doc


@pytest.fixture
def sample_conversation(sample_document):
    """Create a sample conversation for testing modifications."""
    from app.services.conversation_store import create_conversation

    conv = create_conversation(
        document_id=sample_document["id"],
        user_id="user-1",
        title="Test Conversation",
    )
    return conv


# ============ Node Finder Tests ============

def test_find_node_in_content(sample_document):
    """Should find a node by ID in the mind map content."""
    from app.services.modification_applier import find_node_in_content

    content = sample_document["content"]

    # Find root
    node, parent = find_node_in_content(content, "root")
    assert node is not None
    assert node["text"] == "Project Plan"
    assert parent is None  # root has no parent

    # Find nested node
    node, parent = find_node_in_content(content, "node-1-1")
    assert node is not None
    assert node["text"] == "Task A"
    assert parent["id"] == "node-1"

    # Non-existent node
    node, parent = find_node_in_content(content, "nonexistent")
    assert node is None
    assert parent is None


# ============ Apply Modification Tests ============

def test_apply_node_update_modification(temp_db, sample_document, sample_conversation):
    """Applying an 'update' modification should update node text in document."""
    from app.services.conversation_store import create_message, create_modification
    from app.services.modification_applier import apply_modification
    from app.services.document_store import get_document

    msg = create_message(sample_conversation["id"], "assistant", "Updated node text")

    # Create update modification
    mod = create_modification(
        conversation_id=sample_conversation["id"],
        message_id=msg["id"],
        node_id="node-1",
        modification_type="update",
        before_value={"text": "Phase 1"},
        after_value={"text": "Phase 1 - Planning"},
    )

    # Apply modification
    result = apply_modification(mod["id"])

    assert result["applied"] is True
    assert result["node_id"] == "node-1"

    # Verify document content was updated
    doc = get_document(sample_document["id"])
    content = doc["content"]

    # Find the updated node
    from app.services.modification_applier import find_node_in_content
    node, _ = find_node_in_content(content, "node-1")
    assert node["text"] == "Phase 1 - Planning"


def test_apply_node_create_modification(temp_db, sample_document, sample_conversation):
    """Applying a 'create' modification should add a new node to document."""
    from app.services.conversation_store import create_message, create_modification
    from app.services.modification_applier import apply_modification
    from app.services.document_store import get_document

    msg = create_message(sample_conversation["id"], "assistant", "Added new node")

    # Create create modification (add child to node-2)
    mod = create_modification(
        conversation_id=sample_conversation["id"],
        message_id=msg["id"],
        node_id="node-2-1",
        modification_type="create",
        before_value=None,
        after_value={"text": "New Task", "parent_id": "node-2"},
    )

    # Apply modification
    result = apply_modification(mod["id"])

    assert result["applied"] is True

    # Verify new node was added
    doc = get_document(sample_document["id"])
    content = doc["content"]

    from app.services.modification_applier import find_node_in_content
    new_node, parent = find_node_in_content(content, "node-2-1")
    assert new_node is not None
    assert new_node["text"] == "New Task"
    assert parent["id"] == "node-2"


def test_apply_node_delete_modification(temp_db, sample_document, sample_conversation):
    """Applying a 'delete' modification should remove node from document."""
    from app.services.conversation_store import create_message, create_modification
    from app.services.modification_applier import apply_modification
    from app.services.document_store import get_document

    msg = create_message(sample_conversation["id"], "assistant", "Deleted node")

    # Create delete modification
    mod = create_modification(
        conversation_id=sample_conversation["id"],
        message_id=msg["id"],
        node_id="node-1-2",
        modification_type="delete",
        before_value={"text": "Task B"},
        after_value=None,
    )

    # Apply modification
    result = apply_modification(mod["id"])

    assert result["applied"] is True

    # Verify node was deleted
    doc = get_document(sample_document["id"])
    content = doc["content"]

    from app.services.modification_applier import find_node_in_content
    node, _ = find_node_in_content(content, "node-1-2")
    assert node is None  # Should not exist anymore


# ============ Revert Modification Tests ============

def test_revert_node_update_modification(temp_db, sample_document, sample_conversation):
    """Reverting an 'update' modification should restore original text."""
    from app.services.conversation_store import (
        create_message, create_modification, update_modification_status
    )
    from app.services.modification_applier import apply_modification, revert_modification
    from app.services.document_store import get_document

    msg = create_message(sample_conversation["id"], "assistant", "Updated node")

    mod = create_modification(
        conversation_id=sample_conversation["id"],
        message_id=msg["id"],
        node_id="node-1",
        modification_type="update",
        before_value={"text": "Phase 1"},
        after_value={"text": "Phase 1 - Planning"},
    )

    # First apply the modification
    apply_modification(mod["id"])

    # Now revert it
    result = revert_modification(mod["id"])

    assert result["reverted"] is True

    # Verify original text is restored
    doc = get_document(sample_document["id"])
    content = doc["content"]

    from app.services.modification_applier import find_node_in_content
    node, _ = find_node_in_content(content, "node-1")
    assert node["text"] == "Phase 1"


def test_revert_node_create_modification(temp_db, sample_document, sample_conversation):
    """Reverting a 'create' modification should remove the created node."""
    from app.services.conversation_store import (
        create_message, create_modification, update_modification_status
    )
    from app.services.modification_applier import apply_modification, revert_modification
    from app.services.document_store import get_document

    msg = create_message(sample_conversation["id"], "assistant", "Created node")

    mod = create_modification(
        conversation_id=sample_conversation["id"],
        message_id=msg["id"],
        node_id="node-2-1",
        modification_type="create",
        before_value=None,
        after_value={"text": "New Task", "parent_id": "node-2"},
    )

    # Apply then revert
    apply_modification(mod["id"])
    result = revert_modification(mod["id"])

    assert result["reverted"] is True

    # Verify node was removed
    doc = get_document(sample_document["id"])
    content = doc["content"]

    from app.services.modification_applier import find_node_in_content
    node, _ = find_node_in_content(content, "node-2-1")
    assert node is None


def test_revert_node_delete_modification(temp_db, sample_document, sample_conversation):
    """Reverting a 'delete' modification should restore the deleted node."""
    from app.services.conversation_store import (
        create_message, create_modification, update_modification_status
    )
    from app.services.modification_applier import apply_modification, revert_modification
    from app.services.document_store import get_document

    msg = create_message(sample_conversation["id"], "assistant", "Deleted node")

    # Note: before_value must include parent_id for delete modifications to be revertible
    mod = create_modification(
        conversation_id=sample_conversation["id"],
        message_id=msg["id"],
        node_id="node-1-2",
        modification_type="delete",
        before_value={"text": "Task B", "parent_id": "node-1"},
        after_value=None,
    )

    # Apply then revert
    apply_modification(mod["id"])
    result = revert_modification(mod["id"])

    assert result["reverted"] is True

    # Verify node was restored
    doc = get_document(sample_document["id"])
    content = doc["content"]

    from app.services.modification_applier import find_node_in_content
    node, _ = find_node_in_content(content, "node-1-2")
    assert node is not None
    assert node["text"] == "Task B"


# ============ State Validation Tests ============

def test_cannot_apply_already_accepted_modification(temp_db, sample_document, sample_conversation):
    """Should not apply a modification that's already accepted."""
    from app.services.conversation_store import (
        create_message, create_modification, update_modification_status
    )
    from app.services.modification_applier import apply_modification

    msg = create_message(sample_conversation["id"], "assistant", "Test")

    mod = create_modification(
        conversation_id=sample_conversation["id"],
        message_id=msg["id"],
        node_id="node-1",
        modification_type="update",
        before_value={"text": "Phase 1"},
        after_value={"text": "Updated"},
    )

    # Manually mark as accepted
    update_modification_status(mod["id"], "accepted")

    # Try to apply again
    result = apply_modification(mod["id"])

    assert result["applied"] is False
    assert "already" in result.get("reason", "").lower()


def test_cannot_revert_pending_modification(temp_db, sample_document, sample_conversation):
    """Should not revert a modification that's still pending (not applied)."""
    from app.services.conversation_store import create_message, create_modification
    from app.services.modification_applier import revert_modification

    msg = create_message(sample_conversation["id"], "assistant", "Test")

    mod = create_modification(
        conversation_id=sample_conversation["id"],
        message_id=msg["id"],
        node_id="node-1",
        modification_type="update",
        before_value={"text": "Phase 1"},
        after_value={"text": "Updated"},
    )

    # Try to revert without applying first
    result = revert_modification(mod["id"])

    assert result["reverted"] is False
    assert "not applied" in result.get("reason", "").lower()


# ============ Batch Operations Tests ============

def test_batch_apply_modifications(temp_db, sample_document, sample_conversation):
    """Should apply all pending modifications in batch."""
    from app.services.conversation_store import (
        create_message, create_modification
    )
    from app.services.modification_applier import batch_apply_modifications
    from app.services.document_store import get_document

    msg = create_message(sample_conversation["id"], "assistant", "Batch changes")

    # Create multiple modifications
    create_modification(
        conversation_id=sample_conversation["id"],
        message_id=msg["id"],
        node_id="node-1",
        modification_type="update",
        before_value={"text": "Phase 1"},
        after_value={"text": "Phase 1 - Updated"},
    )
    create_modification(
        conversation_id=sample_conversation["id"],
        message_id=msg["id"],
        node_id="node-2",
        modification_type="update",
        before_value={"text": "Phase 2"},
        after_value={"text": "Phase 2 - Updated"},
    )

    # Batch apply
    result = batch_apply_modifications(sample_conversation["id"])

    assert result["applied_count"] == 2
    assert result["failed_count"] == 0

    # Verify both were applied
    doc = get_document(sample_document["id"])
    content = doc["content"]

    from app.services.modification_applier import find_node_in_content
    node1, _ = find_node_in_content(content, "node-1")
    node2, _ = find_node_in_content(content, "node-2")

    assert node1["text"] == "Phase 1 - Updated"
    assert node2["text"] == "Phase 2 - Updated"


def test_batch_apply_by_message(temp_db, sample_document, sample_conversation):
    """Should apply only modifications from a specific message."""
    from app.services.conversation_store import (
        create_message, create_modification
    )
    from app.services.modification_applier import batch_apply_modifications
    from app.services.document_store import get_document

    msg1 = create_message(sample_conversation["id"], "assistant", "Changes 1")
    msg2 = create_message(sample_conversation["id"], "assistant", "Changes 2")

    create_modification(
        conversation_id=sample_conversation["id"],
        message_id=msg1["id"],
        node_id="node-1",
        modification_type="update",
        before_value={"text": "Phase 1"},
        after_value={"text": "Phase 1 - Msg1"},
    )
    create_modification(
        conversation_id=sample_conversation["id"],
        message_id=msg2["id"],
        node_id="node-2",
        modification_type="update",
        before_value={"text": "Phase 2"},
        after_value={"text": "Phase 2 - Msg2"},
    )

    # Apply only msg1's modifications
    result = batch_apply_modifications(sample_conversation["id"], message_id=msg1["id"])

    assert result["applied_count"] == 1

    # Verify only node-1 was updated
    doc = get_document(sample_document["id"])
    content = doc["content"]

    from app.services.modification_applier import find_node_in_content
    node1, _ = find_node_in_content(content, "node-1")
    node2, _ = find_node_in_content(content, "node-2")

    assert node1["text"] == "Phase 1 - Msg1"
    assert node2["text"] == "Phase 2"  # Not updated


# ============ Diff Preview Tests ============

def test_get_modification_diff(temp_db, sample_document, sample_conversation):
    """Should return a diff preview of the modification."""
    from app.services.conversation_store import create_message, create_modification
    from app.services.modification_applier import get_modification_diff

    msg = create_message(sample_conversation["id"], "assistant", "Test")

    mod = create_modification(
        conversation_id=sample_conversation["id"],
        message_id=msg["id"],
        node_id="node-1",
        modification_type="update",
        before_value={"text": "Phase 1"},
        after_value={"text": "Phase 1 - Planning"},
    )

    diff = get_modification_diff(mod["id"])

    assert diff["modification_id"] == mod["id"]
    assert diff["node_id"] == "node-1"
    assert diff["type"] == "update"
    assert diff["before"]["text"] == "Phase 1"
    assert diff["after"]["text"] == "Phase 1 - Planning"
    assert diff["status"] == "pending"
