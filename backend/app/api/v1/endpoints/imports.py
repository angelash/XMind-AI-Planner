from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.document_store import create_document
from app.services.markdown_import import import_markdown

router = APIRouter()


class MarkdownImportRequest(BaseModel):
    markdown: str = Field(min_length=1)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    owner_id: str | None = None


@router.post('/markdown', status_code=status.HTTP_201_CREATED)
def import_markdown_document(payload: MarkdownImportRequest) -> dict[str, Any]:
    try:
        root = import_markdown(payload.markdown, payload.title)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    document_title = payload.title or str(root.get("text") or "Imported Mindmap")
    document = create_document(document_title, root, payload.owner_id)
    return {"document": document, "root": root}
