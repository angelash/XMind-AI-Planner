"""Image export service - converts MindNode to PNG and SVG formats."""

from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from app.core.node_model import MindNode


def render_svg(root_payload: dict[str, object]) -> str:
    """Render a mind map to SVG format.

    Returns SVG as a string.
    """
    root = MindNode.from_dict(root_payload)

    # Calculate dimensions
    width, height, node_positions = _calculate_layout(root)

    # Build SVG
    svg_header = f'<?xml version="1.0" encoding="UTF-8"?>\n'
    svg_header += f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
    svg_header += '  <style>\n'
    svg_header += '    .node-rect { fill: #ffffff; stroke: #333333; stroke-width: 2px; }\n'
    svg_header += '    .node-text { font-family: Arial, sans-serif; font-size: 14px; fill: #333333; }\n'
    svg_header += '    .edge { stroke: #666666; stroke-width: 1.5px; }\n'
    svg_header += '    .memo { font-family: Arial, sans-serif; font-size: 10px; fill: #666666; font-style: italic; }\n'
    svg_header += '  </style>\n'

    # Draw edges first (so they appear behind nodes)
    edges_svg = _render_edges(root, node_positions)

    # Draw nodes
    nodes_svg = _render_nodes(root, node_positions)

    svg_footer = '</svg>'

    return svg_header + edges_svg + nodes_svg + svg_footer


def render_png(root_payload: dict[str, object]) -> bytes:
    """Render a mind map to PNG format.

    Returns PNG as bytes.
    """
    try:
        import cairosvg
    except ImportError as exc:
        raise ImportError(
            "cairosvg is required for PNG export. Install with: pip install cairosvg"
        ) from exc

    svg_content = render_svg(root_payload)
    png_bytes = cairosvg.svg2png(bytestring=svg_content.encode("utf-8"))
    return png_bytes


def _calculate_layout(
    root: MindNode,
) -> tuple[int, int, dict[str, dict[str, float]]]:
    """Calculate node positions for a tree layout.

    Returns (width, height, positions_dict)
    """
    # Simple tree layout: root at top, children below
    NODE_WIDTH = 120
    NODE_HEIGHT = 40
    H_SPACING = 30
    V_SPACING = 60
    MEMO_HEIGHT = 15

    positions: dict[str, dict[str, float]] = {}
    levels: dict[int, list[MindNode]] = {}

    # Group nodes by level
    def collect_levels(node: MindNode, level: int) -> None:
        if level not in levels:
            levels[level] = []
        levels[level].append(node)
        for child in node.children:
            collect_levels(child, level + 1)

    collect_levels(root, 0)

    # Calculate width needed for each level
    max_level_width = 0
    level_y: dict[int, float] = {}

    current_y = 20
    for level in sorted(levels.keys()):
        nodes = levels[level]
        level_width = len(nodes) * (NODE_WIDTH + H_SPACING) - H_SPACING
        max_level_width = max(max_level_width, level_width)

        # Calculate Y position for this level
        level_y[level] = current_y

        # Calculate X positions for nodes in this level
        start_x = (max_level_width - level_width) // 2
        for i, node in enumerate(nodes):
            node_height = NODE_HEIGHT
            if node.memo:
                node_height += MEMO_HEIGHT

            positions[node.id] = {
                "x": start_x + i * (NODE_WIDTH + H_SPACING),
                "y": current_y,
                "width": NODE_WIDTH,
                "height": node_height,
                "text_y": current_y + 20,
                "memo_y": current_y + 35,
            }

        # Move to next level
        level_max_height = max(
            positions[n.id]["height"] for n in nodes if n.id in positions
        )
        current_y += level_max_height + V_SPACING

    total_height = current_y - V_SPACING + 20
    total_width = max_level_width + 40

    return total_width, total_height, positions


def _render_edges(
    root: MindNode, positions: dict[str, dict[str, float]]
) -> str:
    """Render edges (lines connecting parent to children)."""
    edges = []

    def render_node_edges(node: MindNode) -> None:
        if node.id not in positions:
            return

        parent_pos = positions[node.id]
        parent_bottom_x = parent_pos["x"] + parent_pos["width"] / 2
        parent_bottom_y = parent_pos["y"] + parent_pos["height"]

        for child in node.children:
            if child.id not in positions:
                continue

            child_pos = positions[child.id]
            child_top_x = child_pos["x"] + child_pos["width"] / 2
            child_top_y = child_pos["y"]

            # Draw line from parent bottom to child top
            edges.append(
                f'    <line x1="{parent_bottom_x}" y1="{parent_bottom_y}" '
                f'x2="{child_top_x}" y2="{child_top_y}" class="edge"/>'
            )

            # Recursively render child edges
            render_node_edges(child)

    render_node_edges(root)
    return "\n".join(edges) + "\n"


def _render_nodes(
    root: MindNode, positions: dict[str, dict[str, float]]
) -> str:
    """Render node rectangles and text."""
    nodes = []

    def render_node(node: MindNode) -> None:
        if node.id not in positions:
            return

        pos = positions[node.id]

        # Node rectangle
        nodes.append(
            f'    <rect x="{pos["x"]}" y="{pos["y"]}" '
            f'width="{pos["width"]}" height="{pos["height"]}" '
            f'class="node-rect" rx="5" ry="5"/>'
        )

        # Node text (centered, with wrapping)
        nodes.append(
            f'    <text x="{pos["x"] + pos["width"]/2}" y="{pos["text_y"]}" '
            f'text-anchor="middle" class="node-text">'
            f'{escape(node.text)}</text>'
        )

        # Memo text if present
        if node.memo:
            nodes.append(
                f'    <text x="{pos["x"] + pos["width"]/2}" y="{pos["memo_y"]}" '
                f'text-anchor="middle" class="memo">'
                f'{escape(node.memo)}</text>'
            )

        # Recursively render children
        for child in node.children:
            render_node(child)

    render_node(root)
    return "\n".join(nodes) + "\n"
