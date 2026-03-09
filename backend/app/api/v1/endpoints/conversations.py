"""Agent conversation API endpoints.

AG-02: 对话模型与 API
AG-03: Diff + Keep/Undo
AG-04: SSE 流式响应
"""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
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
from app.services.modification_applier import (
    apply_modification,
    revert_modification,
    batch_apply_modifications,
    batch_revert_modifications,
    get_modification_diff,
)
from app.services.conversation_ai import (
    generate_ai_stream,
    parse_ai_response,
    format_modifications_for_response,
)

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


# ============ AG-03: Apply/Revert Endpoints ============

class BatchApplyRequest(BaseModel):
    message_id: int | None = None


class BatchRevertRequest(BaseModel):
    message_id: int | None = None


@router.post("/{conversation_uuid}/modifications/{modification_id}/apply")
def apply_modification_endpoint(
    conversation_uuid: str,
    modification_id: int,
    user: CurrentUser,
) -> dict[str, Any]:
    """Apply (keep) a single modification to the document.

    AG-03: Updates the document content with the modification's after_value
    and marks the modification as accepted.
    """
    conversation = get_conversation(conversation_uuid)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    modification = get_modification(modification_id)
    if modification is None:
        raise HTTPException(status_code=404, detail="modification not found")

    if modification["conversation_id"] != conversation["id"]:
        raise HTTPException(status_code=400, detail="modification does not belong to this conversation")

    result = apply_modification(modification_id)

    if not result["applied"]:
        raise HTTPException(status_code=400, detail=result.get("reason", "failed to apply modification"))

    return result


@router.post("/{conversation_uuid}/modifications/{modification_id}/revert")
def revert_modification_endpoint(
    conversation_uuid: str,
    modification_id: int,
    user: CurrentUser,
) -> dict[str, Any]:
    """Revert (undo) an applied modification.

    AG-03: Restores the document content to the modification's before_value
    and marks the modification as rejected.
    """
    conversation = get_conversation(conversation_uuid)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    modification = get_modification(modification_id)
    if modification is None:
        raise HTTPException(status_code=404, detail="modification not found")

    if modification["conversation_id"] != conversation["id"]:
        raise HTTPException(status_code=400, detail="modification does not belong to this conversation")

    result = revert_modification(modification_id)

    if not result["reverted"]:
        raise HTTPException(status_code=400, detail=result.get("reason", "failed to revert modification"))

    return result


@router.get("/{conversation_uuid}/modifications/{modification_id}/diff")
def get_modification_diff_endpoint(
    conversation_uuid: str,
    modification_id: int,
    user: CurrentUser,
) -> dict[str, Any]:
    """Get a diff preview of a modification.

    AG-03: Returns before/after values for preview in the UI.
    """
    conversation = get_conversation(conversation_uuid)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    modification = get_modification(modification_id)
    if modification is None:
        raise HTTPException(status_code=404, detail="modification not found")

    if modification["conversation_id"] != conversation["id"]:
        raise HTTPException(status_code=400, detail="modification does not belong to this conversation")

    result = get_modification_diff(modification_id)
    if result is None:
        raise HTTPException(status_code=404, detail="modification not found")

    return result


@router.post("/{conversation_uuid}/modifications/batch-apply")
def batch_apply_modifications_endpoint(
    conversation_uuid: str,
    payload: BatchApplyRequest,
    user: CurrentUser,
) -> dict[str, Any]:
    """Apply all pending modifications for a conversation or message.

    AG-03: Batch apply (keep) operation. If message_id is provided,
    only applies modifications from that message.
    """
    conversation = get_conversation(conversation_uuid)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    result = batch_apply_modifications(
        conversation_id=conversation["id"],
        message_id=payload.message_id,
    )

    return result


@router.post("/{conversation_uuid}/modifications/batch-revert")
def batch_revert_modifications_endpoint(
    conversation_uuid: str,
    payload: BatchRevertRequest,
    user: CurrentUser,
) -> dict[str, Any]:
    """Revert all accepted modifications for a conversation or message.

    AG-03: Batch revert (undo) operation. If message_id is provided,
    only reverts modifications from that message.
    """
    conversation = get_conversation(conversation_uuid)
    if conversation is None:
        raise HTTPException(status_code=404, detail="conversation not found")

    result = batch_revert_modifications(
        conversation_id=conversation["id"],
        message_id=payload.message_id,
    )

    return result


