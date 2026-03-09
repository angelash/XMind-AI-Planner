"""Tests for document version endpoints."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


def _configure_env(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'version_test.db'
    monkeypatch.setenv('DB_PATH', str(db_path))
    monkeypatch.setenv('AUTH_JWT_SECRET', 'test-secret')
    monkeypatch.setenv('AUTH_COOKIE_NAME', 'test_session')
    monkeypatch.setenv('AUTH_JWT_EXP_MINUTES', '60')
    monkeypatch.setenv('ADMIN_PASSWORD', 'admin-4399')
    get_settings.cache_clear()


def test_list_versions_empty(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Login and create document
        client.post('/api/v1/auth/login', json={'staff_no': 'e5001'})
        doc_resp = client.post('/api/v1/documents', json={'title': 'Test Doc'})
        doc_id = doc_resp.json()['id']

        # List versions - should be empty
        versions_resp = client.get(f'/api/v1/documents/{doc_id}/versions')
        assert versions_resp.status_code == 200
        assert versions_resp.json() == {'versions': []}


def test_version_workflow(monkeypatch, tmp_path: Path) -> None:
    """Test version creation, listing, and rollback.

    With auto-versioning, update_document automatically creates versions.
    """
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Login and create document
        login_resp = client.post('/api/v1/auth/login', json={'staff_no': 'e5002'})
        user_id = login_resp.json()['user']['id']

        doc_resp = client.post('/api/v1/documents', json={
            'title': 'Version Test',
            'content': {'id': 'root', 'text': 'v1'},
        })
        doc_id = doc_resp.json()['id']

        # Update document (auto-creates version 1)
        from app.services.document_store import update_document
        update_document(doc_id, {'title': 'Version Test v1', 'content': {'id': 'root', 'text': 'v1'}}, changed_by=user_id)

        # Update document again (auto-creates version 2)
        update_document(doc_id, {'title': 'Version Test v2', 'content': {'id': 'root', 'text': 'v2'}}, changed_by=user_id)

        # List versions
        versions_resp = client.get(f'/api/v1/documents/{doc_id}/versions')
        assert versions_resp.status_code == 200
        versions = versions_resp.json()['versions']
        assert len(versions) == 2
        assert versions[0]['version_number'] == 2
        assert versions[1]['version_number'] == 1

        # Get specific version
        v1_id = versions[1]['id']
        v1_resp = client.get(f'/api/v1/documents/{doc_id}/versions/{v1_id}')
        assert v1_resp.status_code == 200
        v1_data = v1_resp.json()
        assert v1_data['content']['text'] == 'v1'

        # Rollback to v1
        rollback_resp = client.post(f'/api/v1/documents/{doc_id}/versions/{v1_id}/rollback', json={})
        assert rollback_resp.status_code == 200
        rollback_data = rollback_resp.json()
        assert rollback_data['content']['text'] == 'v1'

        # Verify document was rolled back
        doc_resp = client.get(f'/api/v1/documents/{doc_id}')
        assert doc_resp.json()['content']['text'] == 'v1'


def test_version_access_control(monkeypatch, tmp_path: Path) -> None:
    """Test that only owner can access versions."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # User 1 creates document
        client.post('/api/v1/auth/login', json={'staff_no': 'e6001'})
        doc_resp = client.post('/api/v1/documents', json={'title': 'Private Doc'})
        doc_id = doc_resp.json()['id']

        # User 2 tries to access versions
        client.post('/api/v1/auth/login', json={'staff_no': 'e6002'})
        versions_resp = client.get(f'/api/v1/documents/{doc_id}/versions')
        assert versions_resp.status_code == 404  # Document not found for this user


def test_version_rollback_requires_owner(monkeypatch, tmp_path: Path) -> None:
    """Test that only owner or admin can rollback."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # User 1 creates document with version
        client.post('/api/v1/auth/login', json={'staff_no': 'e7001'})
        doc_resp = client.post('/api/v1/documents', json={
            'title': 'Test',
            'content': {'id': 'root', 'text': 'v1'},
        })
        doc_id = doc_resp.json()['id']

        from app.services.document_store import create_document_version
        version = create_document_version(doc_id, 'Test', {'id': 'root', 'text': 'v1'}, None, 'v1')
        version_id = version['id']

        # User 2 tries to rollback
        client.post('/api/v1/auth/login', json={'staff_no': 'e7002'})
        rollback_resp = client.post(f'/api/v1/documents/{doc_id}/versions/{version_id}/rollback', json={})
        assert rollback_resp.status_code == 403  # Forbidden
