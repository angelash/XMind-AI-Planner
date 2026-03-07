from pathlib import Path


def test_frontend_bootstrap_files_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "frontend" / "index.html").exists()
    assert (root / "frontend" / "src" / "main.js").exists()
    assert (root / "frontend" / "src" / "styles.css").exists()


def test_frontend_contains_mindmap_mount() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    js = (root / "frontend" / "src" / "main.js").read_text(encoding="utf-8")
    assert 'id="mindmap"' in html
    assert "MindElixir" in js
