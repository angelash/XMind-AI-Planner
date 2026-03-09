"""Tests for file tree endpoints."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


def _configure_env(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'file_tree_test.db'
    monkeypatch.setenv('DB_PATH', str(db_path))
    monkeypatch.setenv('AUTH_JWT_SECRET', 'test-secret')
    monkeypatch.setenv('AUTH_COOKIE_NAME', 'test_session')
    monkeypatch.setenv('AUTH_JWT_EXP_MINUTES', '60')
    monkeypatch.setenv('ADMIN_PASSWORD', 'admin-4399')
    get_settings.cache_clear()


def test_create_folder(monkeypatch, tmp_path: Path) -> None:
    """A project member can create a folder in the file tree."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Login and create project
        client.post('/api/v1/auth/login', json={'staff_no': 'ft1001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'File Tree Test'})
        proj_id = proj_resp.json()['id']

        # Create root folder
        folder_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'Documents',
            'type': 'folder',
        })
        assert folder_resp.status_code == 201
        folder = folder_resp.json()
        assert folder['name'] == 'Documents'
        assert folder['type'] == 'folder'
        assert folder['path'] == '/Documents'
        assert folder['parent_id'] is None


def test_create_file_in_folder(monkeypatch, tmp_path: Path) -> None:
    """A project member can create a file inside a folder."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'ft2001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'File Test'})
        proj_id = proj_resp.json()['id']

        # Create folder
        folder_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'MyFolder',
            'type': 'folder',
        })
        folder_id = folder_resp.json()['id']

        # Create file in folder
        file_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'readme.md',
            'type': 'file',
            'parent_id': folder_id,
        })
        assert file_resp.status_code == 201
        file = file_resp.json()
        assert file['name'] == 'readme.md'
        assert file['type'] == 'file'
        assert file['path'] == '/MyFolder/readme.md'
        assert file['parent_id'] == folder_id


def test_duplicate_path_rejected(monkeypatch, tmp_path: Path) -> None:
    """Cannot create items with duplicate paths."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'ft3001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Dup Test'})
        proj_id = proj_resp.json()['id']

        # Create folder
        client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'Folder',
            'type': 'folder',
        })

        # Try to create duplicate
        dup_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'Folder',
            'type': 'folder',
        })
        assert dup_resp.status_code == 400
        assert 'already exists' in dup_resp.json()['detail']


