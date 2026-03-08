from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


client = TestClient(app)


def _configure_temp_db(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'share_test.db'
    monkeypatch.setenv('DB_PATH', str(db_path))
    get_settings.cache_clear()


def test_share_create_get_patch_flow(monkeypatch, tmp_path: Path) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    create_doc = client.post(
        '/api/v1/documents',
        json={
            'title': 'Shared Plan',
            'content': {'id': 'root', 'text': 'v1'},
        },
    )
    assert create_doc.status_code == 201
    doc_id = create_doc.json()['id']

    create_share = client.post(f'/api/v1/documents/{doc_id}/share', json={'is_editable': True})
    assert create_share.status_code == 200
    share_payload = create_share.json()
    token = share_payload['token']
    assert share_payload['document_id'] == doc_id
    assert 'share.html?token=' in share_payload['share_url']

    get_share = client.get(f'/api/v1/shares/{token}')
    assert get_share.status_code == 200
    assert get_share.json()['document']['title'] == 'Shared Plan'

    patch_share = client.patch(
        f'/api/v1/shares/{token}',
        json={'title': 'Shared Plan v2', 'content': {'id': 'root', 'text': 'v2'}},
    )
    assert patch_share.status_code == 200
    patched = patch_share.json()
    assert patched['document']['title'] == 'Shared Plan v2'
    assert patched['document']['content']['text'] == 'v2'


def test_share_readonly_rejects_update(monkeypatch, tmp_path: Path) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    create_doc = client.post('/api/v1/documents', json={'title': 'Read only'})
    doc_id = create_doc.json()['id']

    create_share = client.post(f'/api/v1/documents/{doc_id}/share', json={'is_editable': False})
    token = create_share.json()['token']

    patch_share = client.patch(f'/api/v1/shares/{token}', json={'title': 'should fail'})
    assert patch_share.status_code == 403
    assert patch_share.json()['detail'] == 'share is read only'


def test_share_missing_cases(monkeypatch, tmp_path: Path) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    create_share = client.post('/api/v1/documents/not-exist/share', json={})
    assert create_share.status_code == 404

    get_share = client.get('/api/v1/shares/not-exist-token')
    assert get_share.status_code == 404

    patch_share = client.patch('/api/v1/shares/not-exist-token', json={'title': 'x'})
    assert patch_share.status_code == 404
