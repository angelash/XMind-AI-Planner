"""Task artifacts storage service.

AUTO-03: Artifacts 存储

Provides file-based storage for task artifacts:
- conversation.jsonl: Full AI conversation records
- diff storage: Code changes grouped by file
- task.patch: Unified patch file
- manifest.json: Task metadata (duration, file list, etc.)
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.settings import get_settings


class ArtifactType:
    """Artifact type constants."""
    CONVERSATION = "conversation"
    DIFF = "diff"
    PATCH = "patch"
    MANIFEST = "manifest"


class ArtifactStorage:
    """Manages file-based storage for task artifacts."""

    def __init__(self, base_path: Path | None = None):
        """Initialize artifact storage.

        Args:
            base_path: Base directory for artifact storage.
                      Defaults to data/artifacts/ under the project root.
        """
        if base_path is None:
            settings = get_settings()
            # Use data directory relative to db_path
            db_path = settings.db_path_abs
            base_path = db_path.parent / "artifacts"
        self.base_path = Path(base_path)
        self._ensure_base_path()

    def _ensure_base_path(self) -> None:
        """Ensure the base artifact directory exists."""
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _task_dir(self, task_id: str) -> Path:
        """Get the artifact directory for a task.

        Args:
            task_id: Task ID

        Returns:
            Path to task's artifact directory
        """
        task_dir = self.base_path / task_id
        return task_dir

    def _ensure_task_dir(self, task_id: str) -> Path:
        """Ensure the artifact directory for a task exists.

        Args:
            task_id: Task ID

        Returns:
            Path to task's artifact directory
        """
        task_dir = self._task_dir(task_id)
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    # =====================
    # Conversation Storage
    # =====================

    def append_conversation_line(
        self,
        task_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Path:
        """Append a line to the conversation.jsonl file.

        Args:
            task_id: Task ID
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata (node modifications, etc.)

        Returns:
            Path to the conversation file
        """
        task_dir = self._ensure_task_dir(task_id)
        conversation_path = task_dir / "conversation.jsonl"

        line_data = {
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
        }
        if metadata:
            line_data["metadata"] = metadata

        with open(conversation_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(line_data, ensure_ascii=False) + "\n")

        return conversation_path

    def get_conversation(self, task_id: str) -> list[dict[str, Any]]:
        """Read the conversation for a task.

        Args:
            task_id: Task ID

        Returns:
            List of conversation entries
        """
        task_dir = self._task_dir(task_id)
        conversation_path = task_dir / "conversation.jsonl"

        if not conversation_path.exists():
            return []

        lines = []
        with open(conversation_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(json.loads(line))
        return lines

    # =====================
    # Diff Storage
    # =====================

    def save_diff(
        self,
        task_id: str,
        file_path: str,
        diff_content: str,
        status: str = "modified",
    ) -> Path:
        """Save a diff for a specific file.

        Args:
            task_id: Task ID
            file_path: Path to the file being changed
            diff_content: Unified diff content
            status: File status (added, modified, deleted)

        Returns:
            Path to the diff file
        """
        task_dir = self._ensure_task_dir(task_id)
        diffs_dir = task_dir / "diffs"
        diffs_dir.mkdir(exist_ok=True)

        # Create a safe filename from the file path
        safe_name = file_path.replace("/", "_").replace("\\", "_")
        diff_path = diffs_dir / f"{safe_name}.diff"

        diff_data = {
            "file_path": file_path,
            "status": status,
            "diff": diff_content,
            "timestamp": datetime.now().isoformat(),
        }

        with open(diff_path, "w", encoding="utf-8") as f:
            json.dump(diff_data, f, ensure_ascii=False, indent=2)

        return diff_path

    def list_diffs(self, task_id: str) -> list[dict[str, Any]]:
        """List all diffs for a task.

        Args:
            task_id: Task ID

        Returns:
            List of diff entries
        """
        task_dir = self._task_dir(task_id)
        diffs_dir = task_dir / "diffs"

        if not diffs_dir.exists():
            return []

        diffs = []
        for diff_file in sorted(diffs_dir.glob("*.diff")):
            with open(diff_file, "r", encoding="utf-8") as f:
                diffs.append(json.load(f))
        return diffs

    def get_diff(self, task_id: str, file_path: str) -> dict[str, Any] | None:
        """Get a specific diff for a file.

        Args:
            task_id: Task ID
            file_path: Path to the file

        Returns:
            Diff entry or None if not found
        """
        task_dir = self._task_dir(task_id)
        diffs_dir = task_dir / "diffs"

        safe_name = file_path.replace("/", "_").replace("\\", "_")
        diff_path = diffs_dir / f"{safe_name}.diff"

        if not diff_path.exists():
            return None

        with open(diff_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # =====================
    # Patch Storage
    # =====================

    def save_patch(
        self,
        task_id: str,
        patch_content: str,
        files: list[str] | None = None,
    ) -> Path:
        """Save the unified patch file for a task.

        Args:
            task_id: Task ID
            patch_content: Unified patch content
            files: List of files affected by the patch

        Returns:
            Path to the patch file
        """
        task_dir = self._ensure_task_dir(task_id)
        patch_path = task_dir / "task.patch"

        patch_data = {
            "task_id": task_id,
            "patch": patch_content,
            "files": files or [],
            "timestamp": datetime.now().isoformat(),
        }

        with open(patch_path, "w", encoding="utf-8") as f:
            json.dump(patch_data, f, ensure_ascii=False, indent=2)

        return patch_path

    def get_patch(self, task_id: str) -> dict[str, Any] | None:
        """Get the patch for a task.

        Args:
            task_id: Task ID

        Returns:
            Patch data or None if not found
        """
        task_dir = self._task_dir(task_id)
        patch_path = task_dir / "task.patch"

        if not patch_path.exists():
            return None

        with open(patch_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # =====================
    # Manifest Storage
    # =====================

    def create_manifest(
        self,
        task_id: str,
        requirement: str,
        trigger_type: str | None = None,
        trigger_node_id: str | None = None,
    ) -> Path:
        """Create a new manifest for a task.

        Args:
            task_id: Task ID
            requirement: Task requirement text
            trigger_type: How the task was triggered
            trigger_node_id: Node that triggered the task

        Returns:
            Path to the manifest file
        """
        task_dir = self._ensure_task_dir(task_id)
        manifest_path = task_dir / "manifest.json"

        manifest = {
            "task_id": task_id,
            "requirement": requirement,
            "trigger_type": trigger_type,
            "trigger_node_id": trigger_node_id,
            "status": "waiting",
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "duration_seconds": None,
            "files_changed": [],
            "tests_run": [],
            "tests_passed": None,
            "error_message": None,
            "artifacts": {
                "conversation": False,
                "diffs": 0,
                "patch": False,
            },
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        return manifest_path

    def get_manifest(self, task_id: str) -> dict[str, Any] | None:
        """Get the manifest for a task.

        Args:
            task_id: Task ID

        Returns:
            Manifest data or None if not found
        """
        task_dir = self._task_dir(task_id)
        manifest_path = task_dir / "manifest.json"

        if not manifest_path.exists():
            return None

        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def update_manifest(
        self,
        task_id: str,
        **updates: Any,
    ) -> dict[str, Any] | None:
        """Update the manifest for a task.

        Args:
            task_id: Task ID
            **updates: Fields to update

        Returns:
            Updated manifest or None if not found
        """
        manifest = self.get_manifest(task_id)
        if manifest is None:
            return None

        manifest.update(updates)

        # Calculate duration if completed
        if updates.get("completed_at") and manifest.get("started_at"):
            started = datetime.fromisoformat(manifest["started_at"])
            completed = datetime.fromisoformat(manifest["completed_at"])
            manifest["duration_seconds"] = int((completed - started).total_seconds())

        # Update artifact counts
        task_dir = self._task_dir(task_id)
        manifest["artifacts"] = {
            "conversation": (task_dir / "conversation.jsonl").exists(),
            "diffs": len(list((task_dir / "diffs").glob("*.diff"))) if (task_dir / "diffs").exists() else 0,
            "patch": (task_dir / "task.patch").exists(),
        }

        manifest_path = task_dir / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        return manifest

    def add_files_to_manifest(
        self,
        task_id: str,
        files: list[str],
    ) -> dict[str, Any] | None:
        """Add files to the manifest's file list.

        Args:
            task_id: Task ID
            files: List of file paths to add

        Returns:
            Updated manifest or None if not found
        """
        manifest = self.get_manifest(task_id)
        if manifest is None:
            return None

        existing_files = set(manifest.get("files_changed", []))
        manifest["files_changed"] = sorted(existing_files | set(files))

        manifest_path = self._task_dir(task_id) / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        return manifest

    def add_tests_to_manifest(
        self,
        task_id: str,
        tests: list[str],
        passed: bool | None = None,
    ) -> dict[str, Any] | None:
        """Add test results to the manifest.

        Args:
            task_id: Task ID
            tests: List of test names
            passed: Whether all tests passed

        Returns:
            Updated manifest or None if not found
        """
        manifest = self.get_manifest(task_id)
        if manifest is None:
            return None

        existing_tests = set(manifest.get("tests_run", []))
        manifest["tests_run"] = sorted(existing_tests | set(tests))

        if passed is not None:
            manifest["tests_passed"] = passed

        manifest_path = self._task_dir(task_id) / "manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        return manifest

    # =====================
    # Bulk Operations
    # =====================

    def get_task_artifacts_summary(self, task_id: str) -> dict[str, Any]:
        """Get a summary of all artifacts for a task.

        Args:
            task_id: Task ID

        Returns:
            Summary of artifacts
        """
        task_dir = self._task_dir(task_id)

        summary = {
            "task_id": task_id,
            "exists": task_dir.exists(),
            "manifest": None,
            "conversation_lines": 0,
            "diffs_count": 0,
            "has_patch": False,
            "files_changed": [],
            "total_size_bytes": 0,
        }

        if not task_dir.exists():
            return summary

        # Manifest
        manifest = self.get_manifest(task_id)
        if manifest:
            summary["manifest"] = manifest
            summary["files_changed"] = manifest.get("files_changed", [])

        # Conversation
        conversation_path = task_dir / "conversation.jsonl"
        if conversation_path.exists():
            with open(conversation_path, "r", encoding="utf-8") as f:
                summary["conversation_lines"] = sum(1 for line in f if line.strip())

        # Diffs
        diffs_dir = task_dir / "diffs"
        if diffs_dir.exists():
            summary["diffs_count"] = len(list(diffs_dir.glob("*.diff")))

        # Patch
        summary["has_patch"] = (task_dir / "task.patch").exists()

        # Total size
        total_size = 0
        for path in task_dir.rglob("*"):
            if path.is_file():
                total_size += path.stat().st_size
        summary["total_size_bytes"] = total_size

        return summary

    def list_task_artifacts(self, task_id: str) -> list[dict[str, Any]]:
        """List all artifact files for a task.

        Args:
            task_id: Task ID

        Returns:
            List of artifact file info
        """
        task_dir = self._task_dir(task_id)

        if not task_dir.exists():
            return []

        artifacts = []

        for path in sorted(task_dir.rglob("*")):
            if path.is_file():
                rel_path = path.relative_to(task_dir)
                stat = path.stat()
                artifacts.append({
                    "path": str(rel_path),
                    "size_bytes": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })

        return artifacts

    def delete_task_artifacts(self, task_id: str) -> bool:
        """Delete all artifacts for a task.

        Args:
            task_id: Task ID

        Returns:
            True if artifacts were deleted, False if none existed
        """
        import shutil

        task_dir = self._task_dir(task_id)

        if task_dir.exists():
            shutil.rmtree(task_dir)
            return True
        return False

    def export_task_artifacts(
        self,
        task_id: str,
        output_path: Path | None = None,
    ) -> Path:
        """Export all artifacts for a task to a zip file.

        Args:
            task_id: Task ID
            output_path: Optional output path for the zip file

        Returns:
            Path to the created zip file
        """
        import shutil

        task_dir = self._task_dir(task_id)

        if output_path is None:
            output_path = self.base_path / f"{task_id}_export.zip"

        if task_dir.exists():
            shutil.make_archive(
                str(output_path.with_suffix("")),
                "zip",
                task_dir,
            )
        else:
            # Create empty zip
            import zipfile
            with zipfile.ZipFile(output_path, "w") as zf:
                zf.writestr("README.txt", "No artifacts for this task")

        return output_path


# Global instance
_storage: ArtifactStorage | None = None


def get_artifact_storage() -> ArtifactStorage:
    """Get the global artifact storage instance.

    Returns:
        ArtifactStorage instance
    """
    global _storage
    if _storage is None:
        _storage = ArtifactStorage()
    return _storage
