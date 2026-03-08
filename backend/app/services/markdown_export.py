from __future__ import annotations

from app.core.node_model import MindNode


def render_markdown(root_payload: dict[str, object]) -> str:
    root = MindNode.from_dict(root_payload)
    lines: list[str] = []
    _render_node(root, depth=0, lines=lines)
    return "\n".join(lines).strip() + "\n"


def _render_node(node: MindNode, *, depth: int, lines: list[str]) -> None:
    if depth == 0:
        lines.append(f"# {node.text}")
        if node.memo:
            lines.append(f"> {node.memo}")
    else:
        indent = "  " * (depth - 1)
        lines.append(f"{indent}- {node.text}")
        if node.memo:
            lines.append(f"{indent}  > {node.memo}")

    for child in node.children:
        _render_node(child, depth=depth + 1, lines=lines)
