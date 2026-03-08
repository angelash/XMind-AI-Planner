from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app
from app.services.user_store import set_user_role


def _configure_env(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'perm_test.db'
    monkeypatch.setenv('DB_PATH', str(db_path))
    monkeypatch.setenv('ADMIN_PASSWORD', 'admin-4399')
    get_settings.cache_clear()


def _login(client: TestClient, staff_no: str, password: str | None = None) -> None:
    payload = {'staff_no': staff_no}
    if password is not None:
        payload['password'] = password
    resp = client.post('/api/v1/auth/login', json=payload)
    assert resp.status_code == 200


def test_reviewer_can_list_all_documents(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    # create reviewer user
    with TestClient(app) as client:
        _login(client, 'e2001')
    set_user_role('e2001', 'reviewer')

    with TestClient(app) as admin_client:
        _login(admin_client, 'admin', 'admin-4399')
        admin_client.post('/api/v1/documents', json={'title': 'A'})
        admin_client.post('/api/v1/documents', json={'title': 'B'})

    with TestClient(app) as reviewer_client:
        _login(reviewer_client, 'e2001')
        resp = reviewer_client.get('/api/v1/documents')
        assert resp.status_code == 200
        assert len(resp.json()['items']) == 2


def test_employee_only_sees_own_documents(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)

    with TestClient(app) as admin_client:
        _login(admin_client, 'admin', 'admin-4399')
        admin_client.post('/api/v1/documents', json={'title': 'Admin Doc'})

    with TestClient(app) as emp1:
        _login(emp1, 'e3001')
        emp1.post('/api/v1/documents', json={'title': 'Emp1 Doc'})

    with TestClient(app) as emp2:
        _login(emp2, 'e3002')
        resp = emp2.get('/api/v1/documents')
        assert resp.status_code == 200
        titles = [item['title'] for item in resp.json()['items']]
        assert titles == []
