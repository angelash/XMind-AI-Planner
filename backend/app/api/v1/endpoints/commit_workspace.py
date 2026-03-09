"""Commit workspace API endpoints.

AUTO-04: 提交工作区与合并区

Provides endpoints for:
- Listing pending commit workspaces
- Viewing workspace details and diffs
- Merging changes into documents
- Discarding unwanted changes
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.services.commit_workspace import (
    WorkspaceStatus,
    create_commit_workspace,
    discard_commit_workspace,
    get_commit_workspace,
    get_workspace_diff,
    list_commit_workspaces,
    merge_commit_workspace,
)

router = APIRouter()


class CreateWorkspaceBody(BaseModel):
    """Request body for creating a commit workspace."""
    task_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    snapshot_before: dict[str, Any] | None = None
    snapshot_after: dict[str, Any]
    changes_summary: str = Field(min_length=1)


def _workspace_to_response(workspace: dict[str, Any]) -> dict[str, Any]:
    """Convert workspace to API response."""
    return {
        "id": workspace["id"],
        "task_id": workspace["task_id"],
        "document_id": workspace["document_id"],
        "snapshot_before": workspace["snapshot_before"],
        "snapshot_after": workspace["snapshot_after"],
        "changes_summary": workspace["changes_summary"],
        "status": workspace["status"],
        "created_by": workspace["created_by"],
        "merged_by": workspace["merged_by"],
        "created_at": workspace["created_at"],
        "merged_at": workspace["merged_at"],
    }


@router.get("")
def list_workspaces(
    document_id: str | None = None,
    task_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
    user: CurrentUser = None,
) -> dict[str, Any]:
    """List commit workspaces.

    Args:
        document_id: Filter by document (optional)
        task_id: Filter by dev task (optional)
        status: Filter by status (optional)
        limit: Maximum results (default 100)
        user: Current user (required)

    Returns:
        List of workspaces and count
    """
    workspaces = list_commit_workspaces(
        document_id=document_id,
        task_id=task_id,
        status=status,
        limit=limit,
    )
    return {
        "items": [_workspace_to_response(w) for w in workspaces],
        "count": len(workspaces),
    }


@router.get("/pending")
def list_pending(
    document_id: str | None = None,
    user: CurrentUser = None,
) -> dict[str, Any]:
    """List pending commit workspaces.

    These are workspaces waiting for review/merge.

    Args:
        document_id: Filter by document (optional)
        user: Current user (required)

    Returns:
        List of pending workspaces and count
    """
    workspaces = list_commit_workspaces(
        document_id=document_id,
        status=WorkspaceStatus.PENDING,
        limit=100,
    )
    return {
        "items": [_workspace_to_response(w) for w in workspaces],
        "count": len(workspaces),
    }


@router.get("/{workspace_id}")
def get_workspace(
    workspace_id: str,
    user: CurrentUser = None,
) -> dict[str, Any]:
    """Get a single commit workspace by ID.

    Args:
        workspace_id: Workspace ID
        user: Current user (required)

    Returns:
        Workspace details

    Raises:
        404: Workspace not found
    """
    workspace = get_commit_workspace(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return _workspace_to_response(workspace)


@router.get("/{workspace_id}/diff")
def get_diff(
    workspace_id: str,
    user: CurrentUser = None,
) -> dict[str, Any]:
    """Get a diff summary for a workspace.

    Shows what nodes were added, removed, or modified.

    Args:
        workspace_id: Workspace ID
        user: Current user (required)

    Returns:
        Diff summary with stats

    Raises:
        404: Workspace not found
    """
    diff = get_workspace_diff(workspace_id)
    if diff is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return diff


@router.post("", status_code=201)
def create_workspace(
    body: CreateWorkspaceBody,
    user: CurrentUser = None,
) -> dict[str, Any]:
    """Create a new commit workspace.

    This is typically called by the AI automation system when
    a task has generated changes that need to be reviewed.

    Args:
        body: Workspace details
        user: Current user (required)

    Returns:
        Created workspace

    Raises:
        400: Validation error or duplicate pending workspace
    """
    try:
        workspace = create_commit_workspace(
            task_id=body.task_id,
            document_id=body.document_id,
            snapshot_before=body.snapshot_before,
            snapshot_after=body.snapshot_after,
            changes_summary=body.changes_summary,
            created_by=user["id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _workspace_to_response(workspace)


@router.post("/{workspace_id}/merge")
def merge_workspace(
    workspace_id: str,
    user: CurrentUser = None,
) -> dict[str, Any]:
    """Merge a pending workspace into the document.

    This applies the proposed changes to the document.

    Args:
        workspace_id: Workspace ID
        user: Current user (required)

    Returns:
        Updated workspace

    Raises:
        400: Workspace not in pending status
        404: Workspace not found
    """
    try:
        workspace = merge_commit_workspace(
            workspace_id=workspace_id,
            merged_by=user["id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _workspace_to_response(workspace)


@router.post("/{workspace_id}/discard")
def discard_workspace(
    workspace_id: str,
    user: CurrentUser = None,
) -> dict[str, Any]:
    """Discard a pending workspace without applying changes.

    Args:
        workspace_id: Workspace ID
        user: Current user (required)

    Returns:
        Updated workspace

    Raises:
        400: Workspace not in pending status
        404: Workspace not found
    """
    try:
        workspace = discard_commit_workspace(
            workspace_id=workspace_id,
            discarded_by=user["id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _workspace_to_response(workspace)
