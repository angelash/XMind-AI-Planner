"""
Tests for Agent Conversation AI Service (AG-02)

Tests for:
- Mindmap summary generation
- Node path finding
- Context building for AI
- AI response parsing
"""

import pytest
from app.services.conversation_ai import (
    AIResponse,
    NodeModification,
    build_context_for_ai,
    build_mindmap_summary,
    build_node_path,
    build_messages_for_ai,
    find_node_by_id,
    parse_ai_response,
    format_modifications_for_response,
)


# Sample mindmap for testing
SAMPLE_MINDMAP = {
    "id": "root",
    "text": "项目概述",
    "children": [
        {
            "id": "node-1",
            "text": "核心功能",
            "children": [
                {"id": "node-1-1", "text": "用户管理"},
                {"id": "node-1-2", "text": "权限控制"},
            ],
        },
        {
            "id": "node-2",
            "text": "技术架构",
            "children": [
                {"id": "node-2-1", "text": "前端框架"},
                {"id": "node-2-2", "text": "后端服务"},
            ],
        },
    ],
}


def test_build_mindmap_summary():
    """build_mindmap_summary should generate a text summary of the mindmap."""
    summary = build_mindmap_summary(SAMPLE_MINDMAP)

    assert "root: 项目概述" in summary
    assert "node-1: 核心功能" in summary
    assert "node-1-1: 用户管理" in summary
    assert "node-2: 技术架构" in summary


def test_build_mindmap_summary_max_depth():
    """build_mindmap_summary should respect max_depth parameter."""
    summary = build_mindmap_summary(SAMPLE_MINDMAP, max_depth=1)

    assert "root: 项目概述" in summary
    assert "node-1: 核心功能" in summary
    assert "node-1-1: 用户管理" not in summary  # Too deep


def test_build_mindmap_summary_max_children():
    """build_mindmap_summary should truncate children list when exceeding max."""
    large_mindmap = {
        "id": "root",
        "text": "Root",
        "children": [{"id": f"child-{i}", "text": f"Child {i}"} for i in range(15)],
    }

    summary = build_mindmap_summary(large_mindmap, max_children_per_level=5)

    assert "child-0" in summary
    assert "child-4" in summary
    assert "child-5" not in summary
    assert "10 more nodes" in summary


def test_build_node_path():
    """build_node_path should find the path from root to a node."""
    path = build_node_path(SAMPLE_MINDMAP, "node-1-1")

    assert path is not None
    assert path == ["项目概述", "核心功能", "用户管理"]


def test_build_node_path_not_found():
    """build_node_path should return None if node not found."""
    path = build_node_path(SAMPLE_MINDMAP, "nonexistent")

    assert path is None


def test_build_node_path_root():
    """build_node_path should return single element for root."""
    path = build_node_path(SAMPLE_MINDMAP, "root")

    assert path == ["项目概述"]


def test_find_node_by_id():
    """find_node_by_id should find a node by its ID."""
    node = find_node_by_id(SAMPLE_MINDMAP, "node-1-2")

    assert node is not None
    assert node["id"] == "node-1-2"
    assert node["text"] == "权限控制"


def test_find_node_by_id_not_found():
    """find_node_by_id should return None if not found."""
    node = find_node_by_id(SAMPLE_MINDMAP, "nonexistent")

    assert node is None


def test_build_context_for_ai():
    """build_context_for_ai should build context string for AI."""
    context = build_context_for_ai(SAMPLE_MINDMAP)

    assert "当前思维导图结构" in context
    assert "项目概述" in context
    assert "核心功能" in context


def test_build_context_for_ai_with_context_node():
    """build_context_for_ai should include context node details."""
    context = build_context_for_ai(SAMPLE_MINDMAP, context_node_id="node-1")

    assert "当前选中节点路径" in context
    assert "项目概述 > 核心功能" in context
    assert "节点 ID: node-1" in context


def test_build_context_for_ai_with_history():
    """build_context_for_ai should include conversation history."""
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi! How can I help?"},
    ]
    context = build_context_for_ai(SAMPLE_MINDMAP, history=history)

    assert "最近对话历史" in context
    assert "用户: Hello" in context
    assert "助手: Hi! How can I help?" in context


