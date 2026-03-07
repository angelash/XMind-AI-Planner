from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ping_endpoint() -> None:
    response = client.get("/api/v1/system/ping")
    assert response.status_code == 200
    assert response.json() == {"message": "pong"}
