"""Tests for commit workspace service.

AUTO-04: 提交工作区与合并区
"""

import json
from pathlib import Path

import pytest

from app.core.settings import get_settings
from app.services.commit_workspace import (
    WorkspaceStatus,
    create_commit_workspace,
    discard_commit_workspace,
    get_commit_workspace,
    get_workspace_diff,
    list_commit_workspaces,
    merge_commit_workspace,
)
from app.services.document_store import create_document, get_document
from app.services.dev_task_store import create_dev_task


@pytest.fixture
def setup_env(monkeypatch, tmp_path: Path) -> None:
    """Configure test environment."""
    db_path = tmp_path / "commit_workspace_test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    get_settings.cache_clear()


class TestCommitWorkspaceCRUD:
    """Tests for basic CRUD operations."""

    def test_create_and_get_workspace(self, setup_env, monkeypatch, tmp_path: Path) -> None:
        """Test creating and retrieving a workspace."""
        # Create document and task
        doc = create_document("Test Doc", {"id": "root", "children": []}, owner_id="user-1")
        task = create_dev_task("Test requirement", document_id=doc["id"])

        # Create workspace
        snapshot_before = {"id": "root", "children": []}
        snapshot_after = {"id": "root", "children": [{"id": "node-1", "text": "New Node"}]}

        workspace = create_commit_workspace(
            task_id=task["id"],
            document_id=doc["id"],
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
            changes_summary="Added new node",
            created_by="user-1",
        )

        assert workspace["id"] is not None
        assert workspace["task_id"] == task["id"]
        assert workspace["document_id"] == doc["id"]
        assert workspace["snapshot_before"] == snapshot_before
        assert workspace["snapshot_after"] == snapshot_after
        assert workspace["changes_summary"] == "Added new node"
        assert workspace["status"] == WorkspaceStatus.PENDING
        assert workspace["created_by"] == "user-1"
        assert workspace["merged_by"] is None

        # Retrieve workspace
        retrieved = get_commit_workspace(workspace["id"])
        assert retrieved is not None
        assert retrieved["id"] == workspace["id"]

    def test_create_workspace_document_not_found(self, setup_env, monkeypatch, tmp_path: Path) -> None:
        """Test creating workspace for non-existent document."""
        task = create_dev_task("Test requirement")

        with pytest.raises(ValueError, match="Document not found"):
            create_commit_workspace(
                task_id=task["id"],
                document_id="non-existent-doc",
                snapshot_before=None,
                snapshot_after={"id": "root"},
                changes_summary="Test",
                created_by="user-1",
            )

    def test_create_workspace_duplicate_pending(self, setup_env, monkeypatch, tmp_path: Path) -> None:
        """Test that creating duplicate pending workspace fails."""
        doc = create_document("Test Doc", {"id": "root", "children": []}, owner_id="user-1")
        task = create_dev_task("Test requirement", document_id=doc["id"])

        # Create first workspace
        create_commit_workspace(
            task_id=task["id"],
            document_id=doc["id"],
            snapshot_before={"id": "root"},
            snapshot_after={"id": "root", "children": [{"id": "n1"}]},
            changes_summary="First change",
            created_by="user-1",
        )

        # Try to create second pending workspace for same document
        task2 = create_dev_task("Second requirement", document_id=doc["id"])
        with pytest.raises(ValueError, match="already has a pending workspace"):
            create_commit_workspace(
                task_id=task2["id"],
                document_id=doc["id"],
                snapshot_before={"id": "root"},
                snapshot_after={"id": "root", "children": [{"id": "n2"}]},
                changes_summary="Second change",
                created_by="user-1",
            )

    def test_list_workspaces(self, setup_env, monkeypatch, tmp_path: Path) -> None:
        """Test listing workspaces with filters."""
        # Create documents and workspaces
        doc1 = create_document("Doc 1", {"id": "root1"}, owner_id="user-1")
        doc2 = create_document("Doc 2", {"id": "root2"}, owner_id="user-1")
        task1 = create_dev_task("Task 1", document_id=doc1["id"])
        task2 = create_dev_task("Task 2", document_id=doc2["id"])

        ws1 = create_commit_workspace(
            task_id=task1["id"],
            document_id=doc1["id"],
            snapshot_before={"id": "root1"},
            snapshot_after={"id": "root1", "children": [{"id": "n1"}]},
            changes_summary="Change 1",
            created_by="user-1",
        )

        ws2 = create_commit_workspace(
            task_id=task2["id"],
            document_id=doc2["id"],
            snapshot_before={"id": "root2"},
            snapshot_after={"id": "root2", "children": [{"id": "n2"}]},
            changes_summary="Change 2",
            created_by="user-1",
        )

        # Merge first workspace
        merge_commit_workspace(ws1["id"], "user-2")

        # List all
        all_ws = list_commit_workspaces()
        assert len(all_ws) == 2

        # List by status
        pending = list_commit_workspaces(status=WorkspaceStatus.PENDING)
        assert len(pending) == 1
        assert pending[0]["id"] == ws2["id"]

        merged = list_commit_workspaces(status=WorkspaceStatus.MERGED)
        assert len(merged) == 1
        assert merged[0]["id"] == ws1["id"]

        # List by document
        doc1_ws = list_commit_workspaces(document_id=doc1["id"])
        assert len(doc1_ws) == 1

    def test_get_non_existent_workspace(self, setup_env, monkeypatch, tmp_path: Path) -> None:
        """Test getting non-existent workspace."""
        workspace = get_commit_workspace("non-existent-id")
        assert workspace is None