def test_get_file_tree_nested(monkeypatch, tmp_path: Path) -> None:
    """File tree returns nested structure with children."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'ft4001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Tree Test'})
        proj_id = proj_resp.json()['id']

        # Create nested structure: /Parent/Child/file.md
        parent_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'Parent',
            'type': 'folder',
        })
        parent_id = parent_resp.json()['id']

        child_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'Child',
            'type': 'folder',
            'parent_id': parent_id,
        })
        child_id = child_resp.json()['id']

        client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'file.md',
            'type': 'file',
            'parent_id': child_id,
        })

        # Get tree
        tree_resp = client.get(f'/api/v1/projects/{proj_id}/file-tree')
        assert tree_resp.status_code == 200
        tree = tree_resp.json()

        assert len(tree) == 1
        assert tree[0]['name'] == 'Parent'
        assert len(tree[0]['children']) == 1
        assert tree[0]['children'][0]['name'] == 'Child'
        assert len(tree[0]['children'][0]['children']) == 1
        assert tree[0]['children'][0]['children'][0]['name'] == 'file.md'


def test_update_item_name(monkeypatch, tmp_path: Path) -> None:
    """Updating item name updates path and children's paths."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'ft5001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Update Test'})
        proj_id = proj_resp.json()['id']

        # Create folder with child
        folder_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'OldName',
            'type': 'folder',
        })
        folder_id = folder_resp.json()['id']

        file_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'file.txt',
            'type': 'file',
            'parent_id': folder_id,
        })
        file_id = file_resp.json()['id']

        # Update folder name
        update_resp = client.patch(
            f'/api/v1/projects/{proj_id}/file-tree/items/{folder_id}',
            json={'name': 'NewName'},
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated['name'] == 'NewName'
        assert updated['path'] == '/NewName'

        # Check child path updated too
        file_check = client.get(f'/api/v1/projects/{proj_id}/file-tree/items/{file_id}')
        assert file_check.json()['path'] == '/NewName/file.txt'


def test_delete_folder_recursive(monkeypatch, tmp_path: Path) -> None:
    """Deleting a folder deletes all children recursively."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'ft6001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Delete Test'})
        proj_id = proj_resp.json()['id']

        # Create nested structure
        folder_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'ToDelete',
            'type': 'folder',
        })
        folder_id = folder_resp.json()['id']

        file_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'child.txt',
            'type': 'file',
            'parent_id': folder_id,
        })
        file_id = file_resp.json()['id']

        # Delete folder
        delete_resp = client.delete(f'/api/v1/projects/{proj_id}/file-tree/items/{folder_id}')
        assert delete_resp.status_code == 204

        # Check child is also gone
        file_check = client.get(f'/api/v1/projects/{proj_id}/file-tree/items/{file_id}')
        assert file_check.status_code == 404


def test_move_item(monkeypatch, tmp_path: Path) -> None:
    """Moving an item updates its path and children's paths."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'ft7001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Move Test'})
        proj_id = proj_resp.json()['id']

        # Create structure: /FolderA/file.txt and /FolderB
        folder_a_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'FolderA',
            'type': 'folder',
        })
        folder_a_id = folder_a_resp.json()['id']

        file_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'file.txt',
            'type': 'file',
            'parent_id': folder_a_id,
        })
        file_id = file_resp.json()['id']

        folder_b_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'FolderB',
            'type': 'folder',
        })
        folder_b_id = folder_b_resp.json()['id']

        # Move file from FolderA to FolderB
        move_resp = client.post(
            f'/api/v1/projects/{proj_id}/file-tree/items/{file_id}/move',
            json={'parent_id': folder_b_id},
        )
        assert move_resp.status_code == 200
        moved = move_resp.json()
        assert moved['parent_id'] == folder_b_id
        assert moved['path'] == '/FolderB/file.txt'


def test_cannot_move_folder_into_self(monkeypatch, tmp_path: Path) -> None:
    """Cannot move a folder into itself or its descendants."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'ft8001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Self Move Test'})
        proj_id = proj_resp.json()['id']

        # Create /Parent/Child
        parent_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'Parent',
            'type': 'folder',
        })
        parent_id = parent_resp.json()['id']

        child_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'Child',
            'type': 'folder',
            'parent_id': parent_id,
        })
        child_id = child_resp.json()['id']

        # Try to move Parent into Child
        move_resp = client.post(
            f'/api/v1/projects/{proj_id}/file-tree/items/{parent_id}/move',
            json={'parent_id': child_id},
        )
        assert move_resp.status_code == 400
        assert 'cannot move' in move_resp.json()['detail'].lower()


def test_non_member_cannot_create_item(monkeypatch, tmp_path: Path) -> None:
    """Non-members cannot create file tree items."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # User 1 creates project
        client.post('/api/v1/auth/login', json={'staff_no': 'ft9001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Private Project'})
        proj_id = proj_resp.json()['id']

        # User 2 tries to create item
        client.post('/api/v1/auth/login', json={'staff_no': 'ft9002'})
        item_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'Hack',
            'type': 'folder',
        })
        assert item_resp.status_code == 403


def test_list_items_by_parent(monkeypatch, tmp_path: Path) -> None:
    """List items can be filtered by parent_id."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'ft10001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'List Test'})
        proj_id = proj_resp.json()['id']

        # Create root folder and file
        folder_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'Folder',
            'type': 'folder',
        })
        folder_id = folder_resp.json()['id']

        client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'root.txt',
            'type': 'file',
        })

        # Create file in folder
        client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'child.txt',
            'type': 'file',
            'parent_id': folder_id,
        })

        # List root items
        root_resp = client.get(f'/api/v1/projects/{proj_id}/file-tree/items')
        assert root_resp.status_code == 200
        root_items = root_resp.json()['items']
        assert len(root_items) == 2  # Folder + root.txt

        # List folder children
        child_resp = client.get(f'/api/v1/projects/{proj_id}/file-tree/items?parent_id={folder_id}')
        assert child_resp.status_code == 200
        child_items = child_resp.json()['items']
        assert len(child_items) == 1
        assert child_items[0]['name'] == 'child.txt'


def test_create_file_with_content(monkeypatch, tmp_path: Path) -> None:
    """A file can be created with initial content."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'ft11001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Content Test'})
        proj_id = proj_resp.json()['id']

        # Create file with content
        file_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'doc.md',
            'type': 'file',
            'content': '# Hello\n\nThis is **markdown** content.',
        })
        assert file_resp.status_code == 201
        file = file_resp.json()
        assert file['name'] == 'doc.md'
        assert file['type'] == 'file'
        assert file['content'] == '# Hello\n\nThis is **markdown** content.'

        # Verify content is persisted
        get_resp = client.get(f"/api/v1/projects/{proj_id}/file-tree/items/{file['id']}")
        assert get_resp.status_code == 200
        assert get_resp.json()['content'] == '# Hello\n\nThis is **markdown** content.'


