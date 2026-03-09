"""Tests for project workspace endpoints."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


def _configure_env(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'project_test.db'
    monkeypatch.setenv('DB_PATH', str(db_path))
    monkeypatch.setenv('AUTH_JWT_SECRET', 'test-secret')
    monkeypatch.setenv('AUTH_COOKIE_NAME', 'test_session')
    monkeypatch.setenv('AUTH_JWT_EXP_MINUTES', '60')
    monkeypatch.setenv('ADMIN_PASSWORD', 'admin-4399')
    get_settings.cache_clear()


def test_create_project(monkeypatch, tmp_path: Path) -> None:
    """A user can create a project and becomes its owner."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Login as employee
        login_resp = client.post('/api/v1/auth/login', json={'staff_no': 'p1001'})
        assert login_resp.status_code == 200
        user_id = login_resp.json()['user']['id']

        # Create project
        proj_resp = client.post('/api/v1/projects', json={
            'name': 'Test Project',
            'description': 'A test project',
        })
        assert proj_resp.status_code == 201
        proj = proj_resp.json()

        assert proj['name'] == 'Test Project'
        assert proj['description'] == 'A test project'
        assert proj['created_by'] == user_id


def test_list_projects_shows_own_projects(monkeypatch, tmp_path: Path) -> None:
    """Users see only projects they are members of."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # User 1 creates a project
        client.post('/api/v1/auth/login', json={'staff_no': 'p2001'})
        proj1 = client.post('/api/v1/projects', json={'name': 'P2001 Project'})
        assert proj1.status_code == 201

        # User 2 creates a project
        client.post('/api/v1/auth/login', json={'staff_no': 'p2002'})
        proj2 = client.post('/api/v1/projects', json={'name': 'P2002 Project'})
        assert proj2.status_code == 201

        # User 2 sees only their project
        list_resp = client.get('/api/v1/projects')
        assert list_resp.status_code == 200
        items = list_resp.json()['items']
        assert len(items) == 1
        assert items[0]['name'] == 'P2002 Project'


def test_admin_sees_all_projects(monkeypatch, tmp_path: Path) -> None:
    """Admin can see all projects."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # User creates a project
        client.post('/api/v1/auth/login', json={'staff_no': 'p3001'})
        client.post('/api/v1/projects', json={'name': 'User Project'})

        # Admin sees all projects
        client.post('/api/v1/auth/login', json={'staff_no': 'admin', 'password': 'admin-4399'})
        list_resp = client.get('/api/v1/projects')
        assert list_resp.status_code == 200
        items = list_resp.json()['items']
        assert len(items) == 1
        assert items[0]['name'] == 'User Project'


def test_get_project_detail(monkeypatch, tmp_path: Path) -> None:
    """Members can get project details."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Create project
        client.post('/api/v1/auth/login', json={'staff_no': 'p4001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Detail Test'})
        proj_id = proj_resp.json()['id']

        # Get details
        detail_resp = client.get(f'/api/v1/projects/{proj_id}')
        assert detail_resp.status_code == 200
        assert detail_resp.json()['name'] == 'Detail Test'


def test_non_member_cannot_access_project(monkeypatch, tmp_path: Path) -> None:
    """Non-members cannot access project details."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # User 1 creates project
        client.post('/api/v1/auth/login', json={'staff_no': 'p5001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Private Project'})
        proj_id = proj_resp.json()['id']

        # User 2 tries to access
        client.post('/api/v1/auth/login', json={'staff_no': 'p5002'})
        detail_resp = client.get(f'/api/v1/projects/{proj_id}')
        assert detail_resp.status_code == 403


def test_list_members(monkeypatch, tmp_path: Path) -> None:
    """Project creator is automatically a member with owner role."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Create project
        login_resp = client.post('/api/v1/auth/login', json={'staff_no': 'p6001'})
        user_id = login_resp.json()['user']['id']
        proj_resp = client.post('/api/v1/projects', json={'name': 'Member Test'})
        proj_id = proj_resp.json()['id']

        # List members
        members_resp = client.get(f'/api/v1/projects/{proj_id}/members')
        assert members_resp.status_code == 200
        members = members_resp.json()['items']

        assert len(members) == 1
        assert members[0]['user_id'] == user_id
        assert members[0]['role'] == 'owner'
        assert members[0]['user_staff_no'] == 'p6001'


def test_add_member(monkeypatch, tmp_path: Path) -> None:
    """Project admin can add members."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # User 1 creates project (becomes owner)
        client.post('/api/v1/auth/login', json={'staff_no': 'p7001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Add Member Test'})
        proj_id = proj_resp.json()['id']

        # User 2 logs in (creates user record)
        login2 = client.post('/api/v1/auth/login', json={'staff_no': 'p7002'})
        user2_id = login2.json()['user']['id']

        # User 1 adds User 2 as member
        client.post('/api/v1/auth/login', json={'staff_no': 'p7001'})
        add_resp = client.post(f'/api/v1/projects/{proj_id}/members', json={
            'user_id': user2_id,
            'role': 'member',
        })
        assert add_resp.status_code == 201
        member = add_resp.json()
        assert member['user_id'] == user2_id
        assert member['role'] == 'member'

        # User 2 can now access the project
        client.post('/api/v1/auth/login', json={'staff_no': 'p7002'})
        detail_resp = client.get(f'/api/v1/projects/{proj_id}')
        assert detail_resp.status_code == 200


