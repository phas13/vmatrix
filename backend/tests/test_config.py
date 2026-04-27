import pytest

from app.core.config import Settings

VALID_FERNET_KEY = "9i-5Juy2gruo4M0LMe5nDDDEd40xBlm9Nhk-btgKOTI="


def test_settings_loads_defaults():
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://user:pass@host/db",
        SECRET_KEY="test_secret_key_with_enough_length",
        FERNET_KEY=VALID_FERNET_KEY,
    )
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60
    assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 30
    assert settings.LLM_PROVIDER == "claude"


def test_settings_database_url_is_async_driver():
    settings = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://user:pass@postgres:5432/vmatrix",
        SECRET_KEY="test_secret",
        FERNET_KEY=VALID_FERNET_KEY,
    )
    assert "asyncpg" in settings.DATABASE_URL


def test_settings_rejects_invalid_fernet_key():
    with pytest.raises(ValueError, match="FERNET_KEY"):
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql+asyncpg://user:pass@host/db",
            SECRET_KEY="test_secret",
            FERNET_KEY="not-a-valid-fernet-key",
        )
