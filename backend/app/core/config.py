from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://geobiz:geobiz@db:5432/geobiz"
    cors_origins: list[str] = ["http://localhost:5173"]
    tile_root: Path = Path("/data/tiles/releases")
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
