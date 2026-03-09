"""Agent conversation AI service.

AG-02: 对话模型与 API

This module provides:
- Context building for AI (mindmap summary, node path, etc.)
- AI response parsing (extract modifications from response)
- Conversation AI integration
- OpenAI-compatible API caller
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
import httpx

from app.services.node_id_constraint import filter_valid_modifications


@dataclass
class NodeModification:
    """Represents a single node modification from AI."""
    node_id: str
    operation: str  # 'update', 'add', 'delete'
    new_text: str | None = None
    new_memo: str | None = None
    parent_id: str | None = None  # For 'add' operations


@dataclass
class AIResponse:
    """Parsed AI response with text and modifications."""
    text: str
    modifications: list[NodeModification] = field(default_factory=list)


def build_mindmap_summary(
    root: dict[str, Any],
    *,
    max_depth: int = 4,
    max_children_per_level: int = 10,
) -> str:
    """Generate a text summary of the mindmap structure.

    Format:
    - node-id: Node text
      - child-id: Child text
        - grandchild-id: Grandchild text
    """
    lines: list[str] = []

    def traverse(node: dict[str, Any], depth: int) -> None:
        if depth > max_depth:
            return

        indent = "  " * depth
        node_id = node.get("id", "unknown")
        text = node.get("text", "")
        lines.append(f"{indent}- {node_id}: {text}")

        children = node.get("children", [])
        if len(children) > max_children_per_level:
            # Truncate with indicator
            for child in children[:max_children_per_level]:
                traverse(child, depth + 1)
            remaining = len(children) - max_children_per_level
            lines.append(f"{indent}  ... and {remaining} more nodes")
        else:
            for child in children:
                traverse(child, depth + 1)

    traverse(root, 0)
    return "\n".join(lines)


def build_node_path(
    root: dict[str, Any],
    target_node_id: str,
) -> list[str] | None:
    """Find the path from root to a target node.

    Returns a list of node texts, or None if not found.
    """
    path: list[str] = []

    def find(node: dict[str, Any], current_path: list[str]) -> bool:
        node_text = node.get("text", "")
        new_path = current_path + [node_text]

        if node.get("id") == target_node_id:
            path.extend(new_path)
            return True

        for child in node.get("children", []):
            if find(child, new_path):
                return True

        return False

    if find(root, []):
        return path
    return None


def build_context_for_ai(
    mindmap: dict[str, Any],
    context_node_id: str | None = None,
    history: list[dict[str, str]] | None = None,
    max_history: int = 10,
) -> str:
    """Build context string for AI prompt.

    Includes:
    - Mindmap structure summary
    - Current context node and its path
    - Recent conversation history
    """
    parts: list[str] = []

    # Add mindmap summary
    summary = build_mindmap_summary(mindmap)
    parts.append("当前思维导图结构：")
    parts.append(summary)
    parts.append("")

    # Add context node info if provided
    if context_node_id:
        path = build_node_path(mindmap, context_node_id)
        if path:
            parts.append("当前选中节点路径：")
            parts.append(" > ".join(path))
            parts.append(f"节点 ID: {context_node_id}")
            parts.append("")

            # Find the node to show its details
            node = find_node_by_id(mindmap, context_node_id)
            if node:
                parts.append("节点详情：")
                parts.append(f"  文本: {node.get('text', '')}")
                memo = node.get("memo")
                if memo:
                    parts.append(f"  备注: {memo[:100]}..." if len(memo) > 100 else f"  备注: {memo}")

                children = node.get("children", [])
                if children:
                    parts.append(f"  子节点 ({len(children)}):")
                    for child in children[:5]:
                        parts.append(f"    - {child.get('text', '')}")
                    if len(children) > 5:
                        parts.append(f"    ... and {len(children) - 5} more")

                parts.append("")

    # Add conversation history
    if history:
        parts.append("最近对话历史：")
        # Take only the most recent messages
        recent = history[-max_history:]
        for msg in recent:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role == "user":
                parts.append(f"用户: {content}")
            elif role == "assistant":
                parts.append(f"助手: {content}")
        parts.append("")

    return "\n".join(parts)


def find_node_by_id(root: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    """Find a node by its ID in the mindmap."""
    if root.get("id") == node_id:
        return root

    for child in root.get("children", []):
        result = find_node_by_id(child, node_id)
        if result:
            return result

    return None


def parse_ai_response(response_text: str) -> AIResponse:
    """Parse AI response to extract modifications.

    The AI can include modifications in a code block with format:
    ```modifications
    [
      {"node_id": "node-xxx", "operation": "update", "new_text": "..."},
      {"node_id": "parent-id", "operation": "add", "new_text": "..."}
    ]
    ```

    Returns parsed text with the modification block removed.
    """
    modifications: list[NodeModification] = []
    text = response_text

    # Pattern to match modification code blocks
    pattern = r'```modifications\s*\n(.*?)\n```'

    def extract_mods(match: re.Match) -> str:
        nonlocal modifications
        try:
            mods_json = match.group(1)
            mods_list = json.loads(mods_json)

            for mod_data in mods_list:
                node_id = mod_data.get("node_id")
                operation = mod_data.get("operation")

                if not node_id or not operation:
                    continue

                if operation not in ("update", "add", "delete"):
                    continue

                mod = NodeModification(
                    node_id=node_id,
                    operation=operation,
                    new_text=mod_data.get("new_text"),
                    new_memo=mod_data.get("new_memo"),
                    parent_id=mod_data.get("parent_id"),
                )
                modifications.append(mod)
        except json.JSONDecodeError:
            pass

        # Remove the modification block from the text
        return ""

    # Extract and remove modification blocks
    text = re.sub(pattern, extract_mods, response_text, flags=re.DOTALL)

    # Clean up extra whitespace
    text = text.strip()

    return AIResponse(text=text, modifications=modifications)


def format_modifications_for_response(modifications: list[NodeModification]) -> list[dict[str, Any]]:
    """Format modifications for API response."""
    result = []
    for mod in modifications:
        item = {
            "node_id": mod.node_id,
            "operation": mod.operation,
        }
        if mod.new_text is not None:
            item["new_text"] = mod.new_text
        if mod.new_memo is not None:
            item["new_memo"] = mod.new_memo
        if mod.parent_id is not None:
            item["parent_id"] = mod.parent_id
        result.append(item)
    return result


# System prompt for AI conversation
SYSTEM_PROMPT = """你是一个思维导图助手，帮助用户编辑和优化思维导图。

