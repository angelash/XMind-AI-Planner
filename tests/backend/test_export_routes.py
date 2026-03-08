from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_export_markdown_route() -> None:
    response = client.post(
        '/api/v1/export/markdown',
        json={'root': {'id': 'r1', 'text': '??', 'children': [{'id': 'c1', 'text': '??'}]}},
    )
    assert response.status_code == 200
    assert response.json()['markdown'] == '# ??\n- ??\n'


def test_export_markdown_route_rejects_invalid_root() -> None:
    response = client.post('/api/v1/export/markdown', json={'root': {'id': '', 'text': 'x'}})
    assert response.status_code == 400
    assert 'node id is required' in response.json()['detail']
