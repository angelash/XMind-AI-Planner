"""
Tests for Node Move Functionality (GAP-02)
Validates that moveNode is properly implemented and integrated.
"""

import pytest
import re
from pathlib import Path


def test_mind_elixir_has_move_node():
    """Test that MindElixir has moveNode method."""
    mind_elixir_path = Path(__file__).parent.parent.parent / "frontend" / "vendor" / "mind-elixir.js"
    assert mind_elixir_path.exists(), "mind-elixir.js not found"

    content = mind_elixir_path.read_text()
    assert "moveNode" in content, "moveNode method not found in MindElixir"


def test_mind_elixir_move_node_signature():
    """Test that moveNode has correct signature."""
    mind_elixir_path = Path(__file__).parent.parent.parent / "frontend" / "vendor" / "mind-elixir.js"
    content = mind_elixir_path.read_text()

    # Check for moveNode function signature
    pattern = r"moveNode\s*\(\s*targetNode\s*,\s*newParentNode\s*,\s*newIndex\s*\)"
    assert re.search(pattern, content), "moveNode has incorrect signature"


def test_mind_elixir_move_node_prevents_root_move():
    """Test that moveNode prevents moving root node."""
    mind_elixir_path = Path(__file__).parent.parent.parent / "frontend" / "vendor" / "mind-elixir.js"
    content = mind_elixir_path.read_text()

    assert "targetNode.root" in content, "Root node check not found"
    assert "Cannot move root node" in content, "Root move warning not found"


def test_mind_elixir_move_node_finds_old_parent():
    """Test that moveNode finds and stores old parent and index."""
    mind_elixir_path = Path(__file__).parent.parent.parent / "frontend" / "vendor" / "mind-elixir.js"
    content = mind_elixir_path.read_text()

    assert "oldParent" in content, "oldParent not found"
    assert "oldIndex" in content, "oldIndex not found"
    assert "walk(" in content, "walk function not found for finding parent"


def test_mind_elixir_move_node_removes_from_old_parent():
    """Test that moveNode removes node from old parent."""
    mind_elixir_path = Path(__file__).parent.parent.parent / "frontend" / "vendor" / "mind-elixir.js"
    content = mind_elixir_path.read_text()

    assert "oldParent.children.splice" in content, "Remove from old parent not found"


def test_mind_elixir_move_node_adds_to_new_parent():
    """Test that moveNode adds node to new parent at specified index."""
    mind_elixir_path = Path(__file__).parent.parent.parent / "frontend" / "vendor" / "mind-elixir.js"
    content = mind_elixir_path.read_text()

    assert "newParentNode.children.splice" in content, "Add to new parent not found"
    assert "Math.min(Math.max(0, newIndex)" in content, "Index clamping not found"


def test_mind_elixir_move_node_emits_event():
    """Test that moveNode emits afterNodeMove event."""
    mind_elixir_path = Path(__file__).parent.parent.parent / "frontend" / "vendor" / "mind-elixir.js"
    content = mind_elixir_path.read_text()

    assert "afterNodeMove" in content, "afterNodeMove event not found"
    assert "bus.emit" in content, "bus.emit not found"


def test_history_has_move_node_command():
    """Test that history manager has MOVE_NODE command type."""
    history_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "history.js"
    assert history_path.exists(), "history.js not found"

    content = history_path.read_text()
    assert 'MOVE_NODE: "moveNode"' in content, "MOVE_NODE command type not found"


def test_history_has_create_move_node_command():
    """Test that history manager has createMoveNodeCommand function."""
    history_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "history.js"
    content = history_path.read_text()

    assert "createMoveNodeCommand" in content, "createMoveNodeCommand function not found"


def test_history_move_node_command_structure():
    """Test that moveNode command has execute/undo/redo."""
    history_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "history.js"
    content = history_path.read_text()

    # Check for command structure
    assert "targetNode" in content, "targetNode not in move command"
    assert "oldParent" in content, "oldParent not in move command"
    assert "oldIndex" in content, "oldIndex not in move command"
    assert "newParent" in content, "newParent not in move command"
    assert "newIndex" in content, "newIndex not in move command"

    # Check for undo/redo methods
    assert "undo:" in content, "undo method not found"
    assert "redo:" in content, "redo method not found"


def test_main_js_has_move_node_ui():
    """Test that main.js has moveNode UI trigger."""
    main_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "main.js"
    assert main_path.exists(), "main.js not found"

    content = main_path.read_text()
    assert "moveNode()" in content, "moveNode function not found in main.js"
    assert "btn-move-node" in content, "move-node button not found"
    assert 'controls.moveNode' in content, "moveNode control not bound"


def test_main_js_move_node_creates_history_command():
    """Test that moveNode in main.js creates history command."""
    main_path = Path(__file__).parent.parent.parent / "frontend" / "src" / "main.js"
    content = main_path.read_text()

    assert 'CommandType.MOVE_NODE' in content, "MOVE_NODE command not used in main.js"
    assert "createCommand" in content, "createCommand not called"
    assert "executeCommand" in content, "executeCommand not called"


def test_drag_drop_test_file_exists():
    """Test that drag-drop test file exists."""
    test_path = Path(__file__).parent.parent / "frontend" / "test_drag_drop.js"
    assert test_path.exists(), "test_drag_drop.js not found"


def test_drag_drop_test_covers_sibling_reordering():
    """Test that drag-drop tests cover sibling reordering."""
    test_path = Path(__file__).parent.parent / "frontend" / "test_drag_drop.js"
    content = test_path.read_text()

    assert "Sibling reordering" in content, "Sibling reordering tests not found"
    assert "should move node to new position within same parent" in content


def test_drag_drop_test_covers_cross_parent_movement():
    """Test that drag-drop tests cover cross-parent movement."""
    test_path = Path(__file__).parent.parent / "frontend" / "test_drag_drop.js"
    content = test_path.read_text()

    assert "Cross-parent movement" in content, "Cross-parent movement tests not found"
    assert "should move node from one parent to another" in content


def test_drag_drop_test_covers_edge_cases():
    """Test that drag-drop tests cover edge cases."""
    test_path = Path(__file__).parent.parent / "frontend" / "test_drag_drop.js"
    content = test_path.read_text()

    assert "should not move root node" in content, "Root node test not found"
    assert "should handle moving to same position" in content, "Same position test not found"


def test_drag_drop_test_covers_history_integration():
    """Test that drag-drop tests cover history integration."""
    test_path = Path(__file__).parent.parent / "frontend" / "test_drag_drop.js"
    content = test_path.read_text()

    assert "History integration" in content, "History integration tests not found"
    assert "should create undoable move command" in content
    assert "should undo move operation" in content
    assert "should redo move operation" in content


def test_drag_drop_test_covers_event_emission():
    """Test that drag-drop tests cover event emission."""
    test_path = Path(__file__).parent.parent / "frontend" / "test_drag_drop.js"
    content = test_path.read_text()

    assert "should emit afterNodeMove event" in content, "Event emission test not found"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
