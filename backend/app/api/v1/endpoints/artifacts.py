"""Task artifacts API endpoints.

AUTO-03: Artifacts 存储

Provides API for downloading and viewing task artifacts.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from app.services.task_artifacts import get_artifact_storage

router = APIRouter()


@router.get("/{task_id}/summary")
def get_artifact_summary(task_id: str) -> dict:
    """Get a summary of all artifacts for a task.

    Args:
        task_id: Task ID

    Returns:
        Summary of artifacts
    """
    storage = get_artifact_storage()
    return storage.get_task_artifacts_summary(task_id)


@router.get("/{task_id}/files")
def list_artifact_files(task_id: str) -> dict:
    """List all artifact files for a task.

    Args:
        task_id: Task ID

    Returns:
        List of artifact files
    """
    storage = get_artifact_storage()
    files = storage.list_task_artifacts(task_id)
    return {"items": files}


@router.get("/{task_id}/conversation")
def get_conversation(task_id: str) -> dict:
    """Get the conversation log for a task.

    Args:
        task_id: Task ID

    Returns:
        Conversation log entries
    """
    storage = get_artifact_storage()
    conversation = storage.get_conversation(task_id)
    return {"items": conversation, "count": len(conversation)}


@router.get("/{task_id}/diffs")
def list_diffs(task_id: str) -> dict:
    """List all diffs for a task.

    Args:
        task_id: Task ID

    Returns:
        List of diff entries
    """
    storage = get_artifact_storage()
    diffs = storage.list_diffs(task_id)
    return {"items": diffs, "count": len(diffs)}


@router.get("/{task_id}/diffs/{file_path:path}")
def get_diff(task_id: str, file_path: str) -> dict:
    """Get a specific diff for a file.

    Args:
        task_id: Task ID
        file_path: Path to the file

    Returns:
        Diff entry
    """
    storage = get_artifact_storage()
    diff = storage.get_diff(task_id, file_path)
    if diff is None:
        raise HTTPException(status_code=404, detail="Diff not found")
    return diff


@router.get("/{task_id}/patch")
def get_patch(task_id: str) -> dict:
    """Get the patch for a task.

    Args:
        task_id: Task ID

    Returns:
        Patch data
    """
    storage = get_artifact_storage()
    patch = storage.get_patch(task_id)
    if patch is None:
        raise HTTPException(status_code=404, detail="Patch not found")
    return patch


@router.get("/{task_id}/patch/download")
def download_patch(task_id: str) -> FileResponse:
    """Download the patch file for a task.

    Args:
        task_id: Task ID

    Returns:
        Patch file download
    """
    storage = get_artifact_storage()
    manifest = storage.get_manifest(task_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="Task not found")

    task_dir = storage._task_dir(task_id)
    patch_path = task_dir / "task.patch"

    if not patch_path.exists():
        raise HTTPException(status_code=404, detail="Patch not found")

    return FileResponse(
        path=patch_path,
        filename=f"{task_id}.patch",
        media_type="application/json",
    )


@router.get("/{task_id}/manifest")
def get_manifest(task_id: str) -> dict:
    """Get the manifest for a task.

    Args:
        task_id: Task ID

    Returns:
        Manifest data
    """
    storage = get_artifact_storage()
    manifest = storage.get_manifest(task_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="Manifest not found")
    return manifest


@router.get("/{task_id}/export")
def export_artifacts(task_id: str) -> FileResponse:
    """Export all artifacts for a task as a zip file.

    Args:
        task_id: Task ID

    Returns:
        Zip file download
    """
    storage = get_artifact_storage()
    output_path = storage.export_task_artifacts(task_id)

    if not output_path.exists():
        raise HTTPException(status_code=404, detail="No artifacts to export")

    return FileResponse(
        path=output_path,
        filename=f"{task_id}_artifacts.zip",
        media_type="application/zip",
    )


@router.delete("/{task_id}")
def delete_artifacts(task_id: str) -> dict:
    """Delete all artifacts for a task.

    Args:
        task_id: Task ID

    Returns:
        Deletion result
    """
    storage = get_artifact_storage()
    deleted = storage.delete_task_artifacts(task_id)
    return {"deleted": deleted}
