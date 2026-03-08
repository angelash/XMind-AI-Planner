import io
import zipfile

from app.services.word_export import render_docx


def _read_document_xml(docx_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as zf:
        return zf.read("word/document.xml").decode("utf-8")


def test_render_docx_tree() -> None:
    docx_bytes = render_docx(
        {
            "id": "root",
            "text": "Plan",
            "memo": "Q2 focus",
            "children": [
                {"id": "a", "text": "Scope"},
                {"id": "b", "text": "Timeline", "memo": "2 weeks"},
            ],
        }
    )
    xml = _read_document_xml(docx_bytes)

    assert "Plan" in xml
    assert "备注: Q2 focus" in xml
    assert "- Scope" in xml
    assert "- Timeline" in xml
    assert "备注: 2 weeks" in xml


def test_render_docx_rejects_invalid_node() -> None:
    try:
        render_docx({"id": "", "text": "x"})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "node id is required" in str(exc)
