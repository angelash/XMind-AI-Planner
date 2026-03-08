import base64
import io
import zipfile

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_export_markdown_route() -> None:
    response = client.post(
        '/api/v1/export/markdown',
        json={'root': {'id': 'r1', 'text': '??', 'children': [{'id': 'c1', 'text': '??'}]}},
    )
    assert response.status_code == 200
    assert response.json()['markdown'] == '# ??\n- ??\n'


def test_export_markdown_route_rejects_invalid_root() -> None:
    response = client.post('/api/v1/export/markdown', json={'root': {'id': '', 'text': 'x'}})
    assert response.status_code == 400
    assert 'node id is required' in response.json()['detail']


def test_export_word_route() -> None:
    response = client.post(
        "/api/v1/export/word",
        json={"root": {"id": "r1", "text": "Plan", "children": [{"id": "c1", "text": "Scope"}]}},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "mindmap.docx"

    docx_bytes = base64.b64decode(payload["docx_base64"])
    with zipfile.ZipFile(io.BytesIO(docx_bytes), "r") as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "Plan" in xml
    assert "- Scope" in xml


def test_export_word_route_rejects_invalid_root() -> None:
    response = client.post("/api/v1/export/word", json={"root": {"id": "", "text": "x"}})
    assert response.status_code == 400
    assert "node id is required" in response.json()["detail"]
