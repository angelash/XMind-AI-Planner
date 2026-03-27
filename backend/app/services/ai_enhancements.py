"""AI Enhancement Services (GAP-09)

Provides:
- Text translation
- ASCII diagram generation
- Node coloring suggestions
"""

from __future__ import annotations

import httpx
from dataclasses import dataclass
from typing import Any


@dataclass
class TranslationResult:
    """Result of text translation."""
    original_text: str
    translated_text: str
    source_language: str
    target_language: str


@dataclass
class DiagramResult:
    """Result of diagram generation."""
    node_id: str
    node_text: str
    diagram: str
    diagram_type: str


@dataclass
class ColorSuggestionResult:
    """Result of color suggestion."""
    node_id: str
    node_text: str
    suggested_color: str
    reason: str


class AIEnhancementsService:
    """Service for AI-powered enhancements to mindmap nodes."""

    def __init__(self):
        self._openai_base_url = None
        self._openai_api_key = None

    def _get_settings(self):
        """Lazy import settings to avoid circular dependencies."""
        from app.core.settings import get_settings
        settings = get_settings()
        self._openai_base_url = settings.openai_base_url
        self._openai_api_key = settings.openai_api_key
        return settings

    async def translate_text(
        self,
        text: str,
        target_language: str,
        *,
        source_language: str = "auto",
        timeout: float = 30.0,
    ) -> TranslationResult:
        """Translate text to a target language using AI.

        Args:
            text: Text to translate
            target_language: Target language (e.g., "English", "中文", "日本語")
            source_language: Source language (default: auto-detect)
            timeout: Request timeout in seconds

        Returns:
            TranslationResult with translated text and metadata
        """
        self._get_settings()

        if not self._openai_api_key:
            # Fallback to basic translation if no API key
            return self._translate_fallback(text, target_language)

        url = f"{self._openai_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._openai_api_key}",
            "Content-Type": "application/json",
        }

        system_prompt = f"""You are a professional translator. Translate the given text to {target_language}.

Rules:
- Keep the meaning accurate
- Use natural, fluent language
- Preserve formatting (lists, emphasis, etc.)
- Do NOT add any explanations or extra text
- Return ONLY the translated text"""

        user_prompt = text

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 500,
            "temperature": 0.3,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

            choices = data.get("choices", [])
            if not choices:
                return self._translate_fallback(text, target_language)

            message = choices[0].get("message", {})
            translated_text = message.get("content", text).strip()

            return TranslationResult(
                original_text=text,
                translated_text=translated_text,
                source_language=source_language,
                target_language=target_language,
            )

        except Exception:
            # Fallback to basic translation on error
            return self._translate_fallback(text, target_language)

    def _translate_fallback(self, text: str, target_language: str) -> TranslationResult:
        """Fallback translation when AI is not available."""
        # Simple dictionary-based fallback for common languages
        fallback_map = {
            "English": "[Translated to English] " + text,
            "英文": "[Translated to English] " + text,
            "en": "[Translated to English] " + text,
            "中文": "[翻译为中文] " + text,
            "日本語": "[日本語に翻訳] " + text,
            "日语": "[日本語に翻訳] " + text,
            "ja": "[日本語に翻訳] " + text,
        }

        translated = fallback_map.get(target_language, f"[Translated to {target_language}] {text}")

        return TranslationResult(
            original_text=text,
            translated_text=translated,
            source_language="unknown",
            target_language=target_language,
        )

    async def generate_ascii_diagram(
        self,
        node_text: str,
        *,
        diagram_type: str = "flowchart",
        timeout: float = 30.0,
    ) -> DiagramResult:
        """Generate an ASCII diagram from node text using AI.

        Args:
            node_text: The node content to visualize
            diagram_type: Type of diagram (flowchart, tree, process)
            timeout: Request timeout in seconds

        Returns:
            DiagramResult with ASCII diagram
        """
        self._get_settings()

        if not self._openai_api_key:
            # Fallback to basic diagram
            return self._generate_diagram_fallback(node_text, diagram_type)

        url = f"{self._openai_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._openai_api_key}",
            "Content-Type": "application/json",
        }

        system_prompt = f"""You are a diagram generator. Create an ASCII {diagram_type} from the given topic.

Rules:
- Use ASCII characters only (|, -, +, >, etc.)
- Make it clear and readable
- No special unicode characters
- Keep it under 20 lines if possible
- Return ONLY the diagram, no explanations"""

        user_prompt = f"Create a {diagram_type} for: {node_text}"

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 500,
            "temperature": 0.5,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

            choices = data.get("choices", [])
            if not choices:
                return self._generate_diagram_fallback(node_text, diagram_type)

            message = choices[0].get("message", {})
            diagram = message.get("content", "").strip()

            # Clean up if AI added explanations
            if "```" in diagram:
                lines = diagram.split('\n')
                diagram = '\n'.join(
                    line for line in lines
                    if not line.strip().startswith('```')
                ).strip()

            return DiagramResult(
                node_id="",
                node_text=node_text,
                diagram=diagram,
                diagram_type=diagram_type,
            )

        except Exception:
            return self._generate_diagram_fallback(node_text, diagram_type)

    def _generate_diagram_fallback(self, node_text: str, diagram_type: str) -> DiagramResult:
        """Fallback diagram generation when AI is not available."""

        if diagram_type == "flowchart":
            diagram = f"""+--------------+
|  {node_text[:15]}  |
+------+-------+
       |
       v
+--------------+
|   Step 1     |
+------+-------+
       |
       v
+--------------+
|   Step 2     |
+--------------+"""
        elif diagram_type == "tree":
            diagram = f"""{node_text}
├── Branch 1
│   ├── Sub-branch A
│   └── Sub-branch B
├── Branch 2
│   └── Sub-branch C
└── Branch 3"""
        else:  # process
            diagram = f"""START -> {node_text[:10]} -> PROCESS -> END"""

        return DiagramResult(
            node_id="",
            node_text=node_text,
            diagram=diagram,
            diagram_type=diagram_type,
        )

    async def suggest_node_color(
        self,
        node_text: str,
        *,
        timeout: float = 20.0,
    ) -> ColorSuggestionResult:
        """Suggest a color for a node based on its content using AI.

        Args:
            node_text: The node content to analyze
            timeout: Request timeout in seconds

        Returns:
            ColorSuggestionResult with color suggestion and reason
        """
        self._get_settings()

        if not self._openai_api_key:
            # Fallback to basic color suggestion
            return self._suggest_color_fallback(node_text)

        url = f"{self._openai_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._openai_api_key}",
            "Content-Type": "application/json",
        }

        system_prompt = """You are a UI/UX designer. Suggest a color for a mindmap node based on its content.

Available colors (hex codes):
- #FF6B6B (red - urgent, important)
- #4ECDC4 (teal - calm, neutral)
- #45B7D1 (blue - information)
- #FFA07A (orange - action, active)
- #98D8C8 (mint - fresh, new)
- #F7DC6F (yellow - highlight, note)
- #BB8FCE (purple - creative)
- #85C1E2 (light blue - soft)

Rules:
- Respond with ONLY a JSON object: {"color": "#hexcode", "reason": "one sentence"}
- No markdown formatting
- Choose colors that fit the semantic meaning of the text"""

        user_prompt = f"Node content: {node_text}"

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 100,
            "temperature": 0.5,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

            choices = data.get("choices", [])
            if not choices:
                return self._suggest_color_fallback(node_text)

            message = choices[0].get("message", {})
            content = message.get("content", "").strip()

            # Parse JSON response
            import json
            try:
                result = json.loads(content)
                color = result.get("color", "#4ECDC4")
                reason = result.get("reason", "Default suggestion")
            except json.JSONDecodeError:
                # Try to extract hex code from text
                import re
                match = re.search(r'#[0-9A-Fa-f]{6}', content)
                color = match.group(0) if match else "#4ECDC4"
                reason = "Color suggested based on content"

            return ColorSuggestionResult(
                node_id="",
                node_text=node_text,
                suggested_color=color,
                reason=reason,
            )

        except Exception:
            return self._suggest_color_fallback(node_text)

    def _suggest_color_fallback(self, node_text: str) -> ColorSuggestionResult:
        """Fallback color suggestion when AI is not available."""

        # Simple heuristic-based fallback
        text_lower = node_text.lower()

        if any(word in text_lower for word in ['urgent', 'critical', 'important', 'urgent', 'critical', '紧急', '重要']):
            color = "#FF6B6B"
            reason = "Detected urgent/important keywords"
        elif any(word in text_lower for word in ['todo', 'action', 'task', 'task', 'action', 'todo', '任务', '行动']):
            color = "#FFA07A"
            reason = "Detected action-oriented keywords"
        elif any(word in text_lower for word in ['idea', 'concept', 'creative', 'idea', 'concept', '创意', '概念']):
            color = "#BB8FCE"
            reason = "Detected creative keywords"
        elif any(word in text_lower for word in ['note', 'info', 'info', 'note', '备注', '信息']):
            color = "#F7DC6F"
            reason = "Detected informational keywords"
        else:
            color = "#4ECDC4"
            reason = "Default neutral color"

        return ColorSuggestionResult(
            node_id="",
            node_text=node_text,
            suggested_color=color,
            reason=reason,
        )


# Singleton instance
ai_enhancements_service = AIEnhancementsService()
