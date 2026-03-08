from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


def _configure_env(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'auth_test.db'
    monkeypatch.setenv('DB_PATH', str(db_path))
    monkeypatch.setenv('AUTH_JWT_SECRET', 'test-secret')
    monkeypatch.setenv('AUTH_COOKIE_NAME', 'test_session')
    monkeypatch.setenv('AUTH_JWT_EXP_MINUTES', '60')
    monkeypatch.setenv('ADMIN_PASSWORD', 'admin-4399')
    get_settings.cache_clear()


def test_staff_login_me_logout_flow(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        login_resp = client.post('/api/v1/auth/login', json={'staff_no': 'e1001'})
        assert login_resp.status_code == 200
        assert login_resp.json()['user']['staff_no'] == 'e1001'
        assert 'test_session' in login_resp.cookies

        me_resp = client.get('/api/v1/auth/me')
        assert me_resp.status_code == 200
        assert me_resp.json()['user']['staff_no'] == 'e1001'
        assert me_resp.json()['user']['role'] == 'employee'

        logout_resp = client.post('/api/v1/auth/logout')
        assert logout_resp.status_code == 200
        assert logout_resp.json() == {'ok': True}

        me_after_logout = client.get('/api/v1/auth/me')
        assert me_after_logout.status_code == 401


def test_admin_login_requires_password(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        no_password = client.post('/api/v1/auth/login', json={'staff_no': 'admin'})
        assert no_password.status_code == 401

        wrong_password = client.post('/api/v1/auth/login', json={'staff_no': 'admin', 'password': 'wrong'})
        assert wrong_password.status_code == 401

        success = client.post('/api/v1/auth/login', json={'staff_no': 'admin', 'password': 'admin-4399'})
        assert success.status_code == 200
        assert success.json()['user']['role'] == 'admin'


def test_me_requires_authentication(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as client:
        me_resp = client.get('/api/v1/auth/me')
        assert me_resp.status_code == 401