def test_non_admin_cannot_add_member(monkeypatch, tmp_path: Path) -> None:
    """Regular members cannot add other members."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # User 1 creates project
        client.post('/api/v1/auth/login', json={'staff_no': 'p8001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Permission Test'})
        proj_id = proj_resp.json()['id']

        # User 2 logs in
        login2 = client.post('/api/v1/auth/login', json={'staff_no': 'p8002'})
        user2_id = login2.json()['user']['id']

        # User 3 logs in
        login3 = client.post('/api/v1/auth/login', json={'staff_no': 'p8003'})
        user3_id = login3.json()['user']['id']

        # User 1 adds User 2 as regular member
        client.post('/api/v1/auth/login', json={'staff_no': 'p8001'})
        client.post(f'/api/v1/projects/{proj_id}/members', json={
            'user_id': user2_id,
            'role': 'member',
        })

        # User 2 (regular member) tries to add User 3 - should fail
        client.post('/api/v1/auth/login', json={'staff_no': 'p8002'})
        add_resp = client.post(f'/api/v1/projects/{proj_id}/members', json={
            'user_id': user3_id,
            'role': 'member',
        })
        assert add_resp.status_code == 403


def test_update_member_role(monkeypatch, tmp_path: Path) -> None:
    """Project admin can update member roles."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # User 1 creates project
        client.post('/api/v1/auth/login', json={'staff_no': 'p9001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Role Test'})
        proj_id = proj_resp.json()['id']

        # User 2 logs in and gets added as member
        login2 = client.post('/api/v1/auth/login', json={'staff_no': 'p9002'})
        user2_id = login2.json()['user']['id']

        client.post('/api/v1/auth/login', json={'staff_no': 'p9001'})
        client.post(f'/api/v1/projects/{proj_id}/members', json={
            'user_id': user2_id,
            'role': 'member',
        })

        # Promote User 2 to admin
        update_resp = client.patch(f'/api/v1/projects/{proj_id}/members/{user2_id}', json={
            'role': 'admin',
        })
        assert update_resp.status_code == 200
        assert update_resp.json()['role'] == 'admin'


def test_remove_member(monkeypatch, tmp_path: Path) -> None:
    """Project admin can remove members."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        # Setup
        client.post('/api/v1/auth/login', json={'staff_no': 'pa001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Remove Test'})
        proj_id = proj_resp.json()['id']

        login2 = client.post('/api/v1/auth/login', json={'staff_no': 'pa002'})
        user2_id = login2.json()['user']['id']

        client.post('/api/v1/auth/login', json={'staff_no': 'pa001'})
        client.post(f'/api/v1/projects/{proj_id}/members', json={
            'user_id': user2_id,
            'role': 'member',
        })

        # Remove member
        remove_resp = client.delete(f'/api/v1/projects/{proj_id}/members/{user2_id}')
        assert remove_resp.status_code == 204

        # User 2 can no longer access
        client.post('/api/v1/auth/login', json={'staff_no': 'pa002'})
        detail_resp = client.get(f'/api/v1/projects/{proj_id}')
        assert detail_resp.status_code == 403


def test_update_project(monkeypatch, tmp_path: Path) -> None:
    """Project admin can update project details."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        client.post('/api/v1/auth/login', json={'staff_no': 'pb001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Update Test'})
        proj_id = proj_resp.json()['id']

        # Update project
        update_resp = client.patch(f'/api/v1/projects/{proj_id}', json={
            'name': 'Updated Name',
            'description': 'New description',
        })
        assert update_resp.status_code == 200
        assert update_resp.json()['name'] == 'Updated Name'
        assert update_resp.json()['description'] == 'New description'


def test_delete_project(monkeypatch, tmp_path: Path) -> None:
    """Project owner can delete project."""
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        client.post('/api/v1/auth/login', json={'staff_no': 'pc001'})
        proj_resp = client.post('/api/v1/projects', json={'name': 'Delete Test'})
        proj_id = proj_resp.json()['id']

        # Delete project
        delete_resp = client.delete(f'/api/v1/projects/{proj_id}')
        assert delete_resp.status_code == 204

        # Project no longer exists
        detail_resp = client.get(f'/api/v1/projects/{proj_id}')
        assert detail_resp.status_code == 404
