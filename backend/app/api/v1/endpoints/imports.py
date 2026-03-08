from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.services.document_store import create_document, get_document, update_document
from app.services.markdown_directory_import import (
    MarkdownDirectoryImportFile,
    import_markdown_directory,
)
from app.services.markdown_import import import_markdown
from app.services.markdown_merge_import import merge_markdown_into_document

router = APIRouter()


class MarkdownImportRequest(BaseModel):
    markdown: str = Field(min_length=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    owner_id: str | None = None


class MarkdownMergeImportRequest(BaseModel):
    document_id: str = Field(min_length=1)
    markdown: str = Field(min_length=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)


class MarkdownDirectoryImportFileRequest(BaseModel):
    path: str = Field(min_length=1)
    markdown: str = Field(min_length=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)


class MarkdownDirectoryImportRequest(BaseModel):
    files: list[MarkdownDirectoryImportFileRequest] = Field(min_length=1)
    owner_id: str | None = None


@router.post('/markdown', status_code=status.HTTP_201_CREATED)
def import_markdown_document(payload: MarkdownImportRequest, user: CurrentUser) -> dict[str, Any]:
    try:
        root = import_markdown(payload.markdown, payload.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    document_title = payload.title or str(root.get("text") or "Imported Mindmap")

    owner_id = payload.owner_id
    if user['role'] != 'admin':
        owner_id = user['id']

    document = create_document(document_title, root, owner_id)
    return {"document": document, "root": root}


@router.post('/markdown/merge')
def merge_markdown_document(payload: MarkdownMergeImportRequest, user: CurrentUser) -> dict[str, Any]:
    document = get_document(payload.document_id)
    if document is None:
        raise HTTPException(status_code=404, detail='document not found')

    if user['role'] != 'admin' and document.get('owner_id') not in (None, user['id']):
        raise HTTPException(status_code=404, detail='document not found')

    try:
        merged_root, stats = merge_markdown_into_document(
            document["content"],
            payload.markdown,
            payload.title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    updated = update_document(
        payload.document_id,
        {
            "content": merged_root,
        },
    )
    if updated is None:
        raise HTTPException(status_code=404, detail='document not found')

    return {
        "document": updated,
        "stats": stats.to_dict(),
    }


@router.post('/markdown/directory', status_code=status.HTTP_201_CREATED)
def import_markdown_directory_documents(payload: MarkdownDirectoryImportRequest, user: CurrentUser) -> dict[str, Any]:
    files = [
        MarkdownDirectoryImportFile(
            path=item.path,
            markdown=item.markdown,
            title=item.title,
        )
        for item in payload.files
    ]

    owner_id = payload.owner_id
    if user['role'] != 'admin':
        owner_id = user['id']

    try:
        results, stats = import_markdown_directory(files, owner_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "results": [item.to_dict() for item in results],
        "stats": stats.to_dict(),
    }
