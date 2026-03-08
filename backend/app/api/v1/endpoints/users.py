from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import AdminUser
from app.services.user_store import (
    ADMIN_STAFF_NO,
    create_user,
    delete_user,
    get_user_by_staff_no,
    list_users,
    update_user,
)

router = APIRouter()


class UserCreateRequest(BaseModel):
    staff_no: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=64)
    role: str = Field(default="employee")


class UserPatchRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=64)
    role: str | None = None


@router.get("")
def list_user_items(_admin: AdminUser) -> dict[str, list[dict[str, Any]]]:
    return {"items": list_users()}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user_item(payload: UserCreateRequest, _admin: AdminUser) -> dict[str, Any]:
    staff_no = payload.staff_no.strip()
    display_name = payload.display_name.strip()

    if staff_no == ADMIN_STAFF_NO:
        raise HTTPException(status_code=400, detail="cannot create built-in admin")

    if get_user_by_staff_no(staff_no) is not None:
        raise HTTPException(status_code=409, detail="staff_no already exists")

    try:
        user = create_user(staff_no=staff_no, display_name=display_name, role=payload.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return user


@router.patch("/{staff_no}")
def patch_user_item(staff_no: str, payload: UserPatchRequest, _admin: AdminUser) -> dict[str, Any]:
    staff_no = staff_no.strip()
    if not staff_no:
        raise HTTPException(status_code=400, detail="staff_no is required")

    if staff_no == ADMIN_STAFF_NO and payload.role is not None:
        raise HTTPException(status_code=400, detail="cannot change admin role")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="no updates provided")

    try:
        updated = update_user(staff_no=staff_no, updates=updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if updated is None:
        raise HTTPException(status_code=404, detail="user not found")
    return updated


@router.delete("/{staff_no}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_item(staff_no: str, _admin: AdminUser) -> None:
    staff_no = staff_no.strip()
    if staff_no == ADMIN_STAFF_NO:
        raise HTTPException(status_code=400, detail="cannot delete admin")

    if not delete_user(staff_no):
        raise HTTPException(status_code=404, detail="user not found")
    return None
