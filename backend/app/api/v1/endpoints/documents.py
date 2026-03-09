from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.services.document_store import (
    create_document,
    delete_document,
    get_document,
    list_documents,
    move_document_to_project,
    update_document,
)
from app.api.v1.endpoints.versions import router as versions_router

router = APIRouter()


class DocumentCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: dict[str, Any] = Field(default_factory=dict)
    owner_id: str | None = None
    project_id: str | None = None


class DocumentPatchRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: dict[str, Any] | None = None
    owner_id: str | None = None
    project_id: str | None = None


class DocumentMoveRequest(BaseModel):
    project_id: str | None = None


@router.get('')
def list_document_items(user: CurrentUser) -> dict[str, list[dict[str, Any]]]:
    items = list_documents(owner_id=None if user['role'] in {'admin', 'reviewer'} else user['id'])
    return {'items': items}


@router.post('', status_code=status.HTTP_201_CREATED)
def create_document_item(payload: DocumentCreateRequest, user: CurrentUser) -> dict[str, Any]:
    # Default owner to current user.
    # NOTE: Use explicit None check so empty strings don't accidentally pass.
    owner_id = payload.owner_id
    if owner_id is None:
        owner_id = user['id']

    # Admin can override owner_id to assign to others.
    if user['role'] != 'admin' and owner_id != user['id']:
        owner_id = user['id']

    return create_document(payload.title, payload.content, owner_id, payload.project_id)


@router.get('/{document_id}')
def get_document_item(document_id: str, user: CurrentUser) -> dict[str, Any]:
    document = get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail='document not found')

    if user['role'] not in {'admin', 'reviewer'} and document.get('owner_id') not in (None, user['id']):
        # Hide existence from other employees.
        raise HTTPException(status_code=404, detail='document not found')

    return document


@router.patch('/{document_id}')
def patch_document_item(document_id: str, payload: DocumentPatchRequest, user: CurrentUser) -> dict[str, Any]:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail='no updates provided')

    document = get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail='document not found')

    if user['role'] not in {'admin', 'reviewer'} and document.get('owner_id') not in (None, user['id']):
        raise HTTPException(status_code=404, detail='document not found')

    if user['role'] not in {'admin', 'reviewer'} and 'owner_id' in updates and updates['owner_id'] != user['id']:
        raise HTTPException(status_code=403, detail='cannot reassign owner')

    updated = update_document(document_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail='document not found')
    return updated


@router.delete('/{document_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_document_item(document_id: str, user: CurrentUser) -> Response:
    document = get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail='document not found')

    if user['role'] not in {'admin', 'reviewer'} and document.get('owner_id') not in (None, user['id']):
        raise HTTPException(status_code=404, detail='document not found')

    if not delete_document(document_id):
        raise HTTPException(status_code=404, detail='document not found')
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post('/{document_id}/move')
def move_document(document_id: str, payload: DocumentMoveRequest, user: CurrentUser) -> dict[str, Any]:
    """Move a document to a project workspace or back to personal workspace."""
    from app.services.project_store import get_project, is_project_member

    document = get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail='document not found')

    # Check access rights based on document location
    is_admin = user['role'] in {'admin', 'reviewer'}
    is_owner = document.get('owner_id') == user['id']

    # For personal workspace documents, only owner can access
    if document.get('project_id') is None:
        if not is_admin and not is_owner:
            raise HTTPException(status_code=404, detail='document not found')
    else:
        # For project documents, check project membership
        if not is_admin and not is_owner:
            if not is_project_member(document['project_id'], user['id']):
                raise HTTPException(status_code=404, detail='document not found')

    # If moving to a project, verify the project exists and user is a member
    if payload.project_id is not None:
        project = get_project(payload.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail='project not found')

        # Admin can move to any project
        if not is_admin:
            if not is_project_member(payload.project_id, user['id']):
                raise HTTPException(status_code=403, detail='not a member of target project')

    # If moving from a project to personal workspace, verify user owns the document
    if document.get('project_id') is not None and payload.project_id is None:
        if not is_admin and not is_owner:
            raise HTTPException(status_code=403, detail='can only move owned documents to personal workspace')

    updated = move_document_to_project(document_id, payload.project_id, user['id'])
    if updated is None:
        raise HTTPException(status_code=404, detail='document not found')
    return updated


# Mount versions under /{document_id}/versions
router.include_router(versions_router, prefix='/{document_id}/versions', tags=['versions'])
