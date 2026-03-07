from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MindNode:
    id: str
    text: str
    memo: str | None = None
    export_separate: bool = False
    children: list["MindNode"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MindNode":
        node_id = data.get("id")
        text = data.get("text")
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("node id is required")
        if not isinstance(text, str) or not text:
            raise ValueError("node text is required")

        children_raw = data.get("children") or []
        if not isinstance(children_raw, list):
            raise ValueError("node children must be a list")

        memo = data.get("memo")
        export_separate = bool(data.get("exportSeparate", False))
        children = [cls.from_dict(child) for child in children_raw]
        return cls(
            id=node_id,
            text=text,
            memo=memo if isinstance(memo, str) and memo else None,
            export_separate=export_separate,
            children=children,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"id": self.id, "text": self.text}
        if self.memo:
            payload["memo"] = self.memo
        if self.export_separate:
            payload["exportSeparate"] = True
        if self.children:
            payload["children"] = [child.to_dict() for child in self.children]
        return payload


def to_mind_elixir_document(root: dict[str, Any]) -> dict[str, Any]:
    model = MindNode.from_dict(root)
    return {"nodeData": _to_mind_elixir_node(model, is_root=True)}


def from_mind_elixir_document(document: dict[str, Any]) -> dict[str, Any]:
    node_data = document.get("nodeData")
    if not isinstance(node_data, dict):
        raise ValueError("mind elixir document requires nodeData")
    model = _from_mind_elixir_node(node_data)
    return model.to_dict()


def _to_mind_elixir_node(node: MindNode, *, is_root: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {"id": node.id, "topic": node.text}
    if is_root:
        payload["root"] = True
    if node.memo:
        payload["memo"] = node.memo
    if node.export_separate:
        payload["exportSeparate"] = True
    if node.children:
        payload["children"] = [
            _to_mind_elixir_node(child, is_root=False) for child in node.children
        ]
    return payload


def _from_mind_elixir_node(node_data: dict[str, Any]) -> MindNode:
    node_id = node_data.get("id")
    topic = node_data.get("topic")
    if not isinstance(node_id, str) or not node_id:
        raise ValueError("mind elixir node id is required")
    if not isinstance(topic, str) or not topic:
        raise ValueError("mind elixir node topic is required")

    children_raw = node_data.get("children") or []
    if not isinstance(children_raw, list):
        raise ValueError("mind elixir node children must be a list")

    memo = node_data.get("memo")
    export_separate = bool(node_data.get("exportSeparate", False))
    children = [_from_mind_elixir_node(child) for child in children_raw]
    return MindNode(
        id=node_id,
        text=topic,
        memo=memo if isinstance(memo, str) and memo else None,
        export_separate=export_separate,
        children=children,
    )
