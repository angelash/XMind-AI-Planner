"""
Tests for Node ID Context Constraint (AG-05)

AG-05 should provide:
- Validation that node IDs in modifications exist in the mindmap
- Context constraint: when context_node_id is set, operations must target that node
- Filtering of invalid modifications (not raising errors, just filtering)
"""
import pytest
from app.services.node_id_constraint import (
    validate_modifications,
    filter_valid_modifications,
    is_node_in_mindmap,
    NodeValidationResult,
)


# ============ Test Mindmaps ============

SIMPLE_MINDMAP = {
    "id": "root",
    "text": "Root",
    "children": [
        {
            "id": "node-1",
            "text": "Child 1",
            "children": [
                {"id": "node-1-1", "text": "Grandchild 1-1"},
                {"id": "node-1-2", "text": "Grandchild 1-2"},
            ],
        },
        {
            "id": "node-2",
            "text": "Child 2",
            "children": [],
        },
    ],
}


# ============ is_node_in_mindmap Tests ============

def test_node_exists_in_mindmap():
    """Should find nodes that exist."""
    assert is_node_in_mindmap(SIMPLE_MINDMAP, "root") is True
    assert is_node_in_mindmap(SIMPLE_MINDMAP, "node-1") is True
    assert is_node_in_mindmap(SIMPLE_MINDMAP, "node-1-1") is True
    assert is_node_in_mindmap(SIMPLE_MINDMAP, "node-2") is True


def test_node_not_exists_in_mindmap():
    """Should not find nodes that don't exist."""
    assert is_node_in_mindmap(SIMPLE_MINDMAP, "nonexistent") is False
    assert is_node_in_mindmap(SIMPLE_MINDMAP, "node-999") is False
    assert is_node_in_mindmap(SIMPLE_MINDMAP, "") is False


def test_empty_mindmap():
    """Should handle empty mindmap."""
    empty_mindmap = {"id": "root", "text": "Empty"}
    assert is_node_in_mindmap(empty_mindmap, "root") is True
    assert is_node_in_mindmap(empty_mindmap, "any-other") is False


# ============ validate_modifications Tests ============

def test_validate_valid_modifications():
    """Valid modifications should pass validation."""
    modifications = [
        {"node_id": "node-1", "operation": "update", "new_text": "Updated"},
        {"node_id": "node-1-1", "operation": "delete"},
        {"node_id": "node-2", "operation": "add", "new_text": "New child"},
    ]

    result = validate_modifications(modifications, SIMPLE_MINDMAP)

    assert result.is_valid is True
    assert len(result.valid_modifications) == 3
    assert len(result.invalid_modifications) == 0


def test_validate_modifications_with_nonexistent_nodes():
    """Modifications with nonexistent node IDs should be flagged."""
    modifications = [
        {"node_id": "node-1", "operation": "update", "new_text": "Valid"},
        {"node_id": "nonexistent", "operation": "update", "new_text": "Invalid"},
        {"node_id": "node-2", "operation": "delete"},  # Valid
    ]

    result = validate_modifications(modifications, SIMPLE_MINDMAP)

    assert result.is_valid is False
    assert len(result.valid_modifications) == 2
    assert len(result.invalid_modifications) == 1
    assert result.invalid_modifications[0]["node_id"] == "nonexistent"
    assert "does not exist" in result.invalid_modifications[0]["reason"]


def test_validate_with_context_node_id():
    """When context_node_id is set, modifications should target that node."""
    # All modifications targeting the context node
    modifications = [
        {"node_id": "node-1", "operation": "update", "new_text": "Updated"},
        {"node_id": "node-1", "operation": "add", "new_text": "New child"},  # add uses parent
    ]

    result = validate_modifications(
        modifications,
        SIMPLE_MINDMAP,
        context_node_id="node-1",
    )

    assert result.is_valid is True
    assert len(result.valid_modifications) == 2


def test_validate_with_context_node_id_violation():
    """Modifications not targeting context node should be flagged."""
    modifications = [
        {"node_id": "node-1", "operation": "update", "new_text": "Valid"},
        {"node_id": "node-2", "operation": "update", "new_text": "Invalid - wrong node"},
    ]

    result = validate_modifications(
        modifications,
        SIMPLE_MINDMAP,
        context_node_id="node-1",
    )

    assert result.is_valid is False
    assert len(result.valid_modifications) == 1
    assert len(result.invalid_modifications) == 1
    assert result.invalid_modifications[0]["node_id"] == "node-2"
    assert "context" in result.invalid_modifications[0]["reason"].lower()


