from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_app_error_shape() -> None:
    response = client.get("/api/v1/system/boom")
    assert response.status_code == 418
    assert response.json() == {
        "error": {"code": "demo_error", "message": "Demo failure"}
    }
