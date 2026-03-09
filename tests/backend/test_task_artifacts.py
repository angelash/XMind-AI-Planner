"""Tests for task artifacts storage service.

AUTO-03: Artifacts 存储
"""

import json
from pathlib import Path
import tempfile

import pytest

from app.services.task_artifacts import ArtifactStorage, get_artifact_storage


@pytest.fixture
def temp_storage(tmp_path: Path) -> ArtifactStorage:
    """Create a temporary artifact storage for testing."""
    return ArtifactStorage(base_path=tmp_path / "artifacts")


class TestConversationStorage:
    """Tests for conversation storage."""

    def test_append_conversation_line(self, temp_storage: ArtifactStorage) -> None:
        """Test appending conversation lines."""
        task_id = "test-task-001"

        # Append first line
        temp_storage.append_conversation_line(
            task_id,
            role="user",
            content="Hello, AI!",
        )

        # Append second line with metadata
        temp_storage.append_conversation_line(
            task_id,
            role="assistant",
            content="Hello! How can I help?",
            metadata={"model": "gpt-4"},
        )

        # Read conversation
        conversation = temp_storage.get_conversation(task_id)
        assert len(conversation) == 2

        assert conversation[0]["role"] == "user"
        assert conversation[0]["content"] == "Hello, AI!"
        assert "metadata" not in conversation[0]

        assert conversation[1]["role"] == "assistant"
        assert conversation[1]["content"] == "Hello! How can I help?"
        assert conversation[1]["metadata"]["model"] == "gpt-4"

    def test_get_empty_conversation(self, temp_storage: ArtifactStorage) -> None:
        """Test getting conversation for non-existent task."""
        conversation = temp_storage.get_conversation("non-existent-task")
        assert conversation == []


class TestDiffStorage:
    """Tests for diff storage."""

    def test_save_and_list_diffs(self, temp_storage: ArtifactStorage) -> None:
        """Test saving and listing diffs."""
        task_id = "test-task-002"

        # Save multiple diffs
        temp_storage.save_diff(
            task_id,
            file_path="src/main.py",
            diff_content="--- a/src/main.py\n+++ b/src/main.py\n@@ -1,3 +1,4 @@\n import os\n+import sys\n",
            status="modified",
        )

        temp_storage.save_diff(
            task_id,
            file_path="src/utils.py",
            diff_content="--- a/src/utils.py\n+++ b/src/utils.py\n@@ -1,1 +1,2 @@\n # utils\n+def helper(): pass\n",
            status="added",
        )

        # List diffs
        diffs = temp_storage.list_diffs(task_id)
        assert len(diffs) == 2

        # Check first diff
        assert diffs[0]["file_path"] == "src/main.py"
        assert diffs[0]["status"] == "modified"
        assert "--- a/src/main.py" in diffs[0]["diff"]

        # Check second diff
        assert diffs[1]["file_path"] == "src/utils.py"
        assert diffs[1]["status"] == "added"

    def test_get_specific_diff(self, temp_storage: ArtifactStorage) -> None:
        """Test getting a specific diff."""
        task_id = "test-task-003"

        temp_storage.save_diff(
            task_id,
            file_path="src/app.py",
            diff_content="changes",
        )

        diff = temp_storage.get_diff(task_id, "src/app.py")
        assert diff is not None
        assert diff["diff"] == "changes"

        # Non-existent diff
        diff = temp_storage.get_diff(task_id, "src/other.py")
        assert diff is None

    def test_list_empty_diffs(self, temp_storage: ArtifactStorage) -> None:
        """Test listing diffs for non-existent task."""
        diffs = temp_storage.list_diffs("non-existent-task")
        assert diffs == []


class TestPatchStorage:
    """Tests for patch storage."""

    def test_save_and_get_patch(self, temp_storage: ArtifactStorage) -> None:
        """Test saving and getting patch."""
        task_id = "test-task-004"

        patch_content = "--- a/file1.py\n+++ b/file1.py\n@@ -1 +1 @@\n-old\n+new\n"
        files = ["file1.py", "file2.py"]

        temp_storage.save_patch(task_id, patch_content, files)

        patch = temp_storage.get_patch(task_id)
        assert patch is not None
        assert patch["task_id"] == task_id
        assert patch["patch"] == patch_content
        assert patch["files"] == files

    def test_get_non_existent_patch(self, temp_storage: ArtifactStorage) -> None:
        """Test getting non-existent patch."""
        patch = temp_storage.get_patch("non-existent-task")
        assert patch is None


