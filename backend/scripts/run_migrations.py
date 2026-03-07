from app.db.config import DEFAULT_DB_PATH, DEFAULT_MIGRATIONS_DIR
from app.db.migrate import run_migrations


if __name__ == "__main__":
    applied = run_migrations(DEFAULT_DB_PATH, DEFAULT_MIGRATIONS_DIR)
    if applied:
        print("Applied migrations:", ", ".join(applied))
    else:
        print("No pending migrations")
