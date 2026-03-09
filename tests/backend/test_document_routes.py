from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


client = TestClient(app)


def _configure_temp_db(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'doc_test.db'
    monkeypatch.setenv('DB_PATH', str(db_path))
    get_settings.cache_clear()


def _login_admin() -> None:
    resp = client.post('/api/v1/auth/login', json={'staff_no': 'admin', 'password': 'admin-4399'})
    assert resp.status_code == 200


def test_document_crud_flow(monkeypatch, tmp_path: Path) -> None:
    _configure_temp_db(monkeypatch, tmp_path)
    _login_admin()

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
    _login_admin()

    create_resp = client.post('/api/v1/documents', json={'title': 'Only title'})
    doc_id = create_resp.json()['id']

    patch_resp = client.patch(f'/api/v1/documents/{doc_id}', json={})
    assert patch_resp.status_code == 400
    assert patch_resp.json()['detail'] == 'no updates provided'


def test_move_document_to_project(monkeypatch, tmp_path: Path) -> None:
    """Test moving a document from personal workspace to a project."""
    _configure_temp_db(monkeypatch, tmp_path)

    with TestClient(app) as tc:
        # Login as user and create a document
        login_resp = tc.post('/api/v1/auth/login', json={'staff_no': 'p1001'})
        assert login_resp.status_code == 200
        user_id = login_resp.json()['user']['id']

        # Create a document in personal workspace
        doc_resp = tc.post('/api/v1/documents', json={'title': 'My Doc'})
        assert doc_resp.status_code == 201
        doc_id = doc_resp.json()['id']
        assert doc_resp.json()['project_id'] is None

        # Create a project (user becomes owner)
        proj_resp = tc.post('/api/v1/projects', json={'name': 'Test Project'})
        assert proj_resp.status_code == 201
        project_id = proj_resp.json()['id']

        # Move document to project
        move_resp = tc.post(f'/api/v1/documents/{doc_id}/move', json={'project_id': project_id})
        assert move_resp.status_code == 200
        moved = move_resp.json()
        assert moved['project_id'] == project_id
        assert moved['owner_id'] == user_id

        # Verify document appears in project documents
        proj_docs = tc.get(f'/api/v1/projects/{project_id}/documents')
        assert proj_docs.status_code == 200
        assert any(d['id'] == doc_id for d in proj_docs.json()['items'])


def test_move_document_to_personal_workspace(monkeypatch, tmp_path: Path) -> None:
    """Test moving a document from project to personal workspace."""
    _configure_temp_db(monkeypatch, tmp_path)

    with TestClient(app) as tc:
        # Login and setup
        login_resp = tc.post('/api/v1/auth/login', json={'staff_no': 'p2001'})
        user_id = login_resp.json()['user']['id']

        # Create project
        proj_resp = tc.post('/api/v1/projects', json={'name': 'Project'})
        project_id = proj_resp.json()['id']

        # Create document directly in project
        doc_resp = tc.post('/api/v1/documents', json={
            'title': 'Project Doc',
            'project_id': project_id,
        })
        assert doc_resp.status_code == 201
        doc_id = doc_resp.json()['id']
        assert doc_resp.json()['project_id'] == project_id

        # Move document to personal workspace (project_id = None)
        move_resp = tc.post(f'/api/v1/documents/{doc_id}/move', json={'project_id': None})
        assert move_resp.status_code == 200
        moved = move_resp.json()
        assert moved['project_id'] is None

        # Verify document no longer in project documents
        proj_docs = tc.get(f'/api/v1/projects/{project_id}/documents')
        assert not any(d['id'] == doc_id for d in proj_docs.json()['items'])


def test_non_member_cannot_move_to_project(monkeypatch, tmp_path: Path) -> None:
    """Non-member cannot move document to a project they don't belong to."""
    _configure_temp_db(monkeypatch, tmp_path)

    with TestClient(app) as tc:
        # User 1 creates document
        tc.post('/api/v1/auth/login', json={'staff_no': 'p3001'})
        doc_resp = tc.post('/api/v1/documents', json={'title': 'My Doc'})
        doc_id = doc_resp.json()['id']

        # User 2 creates project
        tc.post('/api/v1/auth/login', json={'staff_no': 'p3002'})
        proj_resp = tc.post('/api/v1/projects', json={'name': 'Private Project'})
        project_id = proj_resp.json()['id']

        # User 1 tries to move to User 2's project
        tc.post('/api/v1/auth/login', json={'staff_no': 'p3001'})
        move_resp = tc.post(f'/api/v1/documents/{doc_id}/move', json={'project_id': project_id})
        assert move_resp.status_code == 403


def test_cannot_move_others_document_from_project(monkeypatch, tmp_path: Path) -> None:
    """User cannot move another user's document from project to personal."""
    _configure_temp_db(monkeypatch, tmp_path)

    with TestClient(app) as tc:
        # User 1 creates project and adds User 2
        tc.post('/api/v1/auth/login', json={'staff_no': 'p4001'})
        proj_resp = tc.post('/api/v1/projects', json={'name': 'Shared Project'})
        project_id = proj_resp.json()['id']

        # User 2 logs in
        login2 = tc.post('/api/v1/auth/login', json={'staff_no': 'p4002'})
        user2_id = login2.json()['user']['id']

        # User 1 adds User 2 as member
        tc.post('/api/v1/auth/login', json={'staff_no': 'p4001'})
        tc.post(f'/api/v1/projects/{project_id}/members', json={
            'user_id': user2_id,
            'role': 'member',
        })

        # User 1 creates document in project
        doc_resp = tc.post('/api/v1/documents', json={
            'title': 'User1 Doc',
            'project_id': project_id,
        })
        doc_id = doc_resp.json()['id']

        # User 2 tries to move User 1's document to personal workspace
        tc.post('/api/v1/auth/login', json={'staff_no': 'p4002'})
        move_resp = tc.post(f'/api/v1/documents/{doc_id}/move', json={'project_id': None})
        assert move_resp.status_code == 403


def test_list_project_documents(monkeypatch, tmp_path: Path) -> None:
    """Test listing documents in a project."""
    _configure_temp_db(monkeypatch, tmp_path)

    with TestClient(app) as tc:
        # Setup user and project
        tc.post('/api/v1/auth/login', json={'staff_no': 'p5001'})
        proj_resp = tc.post('/api/v1/projects', json={'name': 'Doc Project'})
        project_id = proj_resp.json()['id']

        # Create documents in project
        doc1 = tc.post('/api/v1/documents', json={'title': 'Doc 1', 'project_id': project_id})
        doc2 = tc.post('/api/v1/documents', json={'title': 'Doc 2', 'project_id': project_id})

        # Create document in personal workspace
        tc.post('/api/v1/documents', json={'title': 'Personal Doc'})

        # List project documents
        list_resp = tc.get(f'/api/v1/projects/{project_id}/documents')
        assert list_resp.status_code == 200
        items = list_resp.json()['items']
        assert len(items) == 2
        titles = {d['title'] for d in items}
        assert titles == {'Doc 1', 'Doc 2'}


def test_non_member_cannot_list_project_documents(monkeypatch, tmp_path: Path) -> None:
    """Non-member cannot list project documents."""
    _configure_temp_db(monkeypatch, tmp_path)

    with TestClient(app) as tc:
        # User 1 creates project
        tc.post('/api/v1/auth/login', json={'staff_no': 'p6001'})
        proj_resp = tc.post('/api/v1/projects', json={'name': 'Secret Project'})
        project_id = proj_resp.json()['id']

        # User 2 tries to list documents
        tc.post('/api/v1/auth/login', json={'staff_no': 'p6002'})
        list_resp = tc.get(f'/api/v1/projects/{project_id}/documents')
        assert list_resp.status_code == 403


def test_admin_can_move_any_document(monkeypatch, tmp_path: Path) -> None:
    """Admin can move any document to any project."""
    _configure_temp_db(monkeypatch, tmp_path)

    with TestClient(app) as tc:
        # User creates document
        tc.post('/api/v1/auth/login', json={'staff_no': 'p7001'})
        doc_resp = tc.post('/api/v1/documents', json={'title': 'User Doc'})
        doc_id = doc_resp.json()['id']

        # Admin creates project
        tc.post('/api/v1/auth/login', json={'staff_no': 'admin', 'password': 'admin-4399'})
        proj_resp = tc.post('/api/v1/projects', json={'name': 'Admin Project'})
        project_id = proj_resp.json()['id']

        # Admin moves user's document
        move_resp = tc.post(f'/api/v1/documents/{doc_id}/move', json={'project_id': project_id})
        assert move_resp.status_code == 200
        assert move_resp.json()['project_id'] == project_id
