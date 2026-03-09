"""Agent conversation API endpoints.

AG-02: 对话模型与 API
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser
from app.services.conversation_store import (
    batch_update_modifications_status,
    count_pending_modifications,
    create_conversation,
    create_message,
    create_modification,
    delete_conversation,
    get_conversation,
    get_conversation_by_id,
    get_conversation_with_messages,
    get_modification,
    list_conversations,
    list_messages,
    list_modifications,
    update_conversation,
    update_modification_status,
)
from app.services.document_store import get_document

router = APIRouter()


# ============ Request/Response Models ============

class ConversationCreate(BaseModel):
    document_id: str = Field(min_length=1)
    title: str | None = None
    context_node_id: str | None = None


class ConversationUpdate(BaseModel):
    title: str | None = None
    status: str | None = Field(None, pattern="^(active|closed|archived)$")
    context_node_id: str | None = None


class MessageSend(BaseModel):
    content: str = Field(min_length=1)
    context_node_id: str | None = None


class ModificationStatusUpdate(BaseModel):
    status: str = Field(pattern="^(accepted|rejected)$")


class BatchStatusUpdate(BaseModel):
    status: str = Field(pattern="^(accepted|rejected)$")
    message_id: int | None = None


# ============ Conversation Endpoints ============

@router.post("")
def create_new_conversation(payload: ConversationCreate, user: CurrentUser) -> dict[str, Any]:
    """Create a new conversation for a document."""
    # Verify document exists
    doc = get_document(payload.document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")

    conversation = create_conversation(
        document_id=payload.document_id,
        user_id=user["id"],
        title=payload.title,
        context_node_id=payload.context_node_id,
    )
    return conversation


@router.get("/document/{document_id}")
def list_document_conversations(
    document_id: str,
    status: str | None = None,
    user: CurrentUser = None,
) -> list[dict[str, Any]]:
    """List conversations for a document."""
    # Verify document exists
    doc = get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")

    return list_conversations(document_id, status=status)


@router.get("/{conversation_uuid}")
def get_conversation_detail(
    conversation_uuid: str,
    user: CurrentUser,
) -> dict[str, Any]:
    """Get a conversation with messages and pending modifications."""
    result = get_conversation_with_messages(conversation_uuid)
    if result is None:
        raise HTTPException(status_code=404, detail="conversation not found")
    return result


@router.patch("/{conversation_uuid}")
def update_conversation_detail(
    conversation_uuid: str,
    payload: ConversationUpdate,
    user: CurrentUser,
) -> dict[str, Any]:
    """Update a conversation's fields."""
    current = get_conversation(conversation_uuid)
    if current is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return current

    result = update_conversation(conversation_uuid, updates)
    return result


@router.delete("/{conversation_uuid}")
def delete_conversation_by_uuid(
    conversation_uuid: str,
    user: CurrentUser,
) -> dict[str, str]:
    """Delete a conversation and all its messages."""
    success = delete_conversation(conversation_uuid)
    if not success:
        raise HTTPException(status_code=404, detail="conversation not found")
    return {"status": "deleted"}


# ============ Message Endpoints ============

@router.post("/{conversation_uuid}/messages")
def send_message(
    conversation_uuid: str,
    payload: MessageSend,
    user: CurrentUser,
) -> dict[str, Any]:
    """Send a message to a conversation.

    Returns the user message. AI response will be handled separately
    via streaming endpoint (AG-04).
    """
    conversation = get_conversation(conversation_uuid)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    # Update context node if provided
    if payload.context_node_id is not None:
        update_conversation(conversation_uuid, {"context_node_id": payload.context_node_id})

    # Create user message
    message = create_message(
        conversation_id=conversation["id"],
        role="user",
        content=payload.content,
    )

    return message


@router.get("/{conversation_uuid}/messages")
def list_conversation_messages(
    conversation_uuid: str,
    user: CurrentUser,
) -> list[dict[str, Any]]:
    """List all messages in a conversation."""
    conversation = get_conversation(conversation_uuid)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    return list_messages(conversation["id"])


# ============ Node Modification Endpoints ============

@router.get("/{conversation_uuid}/modifications")
def list_conversation_modifications(
    conversation_uuid: str,
    status: str | None = None,
    user: CurrentUser = None,
) -> list[dict[str, Any]]:
    """List node modifications for a conversation."""
    conversation = get_conversation(conversation_uuid)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    return list_modifications(conversation["id"], status=status)


@router.patch("/{conversation_uuid}/modifications/{modification_id}")
def update_single_modification(
    conversation_uuid: str,
    modification_id: int,
    payload: ModificationStatusUpdate,
    user: CurrentUser,
) -> dict[str, Any]:
    """Update a single modification's status (accept or reject)."""
    conversation = get_conversation(conversation_uuid)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    modification = get_modification(modification_id)
    if modification is None:
        raise HTTPException(status_code=404, detail="modification not found")

    if modification["conversation_id"] != conversation["id"]:
        raise HTTPException(status_code=400, detail="modification does not belong to this conversation")

    result = update_modification_status(modification_id, payload.status)
    return result


@router.post("/{conversation_uuid}/modifications/batch")
def batch_update_modifications(
    conversation_uuid: str,
    payload: BatchStatusUpdate,
    user: CurrentUser,
) -> dict[str, Any]:
    """Batch update modification statuses for a conversation.

    If message_id is provided, only updates modifications for that message.
    Otherwise, updates all pending modifications in the conversation.
    """
    conversation = get_conversation(conversation_uuid)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    count = batch_update_modifications_status(
        conversation_id=conversation["id"],
        message_id=payload.message_id,
        status=payload.status,
    )

    return {
        "updated_count": count,
        "status": payload.status,
    }


@router.get("/{conversation_uuid}/modifications/count")
def count_pending_modifications_endpoint(
    conversation_uuid: str,
    user: CurrentUser,
) -> dict[str, int]:
    """Count pending modifications for a conversation."""
    conversation = get_conversation(conversation_uuid)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    count = count_pending_modifications(conversation["id"])
    return {"pending_count": count}