class TestManifestStorage:
    """Tests for manifest storage."""

    def test_create_and_get_manifest(self, temp_storage: ArtifactStorage) -> None:
        """Test creating and getting manifest."""
        task_id = "test-task-005"

        temp_storage.create_manifest(
            task_id,
            requirement="Implement user authentication",
            trigger_type="manual",
            trigger_node_id="node-123",
        )

        manifest = temp_storage.get_manifest(task_id)
        assert manifest is not None
        assert manifest["task_id"] == task_id
        assert manifest["requirement"] == "Implement user authentication"
        assert manifest["trigger_type"] == "manual"
        assert manifest["trigger_node_id"] == "node-123"
        assert manifest["status"] == "waiting"
        assert manifest["created_at"] is not None
        assert manifest["duration_seconds"] is None

    def test_update_manifest(self, temp_storage: ArtifactStorage) -> None:
        """Test updating manifest."""
        task_id = "test-task-006"

        temp_storage.create_manifest(task_id, "Test requirement")

        # Update status
        temp_storage.update_manifest(task_id, status="coding", started_at="2024-01-01T10:00:00")

        manifest = temp_storage.get_manifest(task_id)
        assert manifest["status"] == "coding"
        assert manifest["started_at"] == "2024-01-01T10:00:00"

        # Complete and calculate duration
        temp_storage.update_manifest(
            task_id,
            status="done",
            completed_at="2024-01-01T10:05:00",
        )

        manifest = temp_storage.get_manifest(task_id)
        assert manifest["duration_seconds"] == 300  # 5 minutes

    def test_add_files_to_manifest(self, temp_storage: ArtifactStorage) -> None:
        """Test adding files to manifest."""
        task_id = "test-task-007"

        temp_storage.create_manifest(task_id, "Test requirement")

        temp_storage.add_files_to_manifest(task_id, ["file1.py", "file2.py"])
        temp_storage.add_files_to_manifest(task_id, ["file3.py", "file1.py"])  # duplicate

        manifest = temp_storage.get_manifest(task_id)
        assert manifest["files_changed"] == ["file1.py", "file2.py", "file3.py"]

    def test_add_tests_to_manifest(self, temp_storage: ArtifactStorage) -> None:
        """Test adding tests to manifest."""
        task_id = "test-task-008"

        temp_storage.create_manifest(task_id, "Test requirement")

        temp_storage.add_tests_to_manifest(
            task_id,
            tests=["test_a.py", "test_b.py"],
            passed=True,
        )

        manifest = temp_storage.get_manifest(task_id)
        assert manifest["tests_run"] == ["test_a.py", "test_b.py"]
        assert manifest["tests_passed"] is True

    def test_get_non_existent_manifest(self, temp_storage: ArtifactStorage) -> None:
        """Test getting non-existent manifest."""
        manifest = temp_storage.get_manifest("non-existent-task")
        assert manifest is None


class TestSummaryAndBulkOperations:
    """Tests for summary and bulk operations."""

    def test_get_task_artifacts_summary(self, temp_storage: ArtifactStorage) -> None:
        """Test getting task artifacts summary."""
        task_id = "test-task-009"

        # Create various artifacts
        temp_storage.create_manifest(task_id, "Test requirement")
        temp_storage.append_conversation_line(task_id, "user", "Hello")
        temp_storage.append_conversation_line(task_id, "assistant", "Hi")
        temp_storage.save_diff(task_id, "file1.py", "diff1")
        temp_storage.save_diff(task_id, "file2.py", "diff2")
        temp_storage.save_patch(task_id, "patch content")

        summary = temp_storage.get_task_artifacts_summary(task_id)

        assert summary["exists"] is True
        assert summary["manifest"] is not None
        assert summary["conversation_lines"] == 2
        assert summary["diffs_count"] == 2
        assert summary["has_patch"] is True
        assert summary["total_size_bytes"] > 0

    def test_get_summary_non_existent(self, temp_storage: ArtifactStorage) -> None:
        """Test getting summary for non-existent task."""
        summary = temp_storage.get_task_artifacts_summary("non-existent-task")

        assert summary["exists"] is False
        assert summary["manifest"] is None
        assert summary["conversation_lines"] == 0

    def test_list_task_artifacts(self, temp_storage: ArtifactStorage) -> None:
        """Test listing task artifacts."""
        task_id = "test-task-010"

        temp_storage.create_manifest(task_id, "Test requirement")
        temp_storage.save_diff(task_id, "file.py", "diff")

        artifacts = temp_storage.list_task_artifacts(task_id)

        # Should have manifest.json and diffs/file.py.diff
        paths = [a["path"] for a in artifacts]
        assert "manifest.json" in paths
        assert "diffs/file.py.diff" in paths

        for artifact in artifacts:
            assert "size_bytes" in artifact
            assert "modified_at" in artifact

    def test_delete_task_artifacts(self, temp_storage: ArtifactStorage) -> None:
        """Test deleting task artifacts."""
        task_id = "test-task-011"

        temp_storage.create_manifest(task_id, "Test requirement")

        # Should exist
        assert temp_storage.get_manifest(task_id) is not None

        # Delete
        deleted = temp_storage.delete_task_artifacts(task_id)
        assert deleted is True

        # Should be gone
        assert temp_storage.get_manifest(task_id) is None

        # Delete non-existent
        deleted = temp_storage.delete_task_artifacts("non-existent-task")
        assert deleted is False

    def test_export_task_artifacts(self, temp_storage: ArtifactStorage) -> None:
        """Test exporting task artifacts."""
        task_id = "test-task-012"

        temp_storage.create_manifest(task_id, "Test requirement")
        temp_storage.save_patch(task_id, "patch content")

        export_path = temp_storage.export_task_artifacts(task_id)

        assert export_path.exists()
        assert export_path.suffix == ".zip"

        # Verify zip contents
        import zipfile
        with zipfile.ZipFile(export_path) as zf:
            names = zf.namelist()
            assert "manifest.json" in names
            assert "task.patch" in names


class TestGlobalInstance:
    """Tests for global artifact storage instance."""

    def test_get_artifact_storage_singleton(self) -> None:
        """Test that get_artifact_storage returns same instance."""
        # Clear the global instance
        import app.services.task_artifacts as module
        module._storage = None

        storage1 = get_artifact_storage()
        storage2 = get_artifact_storage()

        assert storage1 is storage2
