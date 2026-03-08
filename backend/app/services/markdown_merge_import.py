from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from app.core.node_model import MindNode
from app.services.markdown_import import import_markdown


@dataclass
class MergeStats:
    added_nodes: int = 0
    merged_nodes: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "added_nodes": self.added_nodes,
            "merged_nodes": self.merged_nodes,
        }


class _IdGen:
    def __init__(self, root: dict[str, Any]) -> None:
        self._used_ids: set[str] = set()
        self._counter = 0
        self._collect_ids(root)

    def _collect_ids(self, node: dict[str, Any]) -> None:
        node_id = node.get("id")
        if isinstance(node_id, str) and node_id:
            self._used_ids.add(node_id)
        for child in node.get("children") or []:
            if isinstance(child, dict):
                self._collect_ids(child)

    def next(self) -> str:
        while True:
            self._counter += 1
            node_id = f"impm-{self._counter}"
            if node_id not in self._used_ids:
                self._used_ids.add(node_id)
                return node_id


def merge_markdown_into_document(
    existing_root: dict[str, Any],
    markdown: str,
    title: str | None = None,
) -> tuple[dict[str, Any], MergeStats]:
    existing = MindNode.from_dict(existing_root).to_dict()
    imported = import_markdown(markdown, title)

    stats = MergeStats()
    id_gen = _IdGen(existing)

    existing_root_text = _normalize_text(existing.get("text"))
    imported_root_text = _normalize_text(imported.get("text"))
    imported_children = imported.get("children") or []

    if imported_root_text == existing_root_text and imported_children:
        candidates = imported_children
    else:
        candidates = [imported]

    for candidate in candidates:
        _merge_node(existing, candidate, id_gen, stats)

    return existing, stats


def _merge_node(
    parent: dict[str, Any],
    incoming: dict[str, Any],
    id_gen: _IdGen,
    stats: MergeStats,
) -> None:
    children = parent.setdefault("children", [])
    target = _find_child_by_text(children, incoming.get("text"))

    if target is None:
        children.append(_clone_with_new_ids(incoming, id_gen, stats))
        return

    stats.merged_nodes += 1
    for incoming_child in incoming.get("children") or []:
        _merge_node(target, incoming_child, id_gen, stats)


def _clone_with_new_ids(node: dict[str, Any], id_gen: _IdGen, stats: MergeStats) -> dict[str, Any]:
    cloned = deepcopy(node)
    _rewrite_ids(cloned, id_gen, stats)
    return cloned


def _rewrite_ids(node: dict[str, Any], id_gen: _IdGen, stats: MergeStats) -> None:
    node["id"] = id_gen.next()
    stats.added_nodes += 1

    for child in node.get("children") or []:
        _rewrite_ids(child, id_gen, stats)


def _find_child_by_text(children: list[dict[str, Any]], text: Any) -> dict[str, Any] | None:
    normalized = _normalize_text(text)
    if not normalized:
        return None

    for child in children:
        if _normalize_text(child.get("text")) == normalized:
            return child
    return None


def _normalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()