def test_parse_ai_response_no_modifications():
    """parse_ai_response should handle responses without modifications."""
    response_text = "这是一个普通的AI回复，没有修改指令。"
    result = parse_ai_response(response_text)

    assert result.text == "这是一个普通的AI回复，没有修改指令。"
    assert len(result.modifications) == 0


def test_parse_ai_response_with_modifications():
    """parse_ai_response should extract modifications from response."""
    response_text = """我来帮你更新这个节点。

```modifications
[
  {"node_id": "node-1", "operation": "update", "new_text": "更新后的内容"}
]
```

修改已完成。"""

    result = parse_ai_response(response_text)

    assert "我来帮你更新这个节点" in result.text
    assert "修改已完成" in result.text
    assert "```modifications" not in result.text
    assert len(result.modifications) == 1
    assert result.modifications[0].node_id == "node-1"
    assert result.modifications[0].operation == "update"
    assert result.modifications[0].new_text == "更新后的内容"


def test_parse_ai_response_with_multiple_modifications():
    """parse_ai_response should handle multiple modifications."""
    response_text = """我将进行以下修改：

```modifications
[
  {"node_id": "node-1", "operation": "update", "new_text": "更新内容"},
  {"node_id": "node-1", "operation": "add", "new_text": "新子节点"},
  {"node_id": "node-2", "operation": "delete"}
]
```"""

    result = parse_ai_response(response_text)

    assert len(result.modifications) == 3

    update_mod = next(m for m in result.modifications if m.operation == "update")
    assert update_mod.node_id == "node-1"
    assert update_mod.new_text == "更新内容"

    add_mod = next(m for m in result.modifications if m.operation == "add")
    assert add_mod.node_id == "node-1"

    delete_mod = next(m for m in result.modifications if m.operation == "delete")
    assert delete_mod.node_id == "node-2"


def test_parse_ai_response_invalid_json():
    """parse_ai_response should handle invalid JSON gracefully."""
    response_text = """修改如下：

```modifications
[invalid json]
```"""

    result = parse_ai_response(response_text)

    # Should not crash, modifications should be empty
    assert len(result.modifications) == 0
    assert "修改如下" in result.text


def test_parse_ai_response_invalid_operation():
    """parse_ai_response should ignore invalid operations."""
    response_text = """```modifications
[
  {"node_id": "node-1", "operation": "invalid_op", "new_text": "test"},
  {"node_id": "node-2", "operation": "update", "new_text": "valid"}
]
```"""

    result = parse_ai_response(response_text)

    # Only the valid operation should be parsed
    assert len(result.modifications) == 1
    assert result.modifications[0].operation == "update"


def test_format_modifications_for_response():
    """format_modifications_for_response should format modifications for API."""
    mods = [
        NodeModification(node_id="node-1", operation="update", new_text="New text"),
        NodeModification(node_id="node-2", operation="add", new_text="Child", parent_id="parent"),
    ]

    formatted = format_modifications_for_response(mods)

    assert len(formatted) == 2
    assert formatted[0]["node_id"] == "node-1"
    assert formatted[0]["operation"] == "update"
    assert formatted[0]["new_text"] == "New text"
    assert formatted[1]["parent_id"] == "parent"


def test_build_messages_for_ai():
    """build_messages_for_ai should build message list for OpenAI API."""
    messages = build_messages_for_ai(
        user_message="请帮我优化这个节点",
        mindmap=SAMPLE_MINDMAP,
        context_node_id="node-1",
    )

    # Should have system, context, emphasis, and user messages
    assert len(messages) >= 3
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "请帮我优化这个节点"

    # Should emphasize context node
    emphasis_found = any("node-1" in m["content"] for m in messages if m["role"] == "system")
    assert emphasis_found


