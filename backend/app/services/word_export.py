from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape
import zipfile

from app.core.node_model import MindNode


CONTENT_TYPES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""

RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

DOCUMENT_RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
"""


def render_docx(root_payload: dict[str, object]) -> bytes:
    root = MindNode.from_dict(root_payload)
    paragraphs: list[str] = []
    _render_node(root, depth=0, paragraphs=paragraphs)
    document_xml = _build_document_xml(paragraphs)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", CONTENT_TYPES_XML)
        zf.writestr("_rels/.rels", RELS_XML)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/_rels/document.xml.rels", DOCUMENT_RELS_XML)
    return buffer.getvalue()


def _render_node(node: MindNode, *, depth: int, paragraphs: list[str]) -> None:
    if depth == 0:
        paragraphs.append(node.text)
        if node.memo:
            paragraphs.append(f"备注: {node.memo}")
    else:
        indent = "  " * (depth - 1)
        paragraphs.append(f"{indent}- {node.text}")
        if node.memo:
            paragraphs.append(f"{indent}  备注: {node.memo}")

    for child in node.children:
        _render_node(child, depth=depth + 1, paragraphs=paragraphs)


def _build_document_xml(paragraphs: list[str]) -> str:
    nodes: list[str] = []
    for idx, text in enumerate(paragraphs):
        escaped = escape(text)
        if idx == 0:
            nodes.append(
                "<w:p><w:pPr><w:pStyle w:val=\"Heading1\"/></w:pPr>"
                f"<w:r><w:t>{escaped}</w:t></w:r></w:p>"
            )
        else:
            nodes.append(f"<w:p><w:r><w:t xml:space=\"preserve\">{escaped}</w:t></w:r></w:p>")
    body = "".join(nodes) or "<w:p/>"
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">"
        f"<w:body>{body}<w:sectPr/></w:body></w:document>"
    )