class TestMergeAndDiscard:
    """Tests for merge and discard operations."""

    def test_merge_workspace(self, setup_env, monkeypatch, tmp_path: Path) -> None:
        """Test merging workspace into document."""
        # Setup
        doc = create_document("Test Doc", {"id": "root", "text": "Root", "children": []}, owner_id="user-1")
        task = create_dev_task("Test requirement", document_id=doc["id"])

        snapshot_before = {"id": "root", "text": "Root", "children": []}
        snapshot_after = {"id": "root", "text": "Root", "children": [{"id": "node-1", "text": "New Node"}]}

        workspace = create_commit_workspace(
            task_id=task["id"],
            document_id=doc["id"],
            snapshot_before=snapshot_before,
            snapshot_after=snapshot_after,
            changes_summary="Added new node",
            created_by="user-1",
        )

        # Merge
        merged = merge_commit_workspace(workspace["id"], "user-2")

        assert merged["status"] == WorkspaceStatus.MERGED
        assert merged["merged_by"] == "user-2"
        assert merged["merged_at"] is not None

        # Verify document was updated
        updated_doc = get_document(doc["id"])
        assert updated_doc is not None
        assert updated_doc["content"] == snapshot_after

    def test_merge_non_pending_workspace(self, setup_env, monkeypatch, tmp_path: Path) -> None:
        """Test that merging non-pending workspace fails."""
        doc = create_document("Test Doc", {"id": "root"}, owner_id="user-1")
        task = create_dev_task("Test requirement", document_id=doc["id"])

        workspace = create_commit_workspace(
            task_id=task["id"],
            document_id=doc["id"],
            snapshot_before={"id": "root"},
            snapshot_after={"id": "root", "children": [{"id": "n1"}]},
            changes_summary="Test",
            created_by="user-1",
        )

        # Merge first time
        merge_commit_workspace(workspace["id"], "user-2")

        # Try to merge again
        with pytest.raises(ValueError, match="not in pending status"):
            merge_commit_workspace(workspace["id"], "user-3")

    def test_merge_non_existent_workspace(self, setup_env, monkeypatch, tmp_path: Path) -> None:
        """Test merging non-existent workspace."""
        with pytest.raises(ValueError, match="Workspace not found"):
            merge_commit_workspace("non-existent-id", "user-1")

    def test_discard_workspace(self, setup_env, monkeypatch, tmp_path: Path) -> None:
        """Test discarding workspace."""
        doc = create_document("Test Doc", {"id": "root", "text": "Root"}, owner_id="user-1")
        task = create_dev_task("Test requirement", document_id=doc["id"])

        workspace = create_commit_workspace(
            task_id=task["id"],
            document_id=doc["id"],
            snapshot_before={"id": "root", "text": "Root"},
            snapshot_after={"id": "root", "text": "Root", "children": [{"id": "n1"}]},
            changes_summary="Test",
            created_by="user-1",
        )

        # Discard
        discarded = discard_commit_workspace(workspace["id"], "user-2")

        assert discarded["status"] == WorkspaceStatus.DISCARDED
        assert discarded["merged_by"] == "user-2"

        # Verify document was NOT updated
        unchanged_doc = get_document(doc["id"])
        assert unchanged_doc is not None
        assert unchanged_doc["content"] == {"id": "root", "text": "Root"}

    def test_discard_non_pending_workspace(self, setup_env, monkeypatch, tmp_path: Path) -> None:
        """Test that discarding non-pending workspace fails."""
        doc = create_document("Test Doc", {"id": "root"}, owner_id="user-1")
        task = create_dev_task("Test requirement", document_id=doc["id"])

        workspace = create_commit_workspace(
            task_id=task["id"],
            document_id=doc["id"],
            snapshot_before={"id": "root"},
            snapshot_after={"id": "root", "children": [{"id": "n1"}]},
            changes_summary="Test",
            created_by="user-1",
        )

        # Discard first time
        discard_commit_workspace(workspace["id"], "user-2")

        # Try to discard again
        with pytest.raises(ValueError, match="not in pending status"):
            discard_commit_workspace(workspace["id"], "user-3")


