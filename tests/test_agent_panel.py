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


def test_agent_panel_diff_card_styles() -> None:
    """Agent panel should have Diff card styles for AI suggestions."""
    root = Path(__file__).resolve().parents[1]
    css = (root / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")
    
    # Diff card structure
    assert ".agent-diff-card" in css
    assert ".agent-diff-header" in css
    assert ".agent-diff-content" in css
    
    # Diff line styles
    assert ".agent-diff-line-deleted" in css
    assert ".agent-diff-line-added" in css


def test_agent_panel_step_indicator_styles() -> None:
    """Agent panel should have step indicator styles for streaming progress."""
    root = Path(__file__).resolve().parents[1]
    css = (root / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")
    
    # Step indicator
    assert ".agent-step-indicator" in css
    
    # Spinner animation
    assert "@keyframes spin" in css or "spinner" in css


def test_agent_panel_streaming_cursor() -> None:
    """Agent panel should have streaming cursor animation."""
    root = Path(__file__).resolve().parents[1]
    css = (root / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")
    
    # Streaming cursor
    assert ".agent-streaming-cursor" in css
    
    # Blink animation
    assert "@keyframes blink" in css


def test_agent_panel_integrates_with_mindelixir_selection() -> None:
    """Agent panel should be integrated with MindElixir node selection."""
    root = Path(__file__).resolve().parents[1]
    main_js = (root / "frontend" / "src" / "main.js").read_text(encoding="utf-8")
    
    # Should import agent panel functions
    assert "setContextNode" in main_js
    assert "clearContextNode" in main_js


def test_agent_panel_operation_bar_initially_hidden() -> None:
    """Agent operation bar should be initially hidden when no pending changes."""
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    
    # Operation bar should have hidden class initially
    assert 'class="agent-operation-bar hidden"' in html


def test_agent_panel_has_diff_card_function() -> None:
    """Agent panel should have addDiffCard function."""
    root = Path(__file__).resolve().parents[1]
    agent_js = (root / "frontend" / "src" / "agent.js").read_text(encoding="utf-8")
    
    assert "addDiffCard" in agent_js
    assert "handleDiffAction" in agent_js


def test_agent_panel_has_step_indicator_function() -> None:
    """Agent panel should have addStepIndicator function for streaming."""
    root = Path(__file__).resolve().parents[1]
    agent_js = (root / "frontend" / "src" / "agent.js").read_text(encoding="utf-8")
    
    assert "addStepIndicator" in agent_js


def test_agent_panel_has_streaming_cursor_function() -> None:
    """Agent panel should have addStreamingCursor function."""
    root = Path(__file__).resolve().parents[1]
    agent_js = (root / "frontend" / "src" / "agent.js").read_text(encoding="utf-8")
    
    assert "addStreamingCursor" in agent_js


def test_agent_panel_persists_state() -> None:
    """Agent panel should persist state to localStorage."""
    root = Path(__file__).resolve().parents[1]
    agent_js = (root / "frontend" / "src" / "agent.js").read_text(encoding="utf-8")
    
    assert "localStorage" in agent_js
    assert "savePersistedState" in agent_js
    assert "loadPersistedState" in agent_js
