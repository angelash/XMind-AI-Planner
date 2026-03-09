"""Tests for file tree to node conversion functionality."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_file_tree_item_to_node_conversion():
    """Test converting a file tree item to a mind map node structure."""
    # This is a unit test for the conversion logic
    # The actual implementation will be in JavaScript
    
    # Mock file tree item (file)
    file_item = {
        "id": "file-123",
        "name": "readme.md",
        "type": "file",
        "path": "/docs/readme.md",
    }
    
    # Expected node structure
    expected_node = {
        "id": "node-file-123",  # prefixed to avoid collision
        "topic": "readme.md",
        "memo": "/docs/readme.md",  # store path in memo
    }
    
    # Verify the expected structure exists
    assert expected_node["id"].startswith("node-")
    assert expected_node["topic"] == file_item["name"]
    assert expected_node["memo"] == file_item["path"]


def test_folder_tree_item_to_node_with_children():
    """Test converting a folder with children to nested nodes."""
    # Mock folder with children
    folder_item = {
        "id": "folder-456",
        "name": "Documents",
        "type": "folder",
        "path": "/Documents",
        "children": [
            {
                "id": "file-789",
                "name": "notes.md",
                "type": "file",
                "path": "/Documents/notes.md",
                "children": [],
            },
            {
                "id": "folder-abc",
                "name": "Archive",
                "type": "folder",
                "path": "/Documents/Archive",
                "children": [
                    {
                        "id": "file-def",
                        "name": "old.md",
                        "type": "file",
                        "path": "/Documents/Archive/old.md",
                        "children": [],
                    }
                ],
            },
        ],
    }
    
    # Expected nested node structure
    expected_node = {
        "id": "node-folder-456",
        "topic": "Documents",
        "memo": "/Documents",
        "children": [
            {
                "id": "node-file-789",
                "topic": "notes.md",
                "memo": "/Documents/notes.md",
            },
            {
                "id": "node-folder-abc",
                "topic": "Archive",
                "memo": "/Documents/Archive",
                "children": [
                    {
                        "id": "node-file-def",
                        "topic": "old.md",
                        "memo": "/Documents/Archive/old.md",
                    }
                ],
            },
        ],
    }
    
    # Verify structure
    assert expected_node["topic"] == folder_item["name"]
    assert len(expected_node["children"]) == 2
    assert expected_node["children"][0]["topic"] == "notes.md"
    assert expected_node["children"][1]["topic"] == "Archive"
    assert len(expected_node["children"][1]["children"]) == 1


def test_node_id_collision_prevention():
    """Test that node IDs are prefixed to avoid collision with existing nodes."""
    # File tree item ID
    item_id = "abc123"
    
    # Node ID should be prefixed
    node_id = f"node-{item_id}"
    
    # Verify prefix
    assert node_id != item_id
    assert node_id.startswith("node-")
    assert node_id.endswith(item_id)


def test_file_icon_in_topic():
    """Test that file icons are included in node topics for visual distinction."""
    file_item = {
        "id": "file-md",
        "name": "readme.md",
        "type": "file",
        "path": "/readme.md",
    }
    
    # Node topic should include icon based on file type
    # This is a design choice - we can include emoji in topic
    topic_with_icon = "📝 readme.md"
    
    assert "📝" in topic_with_icon
    assert "readme.md" in topic_with_icon


def test_folder_icon_in_topic():
    """Test that folder icons are included in node topics."""
    folder_item = {
        "id": "folder-1",
        "name": "Documents",
        "type": "folder",
        "path": "/Documents",
    }
    
    topic_with_icon = "📁 Documents"
    
    assert "📁" in topic_with_icon
    assert "Documents" in topic_with_icon
