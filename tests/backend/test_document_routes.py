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


def test_json_export_document(monkeypatch, tmp_path: Path) -> None:
    """Test exporting document as JSON."""
    _configure_temp_db(monkeypatch, tmp_path)
    _login_admin()

    # Create a document with complex content
    create_resp = client.post(
        '/api/v1/documents',
        json={
            'title': 'Test Mindmap',
            'content': {
                'id': 'root',
                'text': 'Main Topic',
                'children': [
                    {'id': 'c1', 'text': 'Child 1'},
                    {'id': 'c2', 'text': 'Child 2'},
                ]
            },
            'owner_id': 'u-1',
        },
    )
    assert create_resp.status_code == 201
    doc_id = create_resp.json()['id']

    # Export as JSON
    export_resp = client.get(f'/api/v1/documents/{doc_id}/export/json')
    assert export_resp.status_code == 200
    exported = export_resp.json()

    # Verify exported structure
    assert 'document_id' in exported
    assert 'title' in exported
    assert 'content' in exported
    assert 'exported_at' in exported
    assert exported['document_id'] == doc_id
    assert exported['title'] == 'Test Mindmap'
    assert exported['content']['id'] == 'root'
    assert len(exported['content']['children']) == 2


def test_json_import_document(monkeypatch, tmp_path: Path) -> None:
    """Test importing JSON content to document."""
    _configure_temp_db(monkeypatch, tmp_path)
    _login_admin()

    # Create a document with initial content
    create_resp = client.post(
        '/api/v1/documents',
        json={
            'title': 'Import Test',
            'content': {'id': 'root', 'text': 'Original'},
            'owner_id': 'u-1',
        },
    )
    assert create_resp.status_code == 201
    doc_id = create_resp.json()['id']

    # Import new JSON content
    new_content = {
        'id': 'root',
        'text': 'Imported Topic',
        'children': [
            {'id': 'n1', 'text': 'New Child 1'},
            {'id': 'n2', 'text': 'New Child 2', 'children': [{'id': 'n2-1', 'text': 'Nested'}]},
        ]
    }

    import_resp = client.post(
        f'/api/v1/documents/{doc_id}/import/json',
        json={'content': new_content},
    )
    assert import_resp.status_code == 200
    updated = import_resp.json()

    # Verify content was updated
    assert updated['content']['text'] == 'Imported Topic'
    assert len(updated['content']['children']) == 2
    assert updated['content']['children'][1]['children'][0]['text'] == 'Nested'

    # Verify persisted by fetching again
    get_resp = client.get(f'/api/v1/documents/{doc_id}')
    assert get_resp.status_code == 200
    fetched = get_resp.json()
    assert fetched['content']['text'] == 'Imported Topic'


def test_json_import_validates_content_type(monkeypatch, tmp_path: Path) -> None:
    """Test JSON import validates content is an object."""
    _configure_temp_db(monkeypatch, tmp_path)
    _login_admin()

    # Create document
    create_resp = client.post(
        '/api/v1/documents',
        json={'title': 'Validation Test', 'content': {'id': 'root'}},
    )
    doc_id = create_resp.json()['id']

    # Try to import with invalid content (array instead of object)
    import_resp = client.post(
        f'/api/v1/documents/{doc_id}/import/json',
        json={'content': ['invalid', 'array']},
    )
    assert import_resp.status_code in {400, 422}  # 400 from our validation, 422 from Pydantic

    # Try to import with invalid content (string instead of object)
    import_resp = client.post(
        f'/api/v1/documents/{doc_id}/import/json',
        json={'content': 'invalid string'},
    )
    assert import_resp.status_code in {400, 422}



def test_json_export_requires_access(monkeypatch, tmp_path: Path) -> None:
    """Test JSON export requires document access."""
    _configure_temp_db(monkeypatch, tmp_path)

    with TestClient(app) as tc:
        # User 1 creates a document
        tc.post('/api/v1/auth/login', json={'staff_no': 'p8001'})
        doc_resp = tc.post('/api/v1/documents', json={'title': 'Private Doc', 'content': {'id': 'root'}})
        doc_id = doc_resp.json()['id']

        # User 2 tries to export (should fail)
        tc.post('/api/v1/auth/login', json={'staff_no': 'p8002'})
        export_resp = tc.get(f'/api/v1/documents/{doc_id}/export/json')
        assert export_resp.status_code == 404


def test_json_import_requires_access(monkeypatch, tmp_path: Path) -> None:
    """Test JSON import requires document access."""
    _configure_temp_db(monkeypatch, tmp_path)

    with TestClient(app) as tc:
        # User 1 creates a document
        tc.post('/api/v1/auth/login', json={'staff_no': 'p9001'})
        doc_resp = tc.post('/api/v1/documents', json={'title': 'Private Doc', 'content': {'id': 'root'}})
        doc_id = doc_resp.json()['id']

        # User 2 tries to import (should fail)
        tc.post('/api/v1/auth/login', json={'staff_no': 'p9002'})
        import_resp = tc.post(
            f'/api/v1/documents/{doc_id}/import/json',
            json={'content': {'id': 'root', 'text': 'Hacked'}},
        )
        assert import_resp.status_code == 404


def test_json_roundtrip(monkeypatch, tmp_path: Path) -> None:
    """Test that exported JSON can be imported back without data loss."""
    _configure_temp_db(monkeypatch, tmp_path)
    _login_admin()

    # Create a document with rich content
    original_content = {
        'id': 'root',
        'text': 'Main Topic',
        'root': True,
        'direction': 0,
        'children': [
            {
                'id': 'c1',
                'text': 'Branch 1',
                'note': 'This is a note',
                'hyperlink': 'https://example.com',
                'children': [
                    {'id': 'c1-1', 'text': 'Leaf'},
                ]
            },
            {
                'id': 'c2',
                'text': 'Branch 2',
                'style': {'color': '#FF0000', 'fontSize': 16},
            },
        ],
        'topic': {
            'id': 'root',
            'text': 'Main Topic',
        }
    }

    create_resp = client.post(
        '/api/v1/documents',
        json={
            'title': 'Roundtrip Test',
            'content': original_content,
        },
    )
    doc_id = create_resp.json()['id']

    # Export
    export_resp = client.get(f'/api/v1/documents/{doc_id}/export/json')
    assert export_resp.status_code == 200
    exported = export_resp.json()

    # Create a new document and import the exported content
    create_resp2 = client.post('/api/v1/documents', json={'title': 'Imported Doc'})
    doc_id2 = create_resp2.json()['id']

    import_resp = client.post(
        f'/api/v1/documents/{doc_id2}/import/json',
        json={'content': exported['content']},
    )
    assert import_resp.status_code == 200

    # Verify content matches original
    get_resp = client.get(f'/api/v1/documents/{doc_id2}')
    assert get_resp.status_code == 200
    imported_content = get_resp.json()['content']
    assert imported_content == original_content