你可以：
- 修改节点内容
- 添加子节点
- 删除节点
- 优化表述
- 生成备注

如果你需要修改脑图，请在回复末尾用以下格式的代码块输出修改指令：

```modifications
[
  {"node_id": "节点ID", "operation": "update", "new_text": "新文本"},
  {"node_id": "父节点ID", "operation": "add", "new_text": "新子节点文本"},
  {"node_id": "节点ID", "operation": "delete"}
]
```

注意事项：
- operation 可以是 update、add 或 delete
- update 操作使用 new_text 和可选的 new_memo 字段
- add 操作中 node_id 应为父节点 ID
- 节点 ID 必须是实际存在的 ID
- 当用户提到"当前选中节点"时，操作应使用该节点 ID
"""


def build_messages_for_ai(
    user_message: str,
    mindmap: dict[str, Any],
    context_node_id: str | None = None,
    history: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    """Build the message list for AI API call.

    Returns a list of messages in the format expected by OpenAI-compatible APIs.
    """
    messages: list[dict[str, str]] = []

    # System prompt
    messages.append({"role": "system", "content": SYSTEM_PROMPT})

    # Context
    context = build_context_for_ai(mindmap, context_node_id, history)
    if context:
        messages.append({"role": "system", "content": context})

    # Emphasize context node if provided
    if context_node_id:
        emphasis = f"重要：本次操作的上下文节点 ID 是 {context_node_id}，请确保修改操作使用此节点 ID。"
        messages.append({"role": "system", "content": emphasis})

    # User message
    messages.append({"role": "user", "content": user_message})

    return messages


@dataclass
class AIConversationResult:
    """Result of calling the AI conversation API."""
    text: str
    modifications: list[NodeModification]
    raw_response: dict[str, Any] | None = None
    error: str | None = None


async def call_ai_conversation(
    messages: list[dict[str, str]],
    *,
    model: str = "gpt-4o-mini",
    max_tokens: int = 2000,
    temperature: float = 0.7,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float = 60.0,
) -> AIConversationResult:
    """Call OpenAI-compatible API for conversation.

    Args:
        messages: List of messages in OpenAI format
        model: Model to use (default: gpt-4o-mini)
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature
        base_url: API base URL (falls back to settings)
        api_key: API key (falls back to settings)
        timeout: Request timeout in seconds

    Returns:
        AIConversationResult with parsed text and modifications
    """
    from app.core.settings import get_settings

    settings = get_settings()
    actual_base_url = base_url or settings.openai_base_url
    actual_api_key = api_key or settings.openai_api_key

    if not actual_api_key:
        return AIConversationResult(
            text="",
            modifications=[],
            error="No API key configured. Set OPENAI_API_KEY environment variable.",
        )

    url = f"{actual_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {actual_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        # Extract text from response
        choices = data.get("choices", [])
        if not choices:
            return AIConversationResult(
                text="",
                modifications=[],
                raw_response=data,
                error="No choices in API response",
            )

        message = choices[0].get("message", {})
        content = message.get("content", "")

        # Parse modifications from response
        parsed = parse_ai_response(content)

        return AIConversationResult(
            text=parsed.text,
            modifications=parsed.modifications,
            raw_response=data,
        )

    except httpx.HTTPStatusError as e:
        return AIConversationResult(
            text="",
            modifications=[],
            error=f"API error: {e.response.status_code} - {e.response.text[:200]}",
        )
    except httpx.TimeoutException:
        return AIConversationResult(
            text="",
            modifications=[],
            error=f"API timeout after {timeout} seconds",
        )
    except Exception as e:
        return AIConversationResult(
            text="",
            modifications=[],
            error=f"Unexpected error: {str(e)}",
        )


async def generate_ai_response(
    user_message: str,
    mindmap: dict[str, Any],
    context_node_id: str | None = None,
    history: list[dict[str, str]] | None = None,
    model: str = "gpt-4o-mini",
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float = 60.0,
) -> AIConversationResult:
    """Convenience function to generate AI response for a conversation.

    This combines build_messages_for_ai and call_ai_conversation.

    Args:
        user_message: The user's message
        mindmap: The current mindmap structure
        context_node_id: Optional context node ID
        history: Optional conversation history
        model: Model to use
        base_url: API base URL (falls back to settings)
        api_key: API key (falls back to settings)
        timeout: Request timeout in seconds

    Returns:
        AIConversationResult with parsed response
    """
    messages = build_messages_for_ai(
        user_message=user_message,
        mindmap=mindmap,
        context_node_id=context_node_id,
        history=history,
    )
    return await call_ai_conversation(
        messages,
        model=model,
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
    )


# ============ AG-04: SSE Streaming Support ============

import asyncio
from typing import AsyncGenerator


@dataclass
class StreamChunk:
    """A single chunk from the streaming response."""
    type: str  # "token", "done", "error"
    content: str | None = None
    modifications: list[dict[str, Any]] | None = None
    error: str | None = None


async def call_ai_conversation_stream(
    messages: list[dict[str, str]],
    *,
    model: str = "gpt-4o-mini",
    max_tokens: int = 2000,
    temperature: float = 0.7,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float = 120.0,
) -> AsyncGenerator[dict[str, Any], None]:
    """Call OpenAI-compatible API with streaming support.

    Yields chunks in the format:
    {"type": "token", "content": "..."} for each token
    {"type": "done", "content": "...", "modifications": [...]} at the end
    {"type": "error", "error": "..."} on error

    Args:
        messages: List of messages in OpenAI format
        model: Model to use (default: gpt-4o-mini)
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature
        base_url: API base URL (falls back to settings)
        api_key: API key (falls back to settings)
        timeout: Request timeout in seconds

    Yields:
        Dictionary with streaming chunks
    """
    from app.core.settings import get_settings

    settings = get_settings()
    actual_base_url = base_url or settings.openai_base_url
    actual_api_key = api_key or settings.openai_api_key

    if not actual_api_key:
        yield {"type": "error", "error": "No API key configured. Set OPENAI_API_KEY environment variable."}
        return

    url = f"{actual_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {actual_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,  # Enable streaming
    }

    full_content: list[str] = []

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue

                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]  # Remove "data: " prefix

                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = data.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")

                    if content:
                        full_content.append(content)
                        yield {"type": "token", "content": content}

                    # Check for finish_reason
                    finish_reason = choices[0].get("finish_reason")
                    if finish_reason:
                        break

        # Parse the complete response for modifications
        complete_text = "".join(full_content)
        parsed = parse_ai_response(complete_text)
        modifications = format_modifications_for_response(parsed.modifications)

        yield {
            "type": "done",
            "content": parsed.text,
            "modifications": modifications,
        }

    except httpx.HTTPStatusError as e:
        yield {
            "type": "error",
            "error": f"API error: {e.response.status_code} - {e.response.text[:200]}",
        }
    except httpx.TimeoutException:
        yield {
            "type": "error",
            "error": f"API timeout after {timeout} seconds",
        }
    except Exception as e:
        yield {
            "type": "error",
            "error": f"Unexpected error: {str(e)}",
        }


async def generate_ai_stream(
    user_message: str,
    mindmap: dict[str, Any],
    context_node_id: str | None = None,
    history: list[dict[str, str]] | None = None,
    model: str = "gpt-4o-mini",
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: float = 120.0,
) -> AsyncGenerator[dict[str, Any], None]:
    """Convenience function to stream AI response for a conversation.

    This combines build_messages_for_ai and call_ai_conversation_stream.
    Also filters modifications based on node ID context constraint (AG-05).

    Args:
        user_message: The user's message
        mindmap: The current mindmap structure
        context_node_id: Optional context node ID
        history: Optional conversation history
        model: Model to use
        base_url: API base URL (falls back to settings)
        api_key: API key (falls back to settings)
        timeout: Request timeout in seconds

    Yields:
        Dictionary with streaming chunks
    """
    messages = build_messages_for_ai(
        user_message=user_message,
        mindmap=mindmap,
        context_node_id=context_node_id,
        history=history,
    )
    async for chunk in call_ai_conversation_stream(
        messages,
        model=model,
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
    ):
        # AG-05: Filter modifications to only include valid ones
        if chunk.get("type") == "done" and chunk.get("modifications"):
            raw_mods = chunk["modifications"]
            filtered_mods = filter_valid_modifications(
                raw_mods,
                mindmap,
                context_node_id,
            )
            chunk = {
                **chunk,
                "modifications": filtered_mods,
                "filtered_count": len(raw_mods) - len(filtered_mods),
            }
        yield chunk
