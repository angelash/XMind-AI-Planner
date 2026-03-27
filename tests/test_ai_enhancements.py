"""
Tests for AI Enhancement Services (GAP-09)

Tests for:
- Text translation
- ASCII diagram generation
- Node color suggestions
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.ai_enhancements import (
    AIEnhancementsService,
    TranslationResult,
    DiagramResult,
    ColorSuggestionResult,
    ai_enhancements_service,
)


class TestTranslation:
    """Tests for text translation functionality."""

    def test_translate_fallback_no_api_key(self):
        """Translation should use fallback when no API key is configured."""
        async def run_test():
            service = AIEnhancementsService()
            service._openai_api_key = ""

            result = await service.translate_text(
                text="Hello world",
                target_language="中文",
            )

            assert result.original_text == "Hello world"
            assert result.translated_text == "[翻译为中文] Hello world"
            assert result.source_language == "unknown"
            assert result.target_language == "中文"

        asyncio.run(run_test())

    def test_translate_fallback_with_different_languages(self):
        """Fallback translation should work for different languages."""
        async def run_test():
            service = AIEnhancementsService()
            service._openai_api_key = ""

            # Test English
            result_en = await service.translate_text("Test", "English")
            assert "[Translated to English]" in result_en.translated_text

            # Test Japanese
            result_ja = await service.translate_text("Test", "日本語")
            assert "[日本語に翻訳]" in result_ja.translated_text

            # Test unknown language
            result_unknown = await service.translate_text("Test", "Spanish")
            assert "[Translated to Spanish]" in result_unknown.translated_text

        asyncio.run(run_test())

    def test_translate_with_api_key_success(self):
        """Translation should use AI when API key is configured."""
        async def run_test():
            service = AIEnhancementsService()

            mock_response_data = {
                "choices": [
                    {
                        "message": {
                            "content": "你好世界"
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

                # Mock settings
                with patch("app.core.settings.get_settings") as mock_settings:
                    mock_settings.return_value = MagicMock(
                        openai_base_url="https://api.openai.com/v1",
                        openai_api_key="test-key",
                    )

                    result = await service.translate_text(
                        text="Hello world",
                        target_language="中文",
                    )

                    assert result.original_text == "Hello world"
                    assert result.translated_text == "你好世界"
                    assert result.target_language == "中文"

        asyncio.run(run_test())

    def test_translate_with_api_key_fallback_on_error(self):
        """Translation should fallback to basic translation on API error."""
        async def run_test():
            service = AIEnhancementsService()

            async def mock_post(*args, **kwargs):
                raise httpx.TimeoutException("timeout")

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_instance = MagicMock()
                mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
                mock_instance.__aexit__ = AsyncMock(return_value=None)
                mock_instance.post = mock_post

                mock_client_class.return_value = mock_instance

                # Mock settings
                with patch("app.core.settings.get_settings") as mock_settings:
                    mock_settings.return_value = MagicMock(
                        openai_base_url="https://api.openai.com/v1",
                        openai_api_key="test-key",
                    )

                    result = await service.translate_text(
                        text="Hello world",
                        target_language="中文",
                    )

                    # Should use fallback
                    assert "[翻译为中文]" in result.translated_text

        asyncio.run(run_test())


class TestDiagramGeneration:
    """Tests for ASCII diagram generation."""

    def test_generate_diagram_fallback_flowchart(self):
        """Diagram generation should create a basic flowchart when AI is unavailable."""
        async def run_test():
            service = AIEnhancementsService()

            result = await service.generate_ascii_diagram(
                node_text="My Topic",
                diagram_type="flowchart",
            )

            assert result.node_text == "My Topic"
            assert result.diagram_type == "flowchart"
            assert "+" in result.diagram  # ASCII box characters
            assert "| My Topic" in result.diagram or "My Topic" in result.diagram

        asyncio.run(run_test())

    def test_generate_diagram_fallback_tree(self):
        """Diagram generation should create a tree structure when AI is unavailable."""
        async def run_test():
            service = AIEnhancementsService()

            result = await service.generate_ascii_diagram(
                node_text="Root Node",
                diagram_type="tree",
            )

            assert result.node_text == "Root Node"
            assert result.diagram_type == "tree"
            assert "├──" in result.diagram or "└──" in result.diagram
            assert "Root Node" in result.diagram

        asyncio.run(run_test())

    def test_generate_diagram_fallback_process(self):
        """Diagram generation should create a process flow when AI is unavailable."""
        async def run_test():
            service = AIEnhancementsService()

            result = await service.generate_ascii_diagram(
                node_text="My Process",
                diagram_type="process",
            )

            assert result.node_text == "My Process"
            assert result.diagram_type == "process"
            assert "->" in result.diagram

        asyncio.run(run_test())

    def test_generate_diagram_with_api_key(self):
        """Diagram generation should use AI when API key is configured."""
        async def run_test():
            service = AIEnhancementsService()

            mock_response_data = {
                "choices": [
                    {
                        "message": {
                            "content": "START -> Process -> END"
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

                # Mock settings
                with patch("app.core.settings.get_settings") as mock_settings:
                    mock_settings.return_value = MagicMock(
                        openai_base_url="https://api.openai.com/v1",
                        openai_api_key="test-key",
                    )

                    result = await service.generate_ascii_diagram(
                        node_text="My Topic",
                        diagram_type="flowchart",
                    )

                    assert result.diagram == "START -> Process -> END"

        asyncio.run(run_test())


class TestColorSuggestion:
    """Tests for node color suggestions."""

    def test_suggest_color_fallback_urgent(self):
        """Color suggestion should detect urgent/important keywords."""
        async def run_test():
            service = AIEnhancementsService()

            result = await service.suggest_node_color(
                node_text="URGENT: Critical issue",
            )

            assert result.suggested_color == "#FF6B6B"  # Red
            assert "urgent" in result.reason.lower() or "important" in result.reason.lower()

        asyncio.run(run_test())

    def test_suggest_color_fallback_action(self):
        """Color suggestion should detect action-oriented keywords."""
        async def run_test():
            service = AIEnhancementsService()

            result = await service.suggest_node_color(
                node_text="TODO: Fix the bug",
            )

            assert result.suggested_color == "#FFA07A"  # Orange
            assert "action" in result.reason.lower()

        asyncio.run(run_test())

    def test_suggest_color_fallback_creative(self):
        """Color suggestion should detect creative keywords."""
        async def run_test():
            service = AIEnhancementsService()

            result = await service.suggest_node_color(
                node_text="New idea for product",
            )

            assert result.suggested_color == "#BB8FCE"  # Purple
            assert "creative" in result.reason.lower()

        asyncio.run(run_test())

    def test_suggest_color_fallback_note(self):
        """Color suggestion should detect informational keywords."""
        async def run_test():
            service = AIEnhancementsService()

            result = await service.suggest_node_color(
                node_text="Note: Remember to check",
            )

            assert result.suggested_color == "#F7DC6F"  # Yellow
            assert "informational" in result.reason.lower()

        asyncio.run(run_test())

    def test_suggest_color_fallback_default(self):
        """Color suggestion should use default color for neutral text."""
        async def run_test():
            service = AIEnhancementsService()

            result = await service.suggest_node_color(
                node_text="Just some text",
            )

            assert result.suggested_color == "#4ECDC4"  # Teal
            assert "default" in result.reason.lower()

        asyncio.run(run_test())

    def test_suggest_color_with_api_key(self):
        """Color suggestion should use AI when API key is configured."""
        async def run_test():
            service = AIEnhancementsService()

            mock_response_data = {
                "choices": [
                    {
                        "message": {
                            "content": '{"color": "#FF6B6B", "reason": "Urgent content detected"}'
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

                # Mock settings
                with patch("app.core.settings.get_settings") as mock_settings:
                    mock_settings.return_value = MagicMock(
                        openai_base_url="https://api.openai.com/v1",
                        openai_api_key="test-key",
                    )

                    result = await service.suggest_node_color(
                        node_text="URGENT: Fix now",
                    )

                    assert result.suggested_color == "#FF6B6B"
                    assert result.reason == "Urgent content detected"

        asyncio.run(run_test())


class TestServiceSingleton:
    """Tests for the singleton service instance."""

    def test_singleton_instance(self):
        """The ai_enhancements_service should be a singleton."""
        from app.services.ai_enhancements import ai_enhancements_service

        assert isinstance(ai_enhancements_service, AIEnhancementsService)

    def test_singleton_is_reusable(self):
        """The singleton should be reusable across multiple calls."""
        from app.services.ai_enhancements import ai_enhancements_service as instance1
        from app.services.ai_enhancements import ai_enhancements_service as instance2

        assert instance1 is instance2
