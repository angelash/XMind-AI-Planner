from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.node_model import MindNode

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_LIST_RE = re.compile(r"^([ \t]*)(?:[-*+]\s+|\d+[.)]\s+)(.*\S)\s*$")


@dataclass
class _IdGen:
    counter: int = 0

    def next(self) -> str:
        self.counter += 1
        return f"imp-{self.counter}"


def import_markdown(markdown: str, title: str | None = None) -> dict[str, object]:
    lines = markdown.splitlines()
    id_gen = _IdGen()

    root_text = (title or "").strip() or "Imported Mindmap"
    root = MindNode(id=id_gen.next(), text=root_text)

    heading_stack: dict[int, MindNode] = {0: root}
    list_stack: dict[int, MindNode] = {}

    first_h1_applied = bool(title and title.strip())

    for raw_line in lines:
        line = raw_line.rstrip()
        if not line.strip():
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            text = heading_match.group(2).strip()

            if level == 1 and not first_h1_applied and not root.children:
                root.text = text
                heading_stack = {0: root, 1: root}
                list_stack.clear()
                first_h1_applied = True
                continue

            parent = _nearest_parent(heading_stack, level - 1, fallback=root)
            node = MindNode(id=id_gen.next(), text=text)
            parent.children.append(node)

            heading_stack = {k: v for k, v in heading_stack.items() if k < level}
            heading_stack[level] = node
            list_stack.clear()
            continue

        list_match = _LIST_RE.match(line)
        if list_match:
            indent = _indent_depth(list_match.group(1))
            text = list_match.group(2).strip()

            section_parent = _nearest_parent(heading_stack, max(heading_stack), fallback=root)
            if indent == 0:
                parent = section_parent
            else:
                parent = list_stack.get(indent - 1, section_parent)

            node = MindNode(id=id_gen.next(), text=text)
            parent.children.append(node)

            list_stack = {k: v for k, v in list_stack.items() if k < indent}
            list_stack[indent] = node
            continue

        parent = _nearest_parent(heading_stack, max(heading_stack), fallback=root)
        parent.children.append(MindNode(id=id_gen.next(), text=line.strip()))
        list_stack.clear()

    if not root.children and not root.text.strip():
        raise ValueError("markdown content is empty")
    if not root.children and root.text == "Imported Mindmap":
        raise ValueError("markdown content is empty")

    return root.to_dict()


def _nearest_parent(stack: dict[int, MindNode], preferred_level: int, fallback: MindNode) -> MindNode:
    for level in range(preferred_level, -1, -1):
        node = stack.get(level)
        if node is not None:
            return node
    return fallback


def _indent_depth(prefix: str) -> int:
    spaces = 0
    for char in prefix:
        if char == "\t":
            spaces += 4
        else:
            spaces += 1
    return spaces // 2
