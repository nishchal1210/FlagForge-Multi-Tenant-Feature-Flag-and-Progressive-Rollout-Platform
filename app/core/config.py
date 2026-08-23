
from pydantic_settings import BaseSettings, SettingsConfigDict
# This loads DATABASE_URL from .env.

class Settings(BaseSettings):
    database_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()