"""Project workspace management endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import AdminUser, CurrentUser
from app.services.project_store import (
    add_project_member,
    create_project,
    delete_project,
    get_project,
    get_project_member,
    is_project_admin,
    is_project_member,
    list_project_members,
    list_projects,
    remove_project_member,
    update_project,
    update_project_member_role,
)
from app.services.document_store import list_documents
from app.services.user_store import get_user_by_id

router = APIRouter()


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=512)


class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)


class MemberAddRequest(BaseModel):
    user_id: str = Field(min_length=1)
    role: str = Field(default="member")


class MemberRoleUpdateRequest(BaseModel):
    role: str = Field(min_length=1)


# Project endpoints

@router.get("")
def list_user_projects(user: CurrentUser) -> dict[str, list[dict[str, Any]]]:
    """List projects accessible to the current user."""
    # Admins can see all projects, others see only their own
    if user.get("role") == "admin":
        return {"items": list_projects()}
    return {"items": list_projects(user_id=user["id"])}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_new_project(payload: ProjectCreateRequest, user: CurrentUser) -> dict[str, Any]:
    """Create a new project. Creator becomes the owner."""
    try:
        project = create_project(
            name=payload.name,
            description=payload.description,
            created_by=user["id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return project


@router.get("/{project_id}")
def get_project_detail(project_id: str, user: CurrentUser) -> dict[str, Any]:
    """Get project details. Only members can access."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Admins can access any project
    if user.get("role") == "admin":
        return project

    # Regular users must be members
    if not is_project_member(project_id, user["id"]):
        raise HTTPException(status_code=403, detail="not a project member")

    return project


@router.patch("/{project_id}")
def update_project_detail(project_id: str, payload: ProjectUpdateRequest, user: CurrentUser) -> dict[str, Any]:
    """Update project. Only admins or project admins can update."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Check permissions
    is_admin = user.get("role") == "admin"
    is_proj_admin = is_project_admin(project_id, user["id"])

    if not is_admin and not is_proj_admin:
        raise HTTPException(status_code=403, detail="not authorized to update project")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="no updates provided")

    try:
        updated = update_project(project_id, updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return updated


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_by_id(project_id: str, user: CurrentUser) -> None:
    """Delete project. Only admins or project owners can delete."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Check permissions
    is_admin = user.get("role") == "admin"
    member = get_project_member(project_id, user["id"])
    is_owner = member is not None and member.get("role") == "owner"

    if not is_admin and not is_owner:
        raise HTTPException(status_code=403, detail="not authorized to delete project")

    if not delete_project(project_id):
        raise HTTPException(status_code=500, detail="failed to delete project")
    return None


# Member endpoints

@router.get("/{project_id}/members")
def list_members(project_id: str, user: CurrentUser) -> dict[str, list[dict[str, Any]]]:
    """List project members. Only members can view."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Admins can view any project's members
    if user.get("role") == "admin":
        return {"items": list_project_members(project_id)}

    # Regular users must be members
    if not is_project_member(project_id, user["id"]):
        raise HTTPException(status_code=403, detail="not a project member")

    return {"items": list_project_members(project_id)}


@router.post("/{project_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(project_id: str, payload: MemberAddRequest, user: CurrentUser) -> dict[str, Any]:
    """Add a member to a project. Only admins or project admins can add."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Check permissions
    is_admin = user.get("role") == "admin"
    is_proj_admin = is_project_admin(project_id, user["id"])

    if not is_admin and not is_proj_admin:
        raise HTTPException(status_code=403, detail="not authorized to add members")

    # Verify user exists
    target_user = get_user_by_id(payload.user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="user not found")

    try:
        member = add_project_member(project_id, payload.user_id, payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return member


@router.patch("/{project_id}/members/{user_id}")
def update_member_role(project_id: str, user_id: str, payload: MemberRoleUpdateRequest, user: CurrentUser) -> dict[str, Any]:
    """Update a member's role. Only admins or project owners can update roles."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Check permissions
    is_admin = user.get("role") == "admin"
    is_proj_admin = is_project_admin(project_id, user["id"])

    if not is_admin and not is_proj_admin:
        raise HTTPException(status_code=403, detail="not authorized to update member role")

    try:
        updated = update_project_member_role(project_id, user_id, payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if updated is None:
        raise HTTPException(status_code=404, detail="member not found")

    return updated


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(project_id: str, user_id: str, user: CurrentUser) -> None:
    """Remove a member from a project. Only admins or project admins can remove."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Check permissions
    is_admin = user.get("role") == "admin"
    is_proj_admin = is_project_admin(project_id, user["id"])

    if not is_admin and not is_proj_admin:
        raise HTTPException(status_code=403, detail="not authorized to remove members")

    if not remove_project_member(project_id, user_id):
        raise HTTPException(status_code=404, detail="member not found")
    return None


@router.get("/{project_id}/documents")
def list_project_documents(project_id: str, user: CurrentUser) -> dict[str, list[dict[str, Any]]]:
    """List documents in a project. Only members can view."""
    project = get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    # Admins can view any project's documents
    if user.get("role") == "admin":
        return {"items": list_documents(project_id=project_id)}

    # Regular users must be members
    if not is_project_member(project_id, user["id"]):
        raise HTTPException(status_code=403, detail="not a project member")

    return {"items": list_documents(project_id=project_id)}
