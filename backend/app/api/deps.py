from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request

from app.core.auth_token import decode_jwt
from app.core.settings import get_settings
from app.services.user_store import get_user_by_id


def get_current_user(request: Request) -> dict[str, str]:
    """Resolve current user from signed JWT stored in cookie.

    Returns a minimal user payload.
    """

    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="not authenticated")

    payload = decode_jwt(token, settings.auth_jwt_secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="invalid session")

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(status_code=401, detail="invalid session")

    user = get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")

    return {
        "id": user["id"],
        "staff_no": user["staff_no"],
        "display_name": user["display_name"],
        "role": user["role"],
    }


CurrentUser = Annotated[dict[str, str], Depends(get_current_user)]


def get_optional_user(request: Request) -> dict[str, str] | None:
    """Resolve current user; return None if not authenticated."""

    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        return None

    payload = decode_jwt(token, settings.auth_jwt_secret)
    if payload is None:
        return None

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        return None

    user = get_user_by_id(user_id)
    if user is None:
        return None

    return {
        "id": user["id"],
        "staff_no": user["staff_no"],
        "display_name": user["display_name"],
        "role": user["role"],
    }


OptionalUser = Annotated[dict[str, str] | None, Depends(get_optional_user)]


def require_admin(user: CurrentUser) -> dict[str, str]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    return user


AdminUser = Annotated[dict[str, str], Depends(require_admin)]


def require_reviewer(user: CurrentUser) -> dict[str, str]:
    role = user.get("role")
    if role not in {"reviewer", "admin"}:
        raise HTTPException(status_code=403, detail="reviewer required")
    return user


ReviewerUser = Annotated[dict[str, str], Depends(require_reviewer)]
