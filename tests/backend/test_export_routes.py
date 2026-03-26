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
