from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


def _configure_env(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'user_routes.db'
    monkeypatch.setenv('DB_PATH', str(db_path))
    monkeypatch.setenv('ADMIN_PASSWORD', 'admin-4399')
    get_settings.cache_clear()


def _login_admin(client: TestClient) -> None:
    resp = client.post('/api/v1/auth/login', json={'staff_no': 'admin', 'password': 'admin-4399'})
    assert resp.status_code == 200


def _login_employee(client: TestClient, staff_no: str = 'e1001') -> None:
    resp = client.post('/api/v1/auth/login', json={'staff_no': staff_no})
    assert resp.status_code == 200


def test_users_endpoints_require_admin(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _login_employee(client)
        resp = client.get('/api/v1/users')
        assert resp.status_code == 403


def test_admin_can_crud_users(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _login_admin(client)

        # create
        create = client.post(
            '/api/v1/users',
            json={'staff_no': 'e2001', 'display_name': 'Alice', 'role': 'reviewer'},
        )
        assert create.status_code == 201
        assert create.json()['staff_no'] == 'e2001'
        assert create.json()['role'] == 'reviewer'

        # list
        listing = client.get('/api/v1/users')
        assert listing.status_code == 200
        staff_nos = [u['staff_no'] for u in listing.json()['items']]
        assert 'admin' in staff_nos
        assert 'e2001' in staff_nos

        # patch
        patch = client.patch('/api/v1/users/e2001', json={'display_name': 'Alice 2', 'role': 'employee'})
        assert patch.status_code == 200
        assert patch.json()['display_name'] == 'Alice 2'
        assert patch.json()['role'] == 'employee'

        # delete
        delete = client.delete('/api/v1/users/e2001')
        assert delete.status_code == 204

        missing = client.patch('/api/v1/users/e2001', json={'display_name': 'x'})
        assert missing.status_code == 404


def test_cannot_modify_admin_role_or_delete_admin(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _login_admin(client)

        patch_admin = client.patch('/api/v1/users/admin', json={'role': 'employee'})
        assert patch_admin.status_code == 400

        delete_admin = client.delete('/api/v1/users/admin')
        assert delete_admin.status_code == 400
