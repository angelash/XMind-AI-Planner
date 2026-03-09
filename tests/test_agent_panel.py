"""
Tests for Agent Panel UI (AG-01)

Agent Panel should provide:
- A side panel on the right side of the editor
- Draggable left edge to resize (300-600px, default 400px)
- Header with "AI 助手" title and new/history buttons
- Message list area (linear message flow)
- Bottom operation bar (pending changes, Undo All/Keep All)
- Input area with context tags above and multi-line input below
"""

from pathlib import Path


def test_agent_panel_html_structure_exists() -> None:
    """Agent panel should be present in index.html with all required elements."""
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    
    # Main panel container
    assert 'id="agent-panel"' in html
    assert 'class="agent-panel"' in html
    
    # Resize handle
    assert 'id="agent-resize-handle"' in html
    
    # Header elements
    assert 'id="agent-header"' in html
    assert 'id="agent-title"' in html
    assert 'id="btn-agent-new"' in html
    assert 'id="btn-agent-history"' in html
    
    # Message list
    assert 'id="agent-messages"' in html
    
    # Bottom operation bar
    assert 'id="agent-operation-bar"' in html
    assert 'id="agent-pending-count"' in html
    assert 'id="btn-agent-undo-all"' in html
    assert 'id="btn-agent-keep-all"' in html
    
    # Input area
    assert 'id="agent-context-tags"' in html
    assert 'id="agent-input"' in html


def test_agent_panel_javascript_module_exists() -> None:
    """Agent panel JavaScript module should exist."""
    root = Path(__file__).resolve().parents[1]
    agent_js = root / "frontend" / "src" / "agent.js"
    assert agent_js.exists()
    
    content = agent_js.read_text(encoding="utf-8")
    
    # Core functions should exist
    assert "initAgentPanel" in content
    assert "togglePanel" in content
    assert "resizePanel" in content
    assert "addMessage" in content
    assert "setContextNode" in content
    assert "updatePendingCount" in content


def test_agent_panel_css_styles_exist() -> None:
    """Agent panel styles should be present."""
    root = Path(__file__).resolve().parents[1]
    css = (root / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")
    
    # Panel positioning and layout
    assert ".agent-panel" in css
    assert ".agent-panel-header" in css
    assert ".agent-messages" in css
    assert ".agent-input-area" in css
    
    # Resize handle
    assert ".agent-resize-handle" in css
    
    # Message types
    assert ".agent-message" in css
    assert ".agent-message-user" in css
    assert ".agent-message-ai" in css
    
    # Context tags
    assert ".agent-context-tag" in css
    
    # Operation bar
    assert ".agent-operation-bar" in css


def test_agent_panel_default_width() -> None:
    """Agent panel should have default width of 400px."""
    root = Path(__file__).resolve().parents[1]
    css = (root / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")
    
    # Should specify default width
    assert "400px" in css or "400" in css


def test_agent_panel_resize_constraints() -> None:
    """Agent panel resize should be constrained to 300-600px."""
    root = Path(__file__).resolve().parents[1]
    agent_js = (root / "frontend" / "src" / "agent.js").read_text(encoding="utf-8")
    
    # Should have min/max constraints
    assert "300" in agent_js
    assert "600" in agent_js


def test_agent_panel_wired_to_index() -> None:
    """index.html should load agent.js module."""
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    
    assert "./src/agent.js" in html


def test_agent_panel_has_fold_toggle() -> None:
    """Agent panel should have a toggle button to fold/unfold."""
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    
    assert 'id="btn-agent-toggle"' in html


def test_agent_input_is_multiline() -> None:
    """Agent input should be a textarea for multiline input."""
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    
    assert "<textarea" in html
    assert 'id="agent-input"' in html
