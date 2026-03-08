from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core.auth_token import create_jwt, decode_jwt
from app.core.settings import get_settings
from app.services.user_store import (
    ADMIN_STAFF_NO,
    ensure_default_admin,
    ensure_employee_user,
    get_user_by_id,
    get_user_by_staff_no,
    verify_admin_password,
)

router = APIRouter()


class LoginRequest(BaseModel):
    staff_no: str = Field(min_length=1, max_length=64)
    password: str | None = None




def _cookie_kwargs() -> dict[str, object]:
    settings = get_settings()
    max_age = settings.auth_jwt_exp_minutes * 60
    return {
        'httponly': True,
        'secure': False,
        'samesite': 'lax',
        'max_age': max_age,
        'path': '/',
    }


def _get_token_from_request(request: Request) -> str | None:
    settings = get_settings()
    return request.cookies.get(settings.auth_cookie_name)


def _resolve_current_user(request: Request) -> dict[str, str] | None:
    settings = get_settings()
    token = _get_token_from_request(request)
    if not token:
        return None

    payload = decode_jwt(token, settings.auth_jwt_secret)
    if payload is None:
        return None

    user_id = payload.get('sub')
    if not isinstance(user_id, str) or not user_id:
        return None

    user = get_user_by_id(user_id)
    if user is None:
        return None

    return {
        'id': user['id'],
        'staff_no': user['staff_no'],
        'display_name': user['display_name'],
        'role': user['role'],
    }


@router.post('/login')
def login(payload: LoginRequest, response: Response) -> dict[str, object]:
    ensure_default_admin()
    staff_no = payload.staff_no.strip()
    if not staff_no:
        raise HTTPException(status_code=400, detail='staff_no is required')

    if staff_no == ADMIN_STAFF_NO:
        if not payload.password or not verify_admin_password(payload.password):
            raise HTTPException(status_code=401, detail='invalid admin credentials')
        user = get_user_by_staff_no(ADMIN_STAFF_NO)
        if user is None:
            raise HTTPException(status_code=500, detail='admin user unavailable')
    else:
        user = ensure_employee_user(staff_no)

    settings = get_settings()
    token = create_jwt(
        {
            'sub': user['id'],
            'staff_no': user['staff_no'],
            'role': user['role'],
        },
        settings.auth_jwt_secret,
        settings.auth_jwt_exp_minutes,
    )

    response.set_cookie(settings.auth_cookie_name, token, **_cookie_kwargs())

    user_payload = {
        'id': user['id'],
        'staff_no': user['staff_no'],
        'display_name': user['display_name'],
        'role': user['role'],
    }
    return {'user': user_payload}


@router.get('/me')
def me(request: Request) -> dict[str, object]:
    user = _resolve_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail='not authenticated')
    return {'user': user}


@router.post('/logout')
def logout(response: Response) -> dict[str, bool]:
    settings = get_settings()
    response.delete_cookie(settings.auth_cookie_name, path='/')
    return {'ok': True}

