"""Dependencies for API v1 endpoints.

This module provides FastAPI dependencies for API v1 endpoints.
"""

from __future__ import annotations

import sqlite3
from typing import Generator

from app.core.settings import get_settings
from app.db.migrate import run_migrations


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Get a database connection dependency.

    This function provides a database connection that is automatically
    closed after the request is complete.
    """
    settings = get_settings()
    path = settings.db_path_abs

    # Ensure migrations are run
    from app.db.config import DEFAULT_MIGRATIONS_DIR
    run_migrations(path, DEFAULT_MIGRATIONS_DIR)

    conn = sqlite3.connect(path)
    try:
        yield conn
    finally:
        conn.close()
