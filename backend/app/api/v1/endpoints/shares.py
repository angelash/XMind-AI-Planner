from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.document_store import (
    create_or_refresh_share,
    get_share,
    update_share_document,
)

router = APIRouter()


class ShareCreateRequest(BaseModel):
    is_editable: bool = True


class SharePatchRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: dict[str, Any] | None = None


@router.post('/documents/{document_id}/share')
def create_document_share(document_id: str, payload: ShareCreateRequest) -> dict[str, Any]:
    share = create_or_refresh_share(document_id, is_editable=payload.is_editable)
    if share is None:
        raise HTTPException(status_code=404, detail='document not found')

    return {
        **share,
        'share_url': f'/frontend/share.html?token={share["token"]}',
    }


@router.get('/shares/{token}')
def get_share_document(token: str) -> dict[str, Any]:
    share = get_share(token)
    if share is None:
        raise HTTPException(status_code=404, detail='share not found')
    return share


@router.patch('/shares/{token}')
def patch_share_document(token: str, payload: SharePatchRequest) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail='no updates provided')

    try:
        share = update_share_document(token, updates)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if share is None:
        raise HTTPException(status_code=404, detail='share not found')

    return share