# ============ AG-04: SSE Streaming Endpoints ============

class StreamRequest(BaseModel):
    content: str = Field(min_length=1)
    context_node_id: str | None = None


async def sse_generator(
    conversation_uuid: str,
    user_content: str,
    context_node_id: str | None,
    user_id: str,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for streaming AI response.

    Yields SSE-formatted strings.
    """
    conversation = get_conversation(conversation_uuid)
    if conversation is None:
        yield f"data: {json.dumps({'type': 'error', 'error': 'conversation not found'})}\n\n"
        return

    # Get document for mindmap context
    document = get_document(conversation["document_id"])
    if document is None:
        yield f"data: {json.dumps({'type': 'error', 'error': 'document not found'})}\n\n"
        return

    # Get conversation history
    messages = list_messages(conversation["id"])
    history = [{"role": m["role"], "content": m["content"]} for m in messages]

    # Update context node if provided
    if context_node_id is not None:
        update_conversation(conversation_uuid, {"context_node_id": context_node_id})
    else:
        context_node_id = conversation.get("context_node_id")

    # Store user message
    user_message = create_message(
        conversation_id=conversation["id"],
        role="user",
        content=user_content,
    )

    # Build mindmap structure
    mindmap = document.get("content", {"id": "root", "text": "Root"})

    # Stream AI response
    full_response_text: list[str] = []
    modifications_data: list[dict[str, Any]] = []

    try:
        async for chunk in generate_ai_stream(
            user_message=user_content,
            mindmap=mindmap,
            context_node_id=context_node_id,
            history=history,
        ):
            chunk_type = chunk.get("type")

            if chunk_type == "token":
                content = chunk.get("content", "")
                full_response_text.append(content)
                yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

            elif chunk_type == "done":
                # Store the complete response
                content = chunk.get("content", "")
                modifications_data = chunk.get("modifications", [])

                # Store assistant message
                assistant_message = create_message(
                    conversation_id=conversation["id"],
                    role="assistant",
                    content=content,
                    metadata={"modifications": len(modifications_data)},
                )

                # Create modification records
                for mod in modifications_data:
                    create_modification(
                        conversation_id=conversation["id"],
                        message_id=assistant_message["id"],
                        node_id=mod.get("node_id"),
                        modification_type=mod.get("operation"),
                        before_value={},
                        after_value={
                            "new_text": mod.get("new_text"),
                            "new_memo": mod.get("new_memo"),
                        } if mod.get("operation") != "delete" else None,
                    )

                yield f"data: {json.dumps({'type': 'done', 'content': content, 'modifications': modifications_data, 'message_id': assistant_message['id']})}\n\n"

            elif chunk_type == "error":
                error_msg = chunk.get("error", "Unknown error")
                yield f"data: {json.dumps({'type': 'error', 'error': error_msg})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


@router.post("/{conversation_uuid}/stream")
async def stream_ai_response(
    conversation_uuid: str,
    payload: StreamRequest,
    user: CurrentUser,
) -> StreamingResponse:
    """Stream AI response for a conversation using Server-Sent Events.

    AG-04: SSE streaming endpoint that:
    1. Creates user message
    2. Streams AI response token by token
    3. Extracts modifications from response
    4. Creates modification records for user to accept/reject
    5. Returns final "done" event with complete response and modifications

    SSE Event Types:
    - token: {"type": "token", "content": "..."} - Each token as it arrives
    - done: {"type": "done", "content": "...", "modifications": [...], "message_id": N}
    - error: {"type": "error", "error": "..."}

    The stream automatically stores the user message and creates modification records.
    Modifications start in "pending" status for user to review.
    """
    return StreamingResponse(
        sse_generator(
            conversation_uuid=conversation_uuid,
            user_content=payload.content,
            context_node_id=payload.context_node_id,
            user_id=user["id"],
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
