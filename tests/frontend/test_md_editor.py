"""Tests for MD Editor frontend component."""
import pytest
from pathlib import Path


class TestMdEditorComponent:
    """Tests for MD Editor JavaScript component."""

    def test_md_editor_js_exists(self):
        """Verify the MD editor JavaScript file exists."""
        js_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "mdEditor.js"
        assert js_path.exists(), "mdEditor.js should exist"

    def test_md_editor_exports_required_functions(self):
        """Verify the MD editor exports required functions."""
        js_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "mdEditor.js"
        content = js_path.read_text()

        # Check for exported functions (async functions have 'export async function')
        assert "export function initMdEditor" in content, "Should export initMdEditor"
        assert "export async function openFile" in content or "export function openFile" in content, "Should export openFile"
        assert "export function setProject" in content, "Should export setProject"
        assert "export function isVisible" in content, "Should export isVisible"
        assert "export function hasUnsavedChanges" in content, "Should export hasUnsavedChanges"

    def test_md_editor_has_edit_and_preview_modes(self):
        """Verify the MD editor supports edit and preview modes."""
        js_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "mdEditor.js"
        content = js_path.read_text()

        assert "editorMode" in content, "Should have editorMode state"
        assert "'edit'" in content, "Should support edit mode"
        assert "'preview'" in content, "Should support preview mode"
        assert "toggleMode" in content, "Should have toggleMode function"

    def test_md_editor_has_save_functionality(self):
        """Verify the MD editor has save functionality."""
        js_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "mdEditor.js"
        content = js_path.read_text()

        assert "saveFile" in content, "Should have saveFile function"
        assert "isDirty" in content, "Should track dirty state"
        assert "Ctrl" in content or "ctrlKey" in content, "Should support Ctrl+S shortcut"

    def test_md_editor_handles_file_tree_events(self):
        """Verify the MD editor listens for file tree events."""
        js_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "mdEditor.js"
        content = js_path.read_text()

        assert "fileTreeOpen" in content, "Should listen for fileTreeOpen event"
        assert "addEventListener" in content, "Should use addEventListener"

    def test_md_editor_renders_basic_markdown(self):
        """Verify the MD editor has markdown rendering capability."""
        js_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "mdEditor.js"
        content = js_path.read_text()

        assert "renderMarkdown" in content, "Should have renderMarkdown function"
        assert "renderPreview" in content, "Should have renderPreview function"

    def test_md_editor_has_keyboard_shortcuts(self):
        """Verify the MD editor has keyboard shortcuts."""
        js_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "mdEditor.js"
        content = js_path.read_text()

        # Ctrl+S for save
        assert "'s'" in content or '"s"' in content, "Should handle S key"
        # Escape to close
        assert "Escape" in content, "Should handle Escape key"


class TestMdEditorStyles:
    """Tests for MD Editor CSS styles."""

    def test_md_editor_styles_exist(self):
        """Verify MD editor styles exist in styles.css."""
        css_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "styles.css"
        content = css_path.read_text()

        assert ".md-editor-panel" in content, "Should have .md-editor-panel style"
        assert ".md-editor-textarea" in content, "Should have .md-editor-textarea style"
        assert ".md-preview-container" in content, "Should have .md-preview-container style"

    def test_md_editor_has_hidden_class(self):
        """Verify hidden class is defined for toggling visibility."""
        css_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "styles.css"
        content = css_path.read_text()

        assert ".hidden" in content, "Should have .hidden class"
        assert "display: none" in content, ".hidden should set display: none"
