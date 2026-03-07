from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    app_name: str = "XMind AI Planner"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    db_path: str = "data/xmind_ai_planner.db"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""


    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            app_name=os.getenv("APP_NAME", cls.app_name),
            app_env=os.getenv("APP_ENV", cls.app_env),
            app_host=os.getenv("APP_HOST", cls.app_host),
            app_port=int(os.getenv("APP_PORT", str(cls.app_port))),
            db_path=os.getenv("DB_PATH", cls.db_path),
            openai_base_url=os.getenv("OPENAI_BASE_URL", cls.openai_base_url),
            openai_api_key=os.getenv("OPENAI_API_KEY", cls.openai_api_key),
        )

    @property
    def db_path_abs(self) -> Path:
        root = Path(__file__).resolve().parents[3]
        return (root / self.db_path).resolve()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()
