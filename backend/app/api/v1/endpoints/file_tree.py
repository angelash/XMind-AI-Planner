"""File tree management endpoints for project workspaces."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.services.file_tree_store import (
    create_file_tree_item,
    delete_file_tree_item,
    get_file_tree,
    get_file_tree_item,
    list_file_tree_items,
    move_file_tree_item,
    update_file_tree_item,
)
from app.services.project_store import get_project, is_project_member

router = APIRouter()


class FileTreeItemCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=256)
    type: str = Field(default="folder")
    parent_id: str | None = Field(default=None)
    sort_order: int = Field(default=0)


class FileTreeItemUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=256)
    sort_order: int | None = Field(default=None)


class FileTreeItemMoveRequest(BaseModel):
    parent_id: str | None = Field(default=None)


@router.get("/{project_id}/file-tree")
def get_project_file_tree(project_id: str, user: CurrentUser) -> list[dict[str, Any]]:
    """Get the complete file tree for a project as a nested structure."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Admins can view any project's file tree
    if user.get("role") == "admin":
        return get_file_tree(project_id)

    # Regular users must be members
    if not is_project_member(project_id, user["id"]):
        raise HTTPException(status_code=403, detail="not a project member")

    return get_file_tree(project_id)


@router.get("/{project_id}/file-tree/items")
def list_project_file_tree_items(
    project_id: str,
    parent_id: str | None = None,
    user: CurrentUser = None,
) -> dict[str, list[dict[str, Any]]]:
    """List file tree items in a project, optionally filtered by parent."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Admins can view any project's file tree
    if user.get("role") == "admin":
        return {"items": list_file_tree_items(project_id, parent_id)}

    # Regular users must be members
    if not is_project_member(project_id, user["id"]):
        raise HTTPException(status_code=403, detail="not a project member")

    return {"items": list_file_tree_items(project_id, parent_id)}


@router.post("/{project_id}/file-tree/items", status_code=status.HTTP_201_CREATED)
def create_project_file_tree_item(
    project_id: str,
    payload: FileTreeItemCreateRequest,
    user: CurrentUser,
) -> dict[str, Any]:
    """Create a new file or folder in the project file tree."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Only members can create items
    if user.get("role") != "admin" and not is_project_member(project_id, user["id"]):
        raise HTTPException(status_code=403, detail="not a project member")

    try:
        item = create_file_tree_item(
            project_id=project_id,
            name=payload.name,
            item_type=payload.type,
            parent_id=payload.parent_id,
            created_by=user["id"],
            sort_order=payload.sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return item


@router.get("/{project_id}/file-tree/items/{item_id}")
def get_project_file_tree_item(project_id: str, item_id: str, user: CurrentUser) -> dict[str, Any]:
    """Get a single file tree item by ID."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Admins can view any project's file tree
    if user.get("role") != "admin" and not is_project_member(project_id, user["id"]):
        raise HTTPException(status_code=403, detail="not a project member")

    item = get_file_tree_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")

    if item["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="item not found in this project")

    return item


@router.patch("/{project_id}/file-tree/items/{item_id}")
def update_project_file_tree_item(
    project_id: str,
    item_id: str,
    payload: FileTreeItemUpdateRequest,
    user: CurrentUser,
) -> dict[str, Any]:
    """Update a file tree item's name and/or sort order."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Only members can update items
    if user.get("role") != "admin" and not is_project_member(project_id, user["id"]):
        raise HTTPException(status_code=403, detail="not a project member")

    item = get_file_tree_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")

    if item["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="item not found in this project")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="no updates provided")

    try:
        updated = update_file_tree_item(
            item_id=item_id,
            name=payload.name,
            sort_order=payload.sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if updated is None:
        raise HTTPException(status_code=500, detail="failed to update item")

    return updated


@router.delete("/{project_id}/file-tree/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_file_tree_item(project_id: str, item_id: str, user: CurrentUser) -> None:
    """Delete a file tree item. Folders are deleted recursively."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Only members can delete items
    if user.get("role") != "admin" and not is_project_member(project_id, user["id"]):
        raise HTTPException(status_code=403, detail="not a project member")

    item = get_file_tree_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")

    if item["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="item not found in this project")

    if not delete_file_tree_item(item_id):
        raise HTTPException(status_code=500, detail="failed to delete item")
    return None


@router.post("/{project_id}/file-tree/items/{item_id}/move")
def move_project_file_tree_item(
    project_id: str,
    item_id: str,
    payload: FileTreeItemMoveRequest,
    user: CurrentUser,
) -> dict[str, Any]:
    """Move a file tree item to a new parent."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Only members can move items
    if user.get("role") != "admin" and not is_project_member(project_id, user["id"]):
        raise HTTPException(status_code=403, detail="not a project member")

    item = get_file_tree_item(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")

    if item["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="item not found in this project")

    try:
        moved = move_file_tree_item(item_id, payload.parent_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if moved is None:
        raise HTTPException(status_code=500, detail="failed to move item")

    return moved