def test_update_file_content(monkeypatch, tmp_path: Path) -> None:
    """A file's content can be updated via the content endpoint."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'ft12001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Update Content Test'})
        proj_id = proj_resp.json()['id']

        # Create file without content
        file_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'notes.md',
            'type': 'file',
        })
        file_id = file_resp.json()['id']
        assert file_resp.json()['content'] == ''

        # Update content
        update_resp = client.put(
            f'/api/v1/projects/{proj_id}/file-tree/items/{file_id}/content',
            json={'content': '## Notes\n\n- Item 1\n- Item 2'},
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated['content'] == '## Notes\n\n- Item 1\n- Item 2'
        assert updated['id'] == file_id

        # Verify persisted
        get_resp = client.get(f'/api/v1/projects/{proj_id}/file-tree/items/{file_id}')
        assert get_resp.json()['content'] == '## Notes\n\n- Item 1\n- Item 2'


def test_cannot_update_folder_content(monkeypatch, tmp_path: Path) -> None:
    """Cannot update content of a folder, only files."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'ft13001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Folder Content Test'})
        proj_id = proj_resp.json()['id']

        # Create folder
        folder_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'MyFolder',
            'type': 'folder',
        })
        folder_id = folder_resp.json()['id']

        # Try to update content
        update_resp = client.put(
            f'/api/v1/projects/{proj_id}/file-tree/items/{folder_id}/content',
            json={'content': 'some content'},
        )
        assert update_resp.status_code == 400
        assert 'file' in update_resp.json()['detail'].lower()


def test_non_member_cannot_update_content(monkeypatch, tmp_path: Path) -> None:
    """Non-members cannot update file content."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # User 1 creates project and file
        client.post('/api/v1/auth/login', json={'staff_no': 'ft14001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Private Content'})
        proj_id = proj_resp.json()['id']
        file_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'secret.md',
            'type': 'file',
        })
        file_id = file_resp.json()['id']

        # User 2 tries to update content
        client.post('/api/v1/auth/login', json={'staff_no': 'ft14002'})
        update_resp = client.put(
            f'/api/v1/projects/{proj_id}/file-tree/items/{file_id}/content',
            json={'content': 'hacked!'},
        )
        assert update_resp.status_code == 403


def test_content_in_file_tree(monkeypatch, tmp_path: Path) -> None:
    """File tree includes content for file items."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'ft15001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Tree Content Test'})
        proj_id = proj_resp.json()['id']

        # Create folder and file with content
        folder_resp = client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'docs',
            'type': 'folder',
        })
        folder_id = folder_resp.json()['id']

        client.post(f'/api/v1/projects/{proj_id}/file-tree/items', json={
            'name': 'readme.md',
            'type': 'file',
            'parent_id': folder_id,
            'content': '# README\n\nDocumentation here.',
        })

        # Get tree
        tree_resp = client.get(f'/api/v1/projects/{proj_id}/file-tree')
        assert tree_resp.status_code == 200
        tree = tree_resp.json()

        # Verify content is in tree
        assert len(tree) == 1
        assert tree[0]['name'] == 'docs'
        assert tree[0]['type'] == 'folder'
        assert len(tree[0]['children']) == 1
        file_item = tree[0]['children'][0]
        assert file_item['name'] == 'readme.md'
        assert file_item['type'] == 'file'
        assert file_item['content'] == '# README\n\nDocumentation here.'
