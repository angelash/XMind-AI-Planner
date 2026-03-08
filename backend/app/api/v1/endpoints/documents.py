from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.services.document_store import (
    create_document,
    delete_document,
    get_document,
    list_documents,
    update_document,
)

router = APIRouter()


class DocumentCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: dict[str, Any] = Field(default_factory=dict)
    owner_id: str | None = None


class DocumentPatchRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: dict[str, Any] | None = None
    owner_id: str | None = None


@router.get('')
def list_document_items() -> dict[str, list[dict[str, Any]]]:
    return {'items': list_documents()}


@router.post('', status_code=status.HTTP_201_CREATED)
def create_document_item(payload: DocumentCreateRequest) -> dict[str, Any]:
    return create_document(payload.title, payload.content, payload.owner_id)


@router.get('/{document_id}')
def get_document_item(document_id: str) -> dict[str, Any]:
    document = get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail='document not found')
    return document


@router.patch('/{document_id}')
def patch_document_item(document_id: str, payload: DocumentPatchRequest) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail='no updates provided')

    document = update_document(document_id, updates)
    if document is None:
        raise HTTPException(status_code=404, detail='document not found')
    return document


@router.delete('/{document_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_document_item(document_id: str) -> Response:
    if not delete_document(document_id):
        raise HTTPException(status_code=404, detail='document not found')
    return Response(status_code=status.HTTP_204_NO_CONTENT)
