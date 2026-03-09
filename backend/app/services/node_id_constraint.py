"""Node ID Context Constraint Service (AG-05).

This module provides validation and filtering for AI-generated node modifications,
ensuring:
1. Node IDs in modifications must exist in the mindmap
2. When context_node_id is set, operations must target that node or its children

This prevents AI from making modifications to arbitrary nodes outside the
user's current context.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodeValidationResult:
    """Result of validating modifications."""
    valid_modifications: list[dict[str, Any]] = field(default_factory=list)
    invalid_modifications: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True if all modifications are valid."""
        return len(self.invalid_modifications) == 0

    @property
    def total_count(self) -> int:
        """Total number of modifications validated."""
        return len(self.valid_modifications) + len(self.invalid_modifications)

    @property
    def valid_count(self) -> int:
        """Number of valid modifications."""
        return len(self.valid_modifications)

    @property
    def invalid_count(self) -> int:
        """Number of invalid modifications."""
        return len(self.invalid_modifications)


VALID_OPERATIONS = {"update", "add", "delete"}


def is_node_in_mindmap(root: dict[str, Any], node_id: str) -> bool:
    """Check if a node ID exists in the mindmap.

    Args:
        root: The root node of the mindmap
        node_id: The node ID to search for

    Returns:
        True if the node exists, False otherwise
    """
    if not node_id:
        return False

    if root.get("id") == node_id:
        return True

    for child in root.get("children", []):
        if is_node_in_mindmap(child, node_id):
            return True

    return False


def get_node_children_ids(root: dict[str, Any], node_id: str) -> set[str]:
    """Get all descendant node IDs of a given node.

    Args:
        root: The root node of the mindmap
        node_id: The node ID to get children for

    Returns:
        Set of all descendant node IDs (not including the node itself)
    """
    children_ids: set[str] = set()

    def collect_children(node: dict[str, Any]) -> None:
        for child in node.get("children", []):
            child_id = child.get("id")
            if child_id:
                children_ids.add(child_id)
            collect_children(child)

    # Find the target node first
    target_node = find_node_by_id(root, node_id)
    if target_node:
        collect_children(target_node)

    return children_ids


def find_node_by_id(root: dict[str, Any], node_id: str) -> dict[str, Any] | None:
    """Find a node by its ID in the mindmap.

    Args:
        root: The root node of the mindmap
        node_id: The node ID to find

    Returns:
        The node dict if found, None otherwise
    """
    if root.get("id") == node_id:
        return root

    for child in root.get("children", []):
        result = find_node_by_id(child, node_id)
        if result:
            return result

    return None


def validate_single_modification(
    modification: dict[str, Any],
    mindmap: dict[str, Any],
    context_node_id: str | None = None,
) -> tuple[bool, str]:
    """Validate a single modification.

    Args:
        modification: The modification dict with node_id, operation, etc.
        mindmap: The current mindmap structure
        context_node_id: Optional context node ID for constraint

    Returns:
        Tuple of (is_valid, reason) where reason explains why if invalid
    """
    node_id = modification.get("node_id")
    operation = modification.get("operation")

    # Check required fields
    if not node_id:
        return False, "Missing node_id in modification"

    if not operation:
        return False, "Missing operation in modification"

    # Check valid operation
    if operation not in VALID_OPERATIONS:
        return False, f"Invalid operation '{operation}'. Must be one of: {VALID_OPERATIONS}"

    # Check node exists in mindmap (except for 'add' where node_id is parent)
    if not is_node_in_mindmap(mindmap, node_id):
        return False, f"Node '{node_id}' does not exist in mindmap"

    # Context constraint: if context_node_id is set, modifications must target
    # that node or its descendants
    if context_node_id:
        # The context node itself is always valid
        if node_id == context_node_id:
            return True, ""

        # Children/descendants of context node are valid
        children_ids = get_node_children_ids(mindmap, context_node_id)
        if node_id in children_ids:
            return True, ""

        # Node is not context node or its descendant - violation
        return False, (
            f"Node '{node_id}' is not the context node '{context_node_id}' "
            f"or its descendant. Modifications must target the context node."
        )

    return True, ""


def validate_modifications(
    modifications: list[dict[str, Any]],
    mindmap: dict[str, Any],
    context_node_id: str | None = None,
) -> NodeValidationResult:
    """Validate a list of modifications.

    Args:
        modifications: List of modification dicts
        mindmap: The current mindmap structure
        context_node_id: Optional context node ID for constraint

    Returns:
        NodeValidationResult with valid and invalid modifications separated
    """
    valid: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []

    for mod in modifications:
        is_valid, reason = validate_single_modification(
            mod, mindmap, context_node_id
        )

        if is_valid:
            valid.append(mod)
        else:
            invalid.append({
                **mod,
                "reason": reason,
            })

    return NodeValidationResult(
        valid_modifications=valid,
        invalid_modifications=invalid,
    )


def filter_valid_modifications(
    modifications: list[dict[str, Any]],
    mindmap: dict[str, Any],
    context_node_id: str | None = None,
) -> list[dict[str, Any]]:
    """Filter modifications to only include valid ones.

    This is a convenience function that returns only the valid modifications,
    silently dropping invalid ones.

    Args:
        modifications: List of modification dicts
        mindmap: The current mindmap structure
        context_node_id: Optional context node ID for constraint

    Returns:
        List of only valid modifications
    """
    result = validate_modifications(modifications, mindmap, context_node_id)
    return result.valid_modifications
