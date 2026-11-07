
from pydantic_settings import BaseSettings, SettingsConfigDict
# This loads DATABASE_URL from .env.

class Settings(BaseSettings):
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )



settings = Settings()