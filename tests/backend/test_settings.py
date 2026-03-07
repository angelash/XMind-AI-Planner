from app.core.settings import Settings, get_settings


def test_settings_defaults(monkeypatch) -> None:
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("APP_PORT", raising=False)
    settings = Settings.from_env()
    assert settings.app_name == "XMind AI Planner"
    assert settings.app_port == 8000


def test_settings_env_override(monkeypatch) -> None:
    monkeypatch.setenv("APP_NAME", "Planner Test")
    monkeypatch.setenv("APP_PORT", "9001")
    settings = Settings.from_env()
    assert settings.app_name == "Planner Test"
    assert settings.app_port == 9001


def test_get_settings_cache(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "ci")
    first = get_settings()
    monkeypatch.setenv("APP_ENV", "prod")
    second = get_settings()
    assert first is second
    assert second.app_env == "ci"
