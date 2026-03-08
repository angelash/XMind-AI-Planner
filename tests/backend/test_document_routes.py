from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


client = TestClient(app)


def _configure_temp_db(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'doc_test.db'
    monkeypatch.setenv('DB_PATH', str(db_path))
    get_settings.cache_clear()


def test_document_crud_flow(monkeypatch, tmp_path: Path) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    create_resp = client.post(
        '/api/v1/documents',
        json={
            'title': 'Roadmap',
            'content': {'id': 'root', 'text': 'Roadmap'},
            'owner_id': 'u-1',
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created['title'] == 'Roadmap'
    assert created['content']['id'] == 'root'
    doc_id = created['id']

    get_resp = client.get(f'/api/v1/documents/{doc_id}')
    assert get_resp.status_code == 200
    assert get_resp.json()['id'] == doc_id

    list_resp = client.get('/api/v1/documents')
    assert list_resp.status_code == 200
    assert any(item['id'] == doc_id for item in list_resp.json()['items'])

    patch_resp = client.patch(
        f'/api/v1/documents/{doc_id}',
        json={'title': 'Roadmap v2', 'content': {'id': 'root', 'text': 'Updated'}},
    )
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched['title'] == 'Roadmap v2'
    assert patched['content']['text'] == 'Updated'

    delete_resp = client.delete(f'/api/v1/documents/{doc_id}')
    assert delete_resp.status_code == 204

    missing_resp = client.get(f'/api/v1/documents/{doc_id}')
    assert missing_resp.status_code == 404


def test_document_patch_requires_payload(monkeypatch, tmp_path: Path) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    create_resp = client.post('/api/v1/documents', json={'title': 'Only title'})
    doc_id = create_resp.json()['id']

    patch_resp = client.patch(f'/api/v1/documents/{doc_id}', json={})
    assert patch_resp.status_code == 400
    assert patch_resp.json()['detail'] == 'no updates provided'
