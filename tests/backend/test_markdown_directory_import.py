from pathlib import Path

from app.services.markdown_directory_import import (
    MarkdownDirectoryImportFile,
    import_markdown_directory,
)
from app.core.settings import get_settings


def _configure_temp_db(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "directory_import_test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    get_settings.cache_clear()


def test_markdown_directory_import_creates_documents(monkeypatch, tmp_path: Path) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    results, stats = import_markdown_directory(
        [
            MarkdownDirectoryImportFile(path="team/plan.md", markdown="# Team Plan\n- Kickoff"),
            MarkdownDirectoryImportFile(path="team/risks.md", markdown="# Risks\n- Schedule"),
        ],
        owner_id="u-dir",
    )

    assert stats.total == 2
    assert stats.created == 2
    assert stats.failed == 0
    assert [item.status for item in results] == ["created", "created"]
    assert all(item.document is not None for item in results)
    assert results[0].document["owner_id"] == "u-dir"


def test_markdown_directory_import_collects_failures(monkeypatch, tmp_path: Path) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    results, stats = import_markdown_directory(
        [
            MarkdownDirectoryImportFile(path="ok.md", markdown="# OK"),
            MarkdownDirectoryImportFile(path="bad.md", markdown="  \n\t  "),
        ]
    )

    assert stats.total == 2
    assert stats.created == 1
    assert stats.failed == 1
    assert results[1].status == "failed"
    assert "empty" in str(results[1].error)


def test_markdown_directory_import_requires_files(monkeypatch, tmp_path: Path) -> None:
    _configure_temp_db(monkeypatch, tmp_path)

    try:
        import_markdown_directory([])
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "files" in str(exc)
