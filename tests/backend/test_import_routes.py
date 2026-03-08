from pathlib import Path

from fastapi.testclient import TestClient

from app.core.settings import get_settings
from app.main import app


client = TestClient(app)


def _configure_temp_db(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "import_test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    get_settings.cache_clear()


def test_import_markdown_route_creates_document(monkeypatch, tmp_path: Path) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    response = client.post(
        "/api/v1/import/markdown",
        json={
            "markdown": "# Launch Plan\n- Phase 1\n- Phase 2",
            "owner_id": "u-100",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["root"]["text"] == "Launch Plan"
    assert payload["document"]["title"] == "Launch Plan"
    assert payload["document"]["owner_id"] == "u-100"
    assert payload["document"]["content"]["children"][0]["text"] == "Phase 1"


def test_import_markdown_route_rejects_blank_markdown(monkeypatch, tmp_path: Path) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    response = client.post(
        "/api/v1/import/markdown",
        json={"markdown": "   \n\t  "},
    )

    assert response.status_code == 400
    assert "empty" in response.json()["detail"]


def test_merge_markdown_route_updates_document(monkeypatch, tmp_path: Path) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    created = client.post(
        "/api/v1/documents",
        json={
            "title": "Project Plan",
            "content": {
                "id": "root-1",
                "text": "Project Plan",
                "children": [
                    {
                        "id": "scope-1",
                        "text": "Scope",
                        "children": [{"id": "scope-2", "text": "Backend"}],
                    }
                ],
            },
        },
    ).json()

    response = client.post(
        "/api/v1/import/markdown/merge",
        json={
            "document_id": created["id"],
            "markdown": "# Project Plan\n## Scope\n- API\n## Risks",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["stats"]["merged_nodes"] >= 1

    children = payload["document"]["content"]["children"]
    scope = next(item for item in children if item["text"] == "Scope")
    assert [item["text"] for item in scope["children"]] == ["Backend", "API"]
    assert any(item["text"] == "Risks" for item in children)


def test_merge_markdown_route_requires_existing_document(monkeypatch, tmp_path: Path) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    response = client.post(
        "/api/v1/import/markdown/merge",
        json={"document_id": "missing", "markdown": "# Any"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "document not found"
