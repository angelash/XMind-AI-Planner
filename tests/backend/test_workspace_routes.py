"""Tests for workspace endpoint."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


def _configure_env(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'workspace_test.db'
    monkeypatch.setenv('DB_PATH', str(db_path))
    monkeypatch.setenv('AUTH_JWT_SECRET', 'test-secret')
    monkeypatch.setenv('AUTH_COOKIE_NAME', 'test_session')
    monkeypatch.setenv('AUTH_JWT_EXP_MINUTES', '60')
    monkeypatch.setenv('ADMIN_PASSWORD', 'admin-4399')
    get_settings.cache_clear()


def test_workspace_returns_user_and_documents(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Login as employee
        login_resp = client.post('/api/v1/auth/login', json={'staff_no': 'e2001'})
        assert login_resp.status_code == 200
        user_id = login_resp.json()['user']['id']

        # Create documents
        doc1 = client.post('/api/v1/documents', json={'title': 'Doc 1'})
        assert doc1.status_code == 201
        doc2 = client.post('/api/v1/documents', json={'title': 'Doc 2'})
        assert doc2.status_code == 201

        # Get workspace
        ws_resp = client.get('/api/v1/workspace')
        assert ws_resp.status_code == 200
        ws_data = ws_resp.json()

        # Verify user info
        assert ws_data['user']['staff_no'] == 'e2001'
        assert ws_data['user']['role'] == 'employee'

        # Verify documents
        assert ws_data['stats']['total_documents'] == 2
        assert len(ws_data['documents']) == 2
        titles = {d['title'] for d in ws_data['documents']}
        assert titles == {'Doc 1', 'Doc 2'}


def test_workspace_requires_authentication(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        ws_resp = client.get('/api/v1/workspace')
        assert ws_resp.status_code == 401


def test_workspace_shows_only_own_documents(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Login as employee e3001
        client.post('/api/v1/auth/login', json={'staff_no': 'e3001'})
        doc1 = client.post('/api/v1/documents', json={'title': 'E3001 Doc'})
        assert doc1.status_code == 201

        # Login as another employee e3002
        client.post('/api/v1/auth/login', json={'staff_no': 'e3002'})
        doc2 = client.post('/api/v1/documents', json={'title': 'E3002 Doc'})
        assert doc2.status_code == 201

        # Get workspace for e3002
        ws_resp = client.get('/api/v1/workspace')
        assert ws_resp.status_code == 200
        ws_data = ws_resp.json()

        # Should only see own document
        assert ws_data['stats']['total_documents'] == 1
        assert ws_data['documents'][0]['title'] == 'E3002 Doc'


def test_admin_workspace_shows_own_documents(monkeypatch, tmp_path: Path) -> None:
    """Admin's workspace shows only their own documents."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Login as admin and create a document
        client.post('/api/v1/auth/login', json={'staff_no': 'admin', 'password': 'admin-4399'})
        admin_doc = client.post('/api/v1/documents', json={'title': 'Admin Doc'})
        assert admin_doc.status_code == 201

        # Get workspace - should show admin's own documents
        ws_resp = client.get('/api/v1/workspace')
        assert ws_resp.status_code == 200
        ws_data = ws_resp.json()

        # Admin's workspace shows only their own documents
        assert ws_data['stats']['total_documents'] == 1
        assert ws_data['documents'][0]['title'] == 'Admin Doc'
