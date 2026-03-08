from pathlib import Path


def test_frontend_bootstrap_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "frontend" / "index.html").exists()
    assert (root / "frontend" / "share.html").exists()
    assert (root / "frontend" / "src" / "main.js").exists()
    assert (root / "frontend" / "src" / "share.js").exists()
    assert (root / "frontend" / "src" / "styles.css").exists()
    assert (root / "frontend" / "src" / "nodeModel.js").exists()
    assert (root / "frontend" / "vendor" / "mind-elixir.js").exists()


def test_frontend_contains_mindmap_mount() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    js = (root / "frontend" / "src" / "main.js").read_text(encoding="utf-8")
    assert 'id="mindmap"' in html
    assert "MindElixir" in js
    assert "toMindElixirDocument" in js


def test_frontend_uses_local_mindelixir_asset() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "./vendor/mind-elixir.js" in html
    assert "unpkg.com" not in html


def test_frontend_toolbar_controls_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    for control_id in [
        "btn-add-child",
        "btn-edit-node",
        "btn-delete-node",
        "btn-toggle-fold",
        "btn-zoom-in",
        "btn-zoom-out",
        "btn-center",
        "editor-status",
    ]:
        assert f'id="{control_id}"' in html


def test_frontend_editor_actions_wired() -> None:
    root = Path(__file__).resolve().parents[1]
    js = (root / "frontend" / "src" / "main.js").read_text(encoding="utf-8")
    assert "addChildNode" in js
    assert "editNodeText" in js
    assert "deleteNode" in js
    assert "toggleFold" in js
    assert "zoom(" in js
    assert "centerCanvas" in js


def test_share_page_wired() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "share.html").read_text(encoding="utf-8")
    js = (root / "frontend" / "src" / "share.js").read_text(encoding="utf-8")
    assert "id=\"share-title\"" in html
    assert "id=\"share-content\"" in html
    assert "id=\"share-save\"" in html
    assert "fetchShare" in js
    assert "saveShare" in js
    assert "PATCH" in js
