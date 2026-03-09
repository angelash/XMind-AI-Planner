"""Personal workspace entry endpoint.

Provides a single API to get the current user's workspace info,
including their documents list for the workspace view.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.services.document_store import list_documents

router = APIRouter()


@router.get('')
def get_workspace(user: CurrentUser) -> dict[str, Any]:
    """Get current user's personal workspace.

    Returns user info and their documents for the workspace view.
    """
    # Get user's documents (owner_id filter)
    documents = list_documents(owner_id=user['id'])

    return {
        'user': {
            'id': user['id'],
            'staff_no': user['staff_no'],
            'display_name': user['display_name'],
            'role': user['role'],
        },
        'documents': documents,
        'stats': {
            'total_documents': len(documents),
        },
    }
