from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.markdown_export import render_markdown

router = APIRouter()


class MarkdownExportRequest(BaseModel):
    root: dict[str, Any]


@router.post('/markdown')
def export_markdown(payload: MarkdownExportRequest) -> dict[str, str]:
    try:
        markdown = render_markdown(payload.root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {'markdown': markdown}
