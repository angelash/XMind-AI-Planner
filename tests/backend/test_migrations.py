from pathlib import Path
import sqlite3

from app.db.migrate import run_migrations


def test_run_migrations_applies_sql_files(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir(parents=True, exist_ok=True)
    (migrations_dir / "0001_create.sql").write_text(
        "CREATE TABLE sample (id INTEGER PRIMARY KEY);", encoding="utf-8"
    )

    applied = run_migrations(db_path, migrations_dir)

    assert applied == ["0001_create"]

    with sqlite3.connect(db_path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
        assert "sample" in tables
        assert "schema_migrations" in tables


def test_run_migrations_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir(parents=True, exist_ok=True)
    (migrations_dir / "0001_create.sql").write_text(
        "CREATE TABLE sample (id INTEGER PRIMARY KEY);", encoding="utf-8"
    )

    first = run_migrations(db_path, migrations_dir)
    second = run_migrations(db_path, migrations_dir)

    assert first == ["0001_create"]
    assert second == []
