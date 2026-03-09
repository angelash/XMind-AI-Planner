"""Modification applier service for AG-03.

AG-03: Diff + Keep/Undo

Handles applying and reverting node modifications to document content.
"""
from __future__ import annotations

import copy
from typing import Any

from app.services.conversation_store import (
    get_conversation_by_id,
    get_modification,
    list_modifications,
    update_modification_status,
)
from app.services.document_store import get_document, update_document


# ============ Node Finding Utilities ============

def find_node_in_content(
    content: dict[str, Any],
    node_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Find a node by ID in the mind map content.

    Returns:
        Tuple of (node, parent). Both can be None if not found.
        Root node has parent=None.
    """
    if content.get("id") == node_id:
        return content, None

    def find_recursive(node: dict[str, Any], parent: dict[str, Any] | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        if node.get("id") == node_id:
            return node, parent

        for child in node.get("children", []):
            found, found_parent = find_recursive(child, node)
            if found:
                return found, found_parent

        return None, None

    return find_recursive(content, None)


def _add_child_to_node(parent: dict[str, Any], child: dict[str, Any]) -> None:
    """Add a child node to a parent node."""
    if "children" not in parent:
        parent["children"] = []
    parent["children"].append(child)


def _remove_child_from_node(parent: dict[str, Any], child_id: str) -> bool:
    """Remove a child node from a parent node.

    Returns True if child was found and removed.
    """
    children = parent.get("children", [])
    for i, child in enumerate(children):
        if child.get("id") == child_id:
            children.pop(i)
            return True
    return False


# ============ Apply Modification ============

def apply_modification(modification_id: int) -> dict[str, Any]:
    """Apply a single modification to the document.

    Updates the document content and marks the modification as accepted.

    Returns:
        Dict with 'applied' (bool) and optional 'reason' (str).
    """
    modification = get_modification(modification_id)
    if modification is None:
        return {"applied": False, "reason": "modification not found"}

    # Check status
    if modification["status"] != "pending":
        return {"applied": False, "reason": f"modification already {modification['status']}"}

    # Get conversation and document
    conversation = get_conversation_by_id(modification["conversation_id"])
    if conversation is None:
        return {"applied": False, "reason": "conversation not found"}

    document = get_document(conversation["document_id"])
    if document is None:
        return {"applied": False, "reason": "document not found"}

    # Deep copy content to avoid mutation issues
    content = copy.deepcopy(document["content"])

    mod_type = modification["modification_type"]
    node_id = modification["node_id"]
    after_value = modification["after_value"]

    success = False

    if mod_type == "update":
        success = _apply_update(content, node_id, after_value)
    elif mod_type == "create":
        success = _apply_create(content, node_id, after_value)
    elif mod_type == "delete":
        success = _apply_delete(content, node_id)
    else:
        return {"applied": False, "reason": f"unknown modification type: {mod_type}"}

    if not success:
        return {"applied": False, "reason": f"failed to apply {mod_type} to node {node_id}"}

    # Update document content
    update_document(document["id"], {"content": content}, changed_by=f"modification-{modification_id}")

    # Update modification status
    update_modification_status(modification_id, "accepted")

    return {
        "applied": True,
        "node_id": node_id,
        "modification_type": mod_type,
    }


def _apply_update(content: dict[str, Any], node_id: str, after_value: dict[str, Any] | None) -> bool:
    """Apply an update modification."""
    if after_value is None:
        return False

    node, _ = find_node_in_content(content, node_id)
    if node is None:
        return False

    # Update node properties
    for key, value in after_value.items():
        if key not in ("id", "children"):  # Don't overwrite id or children
            node[key] = value

    return True


def _apply_create(content: dict[str, Any], node_id: str, after_value: dict[str, Any] | None) -> bool:
    """Apply a create modification."""
    if after_value is None:
        return False

    parent_id = after_value.get("parent_id")
    if not parent_id:
        return False

    parent, _ = find_node_in_content(content, parent_id)
    if parent is None:
        return False

    # Create new node (without parent_id in the node itself)
    new_node = {"id": node_id}
    for key, value in after_value.items():
        if key != "parent_id":
            new_node[key] = value

    _add_child_to_node(parent, new_node)
    return True


def _apply_delete(content: dict[str, Any], node_id: str) -> bool:
    """Apply a delete modification."""
    node, parent = find_node_in_content(content, node_id)
    if node is None:
        return False

    if parent is None:
        # Cannot delete root node
        return False

    return _remove_child_from_node(parent, node_id)


# ============ Revert Modification ============

def revert_modification(modification_id: int) -> dict[str, Any]:
    """Revert an applied modification.

    Restores the original state and marks the modification as rejected.

    Returns:
        Dict with 'reverted' (bool) and optional 'reason' (str).
    """
    modification = get_modification(modification_id)
    if modification is None:
        return {"reverted": False, "reason": "modification not found"}

    # Check status - can only revert accepted modifications
    if modification["status"] == "pending":
        return {"reverted": False, "reason": "modification not applied yet"}
    if modification["status"] == "rejected":
        return {"reverted": False, "reason": "modification already rejected"}

    # Get conversation and document
    conversation = get_conversation_by_id(modification["conversation_id"])
    if conversation is None:
        return {"reverted": False, "reason": "conversation not found"}

    document = get_document(conversation["document_id"])
    if document is None:
        return {"reverted": False, "reason": "document not found"}

    # Deep copy content to avoid mutation issues
    content = copy.deepcopy(document["content"])

    mod_type = modification["modification_type"]
    node_id = modification["node_id"]
    before_value = modification["before_value"]

    success = False

    if mod_type == "update":
        success = _revert_update(content, node_id, before_value)
    elif mod_type == "create":
        success = _revert_create(content, node_id)
    elif mod_type == "delete":
        success = _revert_delete(content, node_id, before_value)
    else:
        return {"reverted": False, "reason": f"unknown modification type: {mod_type}"}

    if not success:
        return {"reverted": False, "reason": f"failed to revert {mod_type} for node {node_id}"}

    # Update document content
    update_document(document["id"], {"content": content}, changed_by=f"revert-{modification_id}")

    # Update modification status
    update_modification_status(modification_id, "rejected")

    return {
        "reverted": True,
        "node_id": node_id,
        "modification_type": mod_type,
    }


def _revert_update(content: dict[str, Any], node_id: str, before_value: dict[str, Any] | None) -> bool:
    """Revert an update modification by restoring before_value."""
    if before_value is None:
        return False

    node, _ = find_node_in_content(content, node_id)
    if node is None:
        return False

    # Restore original properties
    for key, value in before_value.items():
        if key not in ("id", "children"):
            node[key] = value

    return True


def _revert_create(content: dict[str, Any], node_id: str) -> bool:
    """Revert a create modification by deleting the created node."""
    node, parent = find_node_in_content(content, node_id)
    if node is None:
        return True  # Already deleted

    if parent is None:
        return False  # Cannot delete root

    return _remove_child_from_node(parent, node_id)


def _revert_delete(content: dict[str, Any], node_id: str, before_value: dict[str, Any] | None) -> bool:
    """Revert a delete modification by recreating the deleted node."""
    if before_value is None:
        return False

    # Check if node already exists (shouldn't)
    node, _ = find_node_in_content(content, node_id)
    if node is not None:
        return True  # Already exists

    # Find parent from before_value or use original parent detection
    # For delete, we need to find where the node was
    # We'll look for a parent_id in before_value or try to find a sibling
    parent_id = before_value.get("parent_id")

    if parent_id:
        parent, _ = find_node_in_content(content, parent_id)
    else:
        # If no parent_id stored, we can't reliably restore position
        # This is a limitation - we could search for parent in before_value
        return False

    if parent is None:
        return False

    # Recreate the node
    new_node = {"id": node_id}
    for key, value in before_value.items():
        if key != "parent_id":
            new_node[key] = value

    _add_child_to_node(parent, new_node)
    return True


# ============ Batch Operations ============

def batch_apply_modifications(
    conversation_id: int,
    message_id: int | None = None,
) -> dict[str, Any]:
    """Apply all pending modifications for a conversation or message.

    Returns:
        Dict with 'applied_count' and 'failed_count'.
    """
    modifications = list_modifications(conversation_id, status="pending")

    applied_count = 0
    failed_count = 0

    for mod in modifications:
        # Filter by message_id if specified
        if message_id is not None and mod["message_id"] != message_id:
            continue

        result = apply_modification(mod["id"])
        if result["applied"]:
            applied_count += 1
        else:
            failed_count += 1

    return {
        "applied_count": applied_count,
        "failed_count": failed_count,
    }


def batch_revert_modifications(
    conversation_id: int,
    message_id: int | None = None,
) -> dict[str, Any]:
    """Revert all accepted modifications for a conversation or message.

    Returns:
        Dict with 'reverted_count' and 'failed_count'.
    """
    modifications = list_modifications(conversation_id, status="accepted")

    reverted_count = 0
    failed_count = 0

    for mod in modifications:
        # Filter by message_id if specified
        if message_id is not None and mod["message_id"] != message_id:
            continue

        result = revert_modification(mod["id"])
        if result["reverted"]:
            reverted_count += 1
        else:
            failed_count += 1

    return {
        "reverted_count": reverted_count,
        "failed_count": failed_count,
    }


# ============ Diff Preview ============

def get_modification_diff(modification_id: int) -> dict[str, Any] | None:
    """Get a diff preview of a modification.

    Returns:
        Dict with modification details for preview, or None if not found.
    """
    modification = get_modification(modification_id)
    if modification is None:
        return None

    return {
        "modification_id": modification["id"],
        "node_id": modification["node_id"],
        "type": modification["modification_type"],
        "before": modification["before_value"],
        "after": modification["after_value"],
        "status": modification["status"],
    }
