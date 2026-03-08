from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


def _configure_env(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / 'ai_test.db'
    monkeypatch.setenv('DB_PATH', str(db_path))
    monkeypatch.setenv('ADMIN_PASSWORD', 'admin-4399')
    get_settings.cache_clear()


def _login_admin(client: TestClient) -> None:
    resp = client.post('/api/v1/auth/login', json={'staff_no': 'admin', 'password': 'admin-4399'})
    assert resp.status_code == 200


def test_generate_initial(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _login_admin(client)
        response = client.post('/api/v1/ai/initial', json={'topic': '季度经营规划'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['root']['text'] == '季度经营规划'
    assert len(payload['root']['children']) == 3


def test_expand_node(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _login_admin(client)
        response = client.post('/api/v1/ai/expand', json={'node_text': '推广策略', 'count': 2})
        assert response.status_code == 200
        payload = response.json()
        assert len(payload['children']) == 2
        assert payload['children'][0]['text'].startswith('推广策略 - ')


def test_rewrite_node(monkeypatch, tmp_path: Path) -> None:
    _configure_env(monkeypatch, tmp_path)
    with TestClient(app) as client:
        _login_admin(client)
        response = client.post(
            '/api/v1/ai/rewrite',
            json={'text': '提升产品触达率', 'instruction': '更正式一些'},
        )
        assert response.status_code == 200
        assert response.json()['text'] == '提升产品触达率（按要求：更正式一些）'
