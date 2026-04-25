import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    environment: str = "development"

    api_key: SecretStr = SecretStr("default_api_key_secret_12345")
    jwt_secret: SecretStr = SecretStr("default_jwt_secret_key_12345")
    jwt_algorithm: str = "HS256"
    jwt_expiration_days: int = 7

    admin_username: str = "admin"
    admin_password: SecretStr = SecretStr("admin_password")

    db_uri: str = "postgresql://postgres:postgres@localhost:5432/fever_db"
    use_memory_checkpointer: bool = False

    llm_provider: str = "google"
    llm_model: str = "gemini-2.5-flash"
    google_api_key: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    anthropic_api_key: SecretStr = SecretStr("")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
