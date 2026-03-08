from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.services.ai_generation import ai_generation_service

router = APIRouter()


class InitialRequest(BaseModel):
    topic: str = Field(min_length=1)


class ExpandRequest(BaseModel):
    node_text: str = Field(min_length=1)
    count: int = Field(default=3, ge=1, le=10)


class RewriteRequest(BaseModel):
    text: str = Field(min_length=1)
    instruction: str | None = None


@router.post('/initial')
def generate_initial(payload: InitialRequest, _user: CurrentUser) -> dict[str, object]:
    return {'root': ai_generation_service.build_initial(payload.topic)}


@router.post('/expand')
def expand_node(payload: ExpandRequest, _user: CurrentUser) -> dict[str, list[dict[str, str]]]:
    return {'children': ai_generation_service.expand(payload.node_text, count=payload.count)}


@router.post('/rewrite')
def rewrite_node(payload: RewriteRequest, _user: CurrentUser) -> dict[str, str]:
    return {'text': ai_generation_service.rewrite(payload.text, payload.instruction)}
