from pathlib import Path


def test_ci_workflow_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    ci_path = root / ".github" / "workflows" / "ci.yml"
    text = ci_path.read_text(encoding="utf-8")
    assert "compileall" in text
    assert "pytest -q" in text
    assert "scripts/build_check.py" in text