class TestWorkspaceDiff:
    """Tests for workspace diff functionality."""

    def test_get_diff_added_nodes(self, setup_env, monkeypatch, tmp_path: Path) -> None:
        """Test diff with added nodes."""
        doc = create_document("Test Doc", {"id": "root", "children": []}, owner_id="user-1")
        task = create_dev_task("Test requirement", document_id=doc["id"])

        workspace = create_commit_workspace(
            task_id=task["id"],
            document_id=doc["id"],
            snapshot_before={"id": "root", "children": []},
            snapshot_after={
                "id": "root",
                "children": [
                    {"id": "node-1", "text": "Node 1"},
                    {"id": "node-2", "text": "Node 2"},
                ],
            },
            changes_summary="Added nodes",
            created_by="user-1",
        )

        diff = get_workspace_diff(workspace["id"])
        assert diff is not None

        assert len(diff["added"]) == 2
        assert diff["stats"]["added_count"] == 2
        assert diff["stats"]["removed_count"] == 0
        assert diff["stats"]["modified_count"] == 0

        added_texts = {n["text"] for n in diff["added"]}
        assert "Node 1" in added_texts
        assert "Node 2" in added_texts

    def test_get_diff_removed_nodes(self, setup_env, monkeypatch, tmp_path: Path) -> None:
        """Test diff with removed nodes."""
        doc = create_document("Test Doc", {
            "id": "root",
            "children": [
                {"id": "node-1", "text": "Node 1"},
                {"id": "node-2", "text": "Node 2"},
            ],
        }, owner_id="user-1")
        task = create_dev_task("Test requirement", document_id=doc["id"])

        workspace = create_commit_workspace(
            task_id=task["id"],
            document_id=doc["id"],
            snapshot_before={
                "id": "root",
                "children": [
                    {"id": "node-1", "text": "Node 1"},
                    {"id": "node-2", "text": "Node 2"},
                ],
            },
            snapshot_after={"id": "root", "children": []},
            changes_summary="Removed nodes",
            created_by="user-1",
        )

        diff = get_workspace_diff(workspace["id"])
        assert diff is not None

        assert len(diff["removed"]) == 2
        assert diff["stats"]["removed_count"] == 2
        assert diff["stats"]["added_count"] == 0

    def test_get_diff_modified_nodes(self, setup_env, monkeypatch, tmp_path: Path) -> None:
        """Test diff with modified nodes."""
        doc = create_document("Test Doc", {
            "id": "root",
            "children": [{"id": "node-1", "text": "Old Text"}],
        }, owner_id="user-1")
        task = create_dev_task("Test requirement", document_id=doc["id"])

        workspace = create_commit_workspace(
            task_id=task["id"],
            document_id=doc["id"],
            snapshot_before={
                "id": "root",
                "children": [{"id": "node-1", "text": "Old Text"}],
            },
            snapshot_after={
                "id": "root",
                "children": [{"id": "node-1", "text": "New Text"}],
            },
            changes_summary="Modified node",
            created_by="user-1",
        )

        diff = get_workspace_diff(workspace["id"])
        assert diff is not None

        assert len(diff["modified"]) == 1
        assert diff["stats"]["modified_count"] == 1
        assert diff["modified"][0]["text"] == "New Text"

    def test_get_diff_non_existent(self, setup_env, monkeypatch, tmp_path: Path) -> None:
        """Test diff for non-existent workspace."""
        diff = get_workspace_diff("non-existent-id")
        assert diff is None
