from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "vmatrix"
    POSTGRES_USER: str = "vmatrix_user"
    POSTGRES_PASSWORD: str = "changeme_local"

    DATABASE_URL: str = (
        "postgresql+asyncpg://vmatrix_user:changeme_local@postgres:5432/vmatrix"
    )

    SECRET_KEY: str = "change_me_to_a_long_random_secret"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    FERNET_KEY: str = "changeme_generate_with_cryptography_fernet"

    LLM_PROVIDER: str = "claude"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""


settings = Settings()
