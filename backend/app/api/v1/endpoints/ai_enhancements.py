"""AI Enhancement API Endpoints (GAP-09)

Endpoints for:
- Text translation
- ASCII diagram generation
- Node color suggestions
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.services.ai_enhancements import ai_enhancements_service


router = APIRouter()


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    target_language: str = Field(min_length=1, max_length=50)
    source_language: str = Field(default="auto", max_length=50)


class TranslateResponse(BaseModel):
    original_text: str
    translated_text: str
    source_language: str
    target_language: str


class DiagramRequest(BaseModel):
    node_text: str = Field(min_length=1, max_length=500)
    diagram_type: str = Field(default="flowchart", pattern="^(flowchart|tree|process)$")
    node_id: str = Field(default="")


class DiagramResponse(BaseModel):
    node_id: str
    node_text: str
    diagram: str
    diagram_type: str


class ColorSuggestionRequest(BaseModel):
    node_text: str = Field(min_length=1, max_length=500)
    node_id: str = Field(default="")


class ColorSuggestionResponse(BaseModel):
    node_id: str
    node_text: str
    suggested_color: str
    reason: str


@router.post('/translate', response_model=TranslateResponse)
async def translate_text(
    request: TranslateRequest,
    _user: CurrentUser,
) -> TranslateResponse:
    """Translate text to a target language."""
    result = await ai_enhancements_service.translate_text(
        text=request.text,
        target_language=request.target_language,
        source_language=request.source_language,
    )

    return TranslateResponse(
        original_text=result.original_text,
        translated_text=result.translated_text,
        source_language=result.source_language,
        target_language=result.target_language,
    )


@router.post('/diagram', response_model=DiagramResponse)
async def generate_diagram(
    request: DiagramRequest,
    _user: CurrentUser,
) -> DiagramResponse:
    """Generate an ASCII diagram from node text."""
    result = await ai_enhancements_service.generate_ascii_diagram(
        node_text=request.node_text,
        diagram_type=request.diagram_type,
    )

    return DiagramResponse(
        node_id=request.node_id,
        node_text=result.node_text,
        diagram=result.diagram,
        diagram_type=result.diagram_type,
    )


@router.post('/color-suggestion', response_model=ColorSuggestionResponse)
async def suggest_color(
    request: ColorSuggestionRequest,
    _user: CurrentUser,
) -> ColorSuggestionResponse:
    """Suggest a color for a node based on its content."""
    result = await ai_enhancements_service.suggest_node_color(
        node_text=request.node_text,
    )

    return ColorSuggestionResponse(
        node_id=request.node_id,
        node_text=result.node_text,
        suggested_color=result.suggested_color,
        reason=result.reason,
    )
