"""XMind export service - converts MindNode to XMind format."""

from __future__ import annotations

import zipfile
from xml.sax.saxutils import escape
from io import BytesIO

from app.core.node_model import MindNode


CONTENT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<xmap-content xmlns="urn:xmind:xmap:xmlns:content:2.0" xmlns:fo="http://www.w3.org/1999/XSL/Format" xmlns:svg="http://www.w3.org/2000/svg" xmlns:xhtml="http://www.w3.org/1999/xhtml" xmlns:xlink="http://www.w3.org/1999/xlink">
  <sheet id="sheet1">
    {topic_xml}
  </sheet>
</xmap-content>
"""


MANIFEST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<manifest xmlns="urn:xmind:xmap:xmlns:manifest:1.0">
  <file-entry full-path="/" media-type=""/>
  <file-entry full-path="content.xml" media-type="text/xml"/>
  <file-entry full-path="META-INF/" media-type=""/>
  <file-entry full-path="META-INF/manifest.xml" media-type="text/xml"/>
</manifest>
"""


def render_xmind(root_payload: dict[str, object]) -> bytes:
    """Render a mind map to XMind format (.xmind file)."""
    root = MindNode.from_dict(root_payload)
    topic_xml = _render_node(root)
    content_xml = CONTENT_XML.format(topic_xml=topic_xml)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("content.xml", content_xml)
        zf.writestr("META-INF/manifest.xml", MANIFEST_XML)
    return buffer.getvalue()


def _render_node(node: MindNode) -> str:
    """Render a node to XMind topic XML."""
    children_xml = ""

    if node.children:
        child_topics = [_render_node(child) for child in node.children]
        children_xml = f"    <children>\n      <topics type=\"attached\">\n{chr(10).join(child_topics)}\n      </topics>\n    </children>"

    memo_xml = ""
    if node.memo:
        memo_xml = f"    <notes>\n      <plain content=\"{escape(node.memo)}\"/>\n    </notes>"

    return f"    <topic id=\"{node.id}\">\n      <title>{escape(node.text)}</title>\n{memo_xml}{children_xml}\n    </topic>"
