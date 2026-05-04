from cryptography.fernet import Fernet
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = (
        "postgresql+asyncpg://vmatrix_user:changeme_local@postgres:5432/vmatrix"
    )

    SECRET_KEY: str = "change_me_to_a_long_random_secret"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    # FERNET_KEY must be provided via environment variable (32 url-safe base64 bytes).
    # Generate one with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    FERNET_KEY: str

    LLM_PROVIDER: str = "claude"
    LLM_MODEL: str = "claude-opus-4-7"
    LLM_TIMEOUT_SECONDS: float = 60.0
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    @field_validator("FERNET_KEY")
    @classmethod
    def _validate_fernet_key(cls, v: str) -> str:
        try:
            Fernet(v.encode() if isinstance(v, str) else v)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                "FERNET_KEY must be 32 url-safe base64-encoded bytes; "
                "generate one with `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`"
            ) from exc
        return v


settings = Settings()