def test_validate_add_to_child_of_context_node():
    """Adding to children of context node should be allowed."""
    # Context node is node-1, adding children to it is valid
    modifications = [
        {"node_id": "node-1", "operation": "add", "new_text": "New child"},
    ]

    result = validate_modifications(
        modifications,
        SIMPLE_MINDMAP,
        context_node_id="node-1",
    )

    assert result.is_valid is True


def test_validate_update_children_of_context_node():
    """Updating children of context node should be allowed."""
    # Context node is node-1, updating its children should be allowed
    modifications = [
        {"node_id": "node-1-1", "operation": "update", "new_text": "Updated"},
        {"node_id": "node-1-2", "operation": "delete"},
    ]

    result = validate_modifications(
        modifications,
        SIMPLE_MINDMAP,
        context_node_id="node-1",
    )

    assert result.is_valid is True


def test_validate_no_context_node_allows_any_valid_node():
    """Without context node, any existing node is valid."""
    modifications = [
        {"node_id": "node-1", "operation": "update", "new_text": "Updated"},
        {"node_id": "node-2", "operation": "update", "new_text": "Updated"},
        {"node_id": "node-1-1", "operation": "delete"},
    ]

    result = validate_modifications(
        modifications,
        SIMPLE_MINDMAP,
        context_node_id=None,
    )

    assert result.is_valid is True
    assert len(result.valid_modifications) == 3


def test_validate_empty_modifications():
    """Empty modifications list should be valid."""
    result = validate_modifications([], SIMPLE_MINDMAP)

    assert result.is_valid is True
    assert len(result.valid_modifications) == 0


def test_validate_modification_missing_node_id():
    """Modifications missing node_id should be invalid."""
    modifications = [
        {"operation": "update", "new_text": "No node ID"},
    ]

    result = validate_modifications(modifications, SIMPLE_MINDMAP)

    assert result.is_valid is False
    assert len(result.invalid_modifications) == 1
    assert "missing node_id" in result.invalid_modifications[0]["reason"].lower()


def test_validate_modification_invalid_operation():
    """Modifications with invalid operation should be flagged."""
    modifications = [
        {"node_id": "node-1", "operation": "invalid_op", "new_text": "Test"},
    ]

    result = validate_modifications(modifications, SIMPLE_MINDMAP)

    assert result.is_valid is False
    assert "invalid operation" in result.invalid_modifications[0]["reason"].lower()


# ============ filter_valid_modifications Tests ============

def test_filter_returns_only_valid():
    """Should return only valid modifications."""
    modifications = [
        {"node_id": "node-1", "operation": "update", "new_text": "Valid"},
        {"node_id": "nonexistent", "operation": "update", "new_text": "Invalid"},
        {"node_id": "node-2", "operation": "delete"},  # Valid
    ]

    filtered = filter_valid_modifications(modifications, SIMPLE_MINDMAP)

    assert len(filtered) == 2
    assert filtered[0]["node_id"] == "node-1"
    assert filtered[1]["node_id"] == "node-2"


def test_filter_with_context_constraint():
    """Should filter out modifications violating context constraint."""
    modifications = [
        {"node_id": "node-1", "operation": "update", "new_text": "Valid"},
        {"node_id": "node-2", "operation": "update", "new_text": "Invalid"},
        {"node_id": "node-1-1", "operation": "update", "new_text": "Valid - child"},
    ]

    filtered = filter_valid_modifications(
        modifications,
        SIMPLE_MINDMAP,
        context_node_id="node-1",
    )

    assert len(filtered) == 2
    node_ids = [m["node_id"] for m in filtered]
    assert "node-1" in node_ids
    assert "node-1-1" in node_ids
    assert "node-2" not in node_ids


def test_filter_empty_list():
    """Should handle empty list."""
    filtered = filter_valid_modifications([], SIMPLE_MINDMAP)
    assert filtered == []


# ============ NodeValidationResult Tests ============

def test_validation_result_properties():
    """NodeValidationResult should have correct properties."""
    result = NodeValidationResult(
        valid_modifications=[{"node_id": "node-1", "operation": "update"}],
        invalid_modifications=[{"node_id": "bad", "reason": "not found"}],
    )

    assert result.is_valid is False
    assert result.total_count == 2
    assert result.valid_count == 1
    assert result.invalid_count == 1


def test_validation_result_all_valid():
    """Result with no invalid modifications should be valid."""
    result = NodeValidationResult(
        valid_modifications=[{"node_id": "node-1"}],
        invalid_modifications=[],
    )

    assert result.is_valid is True
    assert result.total_count == 1
