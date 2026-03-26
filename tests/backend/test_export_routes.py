import base64
import io
from pathlib import Path
import zipfile

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


def _configure_env(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'export_test.db'
    monkeypatch.setenv('DB_PATH', str(db_path))
    monkeypatch.setenv('ADMIN_PASSWORD', 'admin-4399')
    get_settings.cache_clear()


def _login_admin(client: TestClient) -> None:
    resp = client.post('/api/v1/auth/login', json={'staff_no': 'admin', 'password': 'admin-4399'})
    assert resp.status_code == 200


def test_export_markdown_route(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_admin(client)
        response = client.post(
            '/api/v1/export/markdown',
            json={'root': {'id': 'r1', 'text': '??', 'children': [{'id': 'c1', 'text': '??'}]}},
        )
        assert response.status_code == 200
        assert response.json()['markdown'] == '# ??\n- ??\n'


def test_export_markdown_route_rejects_invalid_root(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_admin(client)
        response = client.post('/api/v1/export/markdown', json={'root': {'id': '', 'text': 'x'}})
        assert response.status_code == 400
        assert 'node id is required' in response.json()['detail']


def test_export_word_route(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_admin(client)
        response = client.post(
            '/api/v1/export/word',
            json={'root': {'id': 'r1', 'text': 'Plan', 'children': [{'id': 'c1', 'text': 'Scope'}]}},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload['filename'] == 'mindmap.docx'

        docx_bytes = base64.b64decode(payload['docx_base64'])
        with zipfile.ZipFile(io.BytesIO(docx_bytes), 'r') as zf:
            xml = zf.read('word/document.xml').decode('utf-8')
        assert 'Plan' in xml
        assert '- Scope' in xml


def test_export_word_route_rejects_invalid_root(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_admin(client)
        response = client.post('/api/v1/export/word', json={'root': {'id': '', 'text': 'x'}})
        assert response.status_code == 400
        assert 'node id is required' in response.json()['detail']


def test_export_xmind_route(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_admin(client)
        response = client.post(
            '/api/v1/export/xmind',
            json={'root': {'id': 'r1', 'text': 'Plan', 'children': [{'id': 'c1', 'text': 'Scope'}]}},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload['filename'] == 'mindmap.xmind'

        xmind_bytes = base64.b64decode(payload['xmind_base64'])
        with zipfile.ZipFile(io.BytesIO(xmind_bytes), 'r') as zf:
            xml = zf.read('content.xml').decode('utf-8')
        assert 'Plan' in xml
        assert 'Scope' in xml


def test_export_xmind_route_rejects_invalid_root(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_admin(client)
        response = client.post('/api/v1/export/xmind', json={'root': {'id': '', 'text': 'x'}})
        assert response.status_code == 400
        assert 'node id is required' in response.json()['detail']


def test_export_svg_route(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_admin(client)
        response = client.post(
            '/api/v1/export/svg',
            json={'root': {'id': 'r1', 'text': '计划', 'children': [{'id': 'c1', 'text': '研发'}]}},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload['filename'] == 'mindmap.svg'
        assert 'svg_content' in payload

        svg_content = payload['svg_content']
        assert '<svg' in svg_content
        assert '计划' in svg_content
        assert '研发' in svg_content
        assert '</svg>' in svg_content


def test_export_svg_route_rejects_invalid_root(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_admin(client)
        response = client.post('/api/v1/export/svg', json={'root': {'id': '', 'text': 'x'}})
        assert response.status_code == 400
        assert 'node id is required' in response.json()['detail']


def test_export_png_route(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_admin(client)
        response = client.post(
            '/api/v1/export/png',
            json={'root': {'id': 'r1', 'text': 'Plan', 'children': [{'id': 'c1', 'text': 'Scope'}]}},
        )

        # If cairosvg is not installed, we expect an error
        # Otherwise, it should succeed
        if response.status_code == 200:
            payload = response.json()
            assert payload['filename'] == 'mindmap.png'
            assert 'png_base64' in payload

            # Verify it's valid base64
            png_bytes = base64.b64decode(payload['png_base64'])
            assert len(png_bytes) > 0
            # PNG files start with \x89PNG
            assert png_bytes.startswith(b'\x89PNG')
        elif response.status_code == 400:
            # cairosvg not installed - this is acceptable
            assert 'cairosvg' in response.json()['detail'].lower()
        else:
            assert False, f"Unexpected status code: {response.status_code}"


def test_export_png_route_rejects_invalid_root(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        _login_admin(client)
        response = client.post('/api/v1/export/png', json={'root': {'id': '', 'text': 'x'}})

        # The error could be either:
        # 1. cairosvg not installed (import error)
        # 2. Invalid node (validation error)
        # Both are acceptable
        assert response.status_code == 400
        detail = response.json()['detail']
        assert 'cairosvg' in detail.lower() or 'node id is required' in detail.lower()
