from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.services.image_export import render_png, render_svg
from app.services.markdown_export import render_markdown
from app.services.word_export import render_docx
from app.services.xmind_export import render_xmind

router = APIRouter()


class MarkdownExportRequest(BaseModel):
    root: dict[str, Any]


@router.post('/markdown')
def export_markdown(payload: MarkdownExportRequest, _user: CurrentUser) -> dict[str, str]:
    try:
        markdown = render_markdown(payload.root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {'markdown': markdown}


@router.post('/word')
def export_word(payload: MarkdownExportRequest, _user: CurrentUser) -> dict[str, str]:
    try:
        docx_bytes = render_docx(payload.root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "filename": "mindmap.docx",
        "docx_base64": base64.b64encode(docx_bytes).decode("ascii"),
    }


@router.post('/xmind')
def export_xmind(payload: MarkdownExportRequest, _user: CurrentUser) -> dict[str, str]:
    try:
        xmind_bytes = render_xmind(payload.root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "filename": "mindmap.xmind",
        "xmind_base64": base64.b64encode(xmind_bytes).decode("ascii"),
    }


@router.post('/svg')
def export_svg(payload: MarkdownExportRequest, _user: CurrentUser) -> dict[str, str]:
    try:
        svg_content = render_svg(payload.root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "filename": "mindmap.svg",
        "svg_content": svg_content,
    }


@router.post('/png')
def export_png(payload: MarkdownExportRequest, _user: CurrentUser) -> dict[str, str]:
    try:
        png_bytes = render_png(payload.root)
    except (ValueError, ImportError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "filename": "mindmap.png",
        "png_base64": base64.b64encode(png_bytes).decode("ascii"),
    }
