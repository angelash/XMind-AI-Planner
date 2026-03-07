from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_generate_initial() -> None:
    response = client.post('/api/v1/ai/initial', json={'topic': '季度经营规划'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['root']['text'] == '季度经营规划'
    assert len(payload['root']['children']) == 3


def test_expand_node() -> None:
    response = client.post('/api/v1/ai/expand', json={'node_text': '推广策略', 'count': 2})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload['children']) == 2
    assert payload['children'][0]['text'].startswith('推广策略 - ')


def test_rewrite_node() -> None:
    response = client.post(
        '/api/v1/ai/rewrite',
        json={'text': '提升产品触达率', 'instruction': '更正式一些'},
    )
    assert response.status_code == 200
    assert response.json()['text'] == '提升产品触达率（按要求：更正式一些）'
