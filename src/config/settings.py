import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr

class Settings(BaseSettings):
    environment: str = "development"
    
    # API Security
    api_key: SecretStr = SecretStr("default_api_key_secret_12345")
    jwt_secret: SecretStr = SecretStr("default_jwt_secret_key_12345")
    jwt_algorithm: str = "HS256"
    jwt_expiration_days: int = 7
    
    # Admin Credentials
    admin_username: str = "admin"
    admin_password: SecretStr = SecretStr("admin_password")
    
    # Database
    db_uri: str = "postgresql://postgres:postgres@localhost:5432/fever_db"

    # Allow extra fields from .env file
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
