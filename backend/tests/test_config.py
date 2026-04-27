from app.core.config import Settings


def test_settings_loads_defaults():
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://user:pass@host/db",
        SECRET_KEY="test_secret_key_with_enough_length",
        FERNET_KEY="test_fernet_key",
    )
    assert settings.POSTGRES_PORT == 5432
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60
    assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 30
    assert settings.LLM_PROVIDER == "claude"


def test_settings_database_url_is_async_driver():
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://user:pass@postgres:5432/vmatrix",
        SECRET_KEY="test_secret",
        FERNET_KEY="test_key",
    )
    assert "asyncpg" in settings.DATABASE_URL
