"""Document version history endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.services.document_store import (
    create_document_version,
    get_document,
    get_document_version,
    list_document_versions,
    rollback_to_version,
    update_document,
)

router = APIRouter()


class VersionRollbackRequest(BaseModel):
    changed_by: str | None = None


@router.get('')
def list_versions(document_id: str, user: CurrentUser) -> dict[str, list[dict[str, Any]]]:
    """List all versions of a document."""
    # Check document exists and user has access
    document = get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail='document not found')

    if user['role'] not in {'admin', 'reviewer'} and document.get('owner_id') not in (None, user['id']):
        raise HTTPException(status_code=404, detail='document not found')

    versions = list_document_versions(document_id)
    return {'versions': versions}


@router.get('/{version_id}')
def get_version(document_id: str, version_id: str, user: CurrentUser) -> dict[str, Any]:
    """Get a specific version of a document."""
    # Check document exists and user has access
    document = get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail='document not found')

    if user['role'] not in {'admin', 'reviewer'} and document.get('owner_id') not in (None, user['id']):
        raise HTTPException(status_code=404, detail='document not found')

    version = get_document_version(document_id, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail='version not found')

    return version


@router.post('/{version_id}/rollback')
def rollback_version(
    document_id: str,
    version_id: str,
    payload: VersionRollbackRequest,
    user: CurrentUser,
) -> dict[str, Any]:
    """Rollback document to a specific version."""
    # Check document exists and user has access
    document = get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail='document not found')

    # Only owner or admin can rollback
    if user['role'] not in {'admin', 'reviewer'} and document.get('owner_id') != user['id']:
        raise HTTPException(status_code=403, detail='only owner or admin can rollback')

    # Perform rollback
    changed_by = payload.changed_by or user['id']
    updated = rollback_to_version(document_id, version_id, changed_by)
    if updated is None:
        raise HTTPException(status_code=404, detail='version not found')

    return updated
