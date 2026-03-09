"""Tests for file tree content management."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


def _configure_env(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'file_tree_content_test.db'
    monkeypatch.setenv('DB_PATH', str(db_path))
    monkeypatch.setenv('AUTH_JWT_SECRET', 'test-secret')
    monkeypatch.setenv('AUTH_COOKIE_NAME', 'test_session')
    monkeypatch.setenv('AUTH_JWT_EXP_MINUTES', '60')
    monkeypatch.setenv('ADMIN_PASSWORD', 'admin-4399')
    get_settings.cache_clear()


def test_create_file_with_content(monkeypatch, tmp_path: Path) -> None:
    """Test creating a file with initial content."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Login and create project
        client.post('/api/v1/auth/login', json={'staff_no': 'content001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Content Test'})
        proj_id = proj_resp.json()['id']

        # Create file with content
        response = client.post(
            f"/api/v1/projects/{proj_id}/file-tree/items",
            json={
                "name": "readme.md",
                "type": "file",
                "content": "# Hello World\n\nThis is a test file.",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "readme.md"
        assert data["type"] == "file"
        assert data["content"] == "# Hello World\n\nThis is a test file."


def test_get_file_with_content(monkeypatch, tmp_path: Path) -> None:
    """Test retrieving a file with content."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'content002'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Content Get Test'})
        proj_id = proj_resp.json()['id']

        # Create a file with content
        create_response = client.post(
            f"/api/v1/projects/{proj_id}/file-tree/items",
            json={
                "name": "notes.md",
                "type": "file",
                "content": "## Notes\n\n- Item 1\n- Item 2",
            },
        )
        assert create_response.status_code == 201
        item_id = create_response.json()["id"]

        # Get the file
        get_response = client.get(
            f"/api/v1/projects/{proj_id}/file-tree/items/{item_id}",
        )
        assert get_response.status_code == 200
        data = get_response.json()
        assert data["content"] == "## Notes\n\n- Item 1\n- Item 2"


def test_update_file_content(monkeypatch, tmp_path: Path) -> None:
    """Test updating file content."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'content003'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Content Update Test'})
        proj_id = proj_resp.json()['id']

        # Create a file
        create_response = client.post(
            f"/api/v1/projects/{proj_id}/file-tree/items",
            json={
                "name": "draft.md",
                "type": "file",
                "content": "Initial content",
            },
        )
        assert create_response.status_code == 201
        item_id = create_response.json()["id"]

        # Update content
        update_response = client.put(
            f"/api/v1/projects/{proj_id}/file-tree/items/{item_id}/content",
            json={"content": "Updated content with more text"},
        )
        assert update_response.status_code == 200
        data = update_response.json()
        assert data["content"] == "Updated content with more text"

        # Verify update persisted
        get_response = client.get(
            f"/api/v1/projects/{proj_id}/file-tree/items/{item_id}",
        )
        assert get_response.status_code == 200
        assert get_response.json()["content"] == "Updated content with more text"


def test_cannot_update_folder_content(monkeypatch, tmp_path: Path) -> None:
    """Test that folders cannot have content updated."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'content004'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Folder Content Test'})
        proj_id = proj_resp.json()['id']

        # Create a folder
        create_response = client.post(
            f"/api/v1/projects/{proj_id}/file-tree/items",
            json={
                "name": "my-folder",
                "type": "folder",
            },
        )
        assert create_response.status_code == 201
        item_id = create_response.json()["id"]

        # Try to update content
        update_response = client.put(
            f"/api/v1/projects/{proj_id}/file-tree/items/{item_id}/content",
            json={"content": "Some content"},
        )
        assert update_response.status_code == 400
        assert "can only update content of files" in update_response.json()["detail"].lower()


def test_create_file_without_content_defaults_empty(monkeypatch, tmp_path: Path) -> None:
    """Test that files created without content default to empty string."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'content005'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Empty Content Test'})
        proj_id = proj_resp.json()['id']

        response = client.post(
            f"/api/v1/projects/{proj_id}/file-tree/items",
            json={
                "name": "empty.md",
                "type": "file",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == ""


def test_update_content_nonexistent_item(monkeypatch, tmp_path: Path) -> None:
    """Test updating content of non-existent item returns 404."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'content006'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Nonexistent Test'})
        proj_id = proj_resp.json()['id']

        response = client.put(
            f"/api/v1/projects/{proj_id}/file-tree/items/nonexistent-id/content",
            json={"content": "Some content"},
        )
        assert response.status_code == 404


def test_content_with_multiline_markdown(monkeypatch, tmp_path: Path) -> None:
    """Test storing multi-line markdown content."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'content007'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Markdown Test'})
        proj_id = proj_resp.json()['id']

        markdown_content = """# Document Title

## Section 1

This is a paragraph with **bold** and *italic* text.

### Subsection

- Item 1
- Item 2
- Item 3

## Section 2

```python
def hello():
    print("Hello, World!")
```

[Link](https://example.com)
"""
        # Create file with markdown
        create_response = client.post(
            f"/api/v1/projects/{proj_id}/file-tree/items",
            json={
                "name": "document.md",
                "type": "file",
                "content": markdown_content,
            },
        )
        assert create_response.status_code == 201
        item_id = create_response.json()["id"]

        # Retrieve and verify
        get_response = client.get(
            f"/api/v1/projects/{proj_id}/file-tree/items/{item_id}",
        )
        assert get_response.status_code == 200
        assert get_response.json()["content"] == markdown_content


def test_update_content_clears_to_empty(monkeypatch, tmp_path: Path) -> None:
    """Test updating content to empty string."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'content008'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Clear Content Test'})
        proj_id = proj_resp.json()['id']

        # Create file with content
        create_response = client.post(
            f"/api/v1/projects/{proj_id}/file-tree/items",
            json={
                "name": "to-clear.md",
                "type": "file",
                "content": "Some content to clear",
            },
        )
        assert create_response.status_code == 201
        item_id = create_response.json()["id"]

        # Clear content
        update_response = client.put(
            f"/api/v1/projects/{proj_id}/file-tree/items/{item_id}/content",
            json={"content": ""},
        )
        assert update_response.status_code == 200
        assert update_response.json()["content"] == ""
