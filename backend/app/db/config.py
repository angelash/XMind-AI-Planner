from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = BASE_DIR / "data" / "xmind_ai_planner.db"
DEFAULT_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
