"""Tests for image export service."""

import re


def test_render_svg_basic_tree() -> None:
    """Test basic SVG export with a simple tree structure."""
    from app.services.image_export import render_svg

    svg_content = render_svg(
        {
            "id": "root",
            "text": "计划",
            "memo": "2026Q2 重点",
            "children": [
                {
                    "id": "a",
                    "text": "研发",
                    "children": [{"id": "a1", "text": "后端"}],
                },
                {"id": "b", "text": "测试", "memo": "重点"},
            ],
        }
    )

    # Verify it's valid SVG
    assert svg_content.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "<svg" in svg_content
    assert "</svg>" in svg_content

    # Check for required elements
    assert "<style>" in svg_content
    assert ".node-rect" in svg_content
    assert ".node-text" in svg_content
    assert ".edge" in svg_content

    # Check for nodes
    assert 'text-anchor="middle"' in svg_content
    assert "计划" in svg_content
    assert "研发" in svg_content
    assert "后端" in svg_content
    assert "测试" in svg_content

    # Check for memo text styling
    assert ".memo" in svg_content
    assert "2026Q2 重点" in svg_content
    assert "重点" in svg_content

    # Check for edges
    assert '<line' in svg_content
    assert 'class="edge"' in svg_content


def test_render_svg_single_node() -> None:
    """Test SVG export with just a root node."""
    from app.services.image_export import render_svg

    svg_content = render_svg({"id": "root", "text": "单节点"})

    assert "<svg" in svg_content
    assert "单节点" in svg_content
    # Should have at least one rect for the root node
    assert '<rect' in svg_content


def test_render_svg_rejects_invalid_node() -> None:
    """Test that invalid node structure raises ValueError."""
    from app.services.image_export import render_svg

    try:
        render_svg({"id": "", "text": "invalid"})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "node id is required" in str(exc)


def test_render_svg_dimensions() -> None:
    """Test that SVG has reasonable dimensions."""
    from app.services.image_export import render_svg

    svg_content = render_svg({"id": "root", "text": "Root"})

    # Extract viewBox or width/height
    viewbox_match = re.search(r'viewBox="(\d+) (\d+) (\d+) (\d+)"', svg_content)
    assert viewbox_match is not None, "SVG should have viewBox attribute"

    width, height = int(viewbox_match.group(3)), int(viewbox_match.group(4))

    # Should have positive dimensions
    assert width > 0, f"SVG width should be positive, got {width}"
    assert height > 0, f"SVG height should be positive, got {height}"


def test_render_svg_many_nodes() -> None:
    """Test SVG export with many nodes (layout stability)."""
    from app.services.image_export import render_svg

    # Create a wider tree
    tree = {
        "id": "root",
        "text": "Root",
        "children": [
            {"id": f"child-{i}", "text": f"Child {i}"} for i in range(10)
        ],
    }

    svg_content = render_svg(tree)

    # All children should be present
    for i in range(10):
        assert f"Child {i}" in svg_content

    # Should have edges connecting parent to all children
    line_count = svg_content.count('<line')
    assert line_count >= 10, f"Expected at least 10 edges, got {line_count}"


def test_render_png_import_error_handling() -> None:
    """Test that PNG export provides helpful error message without cairosvg."""
    # This test verifies the error message format
    # The actual ImportError will be caught by users installing cairosvg
    # We can't easily mock __builtins__ import in pytest
    from app.services.image_export import render_png

    # Test with a valid node - will fail if cairosvg not installed
    try:
        result = render_png({"id": "root", "text": "Test"})
        # If cairosvg is installed, this succeeds - that's fine
        assert isinstance(result, bytes)
        assert len(result) > 0
    except ImportError as exc:
        # Verify helpful error message
        assert "cairosvg" in str(exc).lower()


def test_render_svg_memo_formatting() -> None:
    """Test that memo text is properly formatted (italic, smaller)."""
    from app.services.image_export import render_svg

    svg_content = render_svg(
        {"id": "root", "text": "Root", "memo": "This is a memo"}
    )

    # Check for memo styling in CSS
    assert ".memo" in svg_content
    assert "font-style: italic" in svg_content

    # Check memo content
    assert "This is a memo" in svg_content
