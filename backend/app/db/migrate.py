from __future__ import annotations

import sqlite3
from pathlib import Path


def _ensure_meta_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _applied_versions(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    return {row[0] for row in rows}


def run_migrations(db_path: Path, migrations_dir: Path) -> list[str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    migrations_dir.mkdir(parents=True, exist_ok=True)

    applied_now: list[str] = []
    with sqlite3.connect(db_path) as conn:
        _ensure_meta_table(conn)
        already_applied = _applied_versions(conn)

        for file in sorted(migrations_dir.glob("*.sql")):
            version = file.stem
            if version in already_applied:
                continue

            sql = file.read_text(encoding="utf-8")
            with conn:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_migrations(version) VALUES (?)",
                    (version,),
                )
            applied_now.append(version)

    return applied_now