def test_build_messages_for_ai_with_history():
    """build_messages_for_ai should include history in context."""
    history = [
        {"role": "user", "content": "之前的问题"},
        {"role": "assistant", "content": "之前的回答"},
    ]
    messages = build_messages_for_ai(
        user_message="新的问题",
        mindmap=SAMPLE_MINDMAP,
        history=history,
    )

    # History should be reflected in context
    context_msg = next((m for m in messages if "之前的问题" in m.get("content", "")), None)
    assert context_msg is not None


# ============ AI Call Tests (with mocking) ============

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import httpx


def test_call_ai_conversation_no_api_key():
    """call_ai_conversation should return error if no API key configured."""
    async def run_test():
        from app.services.conversation_ai import call_ai_conversation

        result = await call_ai_conversation(
            messages=[{"role": "user", "content": "test"}],
            api_key="",  # No API key
        )

        assert result.error is not None
        assert "No API key" in result.error
        assert result.text == ""

    asyncio.run(run_test())


def test_call_ai_conversation_success():
    """call_ai_conversation should parse successful API response."""
    async def run_test():
        from app.services.conversation_ai import call_ai_conversation

        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": "我来帮你更新这个节点。\n\n```modifications\n[{\"node_id\": \"node-1\", \"operation\": \"update\", \"new_text\": \"更新内容\"}]\n```"
                    }
                }
            ]
        }

        # Create a proper mock response
        mock_http_response = MagicMock()
        mock_http_response.json.return_value = mock_response_data
        mock_http_response.raise_for_status = MagicMock()

        async def mock_post(*args, **kwargs):
            return mock_http_response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post = mock_post

            mock_client_class.return_value = mock_instance

            result = await call_ai_conversation(
                messages=[{"role": "user", "content": "test"}],
                api_key="test-key",
            )

            assert result.error is None
            assert "更新这个节点" in result.text
            assert len(result.modifications) == 1
            assert result.modifications[0].node_id == "node-1"

    asyncio.run(run_test())


def test_call_ai_conversation_timeout():
    """call_ai_conversation should handle timeout."""
    async def run_test():
        from app.services.conversation_ai import call_ai_conversation

        async def mock_post(*args, **kwargs):
            raise httpx.TimeoutException("timeout")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post = mock_post

            mock_client_class.return_value = mock_instance

            result = await call_ai_conversation(
                messages=[{"role": "user", "content": "test"}],
                api_key="test-key",
                timeout=10.0,
            )

            assert result.error is not None
            assert "timeout" in result.error.lower()

    asyncio.run(run_test())


def test_call_ai_conversation_http_error():
    """call_ai_conversation should handle HTTP errors."""
    async def run_test():
        from app.services.conversation_ai import call_ai_conversation

        mock_error_response = MagicMock()
        mock_error_response.status_code = 401
        mock_error_response.text = '{"error": "Invalid API key"}'

        async def mock_post(*args, **kwargs):
            raise httpx.HTTPStatusError("401", request=MagicMock(), response=mock_error_response)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post = mock_post

            mock_client_class.return_value = mock_instance

            result = await call_ai_conversation(
                messages=[{"role": "user", "content": "test"}],
                api_key="invalid-key",
            )

            assert result.error is not None
            assert "401" in result.error

    asyncio.run(run_test())


def test_generate_ai_response():
    """generate_ai_response should combine message building and API call."""
    async def run_test():
        from app.services.conversation_ai import generate_ai_response

        mock_response_data = {
            "choices": [
                {
                    "message": {
                        "content": "好的，我来优化这个节点。"
                    }
                }
            ]
        }

        mock_http_response = MagicMock()
        mock_http_response.json.return_value = mock_response_data
        mock_http_response.raise_for_status = MagicMock()

        async def mock_post(*args, **kwargs):
            return mock_http_response

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.post = mock_post

            mock_client_class.return_value = mock_instance

            result = await generate_ai_response(
                user_message="请优化当前节点",
                mindmap=SAMPLE_MINDMAP,
                context_node_id="node-1",
                model="gpt-4o-mini",
                api_key="test-key",
            )

            assert result.error is None
            assert "优化" in result.text

    asyncio.run(run_test())
