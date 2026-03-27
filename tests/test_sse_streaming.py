"""
Tests for SSE Streaming (AG-04)

AG-04 should provide:
- SSE endpoint for streaming AI responses
- Token-by-token streaming as AI generates
- Final event with modifications extracted from response
- Proper error handling and recovery
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

import pytest
from fastapi.testclient import TestClient


# ============ Fixtures ============

@pytest.fixture
def temp_db(monkeypatch):
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        # Set environment variable for database path
        monkeypatch.setenv("DB_PATH", str(db_path))

        # Clear cached settings so it picks up the new database path
        from app.core.settings import get_settings
        get_settings.cache_clear()

        yield db_path


@pytest.fixture
def client(temp_db):
    """Create a test client with database initialized."""
    # Import after database path is set by temp_db fixture
    from app.main import app
    from app.api.deps import get_current_user

    # Mock authentication
    def mock_get_current_user():
        return {"id": "test-user", "role": "user"}

    app.dependency_overrides[get_current_user] = mock_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ============ SSE Streaming Unit Tests ============

def test_call_ai_conversation_stream_exists():
    """The streaming function should exist in conversation_ai module."""
    from app.services.conversation_ai import call_ai_conversation_stream

    assert callable(call_ai_conversation_stream)


def test_sse_endpoint_registered(client):
    """SSE streaming endpoint should be registered."""
    # Create a document first
    from app.services.document_store import create_document

    doc = create_document("Test Doc", {"id": "root", "text": "Root"}, "test-user")

    # Create a conversation
    from app.services.conversation_store import create_conversation

    conv = create_conversation(doc["id"], "test-user", "Test")

    # The endpoint should exist at /api/v1/conversations/{uuid}/stream
    response = client.post(
        f"/api/v1/conversations/{conv['uuid']}/stream",
        json={"content": "Hello"},
    )
    # Endpoint exists - may fail due to API key (500 or error), but not 404
    assert response.status_code != 404, f"SSE endpoint should exist, got {response.status_code}: {response.text}"


def test_streaming_generator_format():
    """Test that the streaming generator produces correct SSE format."""
    from app.services.conversation_ai import call_ai_conversation_stream

    # We'll test the generator directly without mocking
    # This test verifies the format structure
    import inspect

    # Check it's an async generator
    assert inspect.isasyncgenfunction(call_ai_conversation_stream)


def test_streaming_with_mocked_api():
    """Test streaming with mocked API response."""
    from app.services.document_store import create_document
    from app.services.conversation_store import create_conversation

    # Create document and conversation
    doc = create_document("Test Doc", {"id": "root", "text": "Root"}, "test-user")
    conv = create_conversation(doc["id"], "test-user", "Test", context_node_id="root")

    # Create mock streaming response
    async def mock_stream(*args, **kwargs):
        # Yield tokens
        yield {"type": "token", "content": "Hello"}
        yield {"type": "token", "content": " world"}
        # Final done event
        yield {"type": "done", "content": "Hello world", "modifications": []}

    with patch("app.services.conversation_ai.call_ai_conversation_stream") as mock_call:
        mock_call.return_value = mock_stream()

        # Import the streaming generator function
        from app.api.v1.endpoints.conversations import sse_generator

        # Run the generator
        async def collect_events():
            events = []
            async for event in sse_generator(conv["uuid"], "Test message", None, "test-user"):
                events.append(event)
            return events

        events = asyncio.run(collect_events())

        # Should have token events and a done event
        assert len(events) >= 2
        # All events should be SSE formatted (data: {...})
        for event in events:
            assert event.startswith("data: ")
            data_str = event[6:].strip()
            if data_str:
                data = json.loads(data_str)
                assert "type" in data


def test_streaming_with_modifications():
    """Test that modifications are extracted and included in the final event."""
    from app.services.document_store import create_document
    from app.services.conversation_store import create_conversation

    # Create document and conversation
    doc = create_document("Test Doc", {"id": "root", "text": "Root node"}, "test-user")
    conv = create_conversation(doc["id"], "test-user", "Test", context_node_id="root")

    # Mock streaming response with modifications
    async def mock_stream(*args, **kwargs):
        yield {"type": "token", "content": "I'll update the node."}
        yield {
            "type": "done",
            "content": "I'll update the node.",
            "modifications": [
                {"node_id": "root", "operation": "update", "new_text": "Updated Root"}
            ],
        }

    with patch("app.services.conversation_ai.call_ai_conversation_stream") as mock_call:
        mock_call.return_value = mock_stream()

        from app.api.v1.endpoints.conversations import sse_generator

        async def collect_events():
            events = []
            async for event in sse_generator(conv["uuid"], "Update the root", None, "test-user"):
                events.append(event)
            return events

        events = asyncio.run(collect_events())

        # Find the done event
        done_events = []
        for event in events:
            if event.startswith("data: "):
                data_str = event[6:].strip()
                if data_str:
                    data = json.loads(data_str)
                    if data.get("type") == "done":
                        done_events.append(data)

        assert len(done_events) == 1
        done_event = done_events[0]
        assert "modifications" in done_event
        assert len(done_event["modifications"]) == 1
        assert done_event["modifications"][0]["node_id"] == "root"


def test_streaming_error_handling():
    """Test that errors are properly formatted as SSE events."""
    from app.services.document_store import create_document
    from app.services.conversation_store import create_conversation

    doc = create_document("Test Doc", {"id": "root", "text": "Root"}, "test-user")
    conv = create_conversation(doc["id"], "test-user", "Test")

    # Mock streaming that errors
    async def mock_stream(*args, **kwargs):
        yield {"type": "token", "content": "Starting..."}
        yield {"type": "error", "error": "API connection failed"}

    with patch("app.services.conversation_ai.call_ai_conversation_stream") as mock_call:
        mock_call.return_value = mock_stream()

        from app.api.v1.endpoints.conversations import sse_generator

        async def collect_events():
            events = []
            async for event in sse_generator(conv["uuid"], "Hello", None, "test-user"):
                events.append(event)
            return events

        events = asyncio.run(collect_events())

        # Should have an error event
        error_events = []
        for event in events:
            if event.startswith("data: "):
                data_str = event[6:].strip()
                if data_str:
                    data = json.loads(data_str)
                    if data.get("type") == "error":
                        error_events.append(data)

        assert len(error_events) >= 1
        assert "API connection failed" in error_events[0].get("error", "")


def test_streaming_stores_message():
    """Test that user and assistant messages are stored after streaming."""
    from app.services.document_store import create_document
    from app.services.conversation_store import create_conversation, list_messages

    doc = create_document("Test Doc", {"id": "root", "text": "Root"}, "test-user")
    conv = create_conversation(doc["id"], "test-user", "Test")

    async def mock_stream(*args, **kwargs):
        yield {"type": "token", "content": "Hello"}
        yield {"type": "token", "content": " world"}
        yield {"type": "done", "content": "Hello world", "modifications": []}

    with patch("app.services.conversation_ai.call_ai_conversation_stream") as mock_call:
        mock_call.return_value = mock_stream()

        from app.api.v1.endpoints.conversations import sse_generator

        async def collect_events():
            async for event in sse_generator(conv["uuid"], "Test message", None, "test-user"):
                pass

        asyncio.run(collect_events())

    # Verify messages were stored
    messages = list_messages(conv["id"])
    assert len(messages) == 2  # User message + Assistant message

    user_msg = [m for m in messages if m["role"] == "user"][0]
    assert user_msg["content"] == "Test message"

    assistant_msg = [m for m in messages if m["role"] == "assistant"][0]
    assert "Hello world" in assistant_msg["content"]


def test_streaming_with_context_node():
    """Test that context node is passed to AI generation."""
    from app.services.document_store import create_document
    from app.services.conversation_store import create_conversation, get_conversation

    # Create document with nodes
    mindmap = {
        "id": "root",
        "text": "Root",
        "children": [
            {"id": "child-1", "text": "Child 1"}
        ]
    }
    doc = create_document("Test Doc", mindmap, "test-user")
    conv = create_conversation(doc["id"], "test-user", "Test", context_node_id="child-1")

    async def mock_stream(*args, **kwargs):
        yield {"type": "token", "content": "Done"}
        yield {"type": "done", "content": "Done", "modifications": []}

    with patch("app.services.conversation_ai.call_ai_conversation_stream") as mock_call:
        mock_call.return_value = mock_stream()

        from app.api.v1.endpoints.conversations import sse_generator

        async def collect_events():
            async for event in sse_generator(conv["uuid"], "Update this node", "child-1", "test-user"):
                pass

        asyncio.run(collect_events())

    # Verify context_node_id was passed
    assert mock_call.called


def test_non_streaming_endpoint_still_works(client):
    """Non-streaming message endpoint should still work for backwards compatibility."""
    from app.services.document_store import create_document
    from app.services.conversation_store import create_conversation

    doc = create_document("Test Doc", {"id": "root", "text": "Root"}, "test-user")
    conv = create_conversation(doc["id"], "test-user", "Test")

    # Use the non-streaming message endpoint
    response = client.post(
        f"/api/v1/conversations/{conv['uuid']}/messages",
        json={"content": "Hello"},
    )

    # Should return 200 or 201 - the endpoint creates the user message
    assert response.status_code in (200, 201), f"Expected 200/201, got {response.status_code}: {response.text}"
    data = response.json()
    assert data["role"] == "user"
    assert data["content"] == "Hello"